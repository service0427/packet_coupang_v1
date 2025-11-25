"""
HTTP 요청 모듈 - curl-cffi

Custom TLS 방식 전용 (impersonate 미사용)
"""

import time
import string
from datetime import datetime
from http.cookies import SimpleCookie
from curl_cffi import requests

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from common.fingerprint import build_extra_fp, build_headers


def timestamp():
    """타임스탬프 (H:M:S.밀리초3자리)"""
    now = datetime.now()
    return now.strftime('%H:%M:%S') + f'.{now.microsecond // 1000:03d}'


def generate_trace_id():
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


def make_request(url, cookies, fingerprint, proxy, referer=None, timeout=30):
    """HTTP GET 요청 (Custom TLS)

    Args:
        url: 요청 URL
        cookies: 쿠키 딕셔너리 {name: value}
        fingerprint: DB 핑거프린트 레코드
        proxy: 프록시 URL (socks5://host:port)
        referer: Referer 헤더
        timeout: 타임아웃 (초)

    Returns:
        Response 객체
    """
    headers = build_headers(fingerprint, referer)

    # Custom TLS 방식 (DB 프로파일 사용)
    ja3_text = fingerprint['ja3_text']
    akamai_text = fingerprint['akamai_text']
    extra_fp = build_extra_fp(fingerprint)

    return requests.get(
        url,
        headers=headers,
        cookies=cookies,
        ja3=ja3_text,
        akamai=akamai_text,
        extra_fp=extra_fp,
        proxy=proxy,
        timeout=timeout,
        verify=False
    )


def parse_set_cookie_header(set_cookie_str):
    """Set-Cookie 헤더 파싱

    Args:
        set_cookie_str: Set-Cookie 헤더 값

    Returns:
        dict: {name, value, domain, path, expires, ...}
    """
    cookie = SimpleCookie()
    try:
        cookie.load(set_cookie_str)
        for name, morsel in cookie.items():
            result = {
                'name': name,
                'value': morsel.value,
                'domain': morsel.get('domain', '.coupang.com'),
                'path': morsel.get('path', '/'),
            }
            if morsel.get('expires'):
                result['expires'] = morsel.get('expires')
            if morsel.get('max-age'):
                try:
                    max_age = int(morsel.get('max-age'))
                    result['expires'] = time.time() + max_age
                except:
                    pass
            return result
    except:
        pass
    return None


def parse_response_cookies(resp):
    """응답에서 쿠키 파싱

    Args:
        resp: curl_cffi 응답 객체

    Returns:
        tuple: (cookies_dict, cookies_full_list)
            - cookies_dict: {name: value}
            - cookies_full_list: [{name, value, domain, path, expires, ...}]
    """
    cookies_list = []

    if hasattr(resp, 'headers'):
        set_cookies = resp.headers.get_list('set-cookie') if hasattr(resp.headers, 'get_list') else []

        if not set_cookies:
            set_cookie = resp.headers.get('set-cookie', '')
            if set_cookie:
                set_cookies = [set_cookie]

        for sc in set_cookies:
            parsed = parse_set_cookie_header(sc)
            if parsed:
                cookies_list.append(parsed)

    cookies_dict = {c['name']: c['value'] for c in cookies_list}
    return cookies_dict, cookies_list


if __name__ == '__main__':
    print("HTTP 요청 모듈 테스트")
    print("=" * 60)
    print(f"Timestamp: {timestamp()}")
    print(f"TraceId: {generate_trace_id()}")
