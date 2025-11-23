#!/usr/bin/env python3
"""
TLS 에러 원인 진단 테스트
- 프록시 문제인지 Akamai 차단인지 확인

테스트 항목:
1. 프록시 기본 연결 (httpbin.org)
2. Coupang TLS 연결 (curl-cffi)
3. 동시 연결 테스트
"""

import sys
import json
import time
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, str(Path(__file__).parent / 'lib'))

from common import DEV_PROXY, get_dev_proxy_ip

def test_proxy_basic():
    """1. 프록시 기본 연결 테스트 (httpbin.org)"""
    print("\n" + "="*60)
    print("1. 프록시 기본 연결 테스트")
    print("="*60)

    proxy = DEV_PROXY['socks5']
    print(f"프록시: {proxy}")

    # curl로 httpbin 테스트
    try:
        result = subprocess.run(
            ['curl', '-s', '--proxy', proxy, 'https://httpbin.org/ip', '--max-time', '10'],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            print(f"✅ httpbin.org 연결 성공")
            print(f"   외부 IP: {data.get('origin')}")
            return True
        else:
            print(f"❌ httpbin.org 연결 실패")
            print(f"   stderr: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ 에러: {e}")
        return False


def test_coupang_tls():
    """2. Coupang TLS 연결 테스트 (curl-cffi)"""
    print("\n" + "="*60)
    print("2. Coupang TLS 연결 테스트 (curl-cffi)")
    print("="*60)

    proxy = DEV_PROXY['socks5']

    try:
        from curl_cffi import requests

        # 간단한 요청 (fingerprint 없이)
        print(f"프록시: {proxy}")
        print("요청: https://www.coupang.com/robots.txt")

        start = time.time()
        response = requests.get(
            'https://www.coupang.com/robots.txt',
            proxy=proxy,
            timeout=15,
            impersonate='chrome120'  # 기본 impersonate
        )
        elapsed = int((time.time() - start) * 1000)

        print(f"✅ Coupang TLS 연결 성공")
        print(f"   상태: {response.status_code}")
        print(f"   크기: {len(response.content)} bytes")
        print(f"   시간: {elapsed}ms")
        return True

    except Exception as e:
        error_msg = str(e)
        print(f"❌ Coupang TLS 연결 실패")
        print(f"   에러: {error_msg}")

        if 'TLS connect error' in error_msg:
            print("\n   → TLS 핸드쉐이크 실패")
            print("   → 원인: 프록시 연결 문제 또는 Akamai TLS 차단")

        return False


def test_coupang_with_fingerprint():
    """3. Coupang 정상 요청 테스트 (fingerprint 포함)"""
    print("\n" + "="*60)
    print("3. Coupang 정상 요청 테스트 (fingerprint 포함)")
    print("="*60)

    proxy = DEV_PROXY['socks5']

    try:
        from curl_cffi import requests
        from db import execute_query

        # 최신 fingerprint 로드
        fp = execute_query("""
            SELECT ja3_text, akamai_text, user_agent, signature_algorithms
            FROM fingerprints
            WHERE chrome_major >= 131
            ORDER BY chrome_major DESC
            LIMIT 1
        """)

        if not fp:
            print("❌ fingerprint 없음")
            return False

        fp = fp[0]

        # extra_fp 구성
        sig_algs = fp['signature_algorithms']
        if isinstance(sig_algs, str):
            sig_algs = json.loads(sig_algs)

        sig_names = []
        if sig_algs:
            for s in sig_algs:
                if isinstance(s, dict):
                    sig_names.append(s.get('name', ''))
                elif isinstance(s, str):
                    sig_names.append(s)

        extra_fp = {
            'tls_signature_algorithms': sig_names if sig_names else None,
            'tls_grease': True,
            'tls_permute_extensions': False,
            'tls_cert_compression': 'brotli',
        }

        headers = {
            'User-Agent': fp['user_agent'],
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
        }

        print(f"프록시: {proxy}")
        print("요청: https://www.coupang.com/robots.txt")

        start = time.time()
        response = requests.get(
            'https://www.coupang.com/robots.txt',
            headers=headers,
            proxy=proxy,
            ja3=fp['ja3_text'],
            akamai=fp['akamai_text'],
            extra_fp=extra_fp,
            timeout=15
        )
        elapsed = int((time.time() - start) * 1000)

        print(f"✅ Coupang fingerprint 요청 성공")
        print(f"   상태: {response.status_code}")
        print(f"   크기: {len(response.content)} bytes")
        print(f"   시간: {elapsed}ms")
        return True

    except Exception as e:
        error_msg = str(e)
        print(f"❌ Coupang fingerprint 요청 실패")
        print(f"   에러: {error_msg}")
        return False


def test_concurrent_connections(count=5):
    """4. 동시 연결 테스트"""
    print("\n" + "="*60)
    print(f"4. 동시 연결 테스트 ({count}개)")
    print("="*60)

    proxy = DEV_PROXY['socks5']

    def make_request(i):
        try:
            from curl_cffi import requests
            start = time.time()
            response = requests.get(
                'https://httpbin.org/ip',
                proxy=proxy,
                timeout=15,
                impersonate='chrome120'
            )
            elapsed = int((time.time() - start) * 1000)
            return {'id': i, 'success': True, 'time': elapsed}
        except Exception as e:
            return {'id': i, 'success': False, 'error': str(e)}

    print(f"프록시: {proxy}")
    print(f"동시 요청: {count}개 → httpbin.org/ip")

    results = []
    start_all = time.time()

    with ThreadPoolExecutor(max_workers=count) as executor:
        futures = [executor.submit(make_request, i) for i in range(1, count + 1)]
        for future in as_completed(futures):
            results.append(future.result())

    total_time = int((time.time() - start_all) * 1000)

    # 결과 정렬
    results.sort(key=lambda x: x['id'])

    success_count = 0
    for r in results:
        if r['success']:
            print(f"  [{r['id']}] ✅ {r['time']}ms")
            success_count += 1
        else:
            print(f"  [{r['id']}] ❌ {r['error'][:50]}")

    print(f"\n결과: {success_count}/{count} 성공")
    print(f"총 시간: {total_time}ms")

    return success_count == count


def test_concurrent_coupang(count=3):
    """5. Coupang 동시 연결 테스트"""
    print("\n" + "="*60)
    print(f"5. Coupang 동시 연결 테스트 ({count}개)")
    print("="*60)

    proxy = DEV_PROXY['socks5']

    def make_request(i):
        try:
            from curl_cffi import requests
            start = time.time()
            response = requests.get(
                'https://www.coupang.com/robots.txt',
                proxy=proxy,
                timeout=15,
                impersonate='chrome120'
            )
            elapsed = int((time.time() - start) * 1000)
            return {'id': i, 'success': True, 'time': elapsed, 'size': len(response.content)}
        except Exception as e:
            return {'id': i, 'success': False, 'error': str(e)}

    print(f"프록시: {proxy}")
    print(f"동시 요청: {count}개 → coupang.com/robots.txt")

    results = []
    start_all = time.time()

    with ThreadPoolExecutor(max_workers=count) as executor:
        futures = [executor.submit(make_request, i) for i in range(1, count + 1)]
        for future in as_completed(futures):
            results.append(future.result())

    total_time = int((time.time() - start_all) * 1000)

    # 결과 정렬
    results.sort(key=lambda x: x['id'])

    success_count = 0
    for r in results:
        if r['success']:
            print(f"  [{r['id']}] ✅ {r['time']}ms | {r['size']}B")
            success_count += 1
        else:
            error_short = r['error'][:60]
            print(f"  [{r['id']}] ❌ {error_short}")

    print(f"\n결과: {success_count}/{count} 성공")
    print(f"총 시간: {total_time}ms")

    if success_count < count:
        print("\n⚠️ 일부 실패 - TLS 에러가 있다면:")
        print("   • 프록시 동시 연결 제한 가능성")
        print("   • Akamai TLS 레벨 차단 가능성")

    return success_count == count


def main():
    import argparse
    parser = argparse.ArgumentParser(description='TLS 에러 원인 진단')
    parser.add_argument('-c', '--concurrent', type=int, default=5, help='동시 연결 수 (기본: 5)')
    parser.add_argument('--skip-basic', action='store_true', help='기본 테스트 건너뛰기')
    args = parser.parse_args()

    print("TLS 에러 원인 진단 테스트")
    print("="*60)

    # 프록시 IP 확인
    proxy_ip = get_dev_proxy_ip()
    if not proxy_ip:
        print("❌ 개발 프록시 연결 실패")
        return

    print(f"개발 프록시 IP: {proxy_ip}")

    results = {}

    # 1. 기본 연결
    if not args.skip_basic:
        results['basic'] = test_proxy_basic()

    # 2. Coupang TLS (impersonate)
    results['coupang_tls'] = test_coupang_tls()

    # 3. Coupang fingerprint
    results['coupang_fp'] = test_coupang_with_fingerprint()

    # 4. 동시 연결 (httpbin)
    results['concurrent'] = test_concurrent_connections(args.concurrent)

    # 5. Coupang 동시 연결
    results['coupang_concurrent'] = test_concurrent_coupang(min(args.concurrent, 5))

    # 진단 결과
    print("\n" + "="*60)
    print("진단 결과")
    print("="*60)

    all_pass = all(results.values())

    if all_pass:
        print("✅ 모든 테스트 통과")
        print("   → TLS 에러는 일시적 네트워크 문제일 가능성")
    else:
        if not results.get('basic', True):
            print("❌ 프록시 기본 연결 실패")
            print("   → 프록시 서버 문제 확인 필요")

        if not results.get('coupang_tls'):
            print("❌ Coupang TLS 연결 실패")
            if results.get('basic', True):
                print("   → Akamai TLS 레벨 차단 가능성")
            else:
                print("   → 프록시 문제로 인한 실패")

        if not results.get('concurrent'):
            print("❌ 동시 연결 실패")
            print("   → 프록시 동시 연결 제한 확인 필요")

        if not results.get('coupang_concurrent'):
            print("❌ Coupang 동시 연결 실패")
            print("   → Akamai 또는 프록시 동시 연결 제한")


if __name__ == '__main__':
    main()
