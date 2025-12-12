"""
공통 유틸리티 모듈

- fingerprint: TLS 핑거프린트 관리 (JSON 기반)
- proxy: 프록시 API + 쿠키 바인딩
- cookie: 쿠키 유틸리티

Note: DB 의존성 없음
"""

from .fingerprint import (
    get_tls_profile,
    build_tls_extra_fp,
    build_tls_headers,
    get_tls_platform_for_match_type,
    list_tls_profiles
)
from .proxy import get_proxy_list, get_bound_cookie, report_cookie_result
from .cookie import get_subnet, parse_cookie_data

__all__ = [
    # fingerprint
    'get_tls_profile', 'build_tls_extra_fp', 'build_tls_headers',
    'get_tls_platform_for_match_type', 'list_tls_profiles',
    # proxy
    'get_proxy_list', 'get_bound_cookie', 'report_cookie_result',
    # cookie
    'get_subnet', 'parse_cookie_data',
]
