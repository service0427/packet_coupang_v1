#!/usr/bin/env python3
"""
신규 쿠키 자동 rank 병렬 실행
- created_at이 120초 이내
- last_used_at이 NULL

Usage: python3 run_parallel.py
       python3 run_parallel.py --timeout 180
"""

import sys
import argparse
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent / 'lib'))

from rank_cmd import run_rank
from db import execute_query, get_cursor

def get_fresh_cookies(timeout_seconds=120):
    """신규 쿠키 조회

    조건:
    - created_at이 timeout_seconds초 이내
    - last_used_at이 NULL
    - locked_at이 NULL (중복 호출 방지)
    """
    query = """
        SELECT id FROM cookies
        WHERE created_at >= NOW() - INTERVAL %s SECOND
        AND last_used_at IS NULL
        AND locked_at IS NULL
        ORDER BY id
    """
    return execute_query(query, (timeout_seconds,))


def lock_cookies(cookie_ids):
    """쿠키 잠금 (호출 시작)

    Args:
        cookie_ids: 잠금할 쿠키 ID 리스트
    """
    if not cookie_ids:
        return

    placeholders = ', '.join(['%s'] * len(cookie_ids))
    with get_cursor() as cursor:
        cursor.execute(f"""
            UPDATE cookies SET locked_at = NOW()
            WHERE id IN ({placeholders})
        """, cookie_ids)


def update_cookie_stats(cookie_id, success, click_success=False):
    """쿠키 통계 업데이트

    Args:
        cookie_id: 쿠키 ID
        success: 실행 성공 여부 (상품 발견)
        click_success: 클릭 성공 여부
    """
    with get_cursor() as cursor:
        if success and click_success:
            # 발견 + 클릭 성공
            cursor.execute("""
                UPDATE cookies SET
                    last_used_at = NOW(),
                    use_count = use_count + 1,
                    success_count = success_count + 1
                WHERE id = %s
            """, (cookie_id,))
        else:
            # 실패 (미발견, 클릭실패, 에러)
            cursor.execute("""
                UPDATE cookies SET
                    last_used_at = NOW(),
                    use_count = use_count + 1,
                    fail_count = fail_count + 1
                WHERE id = %s
            """, (cookie_id,))


def run_rank_task(cookie_id, product_id, query, max_page, platform):
    """rank 실행 및 통계 업데이트"""
    args = SimpleNamespace(
        cookie_id=cookie_id,
        product_id=product_id,
        query=query,
        max_page=max_page,
        no_click=False,
        proxy=None,
        platform=platform
    )
    try:
        report = run_rank(args)

        # 결과 판정
        if report and report.get('found'):
            click_result = report.get('click', {})
            click_success = click_result.get('success', False)

            # DB 업데이트
            update_cookie_stats(cookie_id, success=True, click_success=click_success)

            return {
                'cookie_id': cookie_id,
                'success': True,
                'found': True,
                'rank': report.get('actual_rank'),
                'click_success': click_success
            }
        elif report and not report.get('found'):
            # DB 업데이트 (미발견)
            update_cookie_stats(cookie_id, success=False)

            return {
                'cookie_id': cookie_id,
                'success': True,
                'found': False,
                'rank': None
            }
        else:
            # DB 업데이트 (실패)
            update_cookie_stats(cookie_id, success=False)

            return {'cookie_id': cookie_id, 'success': False, 'error': 'No report'}
    except Exception as e:
        # DB 업데이트 (에러)
        try:
            update_cookie_stats(cookie_id, success=False)
        except:
            pass

        return {'cookie_id': cookie_id, 'success': False, 'error': str(e)[:100]}

def main():
    parser = argparse.ArgumentParser(description='신규 쿠키 자동 rank 병렬 실행')
    parser.add_argument('--timeout', type=int, default=120, help='쿠키 생성 후 경과 시간 제한 (초, 기본: 120)')
    parser.add_argument('--product-id', default='9024146312', help='상품 ID')
    parser.add_argument('--query', default='호박 달빛식혜', help='검색어')
    parser.add_argument('--max-page', type=int, default=13, help='최대 페이지')
    parser.add_argument('--platform', default='u22', help='TLS 플랫폼')
    args = parser.parse_args()

    # DB에서 신규 쿠키 조회
    fresh_cookies = get_fresh_cookies(args.timeout)
    cookie_ids = [c['id'] for c in fresh_cookies]

    if not cookie_ids:
        print("=" * 70)
        print("실행할 쿠키 없음")
        print("=" * 70)
        print(f"조건: created_at {args.timeout}초 이내, last_used_at IS NULL, locked_at IS NULL")
        return

    # 즉시 잠금 (중복 호출 방지)
    lock_cookies(cookie_ids)

    workers = len(cookie_ids)

    print("=" * 70)
    print("Rank 병렬 실행")
    print("=" * 70)
    print(f"시작: {datetime.now().strftime('%H:%M:%S')}")
    print(f"쿠키 ID: {cookie_ids} ({len(cookie_ids)}개)")
    print(f"병렬: {workers} (전체)")
    print(f"상품: {args.product_id} ({args.query})")
    print(f"조건: created_at {args.timeout}초 이내")
    print("=" * 70)

    results = []

    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                run_rank_task,
                cookie_id,
                args.product_id,
                args.query,
                args.max_page,
                args.platform
            ): cookie_id
            for cookie_id in cookie_ids
        }

        for future in as_completed(futures):
            cookie_id = futures[future]
            try:
                result = future.result(timeout=120)
                results.append(result)
            except Exception as e:
                # BrokenProcessPool 등 예외 처리
                results.append({
                    'cookie_id': cookie_id,
                    'success': False,
                    'error': str(e)[:100]
                })
                print(f"  Cookie {cookie_id}: ❌ Process error: {str(e)[:50]}")

    # 결과 집계
    success_count = sum(1 for r in results if r.get('success'))
    fail_count = sum(1 for r in results if not r.get('success'))
    found_count = sum(1 for r in results if r.get('found'))
    click_success_count = sum(1 for r in results if r.get('click_success'))

    print("\n" + "=" * 70)
    print("완료")
    print("=" * 70)
    print(f"총: {len(cookie_ids)}개")
    print(f"실행 성공: {success_count}, 실패: {fail_count}")
    print(f"상품 발견: {found_count}, 클릭 성공: {click_success_count}")

    # 상세 결과
    if results:
        print("\n상세 결과:")
        for r in sorted(results, key=lambda x: x['cookie_id']):
            cookie_id = r['cookie_id']
            if r.get('success'):
                if r.get('found'):
                    rank = r.get('rank', '?')
                    click = "✅" if r.get('click_success') else "❌"
                    print(f"  Cookie {cookie_id}: {rank}등, 클릭 {click}")
                else:
                    print(f"  Cookie {cookie_id}: 미발견")
            else:
                print(f"  Cookie {cookie_id}: ❌ {r.get('error', 'Unknown')}")

    print(f"\n종료: {datetime.now().strftime('%H:%M:%S')}")

if __name__ == '__main__':
    main()
