#!/usr/bin/env python3
"""
쿠키 수명 연장 테스트

특정 쿠키를 일정 간격으로 반복 사용하여 수명 확인
"""

import sys
import time
import subprocess
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'lib'))

from db import execute_query
from common import DEV_PROXY, get_dev_proxy_ip


def get_cookie_info(cookie_id):
    """쿠키 정보 조회"""
    result = execute_query("""
        SELECT
            id,
            proxy_ip,
            proxy_url,
            chrome_version,
            use_count,
            success_count,
            fail_count,
            TIMESTAMPDIFF(SECOND, created_at, NOW()) as age_seconds
        FROM cookies
        WHERE id = %s
    """, (cookie_id,))
    return result[0] if result else None


def run_rank_test(cookie_id, proxy):
    """rank 테스트 실행"""
    cmd = [
        'python3', 'coupang.py', 'rank',
        '--cookie-id', str(cookie_id),
        '--proxy', proxy,
        '--max-page', '3'
    ]

    result = subprocess.run(
        cmd,
        cwd=str(Path(__file__).parent),
        capture_output=True,
        text=True,
        timeout=60
    )

    output = result.stdout + result.stderr

    # 결과 파싱
    import re

    # CHALLENGE/BLOCKED 먼저 체크
    if 'CHALLENGE' in output:
        return 'CHALLENGE'
    if 'BLOCKED_403' in output:
        return 'BLOCKED'

    # 상품 발견 또는 미발견 (둘 다 쿠키는 성공)
    if '상품 발견' in output:
        return 'SUCCESS'
    if '상품 미발견' in output:
        return 'SUCCESS'  # 쿠키는 정상 작동

    # Page 결과 확인
    match = re.search(r'Page\s+1:\s+(\d+)개', output)
    if match:
        count = int(match.group(1))
        return 'SUCCESS' if count > 0 else 'EMPTY'

    if 'Error' in output or 'error' in output:
        return 'ERROR'

    return 'UNKNOWN'


def main():
    parser = argparse.ArgumentParser(description='쿠키 수명 테스트')
    parser.add_argument('cookie_id', type=int, help='테스트할 쿠키 ID')
    parser.add_argument('-i', '--interval', type=int, default=60, help='테스트 간격 (초, 기본: 60)')
    parser.add_argument('-n', '--count', type=int, default=60, help='테스트 횟수 (기본: 60)')
    parser.add_argument('--proxy', default=DEV_PROXY['socks5'], help='프록시 URL')
    args = parser.parse_args()

    # 쿠키 확인
    cookie = get_cookie_info(args.cookie_id)
    if not cookie:
        print(f"❌ 쿠키 {args.cookie_id} 없음")
        return

    print("=" * 60)
    print(f"쿠키 수명 테스트")
    print("=" * 60)
    print(f"쿠키 ID: {args.cookie_id}")
    print(f"Chrome: {cookie['chrome_version']}")
    print(f"IP: {cookie['proxy_ip']}")
    print(f"프록시: {args.proxy}")
    print(f"간격: {args.interval}초")
    print(f"횟수: {args.count}회")
    print(f"현재 나이: {cookie['age_seconds']}초 ({cookie['age_seconds']//60}분)")
    print("=" * 60)

    results = []

    for i in range(1, args.count + 1):
        # 쿠키 정보 갱신
        cookie = get_cookie_info(args.cookie_id)
        age_min = cookie['age_seconds'] // 60
        age_sec = cookie['age_seconds'] % 60

        print(f"\n[{i}/{args.count}] 나이: {age_min}분 {age_sec}초 | 사용: {cookie['use_count']}회")

        # 테스트 실행
        start = time.time()
        result = run_rank_test(args.cookie_id, args.proxy)
        elapsed = time.time() - start

        # 결과 기록
        results.append({
            'iteration': i,
            'age_seconds': cookie['age_seconds'],
            'use_count': cookie['use_count'],
            'result': result,
            'elapsed': elapsed
        })

        # 결과 출력
        if result == 'SUCCESS':
            print(f"  ✅ SUCCESS ({elapsed:.1f}초)")
        elif result == 'EMPTY':
            print(f"  ⚠️ EMPTY ({elapsed:.1f}초)")
        else:
            print(f"  ❌ {result} ({elapsed:.1f}초)")

            # 실패 시 중단
            print(f"\n⚠️ 쿠키 만료! (나이: {age_min}분 {age_sec}초, 사용: {cookie['use_count']}회)")
            break

        # 다음 테스트 대기
        if i < args.count:
            print(f"  다음 테스트까지 {args.interval}초 대기...")
            time.sleep(args.interval)

    # 요약
    print("\n" + "=" * 60)
    print("테스트 결과 요약")
    print("=" * 60)

    success_count = sum(1 for r in results if r['result'] == 'SUCCESS')
    total_count = len(results)

    if results:
        last = results[-1]
        print(f"성공: {success_count}/{total_count}회")
        print(f"최종 나이: {last['age_seconds']//60}분 {last['age_seconds']%60}초")
        print(f"최종 사용 횟수: {last['use_count']}회")

        if last['result'] != 'SUCCESS':
            print(f"만료 원인: {last['result']}")


if __name__ == '__main__':
    main()
