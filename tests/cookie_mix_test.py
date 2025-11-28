#!/usr/bin/env python3
"""
쿠키 조합 테스트 - Akamai 쿠키와 쿠팡 쿠키 분리 테스트

테스트 시나리오:
1. 신선한 _abck + 같은 IP의 쿠팡 쿠키 (정상 케이스)
2. 신선한 _abck + 다른 IP의 쿠팡 쿠키 (IP 바인딩 위반)
3. 신선한 _abck만 (쿠팡 쿠키 없음)
4. 쿠팡 쿠키만 (_abck 없음)
"""

import sys
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / 'lib'))

from common.db import execute_query
from common.proxy import get_proxy_list, get_subnet, parse_cookie_data
from common.fingerprint import get_random_fingerprint
from cffi.search import search_product
from cffi.click import click_product, extract_ids_from_url
from cffi.request import make_request


# Akamai 쿠키 목록 (보안 관련)
AKAMAI_COOKIES = ['_abck', 'bm_sz', 'ak_bmsc']

# 쿠팡 쿠키 목록 (세션/사용자 관련)
COUPANG_COOKIES = ['PCID', 'sid', 'x-coupang-accept-language', '_fbp', 'gd1']


def get_fresh_cookie(subnet_list=None):
    """신선한 쿠키 조회 (10분 이내)

    Args:
        subnet_list: 사용 가능한 서브넷 리스트 (있으면 해당 서브넷에서만 조회)
    """
    if subnet_list:
        # 서브넷에 맞는 쿠키 먼저 시도
        for subnet in subnet_list:
            cookies = execute_query("""
                SELECT id, proxy_ip, cookie_data, chrome_version, init_status
                FROM cookies
                WHERE init_status IN ('success', 'default')
                  AND created_at >= NOW() - INTERVAL 10 MINUTE
                  AND proxy_ip LIKE %s
                ORDER BY created_at DESC
                LIMIT 1
            """, (f"{subnet}.%",))
            if cookies:
                return cookies[0]
        return None
    else:
        cookies = execute_query("""
            SELECT id, proxy_ip, cookie_data, chrome_version, init_status
            FROM cookies
            WHERE init_status IN ('success', 'default')
              AND created_at >= NOW() - INTERVAL 10 MINUTE
            ORDER BY created_at DESC
            LIMIT 1
        """)
        return cookies[0] if cookies else None


def get_old_cookie(exclude_subnet=None):
    """오래된 쿠키 조회 (30분 이상, 다른 서브넷)"""
    if exclude_subnet:
        cookies = execute_query("""
            SELECT id, proxy_ip, cookie_data, chrome_version, init_status
            FROM cookies
            WHERE init_status IN ('success', 'default')
              AND created_at < NOW() - INTERVAL 30 MINUTE
              AND proxy_ip NOT LIKE %s
            ORDER BY created_at DESC
            LIMIT 1
        """, (f"{exclude_subnet}.%",))
    else:
        cookies = execute_query("""
            SELECT id, proxy_ip, cookie_data, chrome_version, init_status
            FROM cookies
            WHERE init_status IN ('success', 'default')
              AND created_at < NOW() - INTERVAL 30 MINUTE
            ORDER BY created_at DESC
            LIMIT 1
        """)
    return cookies[0] if cookies else None


def split_cookies(cookie_data):
    """쿠키 데이터를 Akamai/쿠팡으로 분리"""
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


def merge_cookies(*cookie_dicts):
    """여러 쿠키 딕셔너리 병합"""
    result = {}
    for d in cookie_dicts:
        if d:
            result.update(d)
    return result


def run_test(name, cookies, proxy, fingerprint, test_click=False):
    """테스트 실행"""
    print(f"\n{'='*70}")
    print(f"테스트: {name}")
    print(f"{'='*70}")
    print(f"쿠키 키: {list(cookies.keys())}")
    print(f"프록시: {proxy}")

    # 검색 실행 (1페이지만)
    result = search_product(
        query="아이폰 케이스",  # 인기 검색어로 변경
        target_product_id="12345678",  # 없는 상품
        cookies=cookies,
        fingerprint=fingerprint,
        proxy=proxy,
        max_page=1,  # 1페이지만 테스트
        verbose=True,
        save_html=False
    )

    # 결과 분석
    if result['blocked']:
        print(f"\n❌ 차단됨: {result['block_error']}")
        return 'blocked', result['block_error']
    elif len(result['all_products']) > 0:
        print(f"\n✅ 검색 성공: {len(result['all_products'])}개 상품")

        # 클릭 테스트
        if test_click and result['all_products']:
            first_product = result['all_products'][0]
            print(f"\n📦 첫 번째 상품 클릭 테스트:")
            print(f"   상품ID: {first_product.get('productId')}")
            print(f"   URL: {first_product.get('url', '')[:60]}...")

            # 상품 상세 페이지 직접 접속
            product_id = first_product.get('productId')
            if product_id:
                detail_url = f"https://www.coupang.com/vp/products/{product_id}"
                try:
                    resp = make_request(detail_url, cookies, fingerprint, proxy, referer='https://www.coupang.com/')
                    size = len(resp.content)
                    print(f"   상세페이지: Status {resp.status_code} | Size {size:,} bytes")

                    if size > 100000:
                        print(f"   ✅ 상세페이지 접근 성공!")
                        return 'click_success', {'search': len(result['all_products']), 'detail_size': size}
                    else:
                        print(f"   ❌ 상세페이지 차단 (크기 부족)")
                        return 'click_blocked', {'search': len(result['all_products']), 'detail_size': size}
                except Exception as e:
                    print(f"   ❌ 상세페이지 에러: {str(e)[:50]}")
                    return 'click_error', str(e)[:50]

        return 'success', len(result['all_products'])
    else:
        errors = result.get('page_errors', [])
        if errors:
            print(f"\n⚠️ 에러: {errors}")
            return 'error', errors
        else:
            print(f"\n⚠️ 결과 없음")
            return 'empty', None


def find_proxy_by_subnet(subnet, proxies):
    """서브넷에 맞는 프록시 찾기"""
    for p in proxies:
        if get_subnet(p.get('external_ip', '')) == subnet:
            return p
    return None


def main():
    print("=" * 70)
    print("쿠키 조합 테스트")
    print("=" * 70)

    # 프록시 조회
    proxies = get_proxy_list(min_remain=60)
    if not proxies:
        print("❌ 사용 가능한 프록시 없음")
        return

    print(f"\n사용 가능한 프록시: {len(proxies)}개")
    proxy_subnets = list(set([get_subnet(p.get('external_ip', '')) for p in proxies]))
    for p in proxies[:5]:
        print(f"  - {p.get('external_ip')} (서브넷: {get_subnet(p.get('external_ip', ''))}.*)")

    # 핑거프린트
    fingerprint = get_random_fingerprint(verified_only=True)
    print(f"TLS: Chrome {fingerprint['chrome_major']}")

    # 신선한 쿠키 조회 (프록시 서브넷에 맞는 것 우선)
    fresh = get_fresh_cookie(subnet_list=proxy_subnets)
    if not fresh:
        print(f"\n❌ 신선한 쿠키 없음 (10분 이내, 프록시 서브넷 매칭)")
        return

    print(f"\n신선한 쿠키: ID {fresh['id']} (IP: {fresh['proxy_ip']})")
    fresh_data = parse_cookie_data(fresh)
    fresh_akamai, fresh_coupang, fresh_others = split_cookies(fresh_data)
    print(f"  Akamai: {list(fresh_akamai.keys())}")
    print(f"  쿠팡: {list(fresh_coupang.keys())}")
    print(f"  기타: {list(fresh_others.keys())}")

    # 신선한 쿠키에 맞는 프록시 찾기
    fresh_subnet = get_subnet(fresh['proxy_ip'])
    fresh_proxy_info = find_proxy_by_subnet(fresh_subnet, proxies)
    if not fresh_proxy_info:
        print(f"\n❌ 신선한 쿠키 서브넷({fresh_subnet}.*)에 맞는 프록시 없음")
        return
    fresh_proxy = f"socks5://{fresh_proxy_info['proxy']}"
    print(f"  매칭 프록시: {fresh_proxy_info['external_ip']}")

    # 오래된 쿠키 조회 (다른 서브넷)
    old = get_old_cookie(exclude_subnet=fresh_subnet)

    if old:
        print(f"\n오래된 쿠키: ID {old['id']} (IP: {old['proxy_ip']})")
        old_data = parse_cookie_data(old)
        old_akamai, old_coupang, old_others = split_cookies(old_data)
        print(f"  Akamai: {list(old_akamai.keys())}")
        print(f"  쿠팡: {list(old_coupang.keys())}")

        # 오래된 쿠키에 맞는 프록시 찾기
        old_subnet = get_subnet(old['proxy_ip'])
        old_proxy_info = find_proxy_by_subnet(old_subnet, proxies)
        if old_proxy_info:
            old_proxy = f"socks5://{old_proxy_info['proxy']}"
            print(f"  매칭 프록시: {old_proxy_info['external_ip']}")
        else:
            old_proxy = None
            print(f"  ⚠️ 매칭 프록시 없음 (서브넷: {old_subnet}.*)")
    else:
        print("\n⚠️ 오래된 쿠키 없음 (30분+ 다른 서브넷)")
        old_data = None
        old_akamai = old_coupang = old_others = {}
        old_proxy = None

    results = {}

    # 테스트 1: 신선한 전체 쿠키 + 매칭 IP (기준 - 정상 케이스) + 클릭
    test_cookies = merge_cookies(fresh_akamai, fresh_coupang, fresh_others)
    results['1_fresh_all_match_ip'] = run_test(
        "1. 신선한 전체 쿠키 + 매칭 IP (정상)",
        test_cookies, fresh_proxy, fingerprint, test_click=True
    )

    # 테스트 3: 신선한 _abck + 오래된 쿠팡 쿠키 + 신선한 쿠키 IP (IP 불일치) + 클릭
    if old_coupang:
        test_cookies = merge_cookies(fresh_akamai, old_coupang)
        results['3_fresh_akamai_old_coupang_fresh_ip'] = run_test(
            "3. 신선한 Akamai + 오래된 쿠팡 + 신선한 IP",
            test_cookies, fresh_proxy, fingerprint, test_click=True
        )
    else:
        print("\n⏭️ 테스트 3 건너뜀 (오래된 쿠팡 쿠키 없음)")

    # 결과 요약
    print("\n" + "=" * 70)
    print("결과 요약")
    print("=" * 70)
    for name, (status, detail) in results.items():
        icon = "✅" if status == 'success' else "❌" if status == 'blocked' else "⚠️"
        print(f"{icon} {name}: {status} - {detail}")


if __name__ == '__main__':
    main()
