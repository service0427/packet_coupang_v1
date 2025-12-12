# CLAUDE.md

Coupang Akamai Bypass System - curl-cffi 기반 TLS 핑거프린트 매칭

## 실행 방법

```bash
# 워커 실행 (별도 서버 불필요!)
python3 work.py rank -p 3 2>&1 | tee -a logs/work/$(date +%Y%m%d).log
```

## 핵심 조건

| 요소 | 필수 | 설명 |
|------|------|------|
| Chrome 131+ JA3 | ✅ | 구버전 블랙리스트 (127-130 차단) |
| Akamai 핑거프린트 | ✅ | HTTP/2 SETTINGS 매칭 |
| extra_fp | ✅ | signature_algorithms, tls_grease |
| sec-ch-ua 헤더 | ✅ | Client Hints 필수 |
| 신선한 쿠키 | ✅ | `_abck`에 `~-1~` 포함 |
| IP 바인딩 | ✅ | 쿠키 생성 IP = 요청 IP (/24 서브넷) |

## Success Criteria

- Response size > 50,000 bytes = SUCCESS
- Response size ≤ 50,000 bytes = BLOCKED (Challenge 페이지)

## Work API (mkt.techb.kr:3302)

작업 할당 및 결과 보고 API.

```bash
# 작업 할당
curl "http://mkt.techb.kr:3302/api/work/allocate?work_type=rank"
```

## Cookie API (mkt.techb.kr:5151)

쿠키+프록시 할당 API.

```bash
# 쿠키 할당
curl "http://mkt.techb.kr:5151/api/cookies/allocate?minutes=120&type=mobile"
```

## 디렉토리 구조

```
lib/
├── api/
│   └── rank_checker.py     # 순위 체크 핵심 로직
├── common/                 # 공통 유틸리티
│   ├── fingerprint.py      # TLS 프로필 (JSON 기반)
│   ├── proxy.py            # 프록시/쿠키 API
│   └── cookie.py           # 쿠키 유틸리티
├── work/                   # 검색/요청 로직
│   ├── search.py           # 검색 실행
│   ├── request.py          # curl-cffi 요청
│   └── tls_profiles.json   # TLS 프로필 데이터
└── extractor/              # HTML 파싱
    └── search_extractor.py
```

## TLS 프로필

`lib/work/tls_profiles.json`에 38개 프로필 저장 (Chrome 131+)

- Mobile: 5개 (Android)
- PC: 33개 (Windows/Linux)

## 외부 API 의존성

| API | 용도 |
|-----|------|
| mkt.techb.kr:3302 | 작업 할당/결과 보고 |
| mkt.techb.kr:5151 | 쿠키+프록시 할당 |
