"""
IP 연속 실패 추적 모듈

연속 실패가 임계치(기본 5회)에 도달하면 해당 IP를 일시 차단.
성공 시 카운터 리셋.
"""

import threading
from datetime import datetime, timedelta

# 스레드 안전을 위한 락
_lock = threading.Lock()

# IP별 연속 실패 카운터: {ip: {'count': N, 'blocked_at': datetime|None}}
_ip_failures = {}

# 서브넷별 연속 실패 카운터: {subnet: {'count': N, 'blocked_at': datetime|None}}
_subnet_failures = {}

# 설정
MAX_CONSECUTIVE_FAILURES = 5  # 연속 실패 임계치
BLOCK_DURATION_MINUTES = 10   # 차단 지속 시간 (분)


def get_subnet(ip: str) -> str:
    """IP에서 서브넷 추출 (예: 175.223.27.192 -> 175.223.27)"""
    if not ip:
        return ''
    parts = ip.split('.')
    return '.'.join(parts[:3]) if len(parts) >= 3 else ''


def record_failure(ip: str) -> dict:
    """실패 기록. 연속 실패 시 카운터 증가, 임계치 도달 시 차단.

    Returns:
        dict: {'ip_blocked': bool, 'subnet_blocked': bool, 'ip_count': N, 'subnet_count': N}
    """
    if not ip:
        return {'ip_blocked': False, 'subnet_blocked': False, 'ip_count': 0, 'subnet_count': 0}

    subnet = get_subnet(ip)
    now = datetime.now()

    with _lock:
        # IP 카운터 증가
        if ip not in _ip_failures:
            _ip_failures[ip] = {'count': 0, 'blocked_at': None}
        _ip_failures[ip]['count'] += 1
        ip_count = _ip_failures[ip]['count']

        # IP 임계치 도달 시 차단
        ip_blocked = False
        if ip_count >= MAX_CONSECUTIVE_FAILURES and _ip_failures[ip]['blocked_at'] is None:
            _ip_failures[ip]['blocked_at'] = now
            ip_blocked = True

        # 서브넷 카운터 증가
        if subnet not in _subnet_failures:
            _subnet_failures[subnet] = {'count': 0, 'blocked_at': None}
        _subnet_failures[subnet]['count'] += 1
        subnet_count = _subnet_failures[subnet]['count']

        # 서브넷 임계치 (IP보다 높게: 10회)
        subnet_blocked = False
        subnet_threshold = MAX_CONSECUTIVE_FAILURES * 2
        if subnet_count >= subnet_threshold and _subnet_failures[subnet]['blocked_at'] is None:
            _subnet_failures[subnet]['blocked_at'] = now
            subnet_blocked = True

        return {
            'ip_blocked': ip_blocked,
            'subnet_blocked': subnet_blocked,
            'ip_count': ip_count,
            'subnet_count': subnet_count
        }


def record_success(ip: str) -> None:
    """성공 기록. 해당 IP와 서브넷의 연속 실패 카운터 리셋."""
    if not ip:
        return

    subnet = get_subnet(ip)

    with _lock:
        # IP 리셋
        if ip in _ip_failures:
            _ip_failures[ip] = {'count': 0, 'blocked_at': None}

        # 서브넷도 감소 (완전 리셋이 아닌 감소)
        if subnet in _subnet_failures:
            _subnet_failures[subnet]['count'] = max(0, _subnet_failures[subnet]['count'] - 1)
            # 카운터가 임계치 이하면 차단 해제
            if _subnet_failures[subnet]['count'] < MAX_CONSECUTIVE_FAILURES * 2:
                _subnet_failures[subnet]['blocked_at'] = None


def is_ip_blocked(ip: str) -> bool:
    """IP가 차단 상태인지 확인 (시간 경과 시 자동 해제)"""
    if not ip:
        return False

    now = datetime.now()

    with _lock:
        if ip not in _ip_failures:
            return False

        entry = _ip_failures[ip]
        if entry['blocked_at'] is None:
            return False

        # 차단 시간 경과 확인
        if now - entry['blocked_at'] > timedelta(minutes=BLOCK_DURATION_MINUTES):
            # 자동 해제
            entry['blocked_at'] = None
            entry['count'] = 0
            return False

        return True


def is_subnet_blocked(subnet: str) -> bool:
    """서브넷이 차단 상태인지 확인"""
    if not subnet:
        return False

    now = datetime.now()

    with _lock:
        if subnet not in _subnet_failures:
            return False

        entry = _subnet_failures[subnet]
        if entry['blocked_at'] is None:
            return False

        # 차단 시간 경과 확인
        if now - entry['blocked_at'] > timedelta(minutes=BLOCK_DURATION_MINUTES):
            entry['blocked_at'] = None
            entry['count'] = 0
            return False

        return True


def is_blocked(ip: str) -> bool:
    """IP 또는 해당 서브넷이 차단 상태인지 확인"""
    if is_ip_blocked(ip):
        return True
    subnet = get_subnet(ip)
    return is_subnet_blocked(subnet)


def get_blocked_ips() -> list:
    """현재 차단된 IP 목록 반환"""
    now = datetime.now()
    blocked = []

    with _lock:
        for ip, entry in _ip_failures.items():
            if entry['blocked_at'] and now - entry['blocked_at'] <= timedelta(minutes=BLOCK_DURATION_MINUTES):
                blocked.append({
                    'ip': ip,
                    'count': entry['count'],
                    'blocked_at': entry['blocked_at'],
                    'remaining_mins': BLOCK_DURATION_MINUTES - (now - entry['blocked_at']).seconds // 60
                })

    return blocked


def get_blocked_subnets() -> list:
    """현재 차단된 서브넷 목록 반환"""
    now = datetime.now()
    blocked = []

    with _lock:
        for subnet, entry in _subnet_failures.items():
            if entry['blocked_at'] and now - entry['blocked_at'] <= timedelta(minutes=BLOCK_DURATION_MINUTES):
                blocked.append({
                    'subnet': subnet,
                    'count': entry['count'],
                    'blocked_at': entry['blocked_at'],
                    'remaining_mins': BLOCK_DURATION_MINUTES - (now - entry['blocked_at']).seconds // 60
                })

    return blocked


def get_status() -> dict:
    """현재 IP 추적 상태 반환 (디버깅용)"""
    with _lock:
        return {
            'ip_failures': dict(_ip_failures),
            'subnet_failures': dict(_subnet_failures),
            'blocked_ips': get_blocked_ips(),
            'blocked_subnets': get_blocked_subnets()
        }


def clear_all() -> None:
    """모든 추적 데이터 초기화"""
    with _lock:
        _ip_failures.clear()
        _subnet_failures.clear()
