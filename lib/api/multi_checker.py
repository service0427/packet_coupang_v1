"""
멀티-트라이 순위 체크

동시에 N개 요청을 실행하여 첫 번째 성공 결과를 반환
- 성공 즉시 나머지 취소 (쿠키 낭비 최소화)
- 모두 실패 시에만 에러 반환
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor, FIRST_COMPLETED, wait, Future
from typing import Optional
import threading

from api.rank_checker import check_rank


# 취소 플래그를 위한 스레드 로컬 저장소
_cancel_flags = {}
_cancel_lock = threading.Lock()


def _check_rank_with_cancel(task_id: str, keyword: str, product_id: str,
                             item_id: str = None, vendor_item_id: str = None,
                             max_page: int = 13) -> dict:
    """취소 가능한 순위 체크 래퍼"""
    # 취소 확인
    with _cancel_lock:
        if _cancel_flags.get(task_id):
            return {'cancelled': True, 'error_code': 'CANCELLED'}

    # 실제 체크 실행
    result = check_rank(
        keyword=keyword,
        product_id=product_id,
        item_id=item_id,
        vendor_item_id=vendor_item_id,
        max_page=max_page
    )

    return result


def check_rank_multi(keyword: str, product_id: str,
                     item_id: str = None, vendor_item_id: str = None,
                     max_page: int = 13, max_tries: int = 5,
                     timeout: float = 30.0) -> dict:
    """멀티-트라이 순위 체크

    Args:
        keyword: 검색어
        product_id: 상품 ID
        item_id: 아이템 ID (선택)
        vendor_item_id: 벤더 아이템 ID (선택)
        max_page: 최대 검색 페이지
        max_tries: 동시 시도 횟수 (기본 5)
        timeout: 전체 타임아웃 (초)

    Returns:
        dict: 첫 번째 성공 결과 또는 마지막 실패 결과
              + tries_count: 실제 시도 횟수
              + tries_total: 전체 시도 횟수 설정
    """
    import uuid
    import time

    task_id = str(uuid.uuid4())
    start_time = time.time()

    # 취소 플래그 초기화
    with _cancel_lock:
        _cancel_flags[task_id] = False

    results = []
    success_result = None

    try:
        with ThreadPoolExecutor(max_workers=max_tries) as executor:
            # 모든 태스크 제출
            futures = []
            for i in range(max_tries):
                future = executor.submit(
                    _check_rank_with_cancel,
                    task_id, keyword, product_id, item_id, vendor_item_id, max_page
                )
                futures.append((i + 1, future))  # (시도 번호, future)

            # 결과 수집 (성공 시 즉시 반환)
            pending = {f for _, f in futures}
            completed_count = 0

            while pending:
                # 남은 시간 계산
                elapsed = time.time() - start_time
                remaining = max(0.1, timeout - elapsed)

                if elapsed >= timeout:
                    break

                # 하나라도 완료될 때까지 대기
                done, pending = wait(pending, timeout=remaining, return_when=FIRST_COMPLETED)

                for future in done:
                    completed_count += 1
                    try:
                        result = future.result(timeout=0.1)

                        # 취소된 결과는 무시
                        if result.get('cancelled'):
                            continue

                        results.append(result)

                        # 성공 체크 (error_code가 없으면 성공)
                        if not result.get('error_code'):
                            success_result = result
                            # 취소 플래그 설정
                            with _cancel_lock:
                                _cancel_flags[task_id] = True
                            break

                    except Exception as e:
                        results.append({
                            'error_code': 'EXECUTOR_ERROR',
                            'error_message': str(e)[:100]
                        })

                if success_result:
                    break

    finally:
        # 취소 플래그 정리
        with _cancel_lock:
            _cancel_flags.pop(task_id, None)

    # 결과 반환
    if success_result:
        success_result['tries_count'] = len(results)
        success_result['tries_total'] = max_tries
        return success_result

    # 모두 실패 - 마지막 결과 반환
    if results:
        last_result = results[-1]
        last_result['tries_count'] = len(results)
        last_result['tries_total'] = max_tries
        last_result['all_failed'] = True
        return last_result

    # 결과 없음 (타임아웃)
    return {
        'error_code': 'ALL_TIMEOUT',
        'error_message': f'All {max_tries} tries timed out',
        'tries_count': 0,
        'tries_total': max_tries,
        'all_failed': True
    }


async def check_rank_multi_async(keyword: str, product_id: str,
                                  item_id: str = None, vendor_item_id: str = None,
                                  max_page: int = 13, max_tries: int = 5,
                                  timeout: float = 30.0) -> dict:
    """비동기 멀티-트라이 순위 체크"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: check_rank_multi(
            keyword, product_id, item_id, vendor_item_id,
            max_page, max_tries, timeout
        )
    )
