"""
쿠키 생성 모듈 - Playwright (xvfb/GUI)

브라우저를 통해 Akamai 쿠키 생성
- xvfb: 서버 환경 (headless X server)
- GUI: 로컬 환경
"""

import os
import json
import subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from common.db import insert_one

# 경로 설정
CHROME_VERSIONS_DIR = Path(__file__).parent.parent.parent / 'chrome-versions' / 'files'
USER_DATA_BASE_DIR = Path(__file__).parent.parent.parent / 'chrome-profiles'

# 설정
BLOCK_TRAFFIC = True        # 트래픽 절약 모드
USE_XVFB = True             # 가상 디스플레이 (서버용)

# 쿠키 생성 URL (빈 검색 페이지 - 검색 소모 없음)
TARGET_URL = 'https://www.coupang.com/np/search'

# 차단 도메인/경로
BLOCKED_DOMAINS = [
    'google-analytics.com', 'googletagmanager.com',
    'facebook.net', 'doubleclick.net', 'criteo.com',
    'amplitude.com', 'branch.io', 'appsflyer.com',
    'ads.', 'track.', 'pixel.', 'beacon.',
    'log.', 'analytics.', 'metrics.'
]

BLOCKED_PATHS = [
    '/log/', '/beacon/', '/track/', '/pixel/',
    '/recommend/', '/personalize/', '/ads/',
    '/n-api/srp/omp-widget',
    '/n-api/web-adapter/category-list',
    '/n-api/srp/jikgu-promotion',
    '/n-api/srp/brand-shop',
    '/n-api/srp/top-brand'
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


def find_chrome_executable(version):
    """Chrome 실행 파일 찾기

    Args:
        version: Chrome 버전 (예: '136')

    Returns:
        tuple: (chrome_path, version_number, major_version) 또는 (None, None, None)
    """
    chrome_dirs = [d for d in CHROME_VERSIONS_DIR.iterdir()
                   if d.is_dir() and version in d.name]

    if not chrome_dirs:
        return None, None, None

    selected_dir = sorted(chrome_dirs)[-1]
    version_number = selected_dir.name.replace('chrome-', '')
    major_version = int(version_number.split('.')[0])

    # 실행 파일 찾기
    linux_path = selected_dir / 'chrome-linux64' / 'chrome'
    win_path = selected_dir / 'chrome-win64' / 'chrome.exe'
    chrome_path = linux_path if linux_path.exists() else win_path if win_path.exists() else None

    return chrome_path, version_number, major_version


def create_route_handler():
    """트래픽 차단 핸들러 생성"""
    def handle_route(route):
        resource_type = route.request.resource_type
        url = route.request.url

        # 차단 대상: image, font, media, stylesheet
        if resource_type in ['image', 'font', 'media', 'stylesheet']:
            route.abort()
            return

        # 외부 추적/광고 차단
        if any(domain in url for domain in BLOCKED_DOMAINS):
            route.abort()
            return

        # 쿠팡 내부 비필수 API 차단
        if any(path in url for path in BLOCKED_PATHS):
            route.abort()
            return

        # 대용량 JS chunk 차단
        if resource_type == 'script':
            if 'coupangcdn.com' in url and '/chunks/' in url:
                route.abort()
                return

        route.continue_()

    return handle_route


def determine_status(is_access_denied, page_valid, abck_exists, abck_valid):
    """쿠키 상태 결정

    Returns:
        str: 'valid', 'denied', 'blocked', 'invalid', 'no_abck'
    """
    if not abck_exists:
        return 'no_abck'
    if is_access_denied:
        return 'denied'
    elif not page_valid:
        return 'blocked'
    elif not abck_valid:
        return 'invalid'
    else:
        return 'valid'


def generate_cookies(version, proxy, loop_count=1):
    """쿠키 생성

    Args:
        version: Chrome 버전 (예: '136')
        proxy: 프록시 URL (예: 'socks5://host:port')
        loop_count: 생성 횟수

    Returns:
        list: 생성된 쿠키 정보 리스트
    """
    # Xvfb 사용 시 DISPLAY 설정
    if USE_XVFB:
        os.environ['DISPLAY'] = ':99'

    # Chrome 찾기
    chrome_path, version_number, major_version = find_chrome_executable(version)
    if not chrome_path:
        print(f"❌ Chrome 버전 {version} 없음")
        return []

    # 프록시 IP 확인
    proxy_ip = get_proxy_ip(proxy)
    if proxy and not proxy_ip:
        print("❌ 프록시 IP 확인 실패")
        return []

    print(f"Chrome: {version_number}")
    print(f"Proxy: {proxy or 'Direct'}")
    print(f"외부 IP: {proxy_ip or 'Direct'}")
    print(f"반복: {loop_count}")
    print("─" * 50)

    results = []

    with sync_playwright() as p:
        # Launch options
        launch_args = [
            '--disable-blink-features=AutomationControlled',
            '--test-type',
            '--lang=ko-KR',
            '--disable-translate',
            '--disable-popup-blocking',
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-infobars',
            '--enable-features=NetworkService,NetworkServiceInProcess',
        ]

        if proxy:
            launch_args.append(f'--proxy-server={proxy}')

        # 브라우저 실행 (persistent 모드)
        user_data_dir = USER_DATA_BASE_DIR / f'chrome-{major_version}'
        user_data_dir.mkdir(parents=True, exist_ok=True)

        browser = p.chromium.launch_persistent_context(
            user_data_dir=str(user_data_dir),
            executable_path=str(chrome_path),
            headless=False,
            args=launch_args,
            ignore_default_args=['--enable-automation'],
            user_agent=f'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{major_version}.0.0.0 Safari/537.36'
        )
        context = browser

        # 페이지 설정
        if context.pages:
            page = context.pages[0]
        else:
            page = context.new_page()

        # 트래픽 차단
        if BLOCK_TRAFFIC:
            page.route('**/*', create_route_handler())

        # 트래픽 측정
        total_bytes = [0]

        def on_response(response):
            try:
                body = response.body()
                total_bytes[0] += len(body)
            except:
                pass

        page.on('response', on_response)

        # Loop
        for i in range(1, loop_count + 1):
            print(f"\n[{i}/{loop_count}] 쿠키 생성 중...")

            context.clear_cookies()
            total_bytes[0] = 0

            import time
            start_time = time.time()

            # 페이지 이동
            page.goto(TARGET_URL, wait_until='load', timeout=30000)

            # Access Denied 감지
            page_title = page.title()
            is_access_denied = 'Access Denied' in page_title or 'Error' in page_title

            # SRP 컨테이너 대기
            if not is_access_denied:
                try:
                    page.wait_for_selector('[class*="srp_"], [class*="search-"], #wa-search-form', timeout=20000)
                except:
                    page.wait_for_timeout(5000)

            load_time = int((time.time() - start_time) * 1000)

            # 쿠키 수집
            cookies = context.cookies()

            # Akamai 쿠키 분석
            akamai_names = ['_abck', 'ak_bmsc', 'bm_sv', 'bm_sz', 'bm_s', 'bm_so', 'bm_ss', 'bm_lso']
            akamai_cookies = [c for c in cookies if c['name'] in akamai_names]

            abck = next((c for c in akamai_cookies if c['name'] == '_abck'), None)
            abck_exists = abck is not None
            abck_value = abck['value'] if abck else None
            abck_valid = '~-1~' in abck_value if abck_value else False

            # 페이지 검증
            page_valid = False
            if not is_access_denied:
                page_valid = page.evaluate("""
                    () => {
                        const srpExists = document.querySelector('[class*="srp_"]') !== null;
                        const searchExists = document.querySelector('[class*="search-"]') !== null;
                        const waExists = document.querySelector('#wa-search-form') !== null;
                        return srpExists || searchExists || waExists;
                    }
                """)

            # 상태 결정
            init_status = determine_status(is_access_denied, page_valid, abck_exists, abck_valid)

            # DB 저장
            proxy_stripped = proxy.replace('socks5://', '') if proxy else None
            insert_id = insert_one("""
                INSERT INTO cookies
                (proxy_ip, proxy_url, chrome_version, cookie_data, init_status, source)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                proxy_ip or 'direct',
                proxy_stripped,
                version_number,
                json.dumps(cookies),
                init_status,
                'local'
            ))

            # 출력
            traffic_kb = total_bytes[0] / 1024
            status_icons = {'valid': '✅', 'denied': '🚫', 'blocked': '⛔', 'invalid': '⚠️', 'no_abck': '❌'}
            icon = status_icons.get(init_status, '❓')
            print(f"{icon} ID: {insert_id} | {init_status} | 트래픽: {traffic_kb:.0f}KB | 쿠키: {len(cookies)}개 | {load_time}ms")

            results.append({
                'iteration': i,
                'cookie_id': insert_id,
                'cookie_count': len(cookies),
                'akamai_count': len(akamai_cookies),
                'load_time': load_time,
                'init_status': init_status,
            })

            if i < loop_count:
                page.wait_for_timeout(1000)

        browser.close()

    # Summary
    print('\n' + '─' * 50)
    print('완료')
    print('─' * 50)

    by_status = {}
    for r in results:
        status = r.get('init_status', 'unknown')
        if status not in by_status:
            by_status[status] = []
        by_status[status].append(r['cookie_id'])

    print(f"총 저장: {len(results)}개")
    status_icons = {'valid': '✅', 'denied': '🚫', 'blocked': '⛔', 'invalid': '⚠️', 'no_abck': '❌'}
    for status, ids in by_status.items():
        icon = status_icons.get(status, '❓')
        print(f"  {icon} {status}: {len(ids)}개 - {', '.join(map(str, ids))}")

    return results


if __name__ == '__main__':
    import sys
    version = sys.argv[1] if len(sys.argv) > 1 else '136'
    loop_count = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    proxy = None
    for arg in sys.argv[3:]:
        if arg.startswith('--proxy='):
            proxy = arg.split('=')[1]

    generate_cookies(version, proxy, loop_count)
