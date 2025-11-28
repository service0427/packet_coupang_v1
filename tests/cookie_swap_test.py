#!/usr/bin/env python3
"""
쿠키 스왑 테스트 - Akamai와 연결된 쿠팡 쿠키 찾기

신선한 쿠키의 쿠팡 쿠키를 하나씩 오래된 것으로 교체하면서
어떤 쿠키가 차단에 영향을 주는지 확인
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'lib'))

from common.db import execute_query
from common.proxy import get_proxy_list, get_subnet, parse_cookie_data, get_bound_cookie
from common.fingerprint import get_random_fingerprint
from cffi.search import search_product


# 테스트할 쿠팡 쿠키 목록
COUPANG_COOKIES = ['PCID', 'sid', 'x-coupang-accept-language']

# Akamai 쿠키
AKAMAI_COOKIES = ['_abck', 'bm_sz', 'ak_bmsc']


def get_old_cookie_data(exclude_subnet):
    """오래된 쿠키 데이터 조회"""
    cookies = execute_query("""
        SELECT id, proxy_ip, cookie_data
        FROM cookies
        WHERE init_status IN ('success', 'default')
          AND created_at < NOW() - INTERVAL 30 MINUTE
          AND proxy_ip NOT LIKE %s
        ORDER BY created_at DESC
        LIMIT 1
    """, (f"{exclude_subnet}.%",))

    if cookies:
        data = parse_cookie_data(cookies[0])
        return data, cookies[0]['proxy_ip']
    return None, None


def run_search_test(name, cookies, proxy, fingerprint):
    """검색 테스트 (2페이지까지)"""
    print(f"\n{'─'*50}")
    print(f"테스트: {name}")
    print(f"{'─'*50}")

    result = search_product(
        query="아이폰 케이스",
        target_product_id="999999999",
        cookies=cookies,
        fingerprint=fingerprint,
        proxy=proxy,
        max_page=3,  # 2-3페이지까지 테스트
        verbose=True,
        save_html=False
    )

    if result['blocked']:
        print(f"❌ 차단: {result['block_error']}")
        return 'blocked', result['block_error']

    product_count = len(result['all_products'])
    if product_count > 0:
        print(f"✅ 성공: {product_count}개 상품")
        return 'success', product_count
    else:
        errors = result.get('page_errors', [])
        print(f"⚠️ 에러: {errors}")
        return 'error', errors


def main():
    print("=" * 60)
    print("쿠키 스왑 테스트 - Akamai 연결 쿠키 찾기")
    print("=" * 60)

    # 신선한 쿠키 가져오기 (IP 바인딩)
    bound = get_bound_cookie(min_remain=60, max_age_minutes=10)
    if not bound:
        print("❌ 신선한 쿠키 없음 (10분 이내)")
        return

    cookie_record = bound['cookie_record']
    fresh_cookies = bound['cookies']
    proxy = bound['proxy']

    print(f"\n신선한 쿠키: ID {cookie_record['id']} (IP: {cookie_record['proxy_ip']})")
    print(f"프록시: {proxy}")

    # 핑거프린트
    fingerprint = get_random_fingerprint(verified_only=True)
    print(f"TLS: Chrome {fingerprint['chrome_major']}")

    # 쿠키 내용 출력
    print(f"\n[신선한 쿠키 내용]")
    for key in COUPANG_COOKIES + AKAMAI_COOKIES:
        if key in fresh_cookies:
            value = str(fresh_cookies[key])[:50]
            print(f"  {key}: {value}...")

    # 오래된 쿠키 가져오기
    fresh_subnet = get_subnet(cookie_record['proxy_ip'])
    old_cookies, old_ip = get_old_cookie_data(fresh_subnet)

    if not old_cookies:
        print("\n❌ 오래된 쿠키 없음")
        return

    print(f"\n오래된 쿠키: IP {old_ip}")
    print(f"[오래된 쿠키 내용]")
    for key in COUPANG_COOKIES:
        if key in old_cookies:
            value = str(old_cookies[key])[:50]
            print(f"  {key}: {value}...")

    results = {}

    # 기준 테스트: 신선한 전체 쿠키
    print("\n" + "=" * 60)
    print("기준 테스트")
    print("=" * 60)
    results['0_baseline'] = run_search_test(
        "기준 (신선한 전체 쿠키)",
        fresh_cookies.copy(),
        proxy,
        fingerprint
    )

    # 개별 쿠키 스왑 테스트
    print("\n" + "=" * 60)
    print("개별 쿠키 스왑 테스트")
    print("=" * 60)

    for cookie_name in COUPANG_COOKIES:
        if cookie_name not in fresh_cookies:
            print(f"\n⏭️ {cookie_name}: 신선한 쿠키에 없음")
            continue

        if cookie_name not in old_cookies:
            print(f"\n⏭️ {cookie_name}: 오래된 쿠키에 없음")
            continue

        # 해당 쿠키만 오래된 것으로 교체
        test_cookies = fresh_cookies.copy()
        test_cookies[cookie_name] = old_cookies[cookie_name]

        results[f'swap_{cookie_name}'] = run_search_test(
            f"{cookie_name} 스왑 (신선→오래된)",
            test_cookies,
            proxy,
            fingerprint
        )

    # 복합 스왑 테스트
    print("\n" + "=" * 60)
    print("복합 스왑 테스트")
    print("=" * 60)

    if 'sid' in old_cookies and 'PCID' in old_cookies:
        test_cookies = fresh_cookies.copy()
        test_cookies['sid'] = old_cookies['sid']
        test_cookies['PCID'] = old_cookies['PCID']

        results['swap_sid_PCID'] = run_search_test(
            "sid + PCID 동시 스왑",
            test_cookies,
            proxy,
            fingerprint
        )

    # 전체 쿠팡 쿠키 교체 (이전 테스트에서 2페이지 차단됨)
    test_cookies = fresh_cookies.copy()
    for key in COUPANG_COOKIES:
        if key in old_cookies:
            test_cookies[key] = old_cookies[key]

    results['swap_ALL_COUPANG'] = run_search_test(
        "전체 쿠팡 쿠키 스왑 (PCID+sid+lang)",
        test_cookies,
        proxy,
        fingerprint
    )

    # Akamai와 쿠팡 외 기타 쿠키 분리
    akamai_only = {k: v for k, v in fresh_cookies.items() if k in AKAMAI_COOKIES}
    coupang_only = {k: v for k, v in fresh_cookies.items() if k in COUPANG_COOKIES}
    others_only = {k: v for k, v in fresh_cookies.items()
                   if k not in AKAMAI_COOKIES and k not in COUPANG_COOKIES}

    print(f"\n[기타 쿠키 목록]")
    for k in others_only:
        print(f"  - {k}")

    # 신선 Akamai + 오래된 전체 쿠팡 (기타 쿠키 없음)
    test_cookies = akamai_only.copy()
    for key in COUPANG_COOKIES:
        if key in old_cookies:
            test_cookies[key] = old_cookies[key]

    results['fresh_akamai_old_all_coupang'] = run_search_test(
        "신선 Akamai + 오래된 쿠팡 (기타X)",
        test_cookies,
        proxy,
        fingerprint
    )

    # 신선 Akamai + 오래된 쿠팡 + 신선 기타 쿠키
    test_cookies = akamai_only.copy()
    test_cookies.update(others_only)  # 신선한 기타 쿠키 추가
    for key in COUPANG_COOKIES:
        if key in old_cookies:
            test_cookies[key] = old_cookies[key]

    results['fresh_akamai_old_coupang_fresh_others'] = run_search_test(
        "신선 Akamai + 오래된 쿠팡 + 신선 기타",
        test_cookies,
        proxy,
        fingerprint
    )

    # 결과 요약
    print("\n" + "=" * 60)
    print("결과 요약")
    print("=" * 60)
    print(f"{'테스트':<30} | {'결과':<10} | {'상세'}")
    print("-" * 60)

    for name, (status, detail) in results.items():
        icon = "✅" if status == 'success' else "❌"
        detail_str = str(detail)[:30] if detail else ''
        print(f"{icon} {name:<28} | {status:<10} | {detail_str}")

    # 분석
    print("\n" + "=" * 60)
    print("분석")
    print("=" * 60)

    baseline_status = results.get('0_baseline', ('unknown', None))[0]
    if baseline_status != 'success':
        print("⚠️ 기준 테스트가 실패하여 분석 불가")
        return

    blocking_cookies = []
    for name, (status, _) in results.items():
        if name.startswith('swap_') and status == 'blocked':
            cookie_name = name.replace('swap_', '')
            blocking_cookies.append(cookie_name)

    if blocking_cookies:
        print(f"🔴 차단 유발 쿠키: {', '.join(blocking_cookies)}")
    else:
        print("🟢 개별 쿠키 스왑으로는 차단되지 않음")
        print("   → 복합적인 요인이거나 다른 쿠키가 원인일 수 있음")


if __name__ == '__main__':
    main()
