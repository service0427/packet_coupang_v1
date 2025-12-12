"""
FastAPI 앱 및 라우터
- DB 의존성 없음
- 순위 체크 API만 제공
"""

import time
import random
import asyncio
from datetime import datetime, timezone
from fastapi import FastAPI

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


# FastAPI 앱 생성
app = FastAPI(
    title="Rank Check API",
    description="쿠팡 상품 순위 체크 API",
    version="2.0.0"
)


@app.on_event("startup")
async def startup_event():
    """앱 시작 시 워커 풀 초기화"""
    init_worker_pool(max_workers=150)


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

    # page_counts 키를 문자열로 변환 (JSON 호환)
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


@app.post("/api/rank/check-multi", response_model=RankCheckResponse)
async def check_product_rank_multi(request: RankCheckRequest):
    """상품 순위 체크 (Exponential Backoff + Jitter)

    업계 표준 재시도 패턴:
    - 최대 3회 시도
    - 실패 시 지수 백오프: 1초 → 2초 (+ 랜덤 jitter)
    - 30초 총 타임아웃
    - 성공하면 즉시 반환
    """
    product_id = request.product_id
    item_id = request.item_id
    vendor_item_id = request.vendor_item_id

    pool = get_worker_pool()
    total_start = time.time()
    total_timeout = 30.0
    max_tries = 3
    base_delay = 1.0
    last_result = None

    for try_num in range(1, max_tries + 1):
        # 타임아웃 체크
        elapsed = time.time() - total_start
        if elapsed >= total_timeout:
            break

        try:
            result = await pool.submit_async(
                check_rank,
                keyword=request.keyword,
                product_id=product_id,
                item_id=item_id,
                vendor_item_id=vendor_item_id,
                max_page=request.max_page,
                timeout=25.0
            )
        except asyncio.TimeoutError:
            result = {
                'error_code': 'TIMEOUT',
                'error_message': 'Worker timeout after 25s'
            }
        except Exception as e:
            result = {
                'error_code': 'INTERNAL_ERROR',
                'error_message': f'Worker error: {str(e)[:50]}'
            }

        last_result = result

        # 성공 체크
        if not result.get('error_code'):
            result['tries_count'] = try_num
            result['tries_total'] = max_tries
            break

        # 실패 시 Exponential Backoff + Jitter
        if try_num < max_tries:
            backoff = base_delay * (2 ** (try_num - 1))
            jitter = random.uniform(0, 0.5)
            delay = min(backoff + jitter, 5.0)

            remaining = total_timeout - (time.time() - total_start)
            if delay < remaining:
                await asyncio.sleep(delay)

    # 최종 결과 처리
    if last_result is None:
        return RankCheckResponse(
            success=False,
            error=ErrorInfo(
                code="TIMEOUT",
                message="All attempts timed out"
            )
        )

    total_elapsed_ms = int((time.time() - total_start) * 1000)
    tries_count = last_result.get('tries_count', max_tries)

    page_counts = last_result.get('page_counts', {})
    page_counts_str = {str(k): v for k, v in page_counts.items()} if page_counts else None

    if last_result.get('error_code'):
        return RankCheckResponse(
            success=False,
            error=ErrorInfo(
                code=last_result['error_code'],
                message=last_result.get('error_message', ''),
                detail=last_result.get('error_detail')
            ),
            meta=MetaData(
                pages_searched=last_result.get('pages_searched', 0),
                page_counts=page_counts_str,
                elapsed_ms=total_elapsed_ms,
                profile=last_result.get('profile_id'),
                cookie_id=last_result.get('cookie_id'),
                cookie_ip=last_result.get('cookie_ip'),
                cookie_age_seconds=last_result.get('cookie_age_seconds'),
                cookie_success=last_result.get('cookie_success'),
                cookie_fail=last_result.get('cookie_fail'),
                cookie_chrome=last_result.get('cookie_chrome'),
                proxy_ip=last_result.get('proxy_ip'),
                proxy_host=last_result.get('proxy_host'),
                match_type=last_result.get('match_type'),
                tries_count=tries_count,
                tries_total=max_tries
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
            found=last_result['found'],
            rank=last_result.get('rank'),
            page=last_result.get('page'),
            rating=last_result.get('rating'),
            review_count=last_result.get('review_count'),
            id_match_type=last_result.get('id_match_type'),
            checked_at=checked_at
        ),
        meta=MetaData(
            pages_searched=last_result.get('pages_searched', 0),
            page_counts=page_counts_str,
            elapsed_ms=total_elapsed_ms,
            profile=last_result.get('profile_id'),
            cookie_id=last_result.get('cookie_id'),
            cookie_ip=last_result.get('cookie_ip'),
            cookie_age_seconds=last_result.get('cookie_age_seconds'),
            cookie_success=last_result.get('cookie_success'),
            cookie_fail=last_result.get('cookie_fail'),
            cookie_chrome=last_result.get('cookie_chrome'),
            proxy_ip=last_result.get('proxy_ip'),
            proxy_host=last_result.get('proxy_host'),
            match_type=last_result.get('match_type'),
            tries_count=tries_count,
            tries_total=max_tries
        )
    )


@app.get("/")
async def root():
    """루트 경로"""
    return {
        "service": "Rank Check API",
        "version": "2.0.0",
        "endpoints": {
            "POST /api/rank/check": "순위 체크 (단일)",
            "POST /api/rank/check-multi": "순위 체크 (재시도)",
            "GET /api/status": "서버 상태"
        }
    }
