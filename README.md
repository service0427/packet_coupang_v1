# Coupang Rank Check API

쿠팡 상품 순위 체크 API - Akamai TLS 핑거프린트 매칭

## 시스템 구성

```
외부 쿠키 생성 → Cookie Daemon (5151) → Rank API (8088)
                  쿠키+프록시 관리         순위 체크
```

## 서버 실행

```bash
cd /home/tech/packet_coupang_v1/rank_api
python3 server.py                    # 기본 (포트 8088)
python3 server.py --port 8888        # 포트 변경
python3 server.py --workers 30       # 워커 수 변경
```

## API 사용법

### 순위 체크

```bash
# 한 줄 (복사용)
curl -sX POST http://localhost:8088/api/rank/check -H "Content-Type: application/json" -d '{"keyword":"탄소매트","product_id":"9112018393"}' | jq

# 전체 파라미터
curl -sX POST http://localhost:8088/api/rank/check -H "Content-Type: application/json" -d '{"keyword":"탄소매트","product_id":"9112018393","item_id":"12345","vendor_item_id":"67890"}' | jq
```

> `-H "Content-Type: application/json"` 필수 (curl 기본값이 form-urlencoded)

#### 요청 파라미터

| 필드 | 필수 | 타입 | 설명 |
|------|:----:|------|------|
| keyword | O | string | 검색어 |
| product_id | O | string | 상품 ID |
| item_id | X | string | 아이템 ID |
| vendor_item_id | X | string | 벤더 아이템 ID |
| max_page | X | int | 최대 검색 페이지 (1-20, 기본: 13) |

#### 응답 예시 (성공)

```json
{
  "success": true,
  "data": {
    "keyword": "탄소매트",
    "product_id": "9112018393",
    "found": true,
    "rank": 15,
    "page": 1,
    "rating": 4.8,
    "review_count": 1234,
    "checked_at": "2025-01-15T12:30:45+00:00"
  },
  "meta": {
    "pages_searched": 1,
    "elapsed_ms": 2340,
    "profile": "chrome_131_win",
    "proxy_ip": "123.45.67.89",
    "match_type": "exact",
    "id_match_type": "product_only"
  },
  "error": null
}
```

#### 응답 예시 (실패)

```json
{
  "success": false,
  "data": null,
  "meta": {
    "pages_searched": 0,
    "elapsed_ms": 5086,
    "profile": "n935l_138",
    "proxy_ip": "175.223.39.50",
    "match_type": "new_exact",
    "id_match_type": null
  },
  "error": {
    "code": "BLOCKED",
    "message": "Request blocked",
    "detail": "PAGE_ERR_1"
  }
}
```

#### ID 매칭 타입 (id_match_type)

상품 검색 시 ID 매칭 우선순위:

| 순위 | 타입 | 매칭 조건 |
|:----:|------|----------|
| 1 | full_match | product_id + item_id + vendor_item_id |
| 2 | product_vendor | product_id + vendor_item_id |
| 3 | product_item | product_id + item_id |
| 4 | product_only | product_id만 |
| 5 | vendor_only | vendor_item_id만 |
| 6 | item_only | item_id만 |

### 서버 상태

```bash
curl -s http://localhost:8088/api/status | jq
```

```json
{
  "status": "running",
  "workers": 20,
  "active": 5,
  "queue_size": 0,
  "uptime_seconds": 3600
}
```

## 에러 코드

| 코드 | 설명 |
|------|------|
| INVALID_INPUT | 필수 파라미터 누락 |
| NO_COOKIE | 사용 가능한 쿠키 없음 |
| NO_TLS | TLS 프로필 없음 |
| BLOCKED | 요청 차단됨 |
| INTERNAL_ERROR | 내부 오류 |

## Akamai 우회 조건

| 요소 | 필수 | 설명 |
|------|:----:|------|
| Chrome 131+ JA3 | O | 구버전 블랙리스트 (127-130 차단) |
| Akamai 핑거프린트 | O | HTTP/2 SETTINGS 매칭 |
| extra_fp | O | signature_algorithms, tls_grease |
| sec-ch-ua 헤더 | O | Client Hints 필수 |
| 신선한 쿠키 | O | `_abck`에 `~-1~` 포함 |
| IP 바인딩 | O | 쿠키 생성 IP = 요청 IP (/24 서브넷) |

## Success Criteria

- Response size > 50,000 bytes = SUCCESS
- Response size <= 50,000 bytes = BLOCKED
