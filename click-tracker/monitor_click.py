#!/usr/bin/env python3
"""
상품 클릭 시 네트워크 요청 모니터링
- 검색 → 상품 찾기 → 클릭 → 모든 요청 추적
"""

import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright

# Add lib directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'lib'))
from db import execute_query

# Set DISPLAY for Xvfb
if 'DISPLAY' not in os.environ:
    os.environ['DISPLAY'] = ':99'

# 타겟 상품 정보
TARGET_PRODUCT = {
    'product_id': '9024146312',
    'query': '호박 달빛식혜'
}

def get_latest_cookie():
    """DB에서 최신 쿠키 가져오기"""
    rows = execute_query("""
        SELECT id, cookie_data, chrome_version, proxy_url, proxy_ip
        FROM cookies
        WHERE use_count = 0
        ORDER BY id DESC
        LIMIT 1
    """)
    if rows:
        row = rows[0]
        return {
            'id': row['id'],
            'cookie_data': json.loads(row['cookie_data']),
            'chrome_version': row['chrome_version'],
            'proxy_url': row['proxy_url'],
            'proxy_ip': row['proxy_ip']
        }
    return None

def monitor_product_click():
    """상품 클릭 모니터링"""

    # 쿠키 가져오기
    cookie_record = get_latest_cookie()
    if not cookie_record:
        print("❌ 유효한 쿠키가 없습니다")
        return

    # 수집할 데이터
    requests_log = []
    responses_log = []

    print("=" * 70)
    print("상품 클릭 네트워크 모니터링")
    print("=" * 70)
    # DB에는 host:port만 저장
    db_proxy = cookie_record['proxy_url']
    proxy = f'socks5://{db_proxy}' if db_proxy else None

    print(f"검색어: {TARGET_PRODUCT['query']}")
    print(f"상품 ID: {TARGET_PRODUCT['product_id']}")
    print(f"쿠키 ID: {cookie_record['id']}")
    print(f"Chrome: {cookie_record['chrome_version']}")
    print(f"프록시: {proxy}")
    print("=" * 70)

    with sync_playwright() as p:
        # Chrome 버전에서 major 버전 추출
        chrome_version = cookie_record['chrome_version']
        major_version = int(chrome_version.split('.')[0])

        # 실제 Chrome 바이너리 찾기
        chrome_dir = Path(__file__).parent.parent / 'chrome-versions' / 'files'
        chrome_path = None

        for d in chrome_dir.iterdir():
            if d.is_dir() and chrome_version in d.name:
                linux_path = d / 'chrome-linux64' / 'chrome'
                if linux_path.exists():
                    chrome_path = str(linux_path)
                    break

        if not chrome_path:
            print(f"❌ Chrome {chrome_version} 바이너리를 찾을 수 없음")
            return

        print(f"Chrome 바이너리: {chrome_path}")

        # 브라우저 실행 (실제 Chrome 사용)
        browser = p.chromium.launch(
            executable_path=chrome_path,
            headless=False,
            args=[
                '--no-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--no-first-run',
            ],
            proxy={'server': proxy} if proxy else None
        )

        context = browser.new_context(
            user_agent=f'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{major_version}.0.0.0 Safari/537.36'
        )

        # 쿠키 설정
        cookies_for_playwright = []
        for cookie in cookie_record['cookie_data']:
            pw_cookie = {
                'name': cookie['name'],
                'value': cookie['value'],
                'domain': cookie.get('domain', '.coupang.com'),
                'path': cookie.get('path', '/'),
            }
            cookies_for_playwright.append(pw_cookie)

        context.add_cookies(cookies_for_playwright)
        print(f"✅ 쿠키 {len(cookies_for_playwright)}개 설정됨")

        page = context.new_page()

        # 네트워크 요청 로깅
        def on_request(request):
            req_data = {
                'timestamp': datetime.now().isoformat(),
                'url': request.url,
                'method': request.method,
                'resource_type': request.resource_type,
                'headers': dict(request.headers),
                'post_data': request.post_data[:500] if request.post_data else None
            }
            requests_log.append(req_data)

            # 중요 요청만 출력
            if request.resource_type in ['document', 'xhr', 'fetch']:
                url_short = request.url[:80] + '...' if len(request.url) > 80 else request.url
                print(f"[REQ] {request.method} {request.resource_type}: {url_short}")

        def on_response(response):
            resp_data = {
                'timestamp': datetime.now().isoformat(),
                'url': response.url,
                'status': response.status,
                'headers': dict(response.headers),
            }
            responses_log.append(resp_data)

        page.on('request', on_request)
        page.on('response', on_response)

        # 1단계: 검색 페이지 접속
        print("\n[1/4] 검색 페이지 접속...")
        search_url = f"https://www.coupang.com/np/search?q={TARGET_PRODUCT['query']}"
        page.goto(search_url, wait_until='domcontentloaded', timeout=60000)
        page.wait_for_timeout(5000)

        # 페이지 상태 확인
        current_url = page.url
        print(f"현재 URL: {current_url[:80]}...")

        # 2단계: 상품 찾기
        print(f"\n[2/4] 상품 찾기... (ID: {TARGET_PRODUCT['product_id']})")

        # 상품 링크 찾기 (여러 셀렉터 시도)
        product_link = None
        selectors = [
            f"a[href*='products/{TARGET_PRODUCT['product_id']}']",
            f"a[data-product-id='{TARGET_PRODUCT['product_id']}']",
            f"li[data-product-id='{TARGET_PRODUCT['product_id']}'] a",
        ]

        for selector in selectors:
            product_link = page.query_selector(selector)
            if product_link:
                print(f"매칭 셀렉터: {selector}")
                break

        if not product_link:
            print("❌ 상품을 찾을 수 없음")
            # 페이지 스크린샷
            page.screenshot(path='click-tracker/search_page.png')
            print("📸 스크린샷: click-tracker/search_page.png")

            # 페이지 내용 일부 출력
            page_content = page.content()
            if 'Access Denied' in page_content:
                print("⚠️  Access Denied - Akamai 차단")
            elif 'challenge' in page_content.lower():
                print("⚠️  Challenge 페이지 감지")

            browser.close()
            return

        # 상품 정보 추출
        product_url = product_link.get_attribute('href')
        print(f"✅ 상품 발견: {product_url[:60]}...")

        # 전체 URL 생성
        if product_url.startswith('/'):
            full_product_url = f"https://www.coupang.com{product_url}"
        else:
            full_product_url = product_url

        # 3단계: 상품 페이지 이동
        print("\n[3/4] 상품 페이지 이동...")
        print("-" * 70)

        # 클릭 전 요청 수 기록
        requests_before_click = len(requests_log)

        # Referer 설정하고 상품 페이지로 이동
        search_referer = page.url
        page.set_extra_http_headers({'Referer': search_referer})

        # 상품 페이지로 이동
        page.goto(full_product_url, wait_until='domcontentloaded', timeout=60000)
        page.wait_for_timeout(5000)  # 추가 요청 대기 (API 호출 포함)

        print("-" * 70)

        # 4단계: 클릭 후 요청 분석
        print("\n[4/4] 클릭 후 요청 분석...")

        requests_after_click = requests_log[requests_before_click:]

        # 요청 유형별 분류
        request_types = {}
        domains = {}

        for req in requests_after_click:
            # 유형별
            rtype = req['resource_type']
            request_types[rtype] = request_types.get(rtype, 0) + 1

            # 도메인별
            from urllib.parse import urlparse
            domain = urlparse(req['url']).netloc
            domains[domain] = domains.get(domain, 0) + 1

        print(f"\n총 요청 수: {len(requests_after_click)}")

        print("\n[요청 유형]")
        for rtype, count in sorted(request_types.items(), key=lambda x: -x[1]):
            print(f"  {rtype}: {count}")

        print("\n[도메인]")
        for domain, count in sorted(domains.items(), key=lambda x: -x[1])[:10]:
            print(f"  {domain}: {count}")

        # 중요 API 요청 추출
        print("\n[XHR/Fetch 요청]")
        api_requests = [r for r in requests_after_click if r['resource_type'] in ['xhr', 'fetch']]
        for req in api_requests:
            url_short = req['url'][:100]
            print(f"  {req['method']} {url_short}")

        # 스크린샷
        page.screenshot(path='click-tracker/product_page.png')
        print("\n📸 스크린샷: click-tracker/product_page.png")

        browser.close()

    # 결과 저장
    output_dir = Path(__file__).parent

    # 전체 요청 로그
    with open(output_dir / 'requests_log.json', 'w', encoding='utf-8') as f:
        json.dump(requests_log, f, ensure_ascii=False, indent=2)

    # 클릭 후 요청만
    with open(output_dir / 'click_requests.json', 'w', encoding='utf-8') as f:
        json.dump(requests_after_click, f, ensure_ascii=False, indent=2)

    print(f"\n📁 로그 저장:")
    print(f"   - click-tracker/requests_log.json (전체: {len(requests_log)}개)")
    print(f"   - click-tracker/click_requests.json (클릭 후: {len(requests_after_click)}개)")

    # 요약
    print("\n" + "=" * 70)
    print("요약")
    print("=" * 70)
    print(f"검색 → 클릭까지 총 요청: {len(requests_log)}")
    print(f"클릭 후 요청: {len(requests_after_click)}")
    print(f"API 요청 (XHR/Fetch): {len(api_requests)}")

    return {
        'total_requests': len(requests_log),
        'click_requests': len(requests_after_click),
        'api_requests': len(api_requests),
        'requests_log': requests_log,
        'click_requests_log': requests_after_click
    }

if __name__ == '__main__':
    monitor_product_click()
