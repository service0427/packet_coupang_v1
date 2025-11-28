#!/usr/bin/env python3
"""
쿠키 조합 테스트 v2 - 간소화 버전

신선한 Akamai + 오래된 쿠팡 쿠키로 검색+클릭까지 되는지 확인
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'lib'))

from common.db import execute_query
from common.proxy import get_proxy_list, get_subnet, parse_cookie_data, get_bound_cookie
from common.fingerprint import get_random_fingerprint
from cffi.search import search_product
from cffi.request import make_request


# Akamai 쿠키
AKAMAI_COOKIES = ['_abck', 'bm_sz', 'ak_bmsc']

# 쿠팡 쿠키
COUPANG_COOKIES = ['PCID', 'sid', 'x-coupang-accept-language', '_fbp', 'gd1']


def split_cookies(cookie_data):
    """쿠키 분리"""
    if isinstance(cookie_data, str):
        cookie_data = json.loads(cookie_data)

    akamai = {}
    coupang = {}
    others = {}

    for key, value in cookie_data.items():
        if key in AKAMAI_COOKIES:
            akamai[key] = value
        elif key in COUPANG_COOKIES:
            coupang[key] = value
        else:
            others[key] = value

    return akamai, coupang, others


def get_old_coupang_cookies(exclude_subnet):
    """오래된 쿠팡 쿠키 조회 (다른 서브넷에서)"""
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
        _, coupang, _ = split_cookies(data)
        return coupang, cookies[0]['proxy_ip']
    return None, None


def run_test(name, cookies, proxy, fingerprint):
    """단일 테스트 실행"""
    print(f"\n{'='*60}")
    print(f"테스트: {name}")
    print(f"{'='*60}")
    print(f"쿠키: {list(cookies.keys())}")

    # 검색 (1페이지)
    result = search_product(
        query="아이폰 케이스",
        target_product_id="999999999",
        cookies=cookies,
        fingerprint=fingerprint,
        proxy=proxy,
        max_page=1,
        verbose=True,
        save_html=False
    )

    if result['blocked']:
        print(f"\n❌ 검색 차단: {result['block_error']}")
        return 'search_blocked'

    if not result['all_products']:
        print(f"\n⚠️ 검색 결과 없음")
        return 'search_empty'

    print(f"\n✅ 검색 성공: {len(result['all_products'])}개")

    # 첫 상품 클릭 테스트
    first = result['all_products'][0]
    product_id = first.get('productId')
    print(f"\n📦 상품 클릭 테스트: {product_id}")

    url = f"https://www.coupang.com/vp/products/{product_id}"
    try:
        resp = make_request(url, cookies, fingerprint, proxy, referer='https://www.coupang.com/')
        size = len(resp.content)
        print(f"   상세페이지: {resp.status_code} | {size:,} bytes")

        if size > 100000:
            print(f"   ✅ 클릭 성공!")
            return 'click_success'
        else:
            print(f"   ❌ 클릭 차단 (크기 부족)")
            return 'click_blocked'
    except Exception as e:
        print(f"   ❌ 클릭 에러: {e}")
        return 'click_error'


def main():
    print("=" * 60)
    print("쿠키 조합 테스트 v2")
    print("=" * 60)

    # IP 바인딩 쿠키 가져오기
    bound = get_bound_cookie(min_remain=60, max_age_minutes=10)
    if not bound:
        print("❌ 신선한 쿠키 없음")
        return

    cookie_record = bound['cookie_record']
    fresh_cookies = bound['cookies']
    proxy = bound['proxy']

    print(f"\n신선한 쿠키: ID {cookie_record['id']} (IP: {cookie_record['proxy_ip']})")

    # 쿠키 분리
    fresh_akamai, fresh_coupang, fresh_others = split_cookies(fresh_cookies)
    print(f"  Akamai: {list(fresh_akamai.keys())}")
    print(f"  쿠팡: {list(fresh_coupang.keys())}")

    # 핑거프린트
    fingerprint = get_random_fingerprint(verified_only=True)
    print(f"TLS: Chrome {fingerprint['chrome_major']}")
    print(f"프록시: {proxy}")

    # 오래된 쿠팡 쿠키 조회
    fresh_subnet = get_subnet(cookie_record['proxy_ip'])
    old_coupang, old_ip = get_old_coupang_cookies(fresh_subnet)

    if old_coupang:
        print(f"\n오래된 쿠팡 쿠키: IP {old_ip}")
        print(f"  {list(old_coupang.keys())}")
    else:
        print("\n⚠️ 오래된 쿠팡 쿠키 없음")

    results = {}

    # 테스트 1: 정상 (신선한 전체 쿠키)
    test_cookies = {**fresh_akamai, **fresh_coupang, **fresh_others}
    results['1_normal'] = run_test("1. 정상 (전체 쿠키)", test_cookies, proxy, fingerprint)

    # 테스트 2: 신선한 Akamai + 오래된 쿠팡 (IP 불일치)
    if old_coupang:
        test_cookies = {**fresh_akamai, **old_coupang}
        results['2_mixed'] = run_test("2. 신선Akamai + 오래된쿠팡", test_cookies, proxy, fingerprint)

    # 결과 요약
    print("\n" + "=" * 60)
    print("결과 요약")
    print("=" * 60)
    for name, status in results.items():
        icon = "✅" if 'success' in status else "❌"
        print(f"{icon} {name}: {status}")


if __name__ == '__main__':
    main()
