# Coupang Rank Check System

쿠팡 상품 순위 체크 시스템 - Akamai TLS 핑거프린트 매칭

## 설치

```bash
# 1. 클론
git clone https://github.com/service0427/packet_coupang_v1.git
cd packet_coupang_v1

# 2. Python 의존성 설치
pip3 install -r requirements.txt

# 3. logs 폴더 생성
mkdir -p logs/work
```

## 실행

### 기본 모드 (쿠키+프록시 사용)

```bash
# 워커 실행 (별도 서버 불필요!)
python3 work.py rank -p 3 2>&1 | tee -a logs/work/$(date +%Y%m%d).log
```

### 직접 연결 모드 (쿠키/프록시 미사용)

```bash
# 단일 실행
python3 work_direct.py rank

# N번 실행
python3 work_direct.py rank -n 100

# 병렬 실행
python3 work_direct.py rank -p 5

# 무한 반복
python3 work_direct.py rank --loop
```

> **주의**: 직접 연결 모드는 본인 IP로 요청하므로 대량 요청 시 IP 차단 위험이 있습니다.

## 시스템 구조

### 기본 모드 (work.py)

```
work.py (워커)
    │
    ├── GET  mkt.techb.kr:3302/api/work/allocate   # 작업 할당
    │
    ├── lib/api/rank_checker.py (직접 호출)        # 순위 체크
    │         │
    │         └── GET mkt.techb.kr:5151/api/cookies/allocate  # 쿠키+프록시
    │
    └── POST mkt.techb.kr:3302/api/work/result     # 결과 보고
```

### 직접 연결 모드 (work_direct.py)

```
work_direct.py (워커)
    │
    ├── GET  mkt.techb.kr:3302/api/work/allocate   # 작업 할당
    │
    ├── lib/api/rank_checker_direct.py             # 순위 체크 (직접 연결)
    │         │
    │         └── Chrome 143 Mobile TLS 핑거프린트  # 쿠키/프록시 없음
    │
    └── POST mkt.techb.kr:3302/api/work/result     # 결과 보고
```

## 디렉토리 구조

```
packet_coupang_v1/
├── work.py                # 워커 (쿠키+프록시 모드)
├── work_direct.py         # 워커 (직접 연결 모드)
├── requirements.txt       # Python 의존성
├── CLAUDE.md              # 상세 가이드
└── lib/
    ├── api/
    │   ├── rank_checker.py        # 순위 체크 (쿠키+프록시)
    │   └── rank_checker_direct.py # 순위 체크 (직접 연결)
    ├── common/                    # 공통 유틸리티
    │   ├── fingerprint.py         # TLS 프로필 (JSON)
    │   ├── proxy.py               # 프록시/쿠키 API
    │   └── cookie.py
    ├── work/
    │   ├── search.py              # 검색 모듈
    │   ├── request.py             # HTTP 요청
    │   └── tls_profiles.json      # 38개 TLS 프로필
    └── extractor/
        └── search_extractor.py
```

## 모드 비교

| | work.py (기본) | work_direct.py (직접) |
|---|---|---|
| 쿠키 | 5151 API | 미사용 |
| 프록시 | SOCKS5 | 미사용 |
| TLS | tls_profiles.json (38개) | Chrome 143 고정 |
| IP | 프록시 IP | 본인 IP |
| 차단 위험 | 낮음 | 높음 |

## 외부 API 의존성

| API | 포트 | 용도 | 모드 |
|-----|------|------|------|
| mkt.techb.kr | 3302 | 작업 할당/결과 보고 | 공통 |
| mkt.techb.kr | 5151 | 쿠키+프록시 할당 | 기본 모드만 |

## Akamai 우회 조건

| 요소 | 설명 |
|------|------|
| Chrome 131+ | 구버전 블랙리스트 (127-130 차단) |
| JA3/Akamai FP | TLS/HTTP2 핑거프린트 매칭 |
| sec-ch-ua | Client Hints 헤더 필수 |
| IP 바인딩 | 쿠키 생성 IP = 요청 IP (/24) |

## 출력 로그 형식

```
[HH:MM:SS.ms][WID] ✅ P 1 # 13 | 175.223.14.91 | 2.08s | C:7140630 NE 0s [FULL] R:OK | P:9101923326 I:26757401692 V:93728393953 | 키워드
```

| 필드 | 설명 |
|------|------|
| WID | 워커 ID |
| P/# | 페이지/순위 |
| IP | 프록시 IP |
| C: | 쿠키 ID |
| NE/NS | 쿠키 매칭 (Exact/Subnet) |
| FULL | ID 매칭 타입 |
| R:OK | 결과 보고 상태 |
