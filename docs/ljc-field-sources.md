# LJC 이벤트 필드 출처 정리

> 각 필드를 어디서 추출해야 하는지 정리

## 출처별 분류

### 1. 쿠키에서 추출

| 필드 | 쿠키 키 | 설명 |
|------|---------|------|
| `pcid` | `PCID` | 사용자 식별자 |
| `memberSrl` | `memberSrl` 또는 빈값 | 로그인 사용자 (비로그인: 빈 문자열) |

```python
pcid = cookies.get('PCID', '')
member_srl = cookies.get('memberSrl', '')
```

---

### 2. 이전 페이지/요청에서 전달

| 필드 | 출처 | 설명 |
|------|------|------|
| `referrer` | 이전 요청의 URL | Step 1 URL → Step 2~4의 referrer |
| `url` | 현재 요청의 URL | 현재 페이지 URL 그대로 |

```python
# Step 1 검색 페이지 요청 후
search_url = f"https://www.coupang.com/np/search?component=&q={keyword}&traceId={trace_id}&channel=user"

# Step 2~4 LJC 이벤트에서
common_web = {
    "url": search_url,           # 현재 페이지
    "referrer": "https://www.coupang.com/"  # 이전 페이지 (홈)
}

# Step 5~6 상품 상세에서
detail_url = f"https://www.coupang.com/vp/products/{product_id}?itemId={item_id}..."
common_web = {
    "url": detail_url,
    "referrer": search_url       # 이전 페이지 (검색)
}
```

---

### 3. 검색 HTML에서 추출

| 필드 | 추출 방법 | 정규식/위치 |
|------|-----------|-------------|
| `searchId` | HTML 파싱 | `"searchId":"([^"]+)"` |
| `totalProductCount` (searchCount) | HTML 파싱 | `"totalProductCount":(\d+)` |
| `buildId` (webBuildNo) | `__NEXT_DATA__` | `next_data['buildId']` |
| `listSize` | `__NEXT_DATA__` 또는 고정 | 보통 36 (모바일) |

```python
import re
import json

def extract_search_meta(html):
    """검색 HTML에서 메타 정보 추출"""
    result = {}

    # searchId
    match = re.search(r'"searchId"\s*:\s*"([^"]+)"', html)
    if match:
        result['searchId'] = match.group(1)

    # totalProductCount
    match = re.search(r'"totalProductCount"\s*:\s*(\d+)', html)
    if match:
        result['totalProductCount'] = int(match.group(1))

    # __NEXT_DATA__에서 buildId
    match = re.search(r'<script id="__NEXT_DATA__"[^>]*>([^<]+)</script>', html)
    if match:
        try:
            next_data = json.loads(match.group(1))
            result['buildId'] = next_data.get('buildId', '')
        except:
            pass

    return result
```

---

### 4. 검색 HTML 상품 목록에서 추출

| 필드 | 추출 방법 | 설명 |
|------|-----------|------|
| `productId` | data-product-id 또는 URL | 상품 고유 ID |
| `itemId` | URL 파라미터 | `itemId=xxx` |
| `vendorItemId` | URL 파라미터 | `vendorItemId=xxx` |
| `rank` | URL 파라미터 | `rank=xxx` (1부터 시작) |
| `searchRank` | rank와 동일 | 검색 순위 |

```python
# 기존 ProductExtractor 활용
from extractor.search_extractor import ProductExtractor

result = ProductExtractor.extract_products_from_html(html)
for product in result['ranking']:
    product_id = product['productId']
    item_id = product['itemId']
    vendor_item_id = product['vendorItemId']
    rank = product['rank']
```

---

### 5. URL에서 추출

| 필드 | 출처 | 예시 |
|------|------|------|
| `q` (query) | URL 쿼리 파라미터 | `q=아이폰` |
| `traceId` | URL 쿼리 파라미터 | `traceId=miocw5ud` |
| `filterKey` | URL 전체 쿼리스트링 | `component=&q=...&traceId=...` |
| `page` | URL 쿼리 파라미터 | `page=1` (기본값 1) |

```python
from urllib.parse import urlparse, parse_qs, urlencode

def extract_url_params(url):
    parsed = urlparse(url)
    params = parse_qs(parsed.query)

    return {
        'q': params.get('q', [''])[0],
        'traceId': params.get('traceId', [''])[0],
        'page': params.get('page', ['1'])[0],
        'filterKey': parsed.query  # 전체 쿼리스트링
    }
```

---

### 6. 클라이언트에서 생성

| 필드 | 생성 방법 | 설명 |
|------|-----------|------|
| `pvid` | UUID v4 | 페이지뷰마다 새로 생성 |
| `sdpVisitKey` | 랜덤 문자열 18자 | 상품 상세 방문 시 생성 |
| `traceId` | timestamp base36 | 검색 시작 시 생성 |
| `eventTime` | ISO 8601 | 이벤트 발생 시간 |
| `sentTime` | ISO 8601 | 전송 시간 (eventTime과 동일) |

```python
import uuid
import random
import string
import time
from datetime import datetime, timezone

def generate_pvid():
    return str(uuid.uuid4())

def generate_sdp_visit_key():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=18))

def generate_trace_id():
    timestamp_ms = int(time.time() * 1000)
    base36_chars = string.digits + string.ascii_lowercase
    result = []
    ts = timestamp_ms
    while ts > 0:
        result.append(base36_chars[ts % 36])
        ts //= 36
    return ''.join(reversed(result))

def get_event_time():
    now = datetime.now(timezone.utc)
    return now.strftime('%Y-%m-%dT%H:%M:%S.') + f'{now.microsecond // 1000:03d}Z'
```

---

### 7. 고정값

| 필드 | 값 | 비고 |
|------|-----|------|
| `platform` | `"mweb"` | 모바일 웹 |
| `libraryVersion` | `"0.13.16"` | LJC 라이브러리 버전 |
| `lang` | `"ko-KR"` | Accept-Language |
| `resolution` | `"384x832"` | 모바일 해상도 |
| `rvid` | `""` | 빈 문자열 |
| `logCategory` | 이벤트별 고정 | `"page"`, `"event"`, `"impression"` |
| `logType` | 이벤트별 고정 | `"page"`, `"click"`, `"impression"` |

---

## 필드 흐름도

```
[검색 시작]
  │
  ├─ 생성: traceId, pvid (검색 페이지용)
  │
  ▼
[Step 1: 검색 HTML 요청]
  │
  ├─ 추출: searchId, totalProductCount, buildId
  ├─ 추출: 상품 목록 (productId, itemId, vendorItemId, rank)
  │
  ▼
[Step 2~4: LJC 이벤트]
  │
  ├─ 사용: 쿠키(pcid), URL(q, filterKey), HTML(searchId, searchCount)
  ├─ 사용: 상품정보(productId, itemId, vendorItemId, rank)
  ├─ referrer: 홈페이지 URL
  │
  ▼
[Step 5: 상품 상세 HTML 요청]
  │
  ├─ 생성: 새로운 pvid (상세 페이지용), sdpVisitKey
  ├─ referrer: 검색 URL
  │
  ▼
[Step 6: LJC 이벤트]
  │
  ├─ 사용: 검색에서 가져온 정보 (searchId, q, rank 등)
  ├─ 사용: 새로 생성한 pvid, sdpVisitKey
  └─ referrer: 검색 URL
```

---

## 확인이 필요한 항목

- [ ] `webBuildNo` = `buildId` 동일한지 확인
- [ ] `libraryVersion`이 HTML에서 추출 가능한지 확인
- [ ] 상품 상세 HTML에서 추가로 추출할 정보 있는지 확인
