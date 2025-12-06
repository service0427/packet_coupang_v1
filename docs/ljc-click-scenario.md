# LJC 클릭 시나리오 (검색결과 1페이지)

> `python3 work.py click` 실행 시 실제 브라우저처럼 동작하기 위한 요청 시나리오

## 전체 흐름 요약

```
[1] 검색 페이지 요청 (HTML)
     ↓
[2] srp_view_impression (검색결과 페이지 노출)
     ↓
[3] srp_product_unit_impression (타겟 상품 노출)
     ↓
[4] click_search_product (상품 클릭)
     ↓
[5] 상품 상세 페이지 요청 (HTML)
     ↓
[6] sdp_product_page_view (상품 상세 노출)
```

---

## Step 1: 검색 페이지 요청 (HTML)

### Request
```
GET https://www.coupang.com/np/search?component=&q={keyword}&traceId={traceId}&channel=user
```

### traceId 생성
```python
# lib/work/request.py - generate_trace_id()
import time
import string

def generate_trace_id():
    timestamp_ms = int(time.time() * 1000)
    base36_chars = string.digits + string.ascii_lowercase
    result = []
    ts = timestamp_ms
    while ts > 0:
        result.append(base36_chars[ts % 36])
        ts //= 36
    return ''.join(reversed(result))  # 예: 'miocw5ud' (8자리)
```

### Headers
```
User-Agent: Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 ...
sec-ch-ua: "Chromium";v="142", "Google Chrome";v="142", "Not_A Brand";v="99"
sec-ch-ua-mobile: ?1
sec-ch-ua-platform: "Android"
Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8
Accept-Language: ko-KR,ko;q=0.9
Accept-Encoding: gzip, deflate, br
Referer: https://www.coupang.com/
```

### Response에서 추출할 정보
- `searchId`: HTML 또는 JSON에서 추출
- 타겟 상품의 `rank`, `itemId`, `vendorItemId`
- 전체 상품 수 (`searchCount`)

### 생성할 ID
- `pvid`: UUID v4 (이 페이지의 고유 ID, 이후 모든 이벤트에서 사용)

---

## Step 2: srp_view_impression (검색결과 페이지 노출)

> 검색 페이지 로드 직후 전송

### Request
```
POST https://ljc.coupang.com/api/v2/submit?appCode=coupang&market=KR
Content-Type: text/plain
```

### Payload
```json
{
  "common": {
    "platform": "mweb",
    "pcid": "{쿠키에서 추출}",
    "memberSrl": "",
    "libraryVersion": "0.13.16",
    "lang": "ko-KR",
    "resolution": "384x832",
    "eventTime": "{ISO 8601}",
    "webBuildNo": "{빌드해시}",
    "web": {
      "pvid": "{생성한 UUID}",
      "rvid": "",
      "url": "https://www.coupang.com/np/search?component=&q={keyword}&traceId={traceId}&channel=user",
      "referrer": "https://www.coupang.com/"
    }
  },
  "meta": {
    "schemaId": 14809,
    "schemaVersion": 5
  },
  "data": {
    "domain": "srp",
    "logCategory": "page",
    "logType": "page",
    "pageName": "srp",
    "eventName": "srp_view_impression",
    "searchId": "{searchId}",
    "q": "{keyword}",
    "searchCount": {검색결과수},
    "page": "1",
    "listSize": "36"
  },
  "extra": {
    "sentTime": "{ISO 8601}",
    "next": true
  }
}
```

---

## Step 3: srp_product_unit_impression (타겟 상품 노출)

> 타겟 상품이 화면에 노출되었음을 알림 (클릭 전 필수!)

### Request
```
POST https://ljc.coupang.com/api/v2/submit?appCode=coupang&market=KR
Content-Type: text/plain
```

### Payload
```json
{
  "common": {
    "platform": "mweb",
    "pcid": "{pcid}",
    "memberSrl": "",
    "libraryVersion": "0.13.16",
    "lang": "ko-KR",
    "resolution": "384x832",
    "eventTime": "{ISO 8601}",
    "webBuildNo": "{빌드해시}",
    "web": {
      "pvid": "{pvid}",
      "rvid": "",
      "url": "https://www.coupang.com/np/search?component=&q={keyword}&traceId={traceId}&channel=user",
      "referrer": "https://www.coupang.com/"
    }
  },
  "meta": {
    "schemaId": 14741,
    "schemaVersion": 32
  },
  "data": {
    "domain": "srp",
    "logCategory": "impression",
    "logType": "impression",
    "pageName": "srp",
    "eventName": "srp_product_unit_impression",
    "searchId": "{searchId}",
    "searchRank": {rank},
    "rank": {rank},
    "query": "{keyword}",
    "itemId": {itemId},
    "vendorItemId": {vendorItemId},
    "productId": {productId},
    "viewType": "",
    "exposureTimestamp": "{ISO 8601}",
    "isNewReleaseDateAttribute": "false",
    "isRluxString": "false",
    "isFarfetchString": "false",
    "isBestAwardsBadge": "False",
    "bestAwardsBadgeType": "N",
    "badges": "labelArea,benefit,delivery",
    "isLowStockMessage": "False",
    "lowStockMessageNumber": "N",
    "extendPdd": false,
    "promiseDeliveryDate": "",
    "remoteAreaShippingFeeBadge": "False"
  },
  "extra": {
    "sentTime": "{ISO 8601}",
    "next": true,
    "legacyPlatform": "mweb"
  }
}
```

### 시간 간격
- Step 2 이후 **2~5초** 대기 (스크롤 시뮬레이션)

---

## Step 4: click_search_product (상품 클릭)

> 검색결과에서 상품을 클릭

### Request
```
POST https://ljc.coupang.com/api/v2/submit?appCode=coupang&market=KR
Content-Type: text/plain
```

### Payload
```json
{
  "common": {
    "platform": "mweb",
    "pcid": "{pcid}",
    "memberSrl": "",
    "libraryVersion": "0.13.16",
    "lang": "ko-KR",
    "resolution": "384x832",
    "eventTime": "{ISO 8601}",
    "webBuildNo": "{빌드해시}",
    "web": {
      "pvid": "{pvid}",
      "rvid": "",
      "url": "https://www.coupang.com/np/search?component=&q={keyword}&traceId={traceId}&channel=user",
      "referrer": "https://www.coupang.com/"
    }
  },
  "meta": {
    "schemaId": 124,
    "schemaVersion": 47
  },
  "data": {
    "logCategory": "event",
    "logType": "click",
    "eventName": "click_search_product",
    "searchId": "{searchId}",
    "searchRank": {rank},
    "rank": {rank},
    "itemId": "{itemId}",
    "vendorItemId": "{vendorItemId}",
    "productId": "{productId}",
    "pageName": "srp",
    "domain": "srp",
    "q": "{keyword}",
    "searchCount": {searchCount},
    "page": "1",
    "listSize": "36",
    "filterKey": "component=&q={keyword_encoded}&channel=user",
    "isCcidEligible": false,
    "displayCcidBadge": false,
    "wowOnlyInstantDiscountRate": -1,
    "snsDiscountRate": -1,
    "isLoyaltyMember": false,
    "hasAsHandymanBadge": false,
    "sortIsChecked": "Y",
    "hasLastestMedelBadge": false,
    "isInvalid": "",
    "isRlux": false,
    "isFarfetch": false,
    "isBestAwardsBadge": "False",
    "bestAwardsBadgeType": "N",
    "isLowStockMessage": "False",
    "lowStockMessageNumber": "N"
  },
  "extra": {
    "sentTime": "{ISO 8601}",
    "next": true,
    "legacyPlatform": "mweb"
  }
}
```

### 시간 간격
- Step 3 이후 **3~10초** 대기 (사용자가 상품을 보고 클릭하는 시간)

---

## Step 5: 상품 상세 페이지 요청 (HTML)

> 클릭 이벤트 전송 직후 상세 페이지 요청

### Request
```
GET https://www.coupang.com/vp/products/{productId}?itemId={itemId}&vendorItemId={vendorItemId}&q={keyword}&searchId={searchId}&sourceType=search&rank={rank}
```

### Headers
```
User-Agent: Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 ...
sec-ch-ua: "Chromium";v="142", "Google Chrome";v="142", "Not_A Brand";v="99"
sec-ch-ua-mobile: ?1
sec-ch-ua-platform: "Android"
Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8
Accept-Language: ko-KR,ko;q=0.9
Accept-Encoding: gzip, deflate, br
Referer: https://www.coupang.com/np/search?component=&q={keyword}&traceId={traceId}&channel=user
```

### 생성할 ID
- `sdpVisitKey`: 랜덤 문자열 18자 (예: `ihek33act0b8rfqr5c`)
- 새로운 `pvid`: UUID v4 (상세 페이지용)

---

## Step 6: sdp_product_page_view (상품 상세 노출)

> 상품 상세 페이지 로드 직후 전송

### Request
```
POST https://ljc.coupang.com/api/v2/submit?appCode=coupang&market=KR
Content-Type: text/plain
```

### Payload
```json
{
  "common": {
    "platform": "mweb",
    "pcid": "{pcid}",
    "memberSrl": "",
    "libraryVersion": "0.13.16",
    "lang": "ko-KR",
    "resolution": "384x832",
    "eventTime": "{ISO 8601}",
    "webBuildNo": "{빌드해시}",
    "web": {
      "pvid": "{새로운 pvid}",
      "rvid": "",
      "url": "https://www.coupang.com/vp/products/{productId}?itemId={itemId}&vendorItemId={vendorItemId}&q={keyword}&searchId={searchId}&sourceType=search&rank={rank}",
      "referrer": "https://www.coupang.com/np/search?component=&q={keyword}&traceId={traceId}&channel=user"
    }
  },
  "meta": {
    "schemaId": 132,
    "schemaVersion": 68
  },
  "data": {
    "logCategory": "page",
    "logType": "page",
    "eventName": "sdp_product_page_view",
    "domain": "sdp",
    "pageName": "sdp",
    "productId": {productId},
    "itemId": {itemId},
    "vendorItemId": {vendorItemId},
    "sdpVisitKey": "{sdpVisitKey}",
    "productIs3P": false,
    "q": "{keyword}",
    "searchId": "{searchId}",
    "rank": {rank},
    "sourceType": "search",
    "sdpType": "rocketWow",
    "isLoyaltyMember": false
  },
  "extra": {
    "sentTime": "{ISO 8601}",
    "next": true
  }
}
```

---

## 공통 요소

### pcid 추출
쿠키에서 `PCID` 값 사용 (예: `17646665147076318953008`)

### webBuildNo
HTML에서 추출하거나 고정값 사용:
- `98ea500683e805921df3ec29eff9c631aa487d5f`
- `4355d016566f35bf5821870cc1ef3f37f3ce466d`

### pvid 생성
```python
import uuid
pvid = str(uuid.uuid4())
```

### sdpVisitKey 생성
```python
import random
import string
sdpVisitKey = ''.join(random.choices(string.ascii_lowercase + string.digits, k=18))
```

### eventTime / sentTime
```python
from datetime import datetime, timezone
event_time = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.') + f'{datetime.now().microsecond // 1000:03d}Z'
```

### LJC 요청 Headers
```
Content-Type: text/plain
Accept: */*
Accept-Language: ko-KR,ko;q=0.9
sec-ch-ua: "Chromium";v="142", "Google Chrome";v="142", "Not_A Brand";v="99"
sec-ch-ua-mobile: ?1
sec-ch-ua-platform: "Android"
sec-fetch-dest: empty
sec-fetch-mode: cors
sec-fetch-site: same-site
Referer: https://www.coupang.com/
```

---

## 시간 흐름 예시

```
T+0.0s   [1] 검색 페이지 요청
T+0.5s   [2] srp_view_impression
T+3.0s   [3] srp_product_unit_impression (스크롤)
T+8.0s   [4] click_search_product
T+8.1s   [5] 상품 상세 페이지 요청
T+8.6s   [6] sdp_product_page_view
```

---

## 구현 체크리스트

- [ ] `lib/work/ljc.py` 모듈 생성
  - [ ] `generate_pvid()` - UUID 생성
  - [ ] `generate_sdp_visit_key()` - 18자 랜덤 문자열
  - [ ] `get_event_time()` - ISO 8601 포맷
  - [ ] `build_common(pcid, pvid, url, referrer)` - 공통 필드
  - [ ] `send_srp_view_impression()` - Step 2
  - [ ] `send_srp_product_unit_impression()` - Step 3
  - [ ] `send_click_search_product()` - Step 4
  - [ ] `send_sdp_product_page_view()` - Step 6

- [ ] `lib/work/click.py` 수정
  - [ ] LJC 이벤트 전송 통합

- [ ] 테스트
  - [ ] 단일 상품 클릭 테스트
  - [ ] HAR 캡처하여 실제 브라우저와 비교
