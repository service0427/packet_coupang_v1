"""
작업 로그 저장 모듈 (테이블 분리)

성공 로그: rank_success_logs
    - 상품 발견 성공 (rank > 0)
    - 검색 완료, 미발견 (rank = 0)

실패 로그: rank_fail_logs
    - blocked   : Akamai 차단
    - timeout   : 프록시 타임아웃 (IP 토글)
    - no_cookie : 쿠키 없음
    - error     : 기타 에러

쿠키 사용 로그: cookie_usage_logs
    - 쿠키별 사용 기록 및 성공/실패 분석용
"""

from .db import execute_query, insert_one


def save_cookie_usage_log(
    cookie_id,
    fingerprint_id=None,
    proxy_ip=None,
    actual_ip=None,
    is_first_use=False,
    has_previous_success=False,
    use_count_before=0,
    success_count_before=0,
    age_seconds=0,
    success=False,
    found=False,
    rank_position=None,
    click_success=False,
    error_message=None
):
    """쿠키 사용 로그 저장 (분석용)

    Args:
        cookie_id: 쿠키 ID
        fingerprint_id: 핑거프린트 ID (선택)
        proxy_ip: 쿠키 생성 시 프록시 IP
        actual_ip: 실제 요청 시 사용한 IP
        is_first_use: 최초 사용 여부
        has_previous_success: 이전 성공 기록 여부
        use_count_before: 사용 전 use_count
        success_count_before: 사용 전 success_count
        age_seconds: 쿠키 나이 (초)
        success: 검색 성공 (차단 아님)
        found: 상품 발견
        rank_position: 발견 순위
        click_success: 클릭 성공
        error_message: 에러 메시지 (선택)

    Returns:
        int: 생성된 로그 ID
    """
    try:
        return insert_one("""
            INSERT INTO cookie_usage_logs
            (cookie_id, fingerprint_id, proxy_ip, actual_ip,
             is_first_use, has_previous_success, use_count_before, success_count_before,
             age_seconds, success, found, rank_position, click_success, error_message)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            cookie_id,
            fingerprint_id,
            proxy_ip,
            actual_ip,
            1 if is_first_use else 0,
            1 if has_previous_success else 0,
            use_count_before,
            success_count_before,
            age_seconds,
            1 if success else 0,
            1 if found else 0,
            rank_position,
            1 if click_success else 0,
            error_message[:255] if error_message else None
        ))

    except Exception as e:
        print(f"⚠️ 쿠키 사용 로그 저장 실패: {e}")
        return None


def save_success_log(
    pl_id=None,
    keyword=None,
    product_id=None,
    rank=0,
    cookie_id=None,
    proxy_ip=None
):
    """성공 로그 저장 (발견/미발견 모두)

    Args:
        pl_id: progress_id (작업 ID)
        keyword: 검색 키워드
        product_id: 상품 ID
        rank: 발견 순위 (0=미발견)
        cookie_id: 사용한 쿠키 ID
        proxy_ip: 사용한 프록시 IP

    Returns:
        bool: 저장 성공 여부
    """
    try:
        use_count = 1
        cookie_age = 0

        if cookie_id:
            cookie_result = execute_query(
                'SELECT success_count, TIMESTAMPDIFF(SECOND, created_at, NOW()) as age FROM cookies WHERE id = %s',
                (cookie_id,)
            )
            if cookie_result:
                use_count = cookie_result[0]['success_count'] + 1
                cookie_age = cookie_result[0]['age']

        insert_one("""
            INSERT INTO rank_success_logs
            (pl_id, keyword, product_id, rank, cookie_id, use_count, cookie_age, proxy_ip)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            pl_id,
            keyword,
            product_id,
            rank if rank and rank > 0 else 0,
            cookie_id,
            use_count,
            cookie_age,
            proxy_ip
        ))
        return True

    except Exception as e:
        print(f"⚠️ 성공 로그 저장 실패: {e}")
        return False


def save_fail_log(
    pl_id=None,
    keyword=None,
    product_id=None,
    fail_type='error',
    cookie_id=None,
    proxy_ip=None,
    error_msg=None
):
    """실패 로그 저장

    Args:
        pl_id: progress_id (작업 ID)
        keyword: 검색 키워드
        product_id: 상품 ID
        fail_type: 실패 유형 (blocked, timeout, no_cookie, error)
        cookie_id: 사용한 쿠키 ID
        proxy_ip: 사용한 프록시 IP
        error_msg: 에러 메시지 (선택)

    Returns:
        bool: 저장 성공 여부
    """
    try:
        insert_one("""
            INSERT INTO rank_fail_logs
            (pl_id, keyword, product_id, fail_type, cookie_id, proxy_ip, error_msg)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            pl_id,
            keyword,
            product_id,
            fail_type,
            cookie_id,
            proxy_ip,
            error_msg[:255] if error_msg else None
        ))
        return True

    except Exception as e:
        print(f"⚠️ 실패 로그 저장 실패: {e}")
        return False


def get_success_stats(minutes=60, proxy_ip=None):
    """성공 로그 통계 조회

    Returns:
        dict: {total, found, not_found}
    """
    try:
        where_clause = "WHERE created_at >= NOW() - INTERVAL %s MINUTE"
        params = [minutes]

        if proxy_ip:
            where_clause += " AND proxy_ip = %s"
            params.append(proxy_ip)

        result = execute_query(f"""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN rank > 0 THEN 1 ELSE 0 END) as found,
                SUM(CASE WHEN rank = 0 THEN 1 ELSE 0 END) as not_found
            FROM rank_success_logs
            {where_clause}
        """, tuple(params))

        if result:
            return {
                'total': result[0]['total'] or 0,
                'found': result[0]['found'] or 0,
                'not_found': result[0]['not_found'] or 0
            }
        return {'total': 0, 'found': 0, 'not_found': 0}

    except Exception as e:
        print(f"통계 조회 실패: {e}")
        return {'total': 0, 'found': 0, 'not_found': 0}


def get_fail_stats(minutes=60, proxy_ip=None):
    """실패 로그 통계 조회

    Returns:
        dict: {total, blocked, timeout, no_cookie, error}
    """
    try:
        where_clause = "WHERE created_at >= NOW() - INTERVAL %s MINUTE"
        params = [minutes]

        if proxy_ip:
            where_clause += " AND proxy_ip = %s"
            params.append(proxy_ip)

        result = execute_query(f"""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN fail_type = 'blocked' THEN 1 ELSE 0 END) as blocked,
                SUM(CASE WHEN fail_type = 'timeout' THEN 1 ELSE 0 END) as timeout,
                SUM(CASE WHEN fail_type = 'no_cookie' THEN 1 ELSE 0 END) as no_cookie,
                SUM(CASE WHEN fail_type = 'error' THEN 1 ELSE 0 END) as error
            FROM rank_fail_logs
            {where_clause}
        """, tuple(params))

        if result:
            return {
                'total': result[0]['total'] or 0,
                'blocked': result[0]['blocked'] or 0,
                'timeout': result[0]['timeout'] or 0,
                'no_cookie': result[0]['no_cookie'] or 0,
                'error': result[0]['error'] or 0
            }
        return {'total': 0, 'blocked': 0, 'timeout': 0, 'no_cookie': 0, 'error': 0}

    except Exception as e:
        print(f"통계 조회 실패: {e}")
        return {'total': 0, 'blocked': 0, 'timeout': 0, 'no_cookie': 0, 'error': 0}


def get_combined_stats(minutes=60, proxy_ip=None):
    """성공+실패 통합 통계

    Returns:
        dict: {total, found, not_found, blocked, timeout, no_cookie, error}
    """
    success = get_success_stats(minutes, proxy_ip)
    fail = get_fail_stats(minutes, proxy_ip)

    return {
        'total': success['total'] + fail['total'],
        'found': success['found'],
        'not_found': success['not_found'],
        'blocked': fail['blocked'],
        'timeout': fail['timeout'],
        'no_cookie': fail['no_cookie'],
        'error': fail['error']
    }


# 하위 호환성 (기존 함수 유지)
def save_work_log(
    pl_id=None,
    keyword=None,
    product_id=None,
    rank=0,
    cookie_id=None,
    proxy_ip=None,
    status='success'
):
    """기존 호환용 - 새 테이블로 분기"""
    if status in ('blocked', 'timeout', 'no_cookie', 'error'):
        return save_fail_log(
            pl_id=pl_id,
            keyword=keyword,
            product_id=product_id,
            fail_type=status,
            cookie_id=cookie_id,
            proxy_ip=proxy_ip
        )
    else:
        return save_success_log(
            pl_id=pl_id,
            keyword=keyword,
            product_id=product_id,
            rank=rank,
            cookie_id=cookie_id,
            proxy_ip=proxy_ip
        )


def get_log_stats(minutes=60, proxy_ip=None):
    """기존 호환용"""
    return get_combined_stats(minutes, proxy_ip)


def get_recent_logs(limit=20, proxy_ip=None):
    """최근 로그 조회 (성공+실패 통합)"""
    try:
        where_clause = ""
        params = []

        if proxy_ip:
            where_clause = "WHERE proxy_ip = %s"
            params.append(proxy_ip)

        # 성공 로그
        success_logs = execute_query(f"""
            SELECT 'success' as log_type, pl_id, keyword, product_id, rank,
                   cookie_id, proxy_ip, created_at
            FROM rank_success_logs
            {where_clause}
            ORDER BY created_at DESC LIMIT %s
        """, tuple(params + [limit]))

        # 실패 로그
        fail_logs = execute_query(f"""
            SELECT 'fail' as log_type, pl_id, keyword, product_id, fail_type,
                   cookie_id, proxy_ip, created_at
            FROM rank_fail_logs
            {where_clause}
            ORDER BY created_at DESC LIMIT %s
        """, tuple(params + [limit]))

        # 통합 및 정렬
        all_logs = (success_logs or []) + (fail_logs or [])
        all_logs.sort(key=lambda x: x['created_at'], reverse=True)

        return all_logs[:limit]

    except Exception as e:
        print(f"로그 조회 실패: {e}")
        return []
