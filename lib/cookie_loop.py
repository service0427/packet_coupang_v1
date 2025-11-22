"""
쿠키 생성 루프 - Playwright Python
"""

import os
import json
import subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright
from db import insert_one

# Set DISPLAY for Xvfb
if 'DISPLAY' not in os.environ:
    os.environ['DISPLAY'] = ':99'

CHROME_VERSIONS_DIR = Path(__file__).parent.parent / 'chrome-versions' / 'files'

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
    print(f"반복: {loop_count}")
    print("─" * 50)

    results = []

    with sync_playwright() as p:
        # Launch options
        launch_args = [
            '--no-sandbox',
            '--disable-blink-features=AutomationControlled',
            '--no-first-run',
        ]

        browser = p.chromium.launch(
            executable_path=str(chrome_path),
            headless=False,
            args=launch_args,
            proxy={'server': proxy} if proxy else None
        )

        context = browser.new_context(
            user_agent=f'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{major_version}.0.0.0 Safari/537.36'
        )

        page = context.new_page()

        # Block unnecessary requests
        def handle_route(route):
            url = route.request.url
            resource_type = route.request.resource_type

            if resource_type in ['image', 'font', 'stylesheet', 'media']:
                route.abort()
                return

            from urllib.parse import urlparse
            if not urlparse(url).hostname.endswith('coupang.com'):
                route.abort()
                return

            route.continue_()

        page.route('**/*', handle_route)

        # Loop
        for i in range(1, loop_count + 1):
            print(f"\n[{i}/{loop_count}] 쿠키 생성 중...")

            # Clear cookies
            context.clear_cookies()

            import time
            start_time = time.time()

            # Visit login page
            page.goto('https://login.coupang.com/login/login.pang',
                     wait_until='domcontentloaded', timeout=30000)

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

            # Skip invalid cookies
            if not abck_valid:
                print(f"⚠️ [{i}/{loop_count}] 유효하지 않은 쿠키 - 건너뜀 | {load_time}ms")
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

            print(f"✅ ID: {insert_id} | 쿠키: {len(cookies)}개 | Akamai: {len(akamai_cookies)}개 | {load_time}ms")

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
