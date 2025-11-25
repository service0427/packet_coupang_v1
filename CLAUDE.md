# CLAUDE.md

Claude Code 가이드 문서 - Coupang Akamai Bypass System

## sudo
Tech1324!

# Bash에서 ! 문자 이스케이프 필요
PGPASSWORD=Tech1324\! psql -h mkt.techb.kr -U techb_pp -d v1_coupang

## Project Overview

Coupang Akamai Bypass System - curl-cffi를 사용한 TLS 핑거프린트 매칭 기반 Akamai 우회

**Core Approach**: Browser → Cookie 생성 → curl-cffi Packet Mode로 요청

## 주요 명령어

```bash
# 쿠키 생성 (프록시 자동 조회)
python3 coupang.py cookie
python3 coupang.py cookie -t 4 -l 2  # 4 스레드, 조합당 2개

# 상품 검색
python3 coupang.py search
python3 coupang.py search --product-id 12345678 --query "검색어"
python3 coupang.py search --random              # DB에서 랜덤 키워드
python3 coupang.py search --screenshot          # 스크린샷 저장

# 데이터베이스
python3 create-tables.py     # 테이블 생성
```

## Akamai 우회 핵심 조건 (2025-11-22 검증)

### 필수 요소

| 요소 | 필수 | 설명 |
|------|------|------|
| **Chrome 131+ JA3** | ✅ | 구버전 JA3 블랙리스트 (127-130 차단) |
| **Akamai 핑거프린트** | ✅ | HTTP/2 SETTINGS 매칭 |
| **extra_fp** | ✅ | signature_algorithms, tls_grease, tls_cert_compression |
| **sec-ch-ua 헤더** | ✅ | Client Hints 필수 |
| **신선한 쿠키** | ✅ | sensor_data 포함, `_abck`에 `~-1~` 포함 |
| **IP 바인딩** | ✅ | 쿠키 생성 IP = 요청 IP |

### JA3 블랙리스트 (검증됨)

| 버전 | JA3 Hash | 결과 |
|------|----------|------|
| Chrome 127 | `32796ee1a6a63426...` | ❌ BLOCKED |
| Chrome 130 | `44cc14164e512ea1...` | ❌ BLOCKED |
| Chrome 136 | `a3280c747d07805a...` | ✅ SUCCESS |

**안정적 버전**: 136, 138, 140, 142

### curl-cffi Custom TLS 사용법

**중요**: `impersonate` 파라미터는 사용하지 않음. 항상 DB의 custom TLS 프로파일 사용.

```python
from curl_cffi import requests

# DB에서 fingerprint 로드 후 사용
extra_fp = {
    'tls_signature_algorithms': sig_algs,  # 이름 리스트
    'tls_grease': True,
    'tls_permute_extensions': False,
    'tls_cert_compression': 'brotli',
}

headers = {
    'User-Agent': profile['user_agent'],
    'Accept': 'text/html,application/xhtml+xml,...',
    'Accept-Language': 'ko-KR,ko;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br, zstd',
    'Referer': 'https://www.coupang.com/',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Linux"',
    'sec-fetch-dest': 'document',
    'sec-fetch-mode': 'navigate',
    'sec-fetch-site': 'same-origin',
    'sec-fetch-user': '?1',
    'upgrade-insecure-requests': '1',
}

# Custom TLS 방식 (DB 프로파일 사용)
response = requests.get(
    url,
    headers=headers,
    cookies=cookies,
    ja3=ja3_text,        # DB fingerprints.ja3_text
    akamai=akamai_text,  # DB fingerprints.akamai_text
    extra_fp=extra_fp,   # DB fingerprints.signature_algorithms
    proxy=proxy,
    timeout=30
)
```

## IP 바인딩 정책

- 쿠키 생성 IP ≠ 요청 IP → 차단
- 프록시 사용 시: 브라우저와 curl-cffi 모두 동일 프록시 사용
- DB에 `proxy_ip` 저장 → 요청 시 검증

## proxy_url 저장 정책

```python
# 저장: host:port 만 (socks5:// 제외)
proxy_url = "123.45.67.89:1080"

# 사용: socks5:// 추가
proxy = f'socks5://{proxy_url}'
```

## Rate Limit

- ~150회/IP/일
- 요청 간 2-3초 딜레이 권장
- 연속 요청 시 IP 임시 차단 (30초~수분 후 복구)

## 디렉토리 구조

```
packet_coupang_v1/
├── coupang.py              # 메인 CLI (cookie, search)
├── create-tables.py        # DB 테이블 생성
│
├── lib/
│   ├── common/             # 공통 모듈
│   │   ├── db.py           # MySQL 연결
│   │   ├── proxy.py        # 프록시/쿠키 바인딩
│   │   └── fingerprint.py  # TLS 핑거프린트 관리
│   │
│   ├── browser/            # 브라우저 기반 (Playwright)
│   │   ├── cookie_cmd.py   # cookie 명령어 처리
│   │   └── cookie_generator.py  # 브라우저 쿠키 생성
│   │
│   ├── cffi/               # curl-cffi 기반
│   │   ├── request.py      # HTTP 요청 (Custom TLS)
│   │   ├── search.py       # 검색 모듈
│   │   ├── click.py        # 클릭 모듈
│   │   └── search_cmd.py   # search 명령어 처리
│   │
│   ├── extractor/          # HTML 파싱
│   │   ├── search_extractor.py   # 검색 결과 추출
│   │   └── detail_extractor.py   # 상품 상세 추출
│   │
│   └── screenshot/         # 스크린샷 모듈
│
├── chrome-versions/
│   ├── files/              # Chrome 실행 파일
│   └── tls/                # TLS 프로파일 (*.json)
│       ├── u22/            # Ubuntu 22.04
│       └── win11/          # Windows 11
│
├── reports/                # 검색 결과 리포트
└── config.json             # DB 설정
```

## 데이터베이스 스키마

### cookies 테이블 (핵심)
```sql
CREATE TABLE cookies (
    id INT AUTO_INCREMENT PRIMARY KEY,

    -- IP 바인딩
    proxy_ip VARCHAR(45) NOT NULL,      -- 프록시 외부 IP
    proxy_url VARCHAR(255),             -- host:port (socks5:// 제외)

    -- Chrome 버전
    chrome_version VARCHAR(50) NOT NULL,

    -- 쿠키 데이터
    cookie_data JSON NOT NULL,

    -- 사용 통계
    use_count INT DEFAULT 0,
    success_count INT DEFAULT 0,
    fail_count INT DEFAULT 0,

    -- 시간 (3개)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- 쿠키 생성
    locked_at TIMESTAMP NULL,           -- 호출 시작
    last_used_at TIMESTAMP NULL,        -- 사용 완료

    INDEX idx_proxy_ip (proxy_ip),
    INDEX idx_created_at (created_at),
    INDEX idx_use_count (use_count)
);
```

### fingerprints 테이블
```sql
CREATE TABLE fingerprints (
    id INT AUTO_INCREMENT PRIMARY KEY,
    chrome_version VARCHAR(50) NOT NULL,
    chrome_major INT NOT NULL,
    platform VARCHAR(20) NOT NULL,
    ja3_text TEXT NOT NULL,
    ja3_hash VARCHAR(64),
    akamai_text TEXT,
    akamai_hash VARCHAR(64),
    user_agent TEXT,
    signature_algorithms JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE KEY uk_version_platform (chrome_version, platform)
);
```

## TLS 프로파일

위치: `chrome-versions/tls/{platform}/{version}.json`

```json
{
  "ja3_text": "771,4865-4866-...",
  "ja3_hash": "a3280c747d07805a...",
  "akamai_text": "1:65536;2:0;...",
  "akamai_hash": "52d84b11737d980a...",
  "user_agent": "Mozilla/5.0...",
  "tls": {
    "extensions": [
      {
        "name": "signature_algorithms",
        "data": {
          "supported_signature_algorithms": [
            {"name": "ecdsa_secp256r1_sha256", "id": 1027}
          ]
        }
      }
    ]
  }
}
```

## 프록시 API

```bash
curl "http://mkt.techb.kr:3001/api/proxy/status?remain=60"
```

응답에서 `external_ip` 사용 가능:
```json
{
  "success": true,
  "proxies": [
    {
      "proxy": "123.45.67.89:1080",
      "external_ip": "111.222.333.444",
      "remain": 85
    }
  ]
}
```

## Success Criteria

- Response size > 50,000 bytes = SUCCESS
- Response size ≤ 50,000 bytes = BLOCKED (Challenge 페이지)

## 실행 흐름

### 쿠키 생성
```
coupang.py cookie
  → browser/cookie_cmd.py: 프록시 API 조회, 병렬 실행
    → browser/cookie_loop.py: Playwright 브라우저 실행
      → login.coupang.com 접속
      → Akamai 쿠키 생성 (_abck 등)
      → DB 저장 (proxy_ip 포함)
```

### 상품 검색
```
coupang.py search
  → cffi/search_cmd.py
    → common/proxy.py: IP 바인딩 쿠키 자동 선택
    → common/fingerprint.py: 랜덤 TLS 프로파일 선택
    → cffi/search.py: 점진적 배치 검색 (Tier 1→2→3)
    → cffi/click.py: 상품 발견 시 클릭
```
