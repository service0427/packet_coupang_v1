"""
쿠키 생성 명령어

브라우저(Playwright)를 통해 Akamai 쿠키 생성
"""

import sys
import random
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from curl_cffi import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

from browser.cookie_generator import generate_cookies
from common.proxy import get_proxy_list

# browser/cookie_cmd.py -> lib/ -> packet_coupang_v1/
BASE_DIR = Path(__file__).parent.parent.parent
CHROME_DIR = BASE_DIR / 'chrome-versions' / 'files'

# 개발용 프록시
DEV_PROXY = {
    'host': '112.161.54.7',
    'port': '10018',
    'toggle_port': '18',
    'url': '112.161.54.7:10018',
    'socks5': 'socks5://112.161.54.7:10018'
}


def toggle_dev_proxy():
    """개발용 프록시 IP 토글"""
    try:
        toggle_url = f"http://{DEV_PROXY['host']}/toggle/{DEV_PROXY['toggle_port']}"
        resp = requests.get(toggle_url, timeout=40)
        return resp.json()
    except Exception as e:
        return {'success': False, 'error': str(e)}


def get_dev_proxy_ip():
    """개발용 프록시 현재 IP 조회"""
    try:
        resp = requests.get(
            'https://api.ipify.org?format=json',
            proxy=DEV_PROXY['socks5'],
            timeout=10
        )
        return resp.json().get('ip')
    except:
        return None


def run_dev_cookie(args):
    """개발용 쿠키 생성"""
    print("=" * 60)
    print("개발용 쿠키 생성")
    print("=" * 60)

    # IP 토글 (--toggle 옵션)
    if args.toggle:
        print("🔄 프록시 IP 토글 중...")
        result = toggle_dev_proxy()
        if not result.get('success'):
            print(f"❌ IP 토글 실패: {result.get('error')}")
            return
        print(f"   새 IP: {result['ip']}")
    else:
        current_ip = get_dev_proxy_ip()
        if not current_ip:
            print("❌ 프록시 IP 확인 실패")
            return
        print(f"현재 IP: {current_ip}")

    # Chrome 버전
    versions = get_chrome_versions()
    if not versions:
        print("❌ Chrome 버전 없음")
        return

    version = args.version or random.choice(versions)
    print(f"Chrome: {version}")
    print(f"프록시: {DEV_PROXY['socks5']}")
    print(f"반복: {args.loop}")
    print("=" * 60)

    # 쿠키 생성
    results = generate_cookies(version, DEV_PROXY['socks5'], args.loop)

    if results:
        cookie_ids = [r['cookie_id'] for r in results]
        print(f"\n✅ 생성 완료: {len(results)}개")
        print(f"   IDs: {', '.join(map(str, cookie_ids))}")
    else:
        print("\n❌ 쿠키 생성 실패")


def cleanup_previous():
    """이전 프로세스 정리"""
    killed = 0
    try:
        result = subprocess.run(['pgrep', '-f', 'chrome-linux64/chrome'], capture_output=True, text=True)
        if result.stdout.strip():
            subprocess.run(['pkill', '-f', 'chrome-linux64/chrome'], capture_output=True)
            killed += len(result.stdout.strip().split('\n'))
    except:
        pass
    return killed


def get_chrome_versions():
    """사용 가능한 Chrome 버전 (131+)"""
    versions = []
    for d in CHROME_DIR.iterdir():
        if d.is_dir() and d.name.startswith('chrome-'):
            version = d.name.replace('chrome-', '')
            major = int(version.split('.')[0])
            if major >= 131:
                versions.append(version.split('.')[0])
    return sorted(set(versions))


def run_task(task_id, version, proxy, loop_count):
    """개별 작업 실행"""
    try:
        results = generate_cookies(version, proxy, loop_count)
        cookie_ids = [r['cookie_id'] for r in results]
        return {
            'task_id': task_id,
            'version': version,
            'proxy': proxy,
            'success': len(results) == loop_count,
            'cookie_ids': cookie_ids,
            'generated': len(results),
        }
    except Exception as e:
        return {
            'task_id': task_id,
            'version': version,
            'proxy': proxy,
            'success': False,
            'cookie_ids': [],
            'generated': 0,
            'error': str(e)[:100]
        }


def run_cookie(args):
    """쿠키 생성 실행"""
    killed = cleanup_previous()
    if killed > 0:
        print(f"⚠️  이전 프로세스 {killed}개 정리됨")

    # 개발 모드
    if args.dev:
        run_dev_cookie(args)
        return

    print("=" * 60)
    print("쿠키 생성")
    print("=" * 60)
    print(f"시작: {datetime.now().strftime('%H:%M:%S')}")

    versions = get_chrome_versions()
    if not versions:
        print("❌ Chrome 버전 없음")
        return

    # 프록시 목록 가져오기
    if args.proxy:
        proxies = [args.proxy]
    else:
        print("프록시 조회 중...")
        proxy_list = get_proxy_list(min_remain=60)
        proxies = [f"socks5://{p['proxy']}" for p in proxy_list]
        if not proxies:
            print("❌ 사용 가능한 프록시 없음")
            return
        print(f"프록시: {len(proxies)}개 조회됨")

    # 쓰레드 수 결정
    if args.threads is None:
        thread_count = len(proxies)
    else:
        thread_count = min(args.threads, len(proxies))

    print(f"쓰레드: {thread_count}, 조합당: {args.loop}개")
    print(f"Chrome: {', '.join(versions)}")

    tasks = []
    for i in range(thread_count):
        version = args.version or random.choice(versions)
        proxy = proxies[i]
        tasks.append((i + 1, version, proxy, args.loop))

    print(f"\n작업:")
    for t in tasks:
        print(f"  [{t[0]}] Chrome {t[1]} | {t[2].split(':')[-1]}")
    print("=" * 60)

    results = []
    with ThreadPoolExecutor(max_workers=thread_count) as executor:
        futures = {executor.submit(run_task, *t): t for t in tasks}
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            status = "✅" if result['success'] else "⚠️"
            print(f"\n{status} [{result['task_id']}] {result['generated']}/{args.loop}")
            if result['cookie_ids']:
                print(f"   IDs: {result['cookie_ids']}")

    total = sum(r['generated'] for r in results)
    all_ids = [id for r in results for id in r['cookie_ids']]

    print("\n" + "=" * 60)
    print(f"총 생성: {total}")
    if all_ids:
        print(f"IDs: {min(all_ids)} ~ {max(all_ids)}")
    print(f"완료: {datetime.now().strftime('%H:%M:%S')}")
