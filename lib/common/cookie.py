"""
쿠키 관리 모듈
- /24 서브넷 기반 쿠키 조회
- 쿠키 잠금/해제 (동시 사용 방지)
- 쿠키 통계 업데이트
- 쿠키 데이터 파싱 및 갱신
"""

import json
from .db import execute_query

# 쿠키 수명 설정 (분) - created_at 기준
# 분석 결과: 60분+ 쿠키 100% 차단, 0-60분만 성공 (19.7%)
COOKIE_MAX_AGE_MINUTES = 10   # 최대 나이 (분) - 60분 미만만 사용
COOKIE_MIN_AGE_MINUTES = 0    # 최소 나이 (분) - 신선한 쿠키부터

# 쿠키 재사용 쿨다운 (초)
# - last_success_at 이후 이 시간 동안은 재사용하지 않음
# - 쿠키 풀 다양성 확보 및 중복 호출 방지
COOKIE_REUSE_COOLDOWN_SECONDS = 5

# 쿠키 최대 실패 횟수
# - 이 횟수 초과 시 쿠키 제외 (fail_count <= MAX_FAIL_COUNT)
# - 예: 2 = 3회 이상 실패한 쿠키 제외
COOKIE_MAX_FAIL_COUNT = 99


def get_subnet(ip):
    """/24 서브넷 추출

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


def get_cookies_by_subnet(subnet, max_age_minutes=COOKIE_MAX_AGE_MINUTES, max_fail_count=COOKIE_MAX_FAIL_COUNT,
                          lock_timeout_minutes=5, reuse_cooldown_seconds=COOKIE_REUSE_COOLDOWN_SECONDS,
                          source=None):
    """서브넷으로 쿠키 조회 (잠금된 쿠키 제외)

    Args:
        subnet: /24 서브넷 (예: '192.168.1')
        max_age_minutes: 최대 쿠키 나이 (분) - last_success_at 기준, 없으면 created_at 기준
        max_fail_count: 최대 허용 실패 횟수 (기본: 2, 3회 이상 실패면 제외)
        lock_timeout_minutes: 잠금 타임아웃 (분) - 이 시간이 지나면 잠금 무시
        reuse_cooldown_seconds: 재사용 쿨다운 (초) - last_success_at 이후 이 시간 동안 재사용 방지
        source: 쿠키 소스 필터 (예: 'local', 's23+', 'mobile') - None이면 모든 소스

    Returns:
        list: 쿠키 레코드 리스트
    """
    source_condition = "AND source = %s" if source else ""
    params = [f"{subnet}.%", max_age_minutes, max_fail_count, lock_timeout_minutes, reuse_cooldown_seconds]
    if source:
        params.append(source)

    cookies = execute_query(f"""
        SELECT id, proxy_ip, proxy_url, chrome_version, cookie_data, init_status, source,
               fail_count, success_count,
               TIMESTAMPDIFF(MINUTE, COALESCE(last_success_at, created_at), NOW()) as age_minutes,
               TIMESTAMPDIFF(SECOND, created_at, NOW()) as created_age_seconds,
               TIMESTAMPDIFF(SECOND, last_success_at, NOW()) as last_success_age_seconds
        FROM cookies
        WHERE proxy_ip LIKE %s
          AND COALESCE(last_success_at, created_at) >= NOW() - INTERVAL %s MINUTE
          AND fail_count <= %s
          AND (locked_at IS NULL OR locked_at < NOW() - INTERVAL %s MINUTE)
          AND init_status != 'expired'
          AND (last_success_at IS NULL OR last_success_at < NOW() - INTERVAL %s SECOND)
          {source_condition}
        ORDER BY RAND()
        LIMIT 5
    """, tuple(params))

    return cookies if cookies else []


def get_any_cookie(max_age_minutes=COOKIE_MAX_AGE_MINUTES, max_fail_count=COOKIE_MAX_FAIL_COUNT,
                   source=None):
    """아무 쿠키나 랜덤 조회 (IP 바인딩 없이, 잠금 무시)

    Args:
        max_age_minutes: 최대 쿠키 나이 (분)
        max_fail_count: 최대 허용 실패 횟수
        source: 쿠키 소스 필터 - None이면 모든 소스

    Returns:
        dict: 쿠키 레코드 또는 None
    """
    source_condition = "AND source = %s" if source else ""
    params = [max_age_minutes, max_fail_count]
    if source:
        params.append(source)

    cookies = execute_query(f"""
        SELECT id, proxy_ip, proxy_url, chrome_version, cookie_data, init_status, source,
               fail_count, success_count,
               TIMESTAMPDIFF(MINUTE, COALESCE(last_success_at, created_at), NOW()) as age_minutes,
               TIMESTAMPDIFF(SECOND, created_at, NOW()) as created_age_seconds,
               TIMESTAMPDIFF(SECOND, last_success_at, NOW()) as last_success_age_seconds
        FROM cookies
        WHERE COALESCE(last_success_at, created_at) >= NOW() - INTERVAL %s MINUTE
          AND fail_count <= %s
          AND init_status != 'expired'
          {source_condition}
        ORDER BY RAND()
        LIMIT 1
    """, tuple(params))

    return cookies[0] if cookies else None


def get_cookies_by_ip(external_ip, max_age_minutes=COOKIE_MAX_AGE_MINUTES, min_age_minutes=COOKIE_MIN_AGE_MINUTES,
                      max_fail_count=COOKIE_MAX_FAIL_COUNT, lock_timeout_minutes=5,
                      min_chrome_version=121, reuse_cooldown_seconds=COOKIE_REUSE_COOLDOWN_SECONDS):
    """IP로 쿠키 조회 (완전 매칭 우선, 서브넷 매칭 차순위)

    Args:
        external_ip: 외부 IP 주소 (예: '110.70.27.39')
        max_age_minutes: 최대 쿠키 나이 (분) - created_at 기준
        min_age_minutes: 최소 쿠키 나이 (분) - created_at 기준 (테스트: 60분 이상만)
        max_fail_count: 최대 허용 실패 횟수
        lock_timeout_minutes: 잠금 타임아웃 (분)
        min_chrome_version: 최소 Chrome 버전 (131+ 필수, CLAUDE.md 참고)
        reuse_cooldown_seconds: 재사용 쿨다운 (초) - last_success_at 이후 이 시간 동안 재사용 방지

    Returns:
        dict: {'cookie': 쿠키 레코드, 'match_type': 'exact'|'subnet'} 또는 None
    """
    # created_at 기준: min_age_minutes ~ max_age_minutes 범위
    base_conditions = """
        created_at >= NOW() - INTERVAL %s MINUTE
        AND created_at <= NOW() - INTERVAL %s MINUTE
        AND fail_count <= %s
        AND (locked_at IS NULL OR locked_at < NOW() - INTERVAL %s MINUTE)
        AND init_status != 'expired'
        AND CAST(SUBSTRING_INDEX(chrome_version, '.', 1) AS UNSIGNED) >= %s
        AND (last_success_at IS NULL OR last_success_at < NOW() - INTERVAL %s SECOND)
    """

    base_params = (max_age_minutes, min_age_minutes, max_fail_count, lock_timeout_minutes, min_chrome_version, reuse_cooldown_seconds)

    # 1순위: 완전 매칭 (proxy_ip = external_ip)
    exact_cookies = execute_query(f"""
        SELECT id, proxy_ip, proxy_url, chrome_version, cookie_data, init_status, source,
               fail_count, success_count,
               TIMESTAMPDIFF(MINUTE, COALESCE(last_success_at, created_at), NOW()) as age_minutes,
               TIMESTAMPDIFF(SECOND, created_at, NOW()) as created_age_seconds,
               TIMESTAMPDIFF(SECOND, last_success_at, NOW()) as last_success_age_seconds
        FROM cookies
        WHERE proxy_ip = %s
          AND {base_conditions}
        ORDER BY RAND()
        LIMIT 1
    """, (external_ip,) + base_params)

    if exact_cookies:
        return {'cookie': exact_cookies[0], 'match_type': 'exact'}

    # 2순위: 서브넷 매칭 (proxy_ip LIKE 'subnet.%')
    subnet = get_subnet(external_ip)
    if not subnet:
        return None

    subnet_cookies = execute_query(f"""
        SELECT id, proxy_ip, proxy_url, chrome_version, cookie_data, init_status, source,
               fail_count, success_count,
               TIMESTAMPDIFF(MINUTE, COALESCE(last_success_at, created_at), NOW()) as age_minutes,
               TIMESTAMPDIFF(SECOND, created_at, NOW()) as created_age_seconds,
               TIMESTAMPDIFF(SECOND, last_success_at, NOW()) as last_success_age_seconds
        FROM cookies
        WHERE proxy_ip LIKE %s
          AND proxy_ip != %s
          AND {base_conditions}
        ORDER BY RAND()
        LIMIT 1
    """, (f"{subnet}.%", external_ip) + base_params)

    if subnet_cookies:
        return {'cookie': subnet_cookies[0], 'match_type': 'subnet'}

    return None


def get_cookie_by_id(cookie_id):
    """쿠키 ID로 쿠키 레코드 조회"""
    cookies = execute_query("SELECT * FROM cookies WHERE id = %s", (cookie_id,))
    return cookies[0] if cookies else None


def parse_cookie_data(cookie_record):
    """쿠키 레코드에서 쿠키 딕셔너리 추출

    Args:
        cookie_record: DB 쿠키 레코드 또는 API 응답

    Returns:
        dict: {name: value} 형식 쿠키
    """
    # 새 API (5151): cookies 배열 직접 포함
    if 'cookies' in cookie_record and isinstance(cookie_record['cookies'], list):
        cookie_data = cookie_record['cookies']
    # 기존 DB: cookie_data 필드 (JSON 문자열)
    elif 'cookie_data' in cookie_record:
        cookie_data = json.loads(cookie_record['cookie_data'])
    else:
        return {}

    cookies = {}
    for c in cookie_data:
        if c.get('domain', '').endswith('coupang.com'):
            cookies[c['name']] = c['value']
    return cookies


def lock_cookie(cookie_id):
    """쿠키 잠금 (작업 할당 시)

    Args:
        cookie_id: 쿠키 ID
    """
    execute_query("""
        UPDATE cookies
        SET locked_at = NOW()
        WHERE id = %s
    """, (cookie_id,))


def unlock_cookie(cookie_id):
    """쿠키 잠금 해제 (작업 완료 시)

    Args:
        cookie_id: 쿠키 ID
    """
    execute_query("""
        UPDATE cookies
        SET locked_at = NULL
        WHERE id = %s
    """, (cookie_id,))


def update_cookie_stats(cookie_id, success):
    """쿠키 사용 통계 업데이트 및 잠금 해제

    Args:
        cookie_id: 쿠키 ID
        success: 성공 여부
    """
    if success:
        execute_query("""
            UPDATE cookies
            SET use_count = use_count + 1,
                success_count = success_count + 1,
                last_success_at = NOW(),
                locked_at = NULL
            WHERE id = %s
        """, (cookie_id,))
    else:
        execute_query("""
            UPDATE cookies
            SET use_count = use_count + 1,
                fail_count = fail_count + 1,
                last_fail_at = NOW(),
                locked_at = NULL
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
            SET cookie_data = %s, last_success_at = NOW()
            WHERE id = %s
        """, (json.dumps(cookie_data), cookie_id))

    return updated_count
