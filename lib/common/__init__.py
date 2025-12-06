"""
공통 유틸리티 모듈

- db: 데이터베이스 연결
- fingerprint: TLS 핑거프린트 관리
- proxy: 프록시 API + 쿠키 바인딩
- cookie: 쿠키 조회/관리
"""

from .db import get_cursor, execute_query, insert_one
from .fingerprint import get_fingerprint_by_version, get_random_fingerprint
from .proxy import get_proxy_list, get_bound_cookie
from .cookie import (
    COOKIE_MAX_AGE_MINUTES, COOKIE_MIN_AGE_MINUTES, COOKIE_REUSE_COOLDOWN_SECONDS, COOKIE_MAX_FAIL_COUNT,
    get_subnet, get_cookies_by_subnet, get_cookies_by_ip, get_cookie_by_id,
    parse_cookie_data, lock_cookie, unlock_cookie,
    update_cookie_stats, update_cookie_data
)
from .ip_tracker import (
    record_failure, record_success, is_blocked, is_ip_blocked, is_subnet_blocked,
    get_blocked_ips, get_blocked_subnets, get_status as get_ip_tracker_status,
    clear_all as clear_ip_tracker, MAX_CONSECUTIVE_FAILURES, BLOCK_DURATION_MINUTES
)
from .log import save_work_log, get_recent_logs, get_log_stats

__all__ = [
    # db
    'get_cursor', 'execute_query', 'insert_one',
    # fingerprint
    'get_fingerprint_by_version', 'get_random_fingerprint',
    # proxy
    'get_proxy_list', 'get_bound_cookie',
    # cookie
    'COOKIE_MAX_AGE_MINUTES', 'COOKIE_MIN_AGE_MINUTES', 'COOKIE_REUSE_COOLDOWN_SECONDS', 'COOKIE_MAX_FAIL_COUNT',
    'get_subnet', 'get_cookies_by_subnet', 'get_cookies_by_ip', 'get_cookie_by_id',
    'parse_cookie_data', 'lock_cookie', 'unlock_cookie',
    'update_cookie_stats', 'update_cookie_data',
    # ip_tracker
    'record_failure', 'record_success', 'is_blocked', 'is_ip_blocked', 'is_subnet_blocked',
    'get_blocked_ips', 'get_blocked_subnets', 'get_ip_tracker_status', 'clear_ip_tracker',
    'MAX_CONSECUTIVE_FAILURES', 'BLOCK_DURATION_MINUTES',
    # log
    'save_work_log', 'get_recent_logs', 'get_log_stats',
]
