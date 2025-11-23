"""
쿠키 생성 루프 - Playwright Python

생성 모드:
- basic: 매번 새로운 컨텍스트 (기본)
- persistent: 유저폴더 사용 (캐시/상태 유지)
"""

import os
import json
import random
import subprocess
from pathlib import Path
from urllib.parse import quote
from playwright.sync_api import sync_playwright
from db import insert_one, execute_query
from common import generate_traceid

# DISPLAY 설정은 USE_XVFB 플래그에 따라 generate_cookies_loop에서 처리

CHROME_VERSIONS_DIR = Path(__file__).parent.parent / 'chrome-versions' / 'files'
USER_DATA_BASE_DIR = Path(__file__).parent.parent / 'chrome-profiles'

# 쿠키 생성 모드 설정
COOKIE_MODE = 'persistent'  # 'basic' 또는 'persistent'

# 트래픽 차단 설정
BLOCK_TRAFFIC = True  # True: 트래픽 절약 모드, False: 전체 로드

# 타겟 URL 설정
USE_SEARCH_PAGE = True  # True: 검색 페이지, False: 로그인 페이지

# Xvfb 사용 설정
USE_XVFB = True  # True: 가상 디스플레이 (Xvfb), False: 실제 GUI

# 검색 키워드 (30개 롤링)
SEARCH_KEYWORDS = [
    '노트북', '아이폰', '갤럭시', '에어팟', '맥북',
    '삼성TV', 'LG냉장고', '다이슨', '나이키', '아디다스',
    '신라면', '코카콜라', '오레오', '바나나우유', '초코파이',
    '무선이어폰', '키보드', '마우스', '모니터', '웹캠',
    '운동화', '백팩', '선글라스', '시계', '지갑',
    '샴푸', '치약', '화장지', '세제', '물티슈'
]

def get_proxy_ip(proxy):
    """프록시 외부 IP 확인"""
    if not proxy:
        return None
    try:
        result = subprocess.run(
            ['curl', '-s', '--proxy', proxy, 'https://api.ipify.org?format=json'],
            capture_output=True, text=True, timeout=10
        )
        return json.loads(result.stdout).get('ip')
    except:
        return None

def generate_cookies_loop(version, proxy, loop_count):
    """쿠키 생성 루프"""
    # Xvfb 사용 시 DISPLAY 설정
    if USE_XVFB:
        os.environ['DISPLAY'] = ':99'

    # Find Chrome version
    chrome_dirs = [d for d in CHROME_VERSIONS_DIR.iterdir()
                   if d.is_dir() and version in d.name]

    if not chrome_dirs:
        print(f"❌ Chrome 버전 {version} 없음")
        return []

    selected_dir = sorted(chrome_dirs)[-1]
    version_number = selected_dir.name.replace('chrome-', '')
    major_version = int(version_number.split('.')[0])

    # Find Chrome executable
    linux_path = selected_dir / 'chrome-linux64' / 'chrome'
    win_path = selected_dir / 'chrome-win64' / 'chrome.exe'
    chrome_path = linux_path if linux_path.exists() else win_path if win_path.exists() else None

    if not chrome_path:
        print("❌ Chrome 실행 파일 없음")
        return []

    # Get proxy IP
    proxy_ip = get_proxy_ip(proxy)
    if proxy and not proxy_ip:
        print("❌ 프록시 IP 확인 실패")
        return []

    print(f"Chrome: {version_number}")
    print(f"Proxy: {proxy or 'Direct'}")
    print(f"외부 IP: {proxy_ip or 'Direct'}")
    print(f"모드: {COOKIE_MODE}")
    print(f"반복: {loop_count}")
    print("─" * 50)

    results = []

    with sync_playwright() as p:
        # Launch options (coupang_agent_v2 설정 기반)
        launch_args = [
            '--disable-blink-features=AutomationControlled',  # 자동화 감지 방지
            '--test-type',                           # 테스트 모드 (일부 제한 해제)
            '--lang=ko-KR',                          # 한국어 설정
            '--disable-translate',                   # 번역 팝업 방지
            '--disable-popup-blocking',              # 팝업 차단 비활성화
            '--no-sandbox',                          # 샌드박스 비활성화
            '--disable-setuid-sandbox',              # Linux setuid 샌드박스 비활성화
            '--disable-infobars',                    # 정보 바 비활성화
            '--enable-features=NetworkService,NetworkServiceInProcess',  # 네트워크 서비스
        ]

        if proxy:
            launch_args.append(f'--proxy-server={proxy}')

        # 모드에 따라 브라우저 실행
        if COOKIE_MODE == 'persistent':
            # 유저폴더 방식: 캐시/상태 유지
            user_data_dir = USER_DATA_BASE_DIR / f'chrome-{major_version}'
            user_data_dir.mkdir(parents=True, exist_ok=True)

            browser = p.chromium.launch_persistent_context(
                user_data_dir=str(user_data_dir),
                executable_path=str(chrome_path),
                headless=False,
                args=launch_args,
                ignore_default_args=['--enable-automation'],  # 자동화 툴바 숨김
                user_agent=f'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{major_version}.0.0.0 Safari/537.36'
            )
            context = browser
            is_persistent = True
        else:
            # 기본 방식: 매번 새로운 컨텍스트
            browser = p.chromium.launch(
                executable_path=str(chrome_path),
                headless=False,
                args=launch_args,
                ignore_default_args=['--enable-automation']  # 자동화 툴바 숨김
            )
            context = browser.new_context(
                user_agent=f'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{major_version}.0.0.0 Safari/537.36'
            )
            is_persistent = False

        # persistent 모드: 기존 페이지 사용 (about:blank 탭), basic 모드: 새 페이지 생성
        if is_persistent and context.pages:
            page = context.pages[0]
        else:
            page = context.new_page()

        # 트래픽 측정
        total_bytes = [0]
        traffic_details = []

        # 트래픽 차단 모드
        if BLOCK_TRAFFIC:
            def handle_route(route):
                resource_type = route.request.resource_type
                url = route.request.url

                # 차단 대상: image, font, media, stylesheet
                if resource_type in ['image', 'font', 'media', 'stylesheet']:
                    route.abort()
                    return

                # 외부 추적/광고 차단
                blocked_domains = [
                    'google-analytics.com', 'googletagmanager.com',
                    'facebook.net', 'doubleclick.net', 'criteo.com',
                    'amplitude.com', 'branch.io', 'appsflyer.com',
                    'ads.', 'track.', 'pixel.', 'beacon.',
                    'log.', 'analytics.', 'metrics.'
                ]
                if any(domain in url for domain in blocked_domains):
                    route.abort()
                    return

                # 쿠팡 내부 비필수 API 차단
                blocked_paths = [
                    '/log/', '/beacon/', '/track/', '/pixel/',
                    '/recommend/', '/personalize/', '/ads/',
                    '/n-api/srp/omp-widget',
                    '/n-api/web-adapter/category-list',
                    '/n-api/srp/jikgu-promotion',
                    '/n-api/srp/brand-shop',
                    '/n-api/srp/top-brand'
                ]
                if any(path in url for path in blocked_paths):
                    route.abort()
                    return

                # 대용량 JS chunk 차단
                if resource_type == 'script':
                    if 'coupangcdn.com' in url and '/chunks/' in url:
                        route.abort()
                        return

                route.continue_()

            page.route('**/*', handle_route)

        # 응답 트래픽 측정
        def on_response(response):
            try:
                body = response.body()
                size = len(body)
                total_bytes[0] += size
                if size > 100 * 1024:
                    traffic_details.append({
                        'url': response.url[:80],
                        'size': size
                    })
            except:
                pass

        page.on('response', on_response)


        # Loop
        for i in range(1, loop_count + 1):
            print(f"\n[{i}/{loop_count}] 쿠키 생성 중...")

            # Clear cookies
            context.clear_cookies()

            import time
            start_time = time.time()

            # 1단계: 메인 페이지 방문
            # page.goto('https://www.coupang.com/', wait_until='domcontentloaded', timeout=30000)
            # page.wait_for_timeout(1000)

            # 2단계: 타겟 페이지 이동
            if USE_SEARCH_PAGE:
                keyword = random.choice(SEARCH_KEYWORDS)
                trace_id = generate_traceid()
                target_url = f'https://www.coupang.com/np/search?component=&q={quote(keyword)}&traceId={trace_id}&channel=user'
            else:
                target_url = 'https://login.coupang.com/login/login.pang'

            # coupang_agent_v2 방식: waitUntil='load' (모든 리소스 로드 완료)
            page.goto(target_url, wait_until='load', timeout=30000)

            # Access Denied 감지
            page_title = page.title()
            if 'Access Denied' in page_title or 'Error' in page_title:
                load_time = int((time.time() - start_time) * 1000)
                print(f"🚫 [{i}/{loop_count}] Access Denied - 건너뜀 | {load_time}ms")
                continue

            if USE_SEARCH_PAGE:
                # 검색 페이지: 상품 목록 대기 (CSR 렌더링 완료)
                try:
                    page.wait_for_selector('#productList > li, #product-list > li', timeout=20000)
                except:
                    # 타임아웃 시 추가 대기
                    page.wait_for_timeout(5000)
            else:
                # 로그인 페이지 등: 기본 대기
                page.wait_for_timeout(3000)

            load_time = int((time.time() - start_time) * 1000)

            # Get cookies
            cookies = context.cookies()

            # Extract Akamai cookies
            akamai_names = ['_abck', 'ak_bmsc', 'bm_sv', 'bm_sz', 'bm_s', 'bm_so', 'bm_ss', 'bm_lso']
            akamai_cookies = [c for c in cookies if c['name'] in akamai_names]

            abck = next((c for c in akamai_cookies if c['name'] == '_abck'), None)
            abck_value = abck['value'] if abck else None
            abck_valid = '~-1~' in abck_value if abck_value else False

            # 검색 페이지일 때만 상품 개수 검증
            product_count = 0
            if USE_SEARCH_PAGE:
                product_count = page.evaluate("""
                    () => {
                        const selectors = [
                            '#productList > li',
                            '#product-list > li[data-id]',
                            '#product-list > li',
                            'a[href*="/vp/products/"]'
                        ];
                        for (const sel of selectors) {
                            const count = document.querySelectorAll(sel).length;
                            if (count > 0) return count;
                        }
                        return 0;
                    }
                """)
                if product_count == 0:
                    print(f"⚠️ [{i}/{loop_count}] 차단됨 (상품 0개) - 건너뜀 | {load_time}ms")
                    continue

            # Skip invalid cookies
            if not abck_valid:
                print(f"⚠️ [{i}/{loop_count}] 유효하지 않은 쿠키 (_abck 없음) - 건너뜀 | {load_time}ms")
                continue

            # Save to database (only valid cookies)
            # proxy_url에서 socks5:// 제거하여 host:port만 저장
            proxy_stripped = proxy.replace('socks5://', '') if proxy else None
            insert_id = insert_one("""
                INSERT INTO cookies
                (proxy_ip, proxy_url, chrome_version, cookie_data)
                VALUES (%s, %s, %s, %s)
            """, (
                proxy_ip or 'direct',
                proxy_stripped,
                version_number,
                json.dumps(cookies)
            ))

            # 트래픽 KB 계산
            traffic_kb = total_bytes[0] / 1024
            print(f"✅ ID: {insert_id} | 상품: {product_count}개 | 트래픽: {traffic_kb:.0f}KB | 쿠키: {len(cookies)}개 | Akamai: {len(akamai_cookies)}개 | {load_time}ms")

            # 대용량 요청 출력
            # if traffic_details:
            #     print(f"   📦 대용량 요청:")
            #     for t in sorted(traffic_details, key=lambda x: x['size'], reverse=True)[:5]:
            #         print(f"      {t['size']//1024}KB: {t['url']}")

            # 다음 반복을 위해 리셋
            total_bytes[0] = 0
            traffic_details.clear()

            results.append({
                'iteration': i,
                'cookie_id': insert_id,
                'cookie_count': len(cookies),
                'akamai_count': len(akamai_cookies),
                'load_time': load_time,
            })

            if i < loop_count:
                page.wait_for_timeout(1000)

        browser.close()

    # Summary
    print('\n' + '─' * 50)
    print('완료')
    print('─' * 50)

    cookie_ids = [r['cookie_id'] for r in results]

    print(f"저장: {len(results)}개")
    print(f"IDs: {', '.join(map(str, cookie_ids))}")

    return results

if __name__ == '__main__':
    import sys
    version = sys.argv[1] if len(sys.argv) > 1 else '136'
    loop_count = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    proxy = None
    for arg in sys.argv[3:]:
        if arg.startswith('--proxy='):
            proxy = arg.split('=')[1]

    generate_cookies_loop(version, proxy, loop_count)
