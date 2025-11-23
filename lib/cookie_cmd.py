"""
쿠키 생성 명령어
"""

import sys
import random
import subprocess
import requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# Add lib directory to path
sys.path.insert(0, str(Path(__file__).parent))

from cookie_loop import generate_cookies_loop
from common import DEV_PROXY, toggle_dev_proxy, get_dev_proxy_ip

BASE_DIR = Path(__file__).parent.parent
CHROME_DIR = BASE_DIR / 'chrome-versions' / 'files'

PROXY_API_URL = 'http://mkt.techb.kr:3001/api/proxy/status'


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
        # 현재 IP 확인
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
    results = generate_cookies_loop(version, DEV_PROXY['socks5'], args.loop)

    if results:
        cookie_ids = [r['cookie_id'] for r in results]
        print(f"\n✅ 생성 완료: {len(results)}개")
        print(f"   IDs: {', '.join(map(str, cookie_ids))}")
    else:
        print("\n❌ 쿠키 생성 실패")

def get_proxies_from_api(remain=60):
    """API에서 프록시 목록 조회

    Args:
        remain: 최소 남은 트래픽 (기본: 60)

    Returns:
        list: socks5:// 형식의 프록시 URL 리스트
    """
    try:
        resp = requests.get(f'{PROXY_API_URL}?remain={remain}', timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('success') and data.get('proxies'):
                proxies = []
                for p in data['proxies']:
                    proxy_addr = p.get('proxy')
                    if proxy_addr:
                        proxies.append(f'socks5://{proxy_addr}')
                return proxies
    except Exception as e:
        print(f"⚠️  프록시 API 오류: {e}")
    return []

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
    """사용 가능한 Chrome 버전"""
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
        results = generate_cookies_loop(version, proxy, loop_count)
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
    if getattr(args, 'dev', False):
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
        # 특정 프록시 지정 시
        proxies = [args.proxy]
    else:
        # API에서 프록시 조회
        print("프록시 조회 중...")
        proxies = get_proxies_from_api(remain=60)
        if not proxies:
            print("❌ 사용 가능한 프록시 없음")
            return
        print(f"프록시: {len(proxies)}개 조회됨")

    # -t 미지정 시 프록시 개수만큼 자동 설정
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
