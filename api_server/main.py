#!/usr/bin/env python3
"""
쿠팡 순위체크 API - 슬롯관리 연동용
v2_slot_tasks_daily_progress 테이블 순위 업데이트에 사용
"""

import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib'))

from fastapi import FastAPI, Request
from pydantic import BaseModel
from typing import Optional

from api.rank_checker_direct import search

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

LOG_DIR = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)


def log_request(ip, keyword, product_id, rank, elapsed_ms):
    """일자별 로그 파일에 기록"""
    today = datetime.now().strftime('%Y-%m-%d')
    log_file = os.path.join(LOG_DIR, f'{today}.log')
    timestamp = datetime.now().strftime('%H:%M:%S')

    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f'{timestamp}\t{ip}\t{keyword}\t{product_id}\t{rank}\t{elapsed_ms}ms\n')


class SearchRequest(BaseModel):
    product_id: str
    keyword: Optional[str] = None
    item_id: Optional[str] = None
    vendor_item_id: Optional[str] = None


@app.post("/api/search")
async def search_post(req: SearchRequest, request: Request):
    result = search(
        product_id=req.product_id,
        keyword=req.keyword,
        item_id=req.item_id,
        vendor_item_id=req.vendor_item_id,
        max_page=16
    )

    # 로그 기록
    client_ip = request.client.host
    rank = result.get('data', {}).get('rank')
    elapsed_ms = result.get('elapsed_ms', 0)
    log_request(client_ip, req.keyword, req.product_id, rank, elapsed_ms)

    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7999)
