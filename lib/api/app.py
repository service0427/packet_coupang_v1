"""
FastAPI 앱 및 라우터
"""

import time
import json
import threading
from datetime import datetime, timezone
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from api.schemas import (
    RankCheckRequest,
    RankCheckResponse,
    RankData,
    MetaData,
    ErrorInfo,
    StatusResponse
)
from api.worker_pool import get_worker_pool, init_worker_pool
from api.rank_checker import check_rank
from api.multi_checker import check_rank_progressive_async
from common import db


def _save_api_log(log_data: dict):
    """API 로그를 DB에 저장 (별도 스레드)"""
    try:
        conn = db.get_connection()
        with conn.cursor() as cur:
            cur.execute('''
                INSERT INTO api_logs (
                    request_time, response_time, elapsed_ms, client_ip,
                    method, path, status_code, success, error_code,
                    keyword, product_id, found, `rank`, cookie_id, match_type
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
            ''', (
                log_data['request_time'],
                log_data['response_time'],
                log_data['elapsed_ms'],
                log_data['client_ip'],
                log_data['method'],
                log_data['path'],
                log_data['status_code'],
                log_data['success'],
                log_data.get('error_code'),
                log_data.get('keyword'),
                log_data.get('product_id'),
                log_data.get('found'),
                log_data.get('rank'),
                log_data.get('cookie_id'),
                log_data.get('match_type')
            ))
            conn.commit()
    except Exception as e:
        pass  # 로그 저장 실패해도 API는 정상 동작
    finally:
        try:
            conn.close()
        except:
            pass


class APILogMiddleware(BaseHTTPMiddleware):
    """API 호출 로그 미들웨어"""

    async def dispatch(self, request: Request, call_next):
        # /api/rank/ 경로만 로깅
        if not request.url.path.startswith('/api/rank/'):
            return await call_next(request)

        request_time = datetime.now(timezone.utc)
        start_time = time.time()

        # 요청 처리
        response = await call_next(request)

        response_time = datetime.now(timezone.utc)
        elapsed_ms = int((time.time() - start_time) * 1000)

        # 클라이언트 IP (프록시 헤더 우선)
        client_ip = request.headers.get('x-forwarded-for', '').split(',')[0].strip()
        if not client_ip:
            client_ip = request.headers.get('x-real-ip', '')
        if not client_ip and request.client:
            client_ip = request.client.host

        # 응답 본문 읽기 (로그용)
        response_body = b''
        async for chunk in response.body_iterator:
            response_body += chunk

        # 응답 데이터 파싱
        log_data = {
            'request_time': request_time,
            'response_time': response_time,
            'elapsed_ms': elapsed_ms,
            'client_ip': client_ip,
            'method': request.method,
            'path': request.url.path,
            'status_code': response.status_code,
            'success': None,
            'error_code': None,
            'keyword': None,
            'product_id': None,
            'found': None,
            'rank': None,
            'cookie_id': None,
            'match_type': None
        }

        try:
            resp_json = json.loads(response_body)
            log_data['success'] = resp_json.get('success')
            if resp_json.get('error'):
                log_data['error_code'] = resp_json['error'].get('code')
            if resp_json.get('data'):
                log_data['keyword'] = resp_json['data'].get('keyword')
                log_data['product_id'] = resp_json['data'].get('product_id')
                log_data['found'] = resp_json['data'].get('found')
                log_data['rank'] = resp_json['data'].get('rank')
            if resp_json.get('meta'):
                log_data['cookie_id'] = resp_json['meta'].get('cookie_id')
                log_data['match_type'] = resp_json['meta'].get('match_type')
        except:
            pass

        # 비동기로 DB 저장 (응답 지연 방지)
        threading.Thread(target=_save_api_log, args=(log_data,), daemon=True).start()

        # 새 응답 반환 (본문 재사용)
        return Response(
            content=response_body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type
        )


# FastAPI 앱 생성
app = FastAPI(
    title="Rank Check API",
    description="쿠팡 상품 순위 체크 API",
    version="1.0.0"
)

# 로그 미들웨어 등록
app.add_middleware(APILogMiddleware)


@app.on_event("startup")
async def startup_event():
    """앱 시작 시 워커 풀 초기화"""
    init_worker_pool(max_workers=20)


@app.on_event("shutdown")
async def shutdown_event():
    """앱 종료 시 워커 풀 정리"""
    pool = get_worker_pool()
    pool.shutdown(wait=True)


@app.get("/api/status", response_model=StatusResponse)
async def get_status():
    """서버 상태 조회"""
    pool = get_worker_pool()
    status = pool.get_status()
    return StatusResponse(**status)


@app.post("/api/rank/check", response_model=RankCheckResponse)
async def check_product_rank(request: RankCheckRequest):
    """상품 순위 체크

    검색어와 상품 ID를 받아 순위를 반환합니다.
    """
    product_id = request.product_id
    item_id = request.item_id
    vendor_item_id = request.vendor_item_id

    # 워커 풀에서 실행
    pool = get_worker_pool()

    try:
        result = await pool.submit_async(
            check_rank,
            keyword=request.keyword,
            product_id=product_id,
            item_id=item_id,
            vendor_item_id=vendor_item_id,
            max_page=request.max_page
        )
    except Exception as e:
        return RankCheckResponse(
            success=False,
            error=ErrorInfo(
                code="INTERNAL_ERROR",
                message="Worker execution failed",
                detail=str(e)[:100]
            )
        )

    # page_counts 키를 문자열로 변환 (JSON 호환) - 값은 이미 문자열
    page_counts = result.get('page_counts', {})
    page_counts_str = {str(k): v for k, v in page_counts.items()} if page_counts else None

    # 결과 변환
    if result.get('error_code'):
        return RankCheckResponse(
            success=False,
            error=ErrorInfo(
                code=result['error_code'],
                message=result.get('error_message', ''),
                detail=result.get('error_detail')
            ),
            meta=MetaData(
                pages_searched=result.get('pages_searched', 0),
                page_counts=page_counts_str,
                elapsed_ms=result.get('elapsed_ms', 0),
                profile=result.get('profile_id'),
                cookie_id=result.get('cookie_id'),
                cookie_ip=result.get('cookie_ip'),
                cookie_age_seconds=result.get('cookie_age_seconds'),
                cookie_success=result.get('cookie_success'),
                cookie_fail=result.get('cookie_fail'),
                cookie_chrome=result.get('cookie_chrome'),
                proxy_ip=result.get('proxy_ip'),
                proxy_host=result.get('proxy_host'),
                match_type=result.get('match_type')
            )
        )

    # 성공
    checked_at = datetime.now(timezone.utc).isoformat()

    return RankCheckResponse(
        success=True,
        data=RankData(
            keyword=request.keyword,
            product_id=product_id,
            item_id=item_id,
            vendor_item_id=vendor_item_id,
            found=result['found'],
            rank=result.get('rank'),
            page=result.get('page'),
            rating=result.get('rating'),
            review_count=result.get('review_count'),
            id_match_type=result.get('id_match_type'),
            checked_at=checked_at
        ),
        meta=MetaData(
            pages_searched=result.get('pages_searched', 0),
            page_counts=page_counts_str,
            elapsed_ms=result.get('elapsed_ms', 0),
            profile=result.get('profile_id'),
            cookie_id=result.get('cookie_id'),
            cookie_ip=result.get('cookie_ip'),
            cookie_age_seconds=result.get('cookie_age_seconds'),
            cookie_success=result.get('cookie_success'),
            cookie_fail=result.get('cookie_fail'),
            cookie_chrome=result.get('cookie_chrome'),
            proxy_ip=result.get('proxy_ip'),
            proxy_host=result.get('proxy_host'),
            match_type=result.get('match_type')
        )
    )


@app.get("/api/rank/sample", response_model=RankCheckResponse)
async def check_sample_rank():
    """랜덤 샘플로 순위 체크 (테스트용)"""
    # DB에서 랜덤 상품 가져오기
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT keyword, product_id, item_id, vendor_item_id
                FROM product_list_bak ORDER BY RAND() LIMIT 1
            ''')
            row = cur.fetchone()
    finally:
        conn.close()

    if not row:
        return RankCheckResponse(
            success=False,
            error=ErrorInfo(code="NO_SAMPLE", message="No sample data in DB")
        )

    # 실제 체크 실행
    request = RankCheckRequest(
        keyword=row['keyword'],
        product_id=row['product_id'],
        item_id=row.get('item_id'),
        vendor_item_id=row.get('vendor_item_id'),
        max_page=13
    )
    return await check_product_rank(request)


@app.post("/api/rank/check-multi", response_model=RankCheckResponse)
async def check_product_rank_multi(request: RankCheckRequest):
    """상품 순위 체크 (Progressive Retry)

    Round 1: 1개 시도
    Round 2: 2개 동시 시도 (실패 시)
    Round 3: 3개 동시 시도 (실패 시)
    Round 4: 4개 동시 시도 (실패 시)
    최대 10회 시도, 첫 성공 결과 반환
    """
    try:
        result = await check_rank_progressive_async(
            keyword=request.keyword,
            product_id=request.product_id,
            item_id=request.item_id,
            vendor_item_id=request.vendor_item_id,
            max_page=request.max_page,
            timeout_per_round=15.0
        )
    except Exception as e:
        return RankCheckResponse(
            success=False,
            error=ErrorInfo(
                code="INTERNAL_ERROR",
                message="Multi-check execution failed",
                detail=str(e)[:100]
            )
        )

    # page_counts 키를 문자열로 변환
    page_counts = result.get('page_counts', {})
    page_counts_str = {str(k): v for k, v in page_counts.items()} if page_counts else None

    # 결과 변환
    if result.get('error_code'):
        return RankCheckResponse(
            success=False,
            error=ErrorInfo(
                code=result['error_code'],
                message=result.get('error_message', ''),
                detail=result.get('error_detail')
            ),
            meta=MetaData(
                pages_searched=result.get('pages_searched', 0),
                page_counts=page_counts_str,
                elapsed_ms=result.get('elapsed_ms', 0),
                profile=result.get('profile_id'),
                cookie_id=result.get('cookie_id'),
                cookie_ip=result.get('cookie_ip'),
                cookie_age_seconds=result.get('cookie_age_seconds'),
                cookie_success=result.get('cookie_success'),
                cookie_fail=result.get('cookie_fail'),
                cookie_chrome=result.get('cookie_chrome'),
                proxy_ip=result.get('proxy_ip'),
                proxy_host=result.get('proxy_host'),
                match_type=result.get('match_type'),
                tries_count=result.get('tries_count'),
                tries_total=result.get('tries_total'),
                round=result.get('round'),
                round_detail=result.get('round_detail')
            )
        )

    # 성공
    checked_at = datetime.now(timezone.utc).isoformat()

    return RankCheckResponse(
        success=True,
        data=RankData(
            keyword=request.keyword,
            product_id=request.product_id,
            item_id=request.item_id,
            vendor_item_id=request.vendor_item_id,
            found=result['found'],
            rank=result.get('rank'),
            page=result.get('page'),
            rating=result.get('rating'),
            review_count=result.get('review_count'),
            id_match_type=result.get('id_match_type'),
            checked_at=checked_at
        ),
        meta=MetaData(
            pages_searched=result.get('pages_searched', 0),
            page_counts=page_counts_str,
            elapsed_ms=result.get('elapsed_ms', 0),
            profile=result.get('profile_id'),
            cookie_id=result.get('cookie_id'),
            cookie_ip=result.get('cookie_ip'),
            cookie_age_seconds=result.get('cookie_age_seconds'),
            cookie_success=result.get('cookie_success'),
            cookie_fail=result.get('cookie_fail'),
            cookie_chrome=result.get('cookie_chrome'),
            proxy_ip=result.get('proxy_ip'),
            proxy_host=result.get('proxy_host'),
            match_type=result.get('match_type'),
            tries_count=result.get('tries_count'),
            tries_total=result.get('tries_total'),
            round=result.get('round'),
            round_detail=result.get('round_detail')
        )
    )


@app.get("/api/rank/sample-multi", response_model=RankCheckResponse)
async def check_sample_rank_multi():
    """랜덤 샘플로 순위 체크 - 멀티 트라이 (테스트용)"""
    conn = db.get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT keyword, product_id, item_id, vendor_item_id
                FROM product_list_bak ORDER BY RAND() LIMIT 1
            ''')
            row = cur.fetchone()
    finally:
        conn.close()

    if not row:
        return RankCheckResponse(
            success=False,
            error=ErrorInfo(code="NO_SAMPLE", message="No sample data in DB")
        )

    request = RankCheckRequest(
        keyword=row['keyword'],
        product_id=row['product_id'],
        item_id=row.get('item_id'),
        vendor_item_id=row.get('vendor_item_id'),
        max_page=13
    )
    return await check_product_rank_multi(request)


@app.get("/")
async def root():
    """루트 경로"""
    return {
        "service": "Rank Check API",
        "version": "1.0.0",
        "endpoints": {
            "POST /api/rank/check": "순위 체크 (단일)",
            "POST /api/rank/check-multi": "순위 체크 (Progressive: 1→2→3→4)",
            "GET /api/rank/sample": "랜덤 샘플 (단일)",
            "GET /api/rank/sample-multi": "랜덤 샘플 (Progressive)",
            "GET /api/status": "서버 상태"
        }
    }
