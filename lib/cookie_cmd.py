"""
쿠키 생성 명령어
"""

import sys
import random
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# Add lib directory to path
sys.path.insert(0, str(Path(__file__).parent))

from cookie_loop import generate_cookies_loop

BASE_DIR = Path(__file__).parent.parent
CHROME_DIR = BASE_DIR / 'chrome-versions' / 'files'

PROXIES = [
    'socks5://14.37.117.98:10027',
    'socks5://14.37.117.98:10028',
    'socks5://14.37.117.98:10029',
    'socks5://14.37.117.98:10030',
]

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

    print("=" * 60)
    print("쿠키 생성")
    print("=" * 60)
    print(f"시작: {datetime.now().strftime('%H:%M:%S')}")
    print(f"쓰레드: {args.threads}, 조합당: {args.loop}개")

    versions = get_chrome_versions()
    if not versions:
        print("❌ Chrome 버전 없음")
        return

    print(f"Chrome: {', '.join(versions)}")

    tasks = []
    for i in range(args.threads):
        version = args.version or random.choice(versions)
        proxy = args.proxy or PROXIES[i % len(PROXIES)]
        tasks.append((i + 1, version, proxy, args.loop))

    print(f"\n작업:")
    for t in tasks:
        print(f"  [{t[0]}] Chrome {t[1]} | {t[2].split(':')[-1]}")
    print("=" * 60)

    results = []
    with ThreadPoolExecutor(max_workers=args.threads) as executor:
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
