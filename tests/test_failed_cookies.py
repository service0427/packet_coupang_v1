#!/usr/bin/env python3
"""
실패 쿠키 테스트 - init_status가 valid가 아닌 쿠키의 실제 유효성 검증

목적:
- denied/blocked/invalid 상태로 저장된 쿠키가 실제로 사용 가능한지 테스트
- IP 바인딩 (서브넷 매칭)을 통해 테스트

가설:
- 쿠키 생성 시점의 일시적 차단이 원인일 수 있음
- 서브넷만 일치하면 실제로는 사용 가능할 수 있음
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / 'lib'))

from common.db import execute_query
from common.proxy import get_proxy_list, get_subnet, parse_cookie_data
from common.fingerprint import build_extra_fp, build_headers, get_random_fingerprint
from curl_cffi import requests


def get_failed_cookies_with_binding(max_age_minutes=60):
    """IP 바인딩 가능한 실패 쿠키 조회

    Returns:
        list: [{'cookie': {...}, 'proxy_info': {...}, 'match_type': '...'}]
    """
    # 현재 프록시 목록
    proxies = get_proxy_list(min_remain=60)
    if not proxies:
        return []

    # 프록시별 서브넷 맵
    proxy_by_subnet = {}
    for p in proxies:
        subnet = get_subnet(p['external_ip'])
        if subnet and subnet not in proxy_by_subnet:
            proxy_by_subnet[subnet] = p

    if not proxy_by_subnet:
        return []

    # 실패 쿠키 조회 (60분 이내, valid 아닌 것)
    failed_cookies = execute_query("""
        SELECT id, proxy_ip, proxy_url, chrome_version, cookie_data, init_status,
               TIMESTAMPDIFF(MINUTE, created_at, NOW()) as age_minutes,
               created_at
        FROM cookies
        WHERE init_status IN ('denied', 'blocked', 'invalid')
          AND created_at >= NOW() - INTERVAL %s MINUTE
        ORDER BY created_at DESC
    """, (max_age_minutes,))

    if not failed_cookies:
        return []

    # IP 바인딩 매칭
    results = []
    for cookie in failed_cookies:
        cookie_subnet = get_subnet(cookie['proxy_ip'])
        if cookie_subnet in proxy_by_subnet:
            proxy_info = proxy_by_subnet[cookie_subnet]
            match_type = 'exact' if cookie['proxy_ip'] == proxy_info['external_ip'] else 'subnet'
            results.append({
                'cookie': cookie,
                'proxy_info': proxy_info,
                'match_type': match_type
            })

    return results


def test_cookie(cookie_record, proxy_url):
    """쿠키로 검색 테스트

    Returns:
        (success: bool, detail: str)
    """
    fp = get_random_fingerprint(verified_only=True)
    if not fp:
        return None, "핑거프린트 없음"

    cookies = parse_cookie_data(cookie_record)
    headers = build_headers(fp)
    extra_fp = build_extra_fp(fp)

    url = 'https://www.coupang.com/np/search?q=test'

    try:
        resp = requests.get(
            url, headers=headers, cookies=cookies,
            ja3=fp['ja3_text'], akamai=fp['akamai_text'], extra_fp=extra_fp,
            proxy=proxy_url, timeout=15, verify=False
        )
        size = len(resp.content)
        success = size > 50000
        return success, f"{size:,} bytes"
    except Exception as e:
        return False, str(e)[:50]


def main():
    parser = argparse.ArgumentParser(description='실패 쿠키 테스트')
    parser.add_argument('-m', '--max-age', type=int, default=60, help='최대 쿠키 나이 (분, 기본: 60)')
    parser.add_argument('-l', '--limit', type=int, default=10, help='테스트 개수 (기본: 10)')
    parser.add_argument('-s', '--status', type=str, help='특정 상태만 (denied/blocked/invalid)')
    args = parser.parse_args()

    print("=" * 70)
    print("실패 쿠키 테스트 (init_status != valid)")
    print("=" * 70)
    print(f"시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"최대 나이: {args.max_age}분")
    print()

    # 실패 쿠키 통계
    stats = execute_query("""
        SELECT init_status, COUNT(*) as cnt,
               MIN(TIMESTAMPDIFF(MINUTE, created_at, NOW())) as min_age,
               MAX(TIMESTAMPDIFF(MINUTE, created_at, NOW())) as max_age
        FROM cookies
        WHERE init_status IN ('denied', 'blocked', 'invalid')
          AND created_at >= NOW() - INTERVAL %s MINUTE
        GROUP BY init_status
    """, (args.max_age,))

    print("실패 쿠키 통계:")
    print("-" * 50)
    if stats:
        for s in stats:
            icon = {'denied': '🚫', 'blocked': '⛔', 'invalid': '⚠️'}.get(s['init_status'], '❓')
            print(f"  {icon} {s['init_status']:10}: {s['cnt']:3}개 ({s['min_age']}~{s['max_age']}분)")
    else:
        print("  (없음)")
    print()

    # IP 바인딩 가능한 쿠키 조회
    bindable = get_failed_cookies_with_binding(args.max_age)

    # 특정 상태 필터
    if args.status:
        bindable = [b for b in bindable if b['cookie']['init_status'] == args.status]

    print(f"IP 바인딩 가능: {len(bindable)}개")

    if not bindable:
        print("\n테스트 가능한 쿠키 없음")
        print("  - 실패 쿠키가 없거나")
        print("  - 매칭되는 프록시가 없음")
        return

    print("=" * 70)
    print("테스트 시작")
    print("=" * 70)

    results = []

    for i, item in enumerate(bindable[:args.limit], 1):
        cookie = item['cookie']
        proxy_info = item['proxy_info']
        match_type = item['match_type']

        proxy_url = f"socks5://{proxy_info['proxy']}"

        status_icon = {'denied': '🚫', 'blocked': '⛔', 'invalid': '⚠️'}.get(cookie['init_status'], '❓')
        match_icon = '✅' if match_type == 'exact' else '🔗'

        print(f"\n[{i}/{min(len(bindable), args.limit)}] 쿠키 ID: {cookie['id']}")
        print(f"  init_status: {status_icon} {cookie['init_status']}")
        print(f"  나이: {cookie['age_minutes']}분")
        print(f"  쿠키 IP: {cookie['proxy_ip']}")
        print(f"  현재 IP: {proxy_info['external_ip']} ({match_icon} {match_type})")

        success, detail = test_cookie(cookie, proxy_url)

        if success is None:
            print(f"  결과: ⏭️ {detail}")
            continue

        result_icon = '✅' if success else '❌'
        print(f"  결과: {result_icon} {detail}")

        results.append({
            'cookie_id': cookie['id'],
            'init_status': cookie['init_status'],
            'age_minutes': cookie['age_minutes'],
            'match_type': match_type,
            'success': success,
            'detail': detail
        })

    # 요약
    if results:
        print("\n" + "=" * 70)
        print("요약")
        print("=" * 70)

        total = len(results)
        success_count = sum(1 for r in results if r['success'])

        print(f"테스트: {total}개")
        print(f"성공: {success_count}개 ({success_count*100//total}%)")
        print(f"실패: {total - success_count}개")

        # 상태별 성공률
        print("\n상태별 성공률:")
        for status in ['denied', 'blocked', 'invalid']:
            status_results = [r for r in results if r['init_status'] == status]
            if status_results:
                s_total = len(status_results)
                s_success = sum(1 for r in status_results if r['success'])
                icon = {'denied': '🚫', 'blocked': '⛔', 'invalid': '⚠️'}[status]
                print(f"  {icon} {status}: {s_success}/{s_total} ({s_success*100//s_total}%)")

        # 성공한 쿠키 ID 목록
        success_ids = [r['cookie_id'] for r in results if r['success']]
        if success_ids:
            print(f"\n✅ 성공한 쿠키 IDs: {', '.join(map(str, success_ids))}")
            print("  → 이 쿠키들은 init_status와 무관하게 실제로 사용 가능!")


if __name__ == '__main__':
    main()
