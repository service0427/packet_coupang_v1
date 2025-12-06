"""
순위 체크 핵심 로직

순수하게 결과만 반환, 로그/출력 없음
"""

import time
import random

from common.proxy import get_bound_cookie, report_cookie_result
from common.fingerprint import get_tls_profile
from work.search import search_product


def _error_result(start_time: float, code: str, message: str, detail: str = None,
                  debug_info: dict = None, pages_searched: int = 0,
                  page_counts: dict = None) -> dict:
    """에러 결과 생성 헬퍼"""
    d = debug_info or {}
    return {
        'success': False,
        'found': False,
        'rank': None,
        'page': None,
        'pages_searched': pages_searched,
        'page_counts': page_counts or {},
        'elapsed_ms': int((time.time() - start_time) * 1000),
        'profile_id': d.get('profile_id'),
        'cookie_id': d.get('cookie_id'),
        'cookie_ip': d.get('cookie_ip'),
        'cookie_age_seconds': d.get('cookie_age_seconds'),
        'cookie_success': d.get('cookie_success'),
        'cookie_fail': d.get('cookie_fail'),
        'cookie_chrome': d.get('cookie_chrome'),
        'proxy_ip': d.get('proxy_ip'),
        'proxy_host': d.get('proxy_host'),
        'match_type': d.get('match_type'),
        'id_match_type': None,
        'error_code': code,
        'error_message': message,
        'error_detail': detail
    }


def _success_result(start_time: float, found: bool, rank: int, page: int,
                    pages_searched: int, rating: float = None, review_count: int = None,
                    id_match_type: str = None, debug_info: dict = None,
                    page_counts: dict = None) -> dict:
    """성공 결과 생성 헬퍼"""
    d = debug_info or {}
    return {
        'success': True,
        'found': found,
        'rank': rank,
        'page': page,
        'rating': rating,
        'review_count': review_count,
        'id_match_type': id_match_type,
        'pages_searched': pages_searched,
        'page_counts': page_counts or {},
        'elapsed_ms': int((time.time() - start_time) * 1000),
        'profile_id': d.get('profile_id'),
        'cookie_id': d.get('cookie_id'),
        'cookie_ip': d.get('cookie_ip'),
        'cookie_age_seconds': d.get('cookie_age_seconds'),
        'cookie_success': d.get('cookie_success'),
        'cookie_fail': d.get('cookie_fail'),
        'cookie_chrome': d.get('cookie_chrome'),
        'proxy_ip': d.get('proxy_ip'),
        'proxy_host': d.get('proxy_host'),
        'match_type': d.get('match_type'),
        'error_code': None,
        'error_message': None,
        'error_detail': None
    }


def check_rank(keyword: str, product_id: str, item_id: str = None,
               vendor_item_id: str = None, max_page: int = 13) -> dict:
    """순위 체크 실행

    Args:
        keyword: 검색어
        product_id: 상품 ID
        item_id: 아이템 ID (선택)
        vendor_item_id: 벤더 아이템 ID (선택)
        max_page: 최대 검색 페이지 (1-20)

    Returns:
        dict: 순위 체크 결과
    """
    start_time = time.time()

    # 입력값 검증
    if not keyword or not str(keyword).strip():
        return _error_result(start_time, 'INVALID_INPUT', 'keyword is required')
    if not product_id or not str(product_id).strip():
        return _error_result(start_time, 'INVALID_INPUT', 'product_id is required')

    keyword = str(keyword).strip()
    product_id = str(product_id).strip()

    try:
        # 1. 쿠키+프록시 할당 (동일 상품 클릭한 쿠키 제외)
        bound = get_bound_cookie(max_age_minutes=120, platform_type='mobile',
                                 exclude_product=product_id, verbose=False)
        if not bound:
            return _error_result(start_time, 'NO_COOKIE', 'No available cookies')

        proxy = bound['proxy']
        proxy_host = bound.get('proxy_host', '')
        external_ip = bound['external_ip']
        cookie_record = bound['cookie_record']
        cookies = bound['cookies']
        match_type = bound['match_type']

        # 디버그 정보 구성 (cookie_record에서 추출)
        # cookie_ip: 쿠키 생성 시 원본 IP (proxy_ip 필드에 저장됨)
        # cookie_age_seconds: created_at 기준 경과 시간 (초)
        cookie_age_seconds = None
        if cookie_record.get('created_at'):
            try:
                from datetime import datetime, timezone
                created_str = cookie_record['created_at']
                # ISO 형식 파싱 (Z → +00:00)
                if created_str.endswith('Z'):
                    created_str = created_str[:-1] + '+00:00'
                created = datetime.fromisoformat(created_str)
                now = datetime.now(timezone.utc)
                cookie_age_seconds = int((now - created).total_seconds())
            except:
                pass

        debug_info = {
            'cookie_id': cookie_record.get('id'),
            'cookie_ip': cookie_record.get('proxy_ip'),
            'cookie_age_seconds': cookie_age_seconds,
            'cookie_success': cookie_record.get('success_count', 0),
            'cookie_fail': cookie_record.get('fail_count', 0),
            'cookie_chrome': cookie_record.get('chrome_version'),
            'proxy_ip': external_ip,
            'proxy_host': proxy_host,
            'match_type': match_type,
        }

        # 2. 플랫폼 결정 (쿠키 상태에 따라 자동)
        if match_type == 'exact':
            tls_platform = 'pc'
        elif match_type == 'subnet':
            tls_platform = random.choice(['pc', 'mobile'])
        else:
            tls_platform = 'mobile'

        # 3. TLS 프로필 선택
        tls_profile = get_tls_profile(platform=tls_platform)
        if not tls_profile:
            report_cookie_result(cookie_record['id'], False)
            return _error_result(start_time, 'NO_TLS', 'No TLS profile available', debug_info=debug_info)

        profile_id = tls_profile['profile_id']
        debug_info['profile_id'] = profile_id

        # 4. 검색 실행
        result = search_product(
            keyword, product_id, cookies, tls_profile, proxy,
            target_item_id=item_id, target_vendor_item_id=vendor_item_id,
            max_page=max_page, verbose=False, save_html=False
        )

        found = result['found']
        blocked = result['blocked']
        page_errors = result.get('page_errors', [])
        pages_searched = result.get('pages_searched', 0)
        page_counts = result.get('page_counts', {})
        id_match_type = result.get('id_match_type')

        # 5. 쿠키 결과 보고
        is_success = not blocked
        report_cookie_result(cookie_record['id'], is_success)

        # 6. 결과 반환
        if blocked:
            error_detail = result.get('block_error', '')
            # page_errors가 있으면 실제 에러 페이지 정보 표시
            # 예: "p13:BLOCKED_403" 또는 "p4:TIMEOUT,p5:TIMEOUT"
            if page_errors:
                err_parts = [f"p{e['page']}:{e['error']}" for e in page_errors[:3]]  # 최대 3개
                error_detail = ','.join(err_parts)

            return _error_result(
                start_time, 'BLOCKED', 'Request blocked',
                detail=error_detail[:50] if error_detail else None,
                debug_info=debug_info, pages_searched=pages_searched,
                page_counts=page_counts
            )

        if found:
            return _success_result(
                start_time, True, result['actual_rank'], found['page'],
                pages_searched,
                rating=found.get('rating'), review_count=found.get('review_count'),
                id_match_type=id_match_type, debug_info=debug_info,
                page_counts=page_counts
            )
        else:
            return _success_result(
                start_time, False, None, None,
                pages_searched,
                id_match_type=None, debug_info=debug_info,
                page_counts=page_counts
            )

    except Exception as e:
        return _error_result(start_time, 'INTERNAL_ERROR', 'Unexpected error', str(e)[:100])
