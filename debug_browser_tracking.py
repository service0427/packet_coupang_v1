#!/usr/bin/env python3
"""
브라우저에서 상품 페이지 방문 시 발생하는 네트워크 요청 분석
- JavaScript 추적 API 호출 확인
- 개인화 검색에 영향을 주는 요청 식별
"""

import sys
import json
import re
from pathlib import Path
from playwright.sync_api import sync_playwright

def main():
    product_url = "https://www.coupang.com/vp/products/7522489217?itemId=24162779650&vendorItemId=91185106976"
    search_url = "https://www.coupang.com/np/search?q=z플립6보호필름&page=1"

    print("🔍 브라우저 네트워크 요청 분석")
    print(f"   상품 URL: {product_url[:60]}...")
    print(f"   검색 URL: {search_url[:60]}...")
    print()

    # 수집할 요청들
    product_page_requests = []
    search_page_requests = []
    current_phase = 'product'

    with sync_playwright() as p:
        # 프록시 설정 (쿠키 779의 프록시 사용)
        browser = p.chromium.launch(
            headless=True,
            proxy={
                'server': 'socks5://112.161.54.7:10018'
            }
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        def on_request(request):
            url = request.url
            method = request.method

            # 중요한 요청만 필터링
            interesting_patterns = [
                'api', 'track', 'log', 'event', 'click', 'view', 'impression',
                'beacon', 'pixel', 'analytics', 'collect', 'sdk', 'rec',
                'personalize', 'user', 'session', 'visit'
            ]

            # 리소스 파일 제외
            exclude_patterns = ['.js', '.css', '.png', '.jpg', '.gif', '.woff', '.svg', 'googleads', 'facebook', 'google-analytics']

            if any(ex in url.lower() for ex in exclude_patterns):
                return

            is_interesting = any(pattern in url.lower() for pattern in interesting_patterns)

            req_info = {
                'url': url,
                'method': method,
                'interesting': is_interesting,
                'post_data': None
            }

            # POST 데이터 확인
            if method == 'POST':
                try:
                    post_data = request.post_data
                    if post_data:
                        req_info['post_data'] = post_data[:500] if len(post_data) > 500 else post_data
                except:
                    pass

            if current_phase == 'product':
                product_page_requests.append(req_info)
            else:
                search_page_requests.append(req_info)

        page.on('request', on_request)

        # 1단계: 상품 페이지 방문
        print("=" * 60)
        print("1️⃣ 상품 페이지 방문")
        print("=" * 60)

        page.goto(product_url, wait_until='networkidle')
        page.wait_for_timeout(3000)  # JavaScript 완전 실행 대기

        # 2단계: 검색 페이지로 이동
        print("\n" + "=" * 60)
        print("2️⃣ 검색 페이지로 이동")
        print("=" * 60)

        current_phase = 'search'
        page.goto(search_url, wait_until='networkidle')
        page.wait_for_timeout(3000)

        # 검색 결과에서 상품 확인
        try:
            # 상품 카드 찾기
            product_cards = page.query_selector_all('a[href*="/vp/products/7522489217"]')
            if product_cards:
                print(f"\n✅ 상품 발견! ({len(product_cards)}개 요소)")

                # 첫 번째 상품의 순위 확인
                for card in product_cards:
                    href = card.get_attribute('href')
                    rank_match = re.search(r'rank=(\d+)', href)
                    if rank_match:
                        print(f"   Rank: {rank_match.group(1)}")
                        break
            else:
                # 전체 상품 수 확인
                all_products = page.query_selector_all('#productList li a[href*="/vp/products/"]')
                print(f"\n❌ 상품 미발견 (총 {len(all_products)}개 중)")

        except Exception as e:
            print(f"   검색 결과 확인 실패: {e}")

        browser.close()

    # 분석 결과 출력
    print("\n" + "=" * 60)
    print("📊 상품 페이지 네트워크 요청 분석")
    print("=" * 60)

    # 중요한 요청만 필터링
    interesting_requests = [r for r in product_page_requests if r['interesting']]

    print(f"\n총 요청: {len(product_page_requests)}개")
    print(f"주요 요청: {len(interesting_requests)}개")

    if interesting_requests:
        print("\n🔴 주요 추적/분석 API 호출:")
        for i, req in enumerate(interesting_requests, 1):
            # URL 단축
            url = req['url']
            if len(url) > 80:
                url = url[:80] + '...'
            print(f"\n  [{i}] {req['method']} {url}")

            if req['post_data']:
                post = req['post_data']
                if len(post) > 200:
                    post = post[:200] + '...'
                print(f"      POST: {post}")

    # 쿠팡 특정 API 패턴 찾기
    coupang_apis = [r for r in product_page_requests
                    if 'coupang.com' in r['url'] and
                       any(p in r['url'].lower() for p in ['api', 'track', 'log', 'event', 'sdk', 'rec'])]

    if coupang_apis:
        print("\n\n🟠 쿠팡 내부 API 호출:")
        for req in coupang_apis:
            url = req['url']
            # URL에서 경로만 추출
            path = url.replace('https://www.coupang.com', '').split('?')[0]
            print(f"  - {req['method']} {path}")

    print("\n" + "=" * 60)
    print("📊 검색 페이지 네트워크 요청 분석")
    print("=" * 60)

    search_interesting = [r for r in search_page_requests if r['interesting']]
    print(f"\n총 요청: {len(search_page_requests)}개")
    print(f"주요 요청: {len(search_interesting)}개")

if __name__ == '__main__':
    main()
