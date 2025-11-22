# Coupang Akamai Bypass System

쿠팡 Akamai 보안 우회를 위한 TLS 핑거프린트 매칭 시스템

## 개요

curl-cffi를 사용하여 실제 Chrome 브라우저의 TLS 핑거프린트(JA3/Akamai)를 완벽하게 복제하여 Akamai 봇 탐지를 우회합니다.

**핵심 원리**: Browser → Cookie 생성 → curl-cffi Packet Mode로 요청

## 주요 기능

1. **쿠키 생성** (`cookie-generator.py`)
   - 병렬 브라우저 실행으로 대량 쿠키 생성
   - IP + Chrome 버전별 쿠키 관리
   - MySQL 데이터베이스 자동 저장

2. **상품 등수 체크** (`lib/rank-checker.py`)
   - 특정 상품의 검색 순위 확인
   - IP 바인딩 검증
   - 자동 재시도 로직
   - JSON 리포트 생성

## 요구사항

### 시스템
- Linux (Ubuntu 22.04 권장)
- Python 3.8+
- Node.js 18+
- MySQL 8.0+

### Python 패키지
```bash
pip3 install curl-cffi pymysql beautifulsoup4
```

### Node.js 패키지
```bash
npm install playwright
```

## 빠른 시작

### 1. 데이터베이스 설정

```bash
# 테이블 생성
python3 create-tables.py
```

### 2. 쿠키 생성

```bash
# 기본 실행 (2 스레드, 10회 반복)
python3 cookie-generator.py

# 커스텀 설정
python3 cookie-generator.py -t 4 -l 20  # 4 스레드, 20회 반복
```

### 3. 상품 등수 체크

```bash
# 기본 사용법
python3 lib/rank-checker.py --cookie-id 1 --product-id 12345678 --query "노트북"

# 클릭 테스트 포함
python3 lib/rank-checker.py --cookie-id 1 --product-id 12345678 --query "노트북" --click

# 페이지 수 조정 (기본: 13페이지)
python3 lib/rank-checker.py --cookie-id 1 --product-id 12345678 --query "노트북" --max-page 5
```

## 디렉토리 구조

```
packet_coupang_v1/
├── cookie-generator.py      # 메인: 병렬 쿠키 생성
├── lib/
│   ├── rank-checker.py      # 메인: 상품 등수 체크
│   ├── cookie-loop.js       # 브라우저 쿠키 루프
│   ├── cookie-db.js         # DB 저장 모듈
│   ├── db.py                # Python DB 모듈
│   ├── db.js                # Node.js DB 모듈
│   ├── traceid.py           # traceId 생성기
│   ├── cffi-db.py           # 개별 쿠키 테스트
│   ├── concurrent-test.py   # 동시 페이지 테스트
│   ├── product-click.py     # 상품 클릭 테스트
│   ├── product-finder.py    # 상품 검색기
│   ├── browser/             # 브라우저 관련 모듈
│   └── extractor/
│       └── product_extractor.py  # 상품 정보 추출
├── chrome-versions/
│   ├── files/               # Chrome 실행 파일
│   └── tls/                 # TLS 프로파일 (JA3, Akamai)
├── cookies/                 # 쿠키 파일 (legacy)
├── reports/                 # 검색 결과 리포트
└── docs/                    # 문서
```

## Akamai 우회 조건

### 필수 요소

| 요소 | 필수 | 설명 |
|------|------|------|
| Chrome 131+ JA3 | ✅ | 구버전 JA3 블랙리스트 (127-130 차단) |
| Akamai 핑거프린트 | ✅ | HTTP/2 SETTINGS 매칭 |
| extra_fp | ✅ | signature_algorithms, tls_grease, tls_cert_compression |
| sec-ch-ua 헤더 | ✅ | Client Hints 필수 |
| 신선한 쿠키 | ✅ | sensor_data 포함 |
| IP 바인딩 | ✅ | 쿠키 생성 IP = 요청 IP |

### 안정적인 Chrome 버전

- 136, 138, 140, 142 (검증됨)

### 차단된 버전

- Chrome 127-130 (JA3 블랙리스트)

## 데이터베이스 스키마

### fingerprints 테이블
```sql
CREATE TABLE fingerprints (
    id INT PRIMARY KEY AUTO_INCREMENT,
    chrome_version VARCHAR(50),
    chrome_major INT,
    platform VARCHAR(20),
    ja3_text TEXT,
    ja3_hash VARCHAR(64),
    akamai_text TEXT,
    akamai_hash VARCHAR(64),
    user_agent TEXT,
    signature_algorithms JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### cookies 테이블
```sql
CREATE TABLE cookies (
    id INT PRIMARY KEY AUTO_INCREMENT,
    chrome_version VARCHAR(50),
    proxy_url VARCHAR(255),
    proxy_ip VARCHAR(45),
    cookie_data JSON,
    abck_valid BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used TIMESTAMP,
    use_count INT DEFAULT 0,
    status ENUM('active', 'expired', 'blocked') DEFAULT 'active'
);
```

## IP 바인딩 정책

- 쿠키 생성 시 사용한 IP와 요청 시 IP가 반드시 일치해야 함
- 모바일 IP는 ~10,000개가 롤링되므로, IP 불일치 시 나중에 재사용 가능
- 프록시 사용 시 브라우저와 curl-cffi 모두 동일 프록시 사용

## Rate Limit

- ~150회/IP/일
- 요청 간 2-3초 딜레이 권장
- 연속 요청 시 IP 임시 차단 (30초~수분 후 복구)

## 리포트 형식

검색 결과는 `reports/` 디렉토리에 JSON 형식으로 저장됩니다:

```json
{
  "timestamp": "2024-11-22 20:51:00",
  "cookie_id": 1,
  "chrome_version": "136.0.7103.113",
  "proxy_ip": "123.45.67.89",
  "query": "노트북",
  "trace_id": "mha2ebbm",
  "list_size": 72,
  "target_product_id": "12345678",
  "found": true,
  "page": 3,
  "rank": 25,
  "product": {
    "productId": "12345678",
    "itemId": "87654321",
    "vendorItemId": "11111111",
    "name": "상품명...",
    "url": "/vp/products/...",
    "full_url": "https://www.coupang.com/vp/products/..."
  },
  "total_products": 936,
  "all_products": [...]
}
```

## 문제 해결

### 403 BLOCKED
- JA3/Akamai 핑거프린트 확인
- Chrome 버전 131+ 사용
- 쿠키 유효성 확인

### IP 불일치
- 프록시 IP 확인
- 쿠키 재생성 필요

### Challenge 페이지 (1,175 bytes)
- 쿠키 만료 또는 손상
- 새 쿠키로 재시도

## 참고 문서

- `CLAUDE.md` - Claude Code 가이드
- `docs/CURL_CFFI_TEST_RESULTS.md` - curl-cffi 테스트 결과
- `docs/IP_BINDING_TEST_RESULTS.md` - IP 바인딩 테스트 결과

## 라이선스

MIT License
