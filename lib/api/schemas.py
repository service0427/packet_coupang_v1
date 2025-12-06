"""
Pydantic 스키마 정의
"""

from typing import Optional, Dict
from pydantic import BaseModel, Field
from datetime import datetime


class RankCheckRequest(BaseModel):
    """순위 체크 요청"""
    keyword: str = Field(..., min_length=1, description="검색어")
    product_id: str = Field(..., description="상품 ID")
    item_id: Optional[str] = Field(None, description="아이템 ID (선택)")
    vendor_item_id: Optional[str] = Field(None, description="벤더 아이템 ID (선택)")
    max_page: int = Field(default=13, ge=1, le=20, description="최대 검색 페이지")


class RankData(BaseModel):
    """순위 데이터"""
    keyword: str
    product_id: str
    item_id: Optional[str] = None
    vendor_item_id: Optional[str] = None
    found: bool
    rank: Optional[int] = None
    page: Optional[int] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    id_match_type: Optional[str] = None  # full_match, product_vendor, product_item, product_only, vendor_only, item_only
    checked_at: str


class MetaData(BaseModel):
    """메타 정보 (디버깅용)"""
    pages_searched: int = 0
    page_counts: Optional[Dict[str, str]] = None  # {"1": "72", "2": "72(r1)", "13": "-1(r2)"} 페이지별 상품 수(재시도)
    elapsed_ms: int = 0
    profile: Optional[str] = None
    # 쿠키 정보
    cookie_id: Optional[int] = None
    cookie_ip: Optional[str] = None
    cookie_age_seconds: Optional[int] = None
    cookie_success: Optional[int] = None
    cookie_fail: Optional[int] = None
    cookie_chrome: Optional[str] = None
    # 프록시 정보
    proxy_ip: Optional[str] = None
    proxy_host: Optional[str] = None
    # 매칭 정보
    match_type: Optional[str] = None
    # 멀티-트라이 정보
    tries_count: Optional[int] = None  # 실제 시도 횟수
    tries_total: Optional[int] = None  # 전체 시도 설정


class ErrorInfo(BaseModel):
    """에러 정보"""
    code: str
    message: str
    detail: Optional[str] = None


class RankCheckResponse(BaseModel):
    """순위 체크 응답"""
    success: bool
    data: Optional[RankData] = None
    meta: Optional[MetaData] = None
    error: Optional[ErrorInfo] = None


class StatusResponse(BaseModel):
    """상태 응답"""
    status: str
    workers: int
    active: int
    queue_size: int
    uptime_seconds: int
