"""
쿠키 유틸리티 모듈
- IP 서브넷 추출
- 쿠키 데이터 파싱

Note: DB 의존성 없음, 순수 유틸리티 함수만 제공
"""

import json


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


def parse_cookie_data(cookie_record):
    """쿠키 레코드에서 쿠키 딕셔너리 추출

    Args:
        cookie_record: API 응답 (5151 API)

    Returns:
        dict: {name: value} 형식 쿠키
    """
    # API (5151): cookies 배열 직접 포함
    if 'cookies' in cookie_record and isinstance(cookie_record['cookies'], list):
        cookie_data = cookie_record['cookies']
    # 레거시: cookie_data 필드 (JSON 문자열)
    elif 'cookie_data' in cookie_record:
        cookie_data = json.loads(cookie_record['cookie_data'])
    else:
        return {}

    cookies = {}
    for c in cookie_data:
        if c.get('domain', '').endswith('coupang.com'):
            cookies[c['name']] = c['value']
    return cookies
