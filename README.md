# Coupang Akamai Bypass System

쿠팡 Akamai 보안 우회를 위한 TLS 핑거프린트 매칭 시스템

## 개요

curl-cffi를 사용하여 실제 Chrome 브라우저의 TLS 핑거프린트(JA3/Akamai)를 완벽하게 복제하여 Akamai 봇 탐지를 우회합니다.

**핵심 원리**: Browser → Cookie 생성 → curl-cffi Packet Mode로 요청

## 주요 명령어

### 쿠키 생성
```bash
# 기본 실행 (프록시 자동 조회)
python3 coupang.py cookie

# 커스텀 설정
python3 coupang.py cookie -t 4 -l 2    # 4 스레드, 조합당 2개
python3 coupang.py cookie -v 136       # Chrome 136 고정
```

### 상품 등수 체크
```bash
# 기본 (호박 달빛식혜)
python3 coupang.py rank

# 커스텀 설정
python3 coupang.py rank --cookie-id 100 --product-id 12345678 --query "검색어"
python3 coupang.py rank --no-click     # 클릭 없이 순위만
```

### 자동 실행
```bash
# 신규 쿠키 자동 병렬 실행
python3 run_parallel.py

# 쿠키 재사용 테스트
python3 run_reuse.py --remain 60
```

## 디렉토리 구조

```
packet_coupang_v1/
├── coupang.py              # 메인 CLI (cookie, rank)
├── run_parallel.py         # 신규 쿠키 자동 병렬 실행
├── run_reuse.py            # 쿠키 재사용 테스트
├── create-tables.py        # DB 테이블 생성
│
├── lib/
│   ├── cookie_cmd.py       # cookie 명령어 처리
│   ├── cookie_loop.py      # 브라우저 쿠키 생성 루프
│   ├── rank_cmd.py         # rank 명령어 처리
│   ├── common.py           # 공통 유틸리티
│   ├── db.py               # MySQL 연결
│   ├── traceid.py          # traceId 생성기
│   ├── realistic_click.py  # 상품 클릭 시뮬레이션
│   └── extractor/
│       └── product_extractor.py  # 상품 정보 추출
│
├── click-tracker/
│   ├── monitor_click.py    # Playwright로 클릭 모니터링
│   └── click_simulator.py  # curl-cffi로 클릭 시뮬레이션
│
├── chrome-versions/
│   ├── files/              # Chrome 실행 파일
│   └── tls/                # TLS 프로파일 (JA3, Akamai)
│       ├── u22/            # Ubuntu 22.04
│       └── win11/          # Windows 11
│
├── reports/                # 검색 결과 리포트
├── config.json             # DB 설정
└── CLAUDE.md               # Claude Code 가이드
```

## 파일 용도 상세

### 핵심 실행 파일

| 파일 | 용도 |
|------|------|
| `coupang.py` | 메인 CLI - `cookie`/`rank` 서브커맨드 |
| `run_parallel.py` | 신규 쿠키(120초 이내) 자동 병렬 rank 실행 |
| `run_reuse.py` | 이전 쿠키 재사용 테스트 (10분+ 경과) |

### lib/ 모듈

| 파일 | 용도 |
|------|------|
| `cookie_cmd.py` | 프록시 조회 → 브라우저 쿠키 생성 병렬 실행 |
| `cookie_loop.py` | Playwright로 login.coupang.com 접속 → 쿠키 저장 |
| `rank_cmd.py` | 검색 → 상품 찾기 → 클릭 (curl-cffi) |
| `common.py` | DB 조회, HTTP 요청, IP 검증 |
| `db.py` | MySQL 연결 (context manager) |
| `traceid.py` | 쿠팡 traceId 생성 |
| `realistic_click.py` | 상품 클릭 + sdkClick API 호출 |

### click-tracker/ (개발/분석용)

| 파일 | 용도 |
|------|------|
| `monitor_click.py` | Playwright로 실제 브라우저 요청 추적 |
| `click_simulator.py` | curl-cffi로 단독 클릭 테스트 |

## 데이터베이스 스키마

### cookies 테이블
```sql
CREATE TABLE cookies (
    id INT AUTO_INCREMENT PRIMARY KEY,

    -- IP 바인딩 (핵심!)
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

    -- 시간
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
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
- **권장**: 136, 138, 140, 142
- **차단**: 127, 128, 129, 130 (JA3 블랙리스트)

## IP 바인딩 정책

- **쿠키 생성 IP = 요청 IP** 필수
- 프록시 사용 시: 브라우저와 curl-cffi 모두 동일 프록시
- DB에 `proxy_ip` 저장 → 요청 시 검증

### proxy_url 저장 형식
```python
# 저장: host:port 만
proxy_url = "123.45.67.89:1080"

# 사용: socks5:// 추가
proxy = f'socks5://{proxy_url}'
```

## Rate Limit

- ~150회/IP/일
- 요청 간 2-3초 딜레이 권장
- 연속 요청 시 IP 임시 차단 (30초~수분)

## curl-cffi 사용법

```python
from curl_cffi import requests

# extra_fp 설정
extra_fp = {
    'tls_signature_algorithms': sig_algs,  # 이름 리스트
    'tls_grease': True,
    'tls_permute_extensions': False,
    'tls_cert_compression': 'brotli',
}

# 요청
response = requests.get(
    url,
    headers=headers,
    cookies=cookies,
    ja3=ja3_text,        # JA3 문자열
    akamai=akamai_text,  # Akamai 문자열
    extra_fp=extra_fp,
    proxy=proxy,
    timeout=30
)
```

### impersonate 사용 금지
```python
# ❌ 잘못됨 - JA3가 실제 브라우저와 다름
response = requests.get(url, impersonate='chrome136')

# ✅ 올바름 - 직접 JA3/Akamai 지정
response = requests.get(url, ja3=ja3_text, akamai=akamai_text)
```

## 실행 흐름

### 1. 쿠키 생성 흐름
```
coupang.py cookie
  → lib/cookie_cmd.py: 프록시 API 조회, 병렬 실행
    → lib/cookie_loop.py: Playwright 브라우저 실행
      → login.coupang.com 접속
      → Akamai 쿠키 생성 (_abck 등)
      → DB 저장 (proxy_ip 포함)
```

### 2. Rank 체크 흐름
```
coupang.py rank
  → lib/rank_cmd.py
    → DB에서 쿠키/핑거프린트 로드
    → IP 바인딩 검증
    → 검색 페이지 병렬 요청 (curl-cffi)
    → 상품 발견 시 클릭
      → lib/realistic_click.py: 상품 페이지 + sdkClick API
    → reports/ 에 결과 저장
```

### 3. 자동 실행 흐름
```
run_parallel.py
  → 신규 쿠키 조회 (created_at 120초 이내)
  → locked_at 설정 (중복 방지)
  → ProcessPoolExecutor로 rank 병렬 실행
  → 통계 업데이트 (success_count, fail_count)
```

## 프록시 API

```bash
# 프록시 상태 조회
curl "http://mkt.techb.kr:3001/api/proxy/status?remain=60"
```

응답:
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
  "actual_rank": 25,
  "click": {
    "success": true,
    "product_page": {"status": 200, "size": 150000}
  },
  "total_products": 936,
  "all_products": [...]
}
```

## 문제 해결

### 403 BLOCKED
- JA3/Akamai 핑거프린트 확인
- Chrome 버전 131+ 사용
- 쿠키 유효성 확인 (`_abck`에 `~-1~` 포함)

### IP 불일치
- `proxy_ip`와 현재 프록시 IP 비교
- 쿠키 재생성 필요

### Challenge 페이지 (1,175 bytes)
- 쿠키 만료 또는 손상
- 새 쿠키로 재시도

### BrokenProcessPool
- 프로세스 타임아웃
- 병렬 수 줄이기 또는 재시도

## 요구사항

### 시스템
- Linux (Ubuntu 22.04 권장)
- Python 3.8+
- MySQL 8.0+
- Xvfb (헤드리스 브라우저용)

### Python 패키지
```bash
pip3 install curl-cffi pymysql beautifulsoup4 playwright requests
python -m playwright install chromium
```

## 라이선스

MIT License
