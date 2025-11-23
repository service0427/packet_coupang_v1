"""
공통 모듈
- 데이터베이스 쿼리
- 쿠키/핑거프린트 로드
- HTTP 요청
- 유틸리티
"""

import json
import time
import string
from datetime import datetime
from curl_cffi import requests
from db import execute_query

# 개발용 프록시 설정
DEV_PROXY = {
    'host': '112.161.54.7',
    'port': '10018',
    'toggle_port': '18',
    'url': '112.161.54.7:10018',
    'socks5': 'socks5://112.161.54.7:10018'
}


def toggle_dev_proxy():
    """개발용 프록시 IP 토글

    Returns:
        dict: {'success': bool, 'ip': str, 'step': int} 또는 에러
    """
    try:
        toggle_url = f"http://{DEV_PROXY['host']}/toggle/{DEV_PROXY['toggle_port']}"
        resp = requests.get(toggle_url, timeout=40)
        return resp.json()
    except Exception as e:
        return {'success': False, 'error': str(e)}


def get_dev_proxy_ip():
    """개발용 프록시 현재 IP 조회

    Returns:
        str: 현재 외부 IP 또는 None
    """
    try:
        resp = requests.get(
            'https://api.ipify.org?format=json',
            proxy=DEV_PROXY['socks5'],
            timeout=10
        )
        return resp.json().get('ip')
    except:
        return None


def timestamp():
    """타임스탬프 (H:M:S.밀리초3자리)"""
    now = datetime.now()
    return now.strftime('%H:%M:%S') + f'.{now.microsecond // 1000:03d}'


def generate_traceid():
    """Coupang traceId 생성 (timestamp 기반 base36)

    Returns:
        str: 8자리 traceId (예: 'mha2ebbm')
    """
    timestamp_ms = int(time.time() * 1000)
    base36_chars = string.digits + string.ascii_lowercase

    result = []
    ts = timestamp_ms
    while ts > 0:
        result.append(base36_chars[ts % 36])
        ts //= 36

    return ''.join(reversed(result))


def update_cookie_stats(cookie_id, success):
    """쿠키 사용 통계 업데이트

    Args:
        cookie_id: 쿠키 ID
        success: 성공 여부 (True/False)
    """
    if success:
        execute_query("""
            UPDATE cookies
            SET use_count = use_count + 1,
                success_count = success_count + 1,
                last_used_at = NOW()
            WHERE id = %s
        """, (cookie_id,))
    else:
        execute_query("""
            UPDATE cookies
            SET use_count = use_count + 1,
                fail_count = fail_count + 1,
                last_used_at = NOW()
            WHERE id = %s
        """, (cookie_id,))


def update_cookie_data(cookie_id, response_cookies_full):
    """쿠키 데이터 업데이트 (응답 쿠키 반영 - 전체 속성 포함)

    Args:
        cookie_id: 쿠키 ID
        response_cookies_full: 응답에서 받은 쿠키 리스트 [{name, value, domain, path, expires, ...}]

    Returns:
        int: 업데이트된 쿠키 개수
    """
    if not response_cookies_full:
        return 0

    # 기존 cookie_data 조회
    cookie_record = get_cookie_by_id(cookie_id)
    if not cookie_record:
        return 0

    cookie_data = json.loads(cookie_record['cookie_data'])
    updated_count = 0

    # 응답 쿠키를 name으로 인덱싱 (최신 값 우선)
    response_by_name = {}
    for resp_cookie in response_cookies_full:
        name = resp_cookie.get('name')
        if name:
            response_by_name[name] = resp_cookie

    # 기존 쿠키 배열에서 값 + 속성 업데이트
    for cookie in cookie_data:
        name = cookie.get('name')
        if name in response_by_name:
            resp_cookie = response_by_name[name]
            updated = False

            # value 업데이트
            if cookie.get('value', '') != resp_cookie.get('value', ''):
                cookie['value'] = resp_cookie['value']
                updated = True

            # expires 업데이트
            if 'expires' in resp_cookie:
                cookie['expires'] = resp_cookie['expires']
                updated = True

            # domain, path도 업데이트 (응답에 있으면)
            if resp_cookie.get('domain'):
                cookie['domain'] = resp_cookie['domain']
            if resp_cookie.get('path'):
                cookie['path'] = resp_cookie['path']

            if updated:
                updated_count += 1

    # 새로운 쿠키 추가 (기존에 없던 것)
    existing_names = {c.get('name') for c in cookie_data}
    for name, resp_cookie in response_by_name.items():
        if name not in existing_names:
            # 새 쿠키는 전체 속성으로 추가
            new_cookie = {
                'name': name,
                'value': resp_cookie.get('value', ''),
                'domain': resp_cookie.get('domain', '.coupang.com'),
                'path': resp_cookie.get('path', '/')
            }
            if 'expires' in resp_cookie:
                new_cookie['expires'] = resp_cookie['expires']
            cookie_data.append(new_cookie)
            updated_count += 1

    # DB 업데이트
    if updated_count > 0:
        execute_query("""
            UPDATE cookies
            SET cookie_data = %s
            WHERE id = %s
        """, (json.dumps(cookie_data), cookie_id))

    return updated_count


def get_cookie_by_id(cookie_id):
    """쿠키 ID로 쿠키 레코드 조회"""
    cookies = execute_query("SELECT * FROM cookies WHERE id = %s", (cookie_id,))
    return cookies[0] if cookies else None


def get_latest_cookie():
    """유효한 쿠키 랜덤 조회 (120초 이내, use_count < 10, success >= fail)"""
    cookies = execute_query("""
        SELECT * FROM cookies
        WHERE created_at >= NOW() - INTERVAL 300 SECOND
          AND use_count < 10
          AND success_count >= fail_count
        ORDER BY RAND()
        LIMIT 1
    """)
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
