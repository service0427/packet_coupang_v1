#!/usr/bin/env python3
"""
쿠키 흐름 디버그 - previsit 전후 쿠키 변화 추적
"""

import sys
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent / 'lib'))

from db import execute_query
from common import get_fingerprint, build_extra_fp
from product_click import product_click
from curl_cffi import requests

def print_cookies(cookies, label):
    """쿠키 상태 출력"""
    print(f"\n{'='*60}")
    print(f"🍪 {label}")
    print('='*60)

    # Akamai 관련 쿠키
    akamai_keys = ['_abck', 'bm_sz', 'bm_sv', 'bm_s', 'ak_bmsc']

    for key in akamai_keys:
        if key in cookies:
            value = cookies[key]
            # 값이 길면 앞뒤만 표시
            if len(value) > 50:
                display = f"{value[:25]}...{value[-25:]}"
            else:
                display = value
            print(f"  {key}: {display}")
        else:
            print(f"  {key}: (없음)")

    # 기타 쿠키
    other_keys = [k for k in cookies.keys() if k not in akamai_keys]
    if other_keys:
        print(f"\n  기타: {', '.join(other_keys)}")

    print()

def compare_cookies(before, after):
    """쿠키 변화 비교"""
    print(f"\n{'─'*60}")
    print("📊 쿠키 변화 분석")
    print('─'*60)

    all_keys = set(before.keys()) | set(after.keys())

    added = []
    removed = []
    changed = []
    unchanged = []

    for key in all_keys:
        if key not in before:
            added.append(key)
        elif key not in after:
            removed.append(key)
        elif before[key] != after[key]:
            changed.append(key)
        else:
            unchanged.append(key)

    if added:
        print(f"  ➕ 추가: {', '.join(added)}")
    if removed:
        print(f"  ➖ 제거: {', '.join(removed)}")
    if changed:
        print(f"  🔄 변경: {', '.join(changed)}")
        for key in changed:
            print(f"      {key}:")
            print(f"        이전: {before[key][:50]}...")
            print(f"        이후: {after[key][:50]}...")
    if unchanged:
        print(f"  ✓ 유지: {', '.join(unchanged)}")

    print('─'*60)

def main():
    # 테스트할 쿠키 ID와 상품 정보
    cookie_id = 779
    product_id = '7522489217'
    item_id = '24162779650'
    vendor_item_id = '91185106976'

    print("🔍 쿠키 흐름 디버그 테스트")
    print(f"   쿠키 ID: {cookie_id}")
    print(f"   상품 ID: {product_id}")

    # 1. DB에서 쿠키 로드
    cookie_record = execute_query("SELECT * FROM cookies WHERE id = %s", (cookie_id,))
    if not cookie_record:
        print(f"❌ 쿠키 {cookie_id} 없음")
        return

    cookie_record = cookie_record[0]
    cookie_data = json.loads(cookie_record['cookie_data'])

    # 쿠키 형식 변환 (리스트 → 딕셔너리)
    if isinstance(cookie_data, list):
        cookies = {c['name']: c['value'] for c in cookie_data}
    else:
        cookies = cookie_data

    # 핑거프린트 로드
    fingerprint = get_fingerprint(cookie_record['chrome_version'], 'u22')
    if not fingerprint:
        print("❌ 핑거프린트 없음")
        return

    # 프록시 설정
    proxy = f"socks5://{cookie_record['proxy_url']}" if cookie_record.get('proxy_url') else None

    print_cookies(cookies, "1️⃣ 초기 쿠키 (DB에서 로드)")

    # 2. 상품 페이지 방문 (previsit)
    print("\n📦 상품 페이지 방문 중...")

    previsit_url = f"/vp/products/{product_id}?itemId={item_id}&vendorItemId={vendor_item_id}"
    print(f"   URL: https://www.coupang.com{previsit_url}")

    cookies_before = cookies.copy()

    previsit_info = {
        'productId': product_id,
        'url': previsit_url,
        'itemId': item_id,
        'vendorItemId': vendor_item_id
    }

    previsit_result = product_click(
        previsit_info,
        'https://www.coupang.com/',
        cookies,
        fingerprint,
        proxy,
        verbose=False
    )

    if previsit_result['success']:
        print(f"   ✅ 성공 ({previsit_result['size']:,} bytes)")
    else:
        print(f"   ❌ 실패: {previsit_result.get('error')}")

    # 응답 쿠키 확인
    response_cookies = previsit_result.get('response_cookies', {})
    print(f"\n   📨 응답 쿠키: {len(response_cookies)}개")
    for key, value in response_cookies.items():
        if len(value) > 40:
            print(f"      {key}: {value[:20]}...{value[-20:]}")
        else:
            print(f"      {key}: {value}")

    # 쿠키 업데이트
    cookies.update(response_cookies)

    print_cookies(cookies, "2️⃣ previsit 후 쿠키")
    compare_cookies(cookies_before, cookies)

    # 3. 검색 페이지 요청
    print("\n🔍 검색 페이지 요청 중...")

    from urllib.parse import quote
    search_url = f"https://www.coupang.com/np/search?q={quote('z플립6보호필름')}&page=1"

    cookies_before_search = cookies.copy()

    # 검색 요청
    from product_click import get_sec_ch_ua
    major_version = fingerprint['chrome_major']

    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'ko-KR,ko;q=0.9',
        'Cache-Control': 'max-age=0',
        'Connection': 'keep-alive',
        'Referer': f'https://www.coupang.com{previsit_url}',  # 상품 페이지에서 검색으로
        'Sec-Ch-Ua': get_sec_ch_ua(major_version),
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Linux"',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-User': '?1',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': fingerprint['user_agent'],
    }

    ja3 = fingerprint['ja3_text']
    akamai = fingerprint['akamai_text']
    extra_fp = build_extra_fp(fingerprint)

    try:
        response = requests.get(
            search_url,
            headers=headers,
            cookies=cookies,
            ja3=ja3,
            akamai=akamai,
            extra_fp=extra_fp,
            proxy=proxy,
            timeout=30,
            allow_redirects=True,
            verify=False
        )

        size = len(response.content)
        print(f"   응답: {response.status_code} - {size:,} bytes")

        # 검색 응답 쿠키
        search_response_cookies = {}
        if response.cookies:
            for name, value in response.cookies.items():
                search_response_cookies[name] = value

        print(f"\n   📨 검색 응답 쿠키: {len(search_response_cookies)}개")
        for key, value in search_response_cookies.items():
            if len(value) > 40:
                print(f"      {key}: {value[:20]}...{value[-20:]}")
            else:
                print(f"      {key}: {value}")

        cookies.update(search_response_cookies)

        # 상품 순위 확인
        if size > 50000:
            from extractor.search_extractor import ProductExtractor
            result = ProductExtractor.extract_products_from_html(response.text)

            # 타겟 상품 찾기
            found = None
            for product in result['ranking']:
                if product['productId'] == product_id:
                    found = product
                    break

            if found:
                print(f"\n   ✅ 상품 발견! Rank: {found['rank']}")
            else:
                print(f"\n   ❌ 상품 미발견 (총 {len(result['ranking'])}개 중)")
        else:
            print(f"\n   ⚠️ 응답이 너무 작음 (차단 가능성)")

    except Exception as e:
        print(f"   ❌ 에러: {e}")

    print_cookies(cookies, "3️⃣ 검색 후 쿠키")
    compare_cookies(cookies_before_search, cookies)

    # 최종 비교
    print("\n" + "="*60)
    print("📈 전체 쿠키 변화 (초기 → 최종)")
    print("="*60)
    compare_cookies(cookies_before, cookies)

if __name__ == '__main__':
    main()
