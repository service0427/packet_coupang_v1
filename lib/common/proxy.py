"""
프록시 및 쿠키 바인딩 모듈
- 프록시 API 조회
- /24 서브넷 기반 쿠키 매칭
- IP 바인딩 검증
"""

import json
import random
from curl_cffi import requests
from .db import execute_query

# 프록시 API 설정
PROXY_API_URL = 'http://mkt.techb.kr:3001/api/proxy/status'


def get_proxy_list(min_remain=30):
    """프록시 API에서 사용 가능한 프록시 목록 조회

    Args:
        min_remain: 최소 남은 시간 (초)

    Returns:
        list: [{'proxy': 'host:port', 'external_ip': '...', 'remaining_work_seconds': '...'}, ...]
    """
    try:
        resp = requests.get(f'{PROXY_API_URL}?remain={min_remain}', timeout=10)
        data = resp.json()
        if data.get('success'):
            return data.get('proxies', [])
    except Exception as e:
        print(f"프록시 API 오류: {e}")
    return []


def get_subnet(ip):
    """IP에서 /24 서브넷 추출

    Args:
        ip: IP 주소 (예: '192.168.1.100')

    Returns:
        str: 서브넷 (예: '192.168.1') 또는 None
    """
    if not ip:
        return None
    parts = ip.split('.')
    if len(parts) == 4:
        return '.'.join(parts[:3])
    return None


def check_external_ip(proxy_url):
    """프록시를 통한 외부 IP 확인

    Args:
        proxy_url: socks5://host:port 형식

    Returns:
        str: 외부 IP 또는 None
    """
    try:
        resp = requests.get(
            'https://api.ipify.org?format=json',
            proxy=proxy_url,
            timeout=10,
            verify=False
        )
        return resp.json().get('ip')
    except:
        return None


def get_cookies_by_subnet(subnet, max_age_minutes=60, valid_only=True, max_fail_count=2):
    """서브넷으로 쿠키 조회

    Args:
        subnet: /24 서브넷 (예: '192.168.1')
        max_age_minutes: 최대 쿠키 나이 (분)
        valid_only: True면 init_status='valid'만
        max_fail_count: 최대 허용 실패 횟수 (기본: 2, 3회 이상 실패면 제외)

    Returns:
        list: 쿠키 레코드 리스트
    """
    if valid_only:
        cookies = execute_query("""
            SELECT id, proxy_ip, proxy_url, chrome_version, cookie_data, init_status,
                   fail_count, success_count,
                   TIMESTAMPDIFF(MINUTE, created_at, NOW()) as age_minutes
            FROM cookies
            WHERE proxy_ip LIKE %s
              AND created_at >= NOW() - INTERVAL %s MINUTE
              AND init_status = 'valid'
              AND fail_count <= %s
            ORDER BY fail_count ASC, created_at DESC
            LIMIT 5
        """, (f"{subnet}.%", max_age_minutes, max_fail_count))
    else:
        cookies = execute_query("""
            SELECT id, proxy_ip, proxy_url, chrome_version, cookie_data, init_status,
                   fail_count, success_count,
                   TIMESTAMPDIFF(MINUTE, created_at, NOW()) as age_minutes
            FROM cookies
            WHERE proxy_ip LIKE %s
              AND created_at >= NOW() - INTERVAL %s MINUTE
              AND fail_count <= %s
            ORDER BY fail_count ASC, created_at DESC
            LIMIT 5
        """, (f"{subnet}.%", max_age_minutes, max_fail_count))

    return cookies if cookies else []


def get_cookie_by_id(cookie_id):
    """쿠키 ID로 쿠키 레코드 조회"""
    cookies = execute_query("SELECT * FROM cookies WHERE id = %s", (cookie_id,))
    return cookies[0] if cookies else None


def parse_cookie_data(cookie_record):
    """쿠키 레코드에서 쿠키 딕셔너리 추출

    Args:
        cookie_record: DB 쿠키 레코드

    Returns:
        dict: {name: value} 형식 쿠키
    """
    cookie_data = json.loads(cookie_record['cookie_data'])
    cookies = {}
    for c in cookie_data:
        if c.get('domain', '').endswith('coupang.com'):
            cookies[c['name']] = c['value']
    return cookies


def get_bound_cookie(min_remain=30, max_age_minutes=60):
    """IP 바인딩된 프록시 + 쿠키 조합 반환

    핵심 알고리즘:
    1. 사용 가능한 프록시 랜덤 선택
    2. /24 서브넷으로 매칭되는 쿠키 랜덤 선택

    Args:
        min_remain: 프록시 최소 남은 시간 (초)
        max_age_minutes: 쿠키 최대 나이 (분)

    Returns:
        dict: {
            'proxy': 'socks5://host:port',
            'proxy_host': 'host:port',
            'external_ip': '...',
            'cookie_record': {...},
            'cookies': {name: value},
            'match_type': 'exact' | 'subnet'
        } 또는 None
    """
    proxies = get_proxy_list(min_remain)
    if not proxies:
        return None

    # 프록시 목록 섞기
    random.shuffle(proxies)

    for proxy_info in proxies:
        external_ip = proxy_info.get('external_ip')
        subnet = get_subnet(external_ip)

        if not subnet:
            continue

        cookies = get_cookies_by_subnet(subnet, max_age_minutes)
        if not cookies:
            continue

        # 첫 번째 쿠키 선택 (이미 랜덤 정렬됨)
        cookie_record = cookies[0]
        match_type = 'exact' if cookie_record['proxy_ip'] == external_ip else 'subnet'

        return {
            'proxy': f"socks5://{proxy_info['proxy']}",
            'proxy_host': proxy_info['proxy'],
            'external_ip': external_ip,
            'cookie_record': cookie_record,
            'cookies': parse_cookie_data(cookie_record),
            'match_type': match_type
        }

    return None


def update_cookie_stats(cookie_id, success):
    """쿠키 사용 통계 업데이트

    Args:
        cookie_id: 쿠키 ID
        success: 성공 여부
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
    """쿠키 데이터 업데이트 (응답 쿠키 반영)

    Args:
        cookie_id: 쿠키 ID
        response_cookies_full: 응답에서 받은 쿠키 리스트 [{name, value, domain, path, expires, ...}]

    Returns:
        int: 업데이트된 쿠키 개수
    """
    if not response_cookies_full:
        return 0

    cookie_record = get_cookie_by_id(cookie_id)
    if not cookie_record:
        return 0

    cookie_data = json.loads(cookie_record['cookie_data'])
    updated_count = 0

    # 응답 쿠키를 name으로 인덱싱
    response_by_name = {c.get('name'): c for c in response_cookies_full if c.get('name')}

    # 기존 쿠키 업데이트
    for cookie in cookie_data:
        name = cookie.get('name')
        if name in response_by_name:
            resp_cookie = response_by_name[name]

            if cookie.get('value', '') != resp_cookie.get('value', ''):
                cookie['value'] = resp_cookie['value']
                updated_count += 1

            if 'expires' in resp_cookie:
                cookie['expires'] = resp_cookie['expires']

            if resp_cookie.get('domain'):
                cookie['domain'] = resp_cookie['domain']
            if resp_cookie.get('path'):
                cookie['path'] = resp_cookie['path']

    # 새 쿠키 추가
    existing_names = {c.get('name') for c in cookie_data}
    for name, resp_cookie in response_by_name.items():
        if name not in existing_names:
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
            SET cookie_data = %s, last_used_at = NOW()
            WHERE id = %s
        """, (json.dumps(cookie_data), cookie_id))

    return updated_count


if __name__ == '__main__':
    print("프록시/쿠키 바인딩 모듈 테스트")
    print("=" * 60)

    # 프록시 목록
    proxies = get_proxy_list(min_remain=30)
    print(f"\n사용 가능한 프록시: {len(proxies)}개")
    for p in proxies[:3]:
        print(f"  {p['proxy']} → {p['external_ip']}")

    # IP 바인딩 테스트
    print(f"\nIP 바인딩 쿠키 조회...")
    bound = get_bound_cookie(min_remain=30, max_age_minutes=60)
    if bound:
        print(f"  ✅ 매칭 성공 ({bound['match_type']})")
        print(f"     프록시: {bound['proxy_host']}")
        print(f"     외부 IP: {bound['external_ip']}")
        print(f"     쿠키 ID: {bound['cookie_record']['id']}")
        print(f"     쿠키 IP: {bound['cookie_record']['proxy_ip']}")
    else:
        print("  ❌ 매칭 실패")
