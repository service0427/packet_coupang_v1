"""
공통 모듈
- 데이터베이스 쿼리
- 쿠키/핑거프린트 로드
- HTTP 요청
- 유틸리티
"""

import json
from datetime import datetime
from curl_cffi import requests
from db import execute_query


def timestamp():
    """타임스탬프 (H:M:S.밀리초3자리)"""
    now = datetime.now()
    return now.strftime('%H:%M:%S') + f'.{now.microsecond // 1000:03d}'


def get_cookie_by_id(cookie_id):
    """쿠키 ID로 쿠키 레코드 조회"""
    cookies = execute_query("SELECT * FROM cookies WHERE id = %s", (cookie_id,))
    return cookies[0] if cookies else None


def get_latest_cookie():
    """가장 최근 쿠키 조회"""
    cookies = execute_query("SELECT * FROM cookies ORDER BY id DESC LIMIT 1")
    return cookies[0] if cookies else None


def get_fingerprint(chrome_version, platform='u22'):
    """Chrome 버전으로 핑거프린트 조회"""
    fps = execute_query(
        "SELECT * FROM fingerprints WHERE chrome_version = %s AND platform = %s",
        (chrome_version, platform)
    )
    if not fps:
        major = int(chrome_version.split('.')[0])
        fps = execute_query(
            "SELECT * FROM fingerprints WHERE chrome_major = %s AND platform = %s ORDER BY chrome_version DESC LIMIT 1",
            (major, platform)
        )
    return fps[0] if fps else None


def check_proxy_ip(proxy):
    """프록시 외부 IP 확인"""
    if not proxy:
        return None
    try:
        resp = requests.get(
            'https://api.ipify.org?format=json',
            proxy=proxy,
            timeout=10,
            verify=False
        )
        return resp.json().get('ip')
    except:
        return None


def parse_cookies(cookie_record):
    """쿠키 레코드에서 쿠키 딕셔너리 추출"""
    cookie_data = json.loads(cookie_record['cookie_data'])
    cookies = {}
    for c in cookie_data:
        if c.get('domain', '').endswith('coupang.com'):
            cookies[c['name']] = c['value']
    return cookies


def build_extra_fp(fingerprint):
    """extra_fp 딕셔너리 생성"""
    sig_algs = json.loads(fingerprint['signature_algorithms'])
    return {
        'tls_signature_algorithms': sig_algs,
        'tls_grease': True,
        'tls_permute_extensions': False,
        'tls_cert_compression': 'brotli',
    }


def build_headers(fingerprint, referer=None):
    """표준 헤더 생성"""
    major_ver = fingerprint['chrome_major']
    return {
        'User-Agent': fingerprint['user_agent'],
        'sec-ch-ua': f'"Chromium";v="{major_ver}", "Not.A/Brand";v="99"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Linux"',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Referer': referer or 'https://www.coupang.com/',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'same-origin',
    }


def make_request(url, cookies, fingerprint, proxy, referer=None, timeout=30):
    """공통 HTTP 요청 함수"""
    ja3_text = fingerprint['ja3_text']
    akamai_text = fingerprint['akamai_text']
    extra_fp = build_extra_fp(fingerprint)
    headers = build_headers(fingerprint, referer)

    return requests.get(
        url, headers=headers, cookies=cookies,
        ja3=ja3_text, akamai=akamai_text, extra_fp=extra_fp,
        proxy=proxy, timeout=timeout, verify=False
    )


def verify_ip_binding(proxy, expected_ip, verbose=True):
    """IP 바인딩 검증

    Returns:
        tuple: (success: bool, current_ip: str or None, message: str)
    """
    if not proxy:
        return (True, None, "프록시 없음 - 검증 생략")

    current_ip = check_proxy_ip(proxy)

    if not current_ip:
        return (False, None, "프록시 IP 확인 실패")

    if current_ip != expected_ip:
        message = f"IP 불일치 - 현재: {current_ip}, 예상: {expected_ip}"
        return (False, current_ip, message)

    return (True, current_ip, "IP 일치")


if __name__ == '__main__':
    # Test
    print("Testing common module...")
    print(f"Timestamp: {timestamp()}")

    # Test IP check
    ip = check_proxy_ip(None)
    print(f"Direct IP: {ip}")
