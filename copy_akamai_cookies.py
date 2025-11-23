#!/usr/bin/env python3
"""
Akamai 쿠키 복사 스크립트
- 소스 쿠키(518)에서 Akamai 관련 쿠키만 추출
- 타겟 쿠키들(300~516)에 업데이트
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'lib'))

from db import execute_query

# Akamai 관련 쿠키 목록
AKAMAI_COOKIES = [
    '_abck',      # Akamai Bot Manager
    'ak_bmsc',    # Akamai Bot Manager Session Cookie
    'bm_mi',      # Bot Manager
    'bm_s',       # Bot Manager Session
    'bm_so',      # Bot Manager
    'bm_sv',      # Bot Manager Session Verify
    'bm_sz',      # Bot Manager Size
]


def get_cookie_data(cookie_id):
    """쿠키 데이터 조회"""
    result = execute_query("SELECT cookie_data FROM cookies WHERE id = %s", (cookie_id,))
    if result:
        return json.loads(result[0]['cookie_data'])
    return None


def extract_akamai_cookies(cookie_data):
    """Akamai 쿠키만 추출"""
    akamai = {}
    for cookie in cookie_data:
        name = cookie.get('name')
        if name in AKAMAI_COOKIES:
            akamai[name] = cookie
    return akamai


def update_cookie_with_akamai(cookie_id, akamai_cookies):
    """타겟 쿠키에 Akamai 쿠키 업데이트"""
    cookie_data = get_cookie_data(cookie_id)
    if not cookie_data:
        return False, "쿠키 없음"

    updated_count = 0

    # 기존 쿠키에서 Akamai 쿠키 업데이트
    for cookie in cookie_data:
        name = cookie.get('name')
        if name in akamai_cookies:
            source = akamai_cookies[name]
            cookie['value'] = source['value']
            if 'expires' in source:
                cookie['expires'] = source['expires']
            updated_count += 1

    # 기존에 없던 Akamai 쿠키 추가
    existing_names = {c.get('name') for c in cookie_data}
    for name, source in akamai_cookies.items():
        if name not in existing_names:
            cookie_data.append(source.copy())
            updated_count += 1

    # DB 업데이트
    execute_query("""
        UPDATE cookies
        SET cookie_data = %s
        WHERE id = %s
    """, (json.dumps(cookie_data), cookie_id))

    return True, updated_count


def main():
    source_id = 518
    start_id = 300
    end_id = 516

    print("=" * 60)
    print("Akamai 쿠키 복사")
    print("=" * 60)
    print(f"소스: {source_id}")
    print(f"타겟: {start_id} ~ {end_id}")
    print("=" * 60)

    # 소스 쿠키에서 Akamai 쿠키 추출
    source_data = get_cookie_data(source_id)
    if not source_data:
        print(f"❌ 소스 쿠키 {source_id} 없음")
        return

    akamai_cookies = extract_akamai_cookies(source_data)
    print(f"\n소스 Akamai 쿠키: {list(akamai_cookies.keys())}")

    if not akamai_cookies:
        print("❌ Akamai 쿠키 없음")
        return

    # 타겟 쿠키들 업데이트
    print(f"\n업데이트 중...")

    success_count = 0
    fail_count = 0
    skip_count = 0

    for cookie_id in range(start_id, end_id + 1):
        success, result = update_cookie_with_akamai(cookie_id, akamai_cookies)
        if success:
            if result > 0:
                success_count += 1
            else:
                skip_count += 1
        else:
            fail_count += 1

    print(f"\n{'=' * 60}")
    print("결과")
    print(f"{'=' * 60}")
    print(f"성공: {success_count}")
    print(f"건너뜀: {skip_count}")
    print(f"실패: {fail_count}")
    print(f"총: {end_id - start_id + 1}")


if __name__ == '__main__':
    main()
