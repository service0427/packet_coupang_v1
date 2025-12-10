"""
Progressive Retry 순위 체크

단계적 재시도 전략:
- Round 1: 1개 시도
- Round 2: 2개 동시 시도 (Round 1 실패 시)
- Round 3: 3개 동시 시도 (Round 2 실패 시)
- Round 4: 4개 동시 시도 (Round 3 실패 시)

장점:
- 첫 시도 성공 시 쿠키 1개만 사용
- 실패할수록 동시 시도 증가로 성공 확률 상승
- 최대 10회(1+2+3+4), 평균적으로 훨씬 적은 쿠키 소모
"""

import time
from concurrent.futures import ThreadPoolExecutor, FIRST_COMPLETED, wait
from typing import Tuple

from api.rank_checker import check_rank


def _run_concurrent_checks(keyword: str, product_id: str,
                           item_id: str, vendor_item_id: str,
                           max_page: int, count: int, timeout: float) -> Tuple[dict, int]:
    """동시 체크 실행

    Args:
        count: 동시 시도 횟수

    Returns:
        tuple: (성공 결과 또는 None, 실제 시도 횟수)
    """
    results = []

    with ThreadPoolExecutor(max_workers=count) as executor:
        futures = [
            executor.submit(check_rank, keyword, product_id, item_id, vendor_item_id, max_page)
            for _ in range(count)
        ]

        pending = set(futures)
        start = time.time()

        while pending:
            elapsed = time.time() - start
            remaining = max(0.1, timeout - elapsed)

            if elapsed >= timeout:
                break

            done, pending = wait(pending, timeout=remaining, return_when=FIRST_COMPLETED)

            for future in done:
                try:
                    result = future.result(timeout=0.1)
                    results.append(result)

                    # 성공 체크 (error_code가 없으면 성공)
                    if not result.get('error_code'):
                        return result, len(results)
                except Exception as e:
                    results.append({
                        'error_code': 'EXECUTOR_ERROR',
                        'error_message': str(e)[:100]
                    })

    # 모두 실패 - 마지막 결과 반환
    last_result = results[-1] if results else {
        'error_code': 'TIMEOUT',
        'error_message': 'All attempts timed out'
    }
    return None, len(results), last_result


def check_rank_progressive(keyword: str, product_id: str,
                            item_id: str = None, vendor_item_id: str = None,
                            max_page: int = 13,
                            timeout_per_round: float = 25.0,
                            total_timeout: float = 30.0) -> dict:
    """Progressive Retry 순위 체크

    Round 1: 1개 시도
    Round 2: 2개 동시 시도 (실패 시)
    Round 3: 3개 동시 시도 (실패 시)

    Args:
        keyword: 검색어
        product_id: 상품 ID
        item_id: 아이템 ID (선택)
        vendor_item_id: 벤더 아이템 ID (선택)
        max_page: 최대 검색 페이지
        timeout_per_round: 라운드별 타임아웃 (초)
        total_timeout: 전체 타임아웃 (초, 기본 30초)

    Returns:
        dict: 성공 결과 또는 마지막 실패 결과
              + tries_count: 실제 시도 횟수
              + tries_total: 전체 시도 횟수 (최대 10)
              + round: 성공한 라운드 (1, 2, 3, 4)
    """
    total_start = time.time()
    total_tries = 0
    last_error = None
    rounds = [1, 2, 3, 4]  # 각 라운드별 동시 시도 수 (총 10회)

    for round_num, concurrent_count in enumerate(rounds, 1):
        # 전체 타임아웃 체크
        elapsed = time.time() - total_start
        if elapsed >= total_timeout:
            return {
                'error_code': 'TOTAL_TIMEOUT',
                'error_message': f'Total timeout after {int(elapsed)}s',
                'tries_count': total_tries,
                'tries_total': sum(rounds),
                'round': round_num - 1,
                'elapsed_ms': int(elapsed * 1000)
            }

        round_start = time.time()

        result = _run_concurrent_checks(
            keyword, product_id, item_id, vendor_item_id,
            max_page, concurrent_count, timeout_per_round
        )

        # _run_concurrent_checks가 3개 값을 반환
        if len(result) == 2:
            success_result, tries = result
            last_error = None
        else:
            success_result, tries, last_error = result

        total_tries += tries
        round_elapsed = int((time.time() - round_start) * 1000)

        if success_result:
            # 성공
            success_result['tries_count'] = total_tries
            success_result['tries_total'] = sum(rounds)  # 6
            success_result['round'] = round_num
            success_result['round_detail'] = f"R{round_num}({concurrent_count})"
            return success_result

    # 모두 실패
    total_elapsed = int((time.time() - total_start) * 1000)

    if last_error:
        last_error['tries_count'] = total_tries
        last_error['tries_total'] = sum(rounds)
        last_error['round'] = len(rounds)
        last_error['all_failed'] = True
        last_error['elapsed_ms'] = total_elapsed
        return last_error

    return {
        'error_code': 'ALL_FAILED',
        'error_message': f'All {total_tries} tries failed across {len(rounds)} rounds',
        'tries_count': total_tries,
        'tries_total': sum(rounds),
        'round': len(rounds),
        'all_failed': True,
        'elapsed_ms': total_elapsed
    }


async def check_rank_progressive_async(keyword: str, product_id: str,
                                         item_id: str = None, vendor_item_id: str = None,
                                         max_page: int = 13,
                                         timeout_per_round: float = 25.0,
                                         total_timeout: float = 30.0) -> dict:
    """비동기 Progressive Retry 순위 체크"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: check_rank_progressive(
            keyword, product_id, item_id, vendor_item_id,
            max_page, timeout_per_round, total_timeout
        )
    )


# ============================================================================
# 레거시 호환 (기존 API 유지)
# ============================================================================

def check_rank_multi(keyword: str, product_id: str,
                     item_id: str = None, vendor_item_id: str = None,
                     max_page: int = 13, max_tries: int = 5,
                     timeout: float = 30.0) -> dict:
    """레거시: 멀티-트라이 순위 체크 (Progressive로 대체)"""
    return check_rank_progressive(
        keyword, product_id, item_id, vendor_item_id,
        max_page, timeout_per_round=timeout / 3
    )


async def check_rank_multi_async(keyword: str, product_id: str,
                                  item_id: str = None, vendor_item_id: str = None,
                                  max_page: int = 13, max_tries: int = 5,
                                  timeout: float = 30.0) -> dict:
    """레거시: 비동기 멀티-트라이 순위 체크"""
    return await check_rank_progressive_async(
        keyword, product_id, item_id, vendor_item_id,
        max_page, timeout_per_round=timeout / 3
    )
