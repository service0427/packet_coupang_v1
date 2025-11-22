#!/usr/bin/env python3
"""
상품 클릭 시뮬레이터 - curl-cffi 사용
검색 결과에서 상품 페이지로의 네비게이션 시뮬레이션
"""

import sys
import json
from pathlib import Path
from datetime import datetime
from urllib.parse import quote, urlencode

# Add lib directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'lib'))
from db import execute_query
from curl_cffi import requests

BASE_DIR = Path(__file__).parent.parent

def get_cookie_by_id(cookie_id):
    """특정 ID의 쿠키 가져오기"""
    rows = execute_query("""
        SELECT id, cookie_data, chrome_version, proxy_url, proxy_ip
        FROM cookies
        WHERE id = %s
    """, (cookie_id,))
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

def get_fingerprint(chrome_version, platform='u22'):
    """TLS 프로파일 로드"""
    tls_dir = BASE_DIR / 'chrome-versions' / 'tls' / platform

    # 정확한 버전 매칭
    tls_file = tls_dir / f"{chrome_version}.json"
    if tls_file.exists():
        with open(tls_file) as f:
            return json.load(f)

    # Major 버전 매칭
    major = chrome_version.split('.')[0]
    for f in tls_dir.glob(f"{major}.*.json"):
        with open(f) as file:
            return json.load(file)

    return None

def parse_cookies(cookie_record):
    """쿠키 데이터를 requests 형식으로 변환"""
    cookies = {}
    for cookie in cookie_record['cookie_data']:
        cookies[cookie['name']] = cookie['value']
    return cookies

def build_headers(fingerprint, referer=None):
    """요청 헤더 생성"""
    major_version = fingerprint.get('user_agent', '').split('Chrome/')[1].split('.')[0] if 'Chrome/' in fingerprint.get('user_agent', '') else '136'

    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br, zstd',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        'Cache-Control': 'max-age=0',
        'Connection': 'keep-alive',
        'Host': 'www.coupang.com',
        'Sec-Ch-Ua': f'"Chromium";v="{major_version}", "Google Chrome";v="{major_version}", "Not-A.Brand";v="24"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Linux"',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-User': '?1',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': fingerprint.get('user_agent', f'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{major_version}.0.0.0 Safari/537.36'),
    }

    if referer:
        headers['Referer'] = referer

    return headers

def build_extra_fp(fingerprint):
    """curl-cffi extra_fp 생성"""
    extra_fp = {
        'tls_grease': True,
        'tls_permute_extensions': False,
        'tls_cert_compression': 'brotli',
    }

    # signature_algorithms 추출
    if 'tls' in fingerprint and 'extensions' in fingerprint['tls']:
        for ext in fingerprint['tls']['extensions']:
            if ext.get('name') == 'signature_algorithms':
                sig_algs = ext.get('data', {}).get('supported_signature_algorithms', [])
                if sig_algs:
                    extra_fp['tls_signature_algorithms'] = [s['name'] for s in sig_algs]
                break

    return extra_fp

def simulate_click(product_url, search_url, cookies, fingerprint, proxy=None):
    """
    상품 클릭 시뮬레이션

    Args:
        product_url: 상품 페이지 URL (full URL)
        search_url: 검색 결과 페이지 URL (Referer로 사용)
        cookies: 쿠키 딕셔너리
        fingerprint: TLS 프로파일
        proxy: 프록시 URL (optional)

    Returns:
        dict: 결과 정보
    """
    headers = build_headers(fingerprint, referer=search_url)
    extra_fp = build_extra_fp(fingerprint)

    ja3 = fingerprint.get('ja3_text', '')
    akamai = fingerprint.get('akamai_text', '')

    try:
        response = requests.get(
            product_url,
            headers=headers,
            cookies=cookies,
            ja3=ja3,
            akamai=akamai,
            extra_fp=extra_fp,
            proxy=proxy,
            timeout=30,
            allow_redirects=True
        )

        size = len(response.content)

        # 성공 판정
        if response.status_code == 200 and size > 50000:
            return {
                'success': True,
                'status': response.status_code,
                'size': size,
                'url': response.url
            }
        elif response.status_code == 403:
            return {
                'success': False,
                'status': 403,
                'size': size,
                'error': 'BLOCKED_403'
            }
        else:
            return {
                'success': False,
                'status': response.status_code,
                'size': size,
                'error': f'INVALID_RESPONSE_{size}B'
            }

    except Exception as e:
        return {
            'success': False,
            'status': None,
            'size': 0,
            'error': str(e)[:100]
        }

def main():
    """테스트 실행"""
    import argparse
    parser = argparse.ArgumentParser(description='상품 클릭 시뮬레이터')
    parser.add_argument('--cookie-id', type=int, help='쿠키 ID (생략 시 최신)')
    args = parser.parse_args()

    print("=" * 70)
    print("상품 클릭 시뮬레이터")
    print("=" * 70)

    # 쿠키 가져오기
    if args.cookie_id:
        cookie_record = get_cookie_by_id(args.cookie_id)
        if not cookie_record:
            print(f"❌ 쿠키 ID {args.cookie_id}를 찾을 수 없습니다")
            return
    else:
        cookie_record = get_latest_cookie()
        if not cookie_record:
            print("❌ 유효한 쿠키가 없습니다")
            return

    print(f"쿠키 ID: {cookie_record['id']}")
    print(f"Chrome: {cookie_record['chrome_version']}")
    # DB에는 host:port만 저장
    db_proxy = cookie_record['proxy_url']
    proxy = f'socks5://{db_proxy}' if db_proxy else None
    print(f"프록시: {proxy}")

    # 핑거프린트 로드
    fingerprint = get_fingerprint(cookie_record['chrome_version'])
    if not fingerprint:
        print("❌ TLS 프로파일을 찾을 수 없습니다")
        return

    print(f"JA3: {fingerprint.get('ja3_hash', 'N/A')[:20]}...")

    # 쿠키 파싱
    cookies = parse_cookies(cookie_record)

    # 테스트 상품 정보
    product_id = '9024146312'
    query = '호박 달빛식혜'

    # URL 생성
    search_url = f"https://www.coupang.com/np/search?q={quote(query)}"
    product_url = f"https://www.coupang.com/vp/products/{product_id}?itemId=26462223016&vendorItemId=93437504341&q={quote(query)}&searchId=test123&sourceType=search&searchRank=5&rank=5"

    print("=" * 70)
    print(f"검색 URL: {search_url}")
    print(f"상품 URL: {product_url[:80]}...")
    print("=" * 70)

    # 클릭 시뮬레이션
    print("\n[1/1] 클릭 시뮬레이션...")

    result = simulate_click(
        product_url=product_url,
        search_url=search_url,
        cookies=cookies,
        fingerprint=fingerprint,
        proxy=proxy
    )

    # 결과 출력
    print("\n" + "=" * 70)
    print("결과")
    print("=" * 70)

    if result['success']:
        print(f"✅ 클릭 성공")
        print(f"   Status: {result['status']}")
        print(f"   Size: {result['size']:,} bytes")
    else:
        print(f"❌ 클릭 실패")
        print(f"   Status: {result['status']}")
        print(f"   Error: {result.get('error')}")
        print(f"   Size: {result['size']:,} bytes")

    return result

if __name__ == '__main__':
    main()
