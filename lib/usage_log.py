"""
쿠키 사용 로그 모듈
"""

import json
from db import execute_query, insert_one


def log_cookie_usage(cookie_id, cookie_record, fingerprint, result, actual_ip=None):
    """쿠키 사용 결과 로깅

    Args:
        cookie_id: 쿠키 ID
        cookie_record: 쿠키 DB 레코드
        fingerprint: 핑거프린트 정보
        result: 실행 결과 dict
            - success: 성공 여부
            - found: 상품 발견 여부
            - rank: 발견 순위
            - click_success: 클릭 성공 여부
            - error: 에러 메시지
        actual_ip: 실제 연결된 IP (프록시 외부 IP)

    Returns:
        int: 로그 ID
    """
    # 쿠키 상태 분석
    use_count = cookie_record.get('use_count', 0)
    success_count = cookie_record.get('success_count', 0)

    # 최초 사용 여부
    is_first_use = use_count == 0

    # 이전 성공 기록 여부
    has_previous_success = success_count > 0

    # 쿠키 나이 (초)
    created_at = cookie_record.get('created_at')
    if created_at:
        from datetime import datetime
        age_seconds = int((datetime.now() - created_at).total_seconds())
    else:
        age_seconds = 0

    # fingerprint ID
    fingerprint_id = fingerprint.get('id') if fingerprint else None

    # 결과 정보
    success = result.get('success', False)
    found = result.get('found', False)
    rank = result.get('rank')
    click_success = result.get('click_success', False)
    error = result.get('error', '')

    # 로그 저장
    log_id = insert_one("""
        INSERT INTO cookie_usage_logs
        (cookie_id, fingerprint_id, proxy_ip, actual_ip,
         is_first_use, has_previous_success, use_count_before, success_count_before,
         age_seconds, success, found, rank_position, click_success, error_message)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        cookie_id,
        fingerprint_id,
        cookie_record.get('proxy_ip', ''),
        actual_ip,
        is_first_use,
        has_previous_success,
        use_count,
        success_count,
        age_seconds,
        success,
        found,
        rank,
        click_success,
        error[:255] if error else None
    ))

    return log_id


def get_usage_stats():
    """사용 통계 조회

    Returns:
        dict: 통계 정보
    """
    # 전체 통계
    total = execute_query("""
        SELECT
            COUNT(*) as total,
            SUM(success) as success_count,
            SUM(found) as found_count,
            SUM(click_success) as click_count
        FROM cookie_usage_logs
    """)[0]

    # 버전별 통계
    by_version = execute_query("""
        SELECT
            chrome_major,
            COUNT(*) as total,
            SUM(success) as success_count,
            SUM(found) as found_count,
            ROUND(SUM(found) * 100.0 / COUNT(*), 1) as found_rate
        FROM cookie_usage_logs
        GROUP BY chrome_major
        ORDER BY chrome_major
    """)

    # 최초 사용 vs 재사용 통계
    by_usage = execute_query("""
        SELECT
            is_first_use,
            has_previous_success,
            COUNT(*) as total,
            SUM(found) as found_count,
            ROUND(SUM(found) * 100.0 / COUNT(*), 1) as found_rate,
            ROUND(AVG(age_seconds), 0) as avg_age
        FROM cookie_usage_logs
        GROUP BY is_first_use, has_previous_success
        ORDER BY is_first_use DESC, has_previous_success DESC
    """)

    # 나이별 통계 (최초 사용)
    first_use_by_age = execute_query("""
        SELECT
            CASE
                WHEN age_seconds < 60 THEN '0-1분'
                WHEN age_seconds < 300 THEN '1-5분'
                WHEN age_seconds < 600 THEN '5-10분'
                ELSE '10분+'
            END as age_group,
            COUNT(*) as total,
            SUM(found) as found_count,
            ROUND(SUM(found) * 100.0 / COUNT(*), 1) as found_rate
        FROM cookie_usage_logs
        WHERE is_first_use = 1
        GROUP BY age_group
        ORDER BY MIN(age_seconds)
    """)

    # 나이별 통계 (재사용, 이전 성공 있음)
    reuse_success_by_age = execute_query("""
        SELECT
            CASE
                WHEN age_seconds < 300 THEN '0-5분'
                WHEN age_seconds < 600 THEN '5-10분'
                WHEN age_seconds < 900 THEN '10-15분'
                ELSE '15분+'
            END as age_group,
            COUNT(*) as total,
            SUM(found) as found_count,
            ROUND(SUM(found) * 100.0 / COUNT(*), 1) as found_rate
        FROM cookie_usage_logs
        WHERE is_first_use = 0 AND has_previous_success = 1
        GROUP BY age_group
        ORDER BY MIN(age_seconds)
    """)

    return {
        'total': total,
        'by_version': by_version,
        'by_usage': by_usage,
        'first_use_by_age': first_use_by_age,
        'reuse_success_by_age': reuse_success_by_age
    }


def print_usage_stats():
    """사용 통계 출력"""
    stats = get_usage_stats()

    print("=" * 60)
    print("쿠키 사용 통계")
    print("=" * 60)

    # 전체
    t = stats['total']
    if t['total']:
        print(f"\n전체: {t['total']}회")
        print(f"  성공: {t['success_count']} ({t['success_count']*100//t['total']}%)")
        print(f"  발견: {t['found_count']} ({t['found_count']*100//t['total']}%)")
        print(f"  클릭: {t['click_count']} ({t['click_count']*100//t['total']}%)")

    # 버전별
    if stats['by_version']:
        print("\n버전별 발견율:")
        for v in stats['by_version']:
            print(f"  Chrome {v['chrome_major']}: {v['found_count']}/{v['total']} ({v['found_rate']}%)")

    # 최초/재사용별
    if stats['by_usage']:
        print("\n사용 유형별:")
        for u in stats['by_usage']:
            if u['is_first_use']:
                label = "최초 사용"
            elif u['has_previous_success']:
                label = "재사용 (이전 성공)"
            else:
                label = "재사용 (이전 실패)"
            avg_min = u['avg_age'] // 60
            print(f"  {label}: {u['found_count']}/{u['total']} ({u['found_rate']}%) | 평균 {avg_min}분")

    # 최초 사용 나이별
    if stats['first_use_by_age']:
        print("\n최초 사용 - 나이별:")
        for a in stats['first_use_by_age']:
            print(f"  {a['age_group']}: {a['found_count']}/{a['total']} ({a['found_rate']}%)")

    # 재사용 (이전 성공) 나이별
    if stats['reuse_success_by_age']:
        print("\n재사용 (이전 성공) - 나이별:")
        for a in stats['reuse_success_by_age']:
            print(f"  {a['age_group']}: {a['found_count']}/{a['total']} ({a['found_rate']}%)")

    print("\n" + "=" * 60)
