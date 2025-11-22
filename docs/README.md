# Documentation

**Coupang Akamai Bypass - Chrome Build TLS Testing System**

쿠팡 Akamai Bot Manager를 우회하는 Chrome 빌드 버전을 찾는 프로젝트

---

## 📚 핵심 문서 (8개)

### 1. 정책 & 매뉴얼 (필독)

#### [PROJECT_POLICY.md](../PROJECT_POLICY.md) ⭐⭐⭐
**절대 규칙 - 반드시 읽기**
- ❌ **NEVER** use curl-cffi impersonate profiles
- ✅ **ALWAYS** use direct JA3 + Akamai strings
- TLS 프로파일 수집 이유
- 프로젝트 구조 정책
- 코딩 표준 및 금지사항

#### [TLS_DIRECT_USAGE_MANUAL.md](TLS_DIRECT_USAGE_MANUAL.md) ⭐⭐
**Direct TLS 사용법 완전 가이드**
- Why Direct TLS? (impersonate 문제점)
- TLS 프로파일 수집 시스템
- JA3/Akamai 문자열 형식
- `src/tls_custom_request.py` 사용법
- `find-allowed-chrome-version.js` 동작 방식
- 검증 및 문제 해결

#### [TLS_CACHE_SYSTEM.md](TLS_CACHE_SYSTEM.md)
**TLS 캐시 시스템 설명**
- 캐시 파일 구조 (`tls_profiles_cache.json`)
- 성능 최적화 (즉시 로딩)
- 캐시 생성 및 업데이트 방법
- Cache-first 전략

---

### 2. 기술 참고 문서

#### [CURL_CFFI_CUSTOM_TLS.md](CURL_CFFI_CUSTOM_TLS.md)
**curl-cffi 커스텀 TLS 기술 문서**
- JA3 + Akamai 문자열 사용법
- extra_fp 파라미터
- 우리 TLS 프로파일 구조
- Implementation 전략
- 공식 문서: https://curl-cffi.readthedocs.io/en/stable/impersonate/customize.html

#### [AKAMAI_BYPASS_GUIDE.md](AKAMAI_BYPASS_GUIDE.md)
**Akamai Bot Manager 우회 핵심 가이드**
- Akamai 센서 스크립트 차단
- Playwright 자연스러운 동작 시뮬레이션
- BrowserFactory 필수 사용법
- Cookie 관리 전략

---

### 3. 실행 & 테스트

#### [RATE_LIMITER_GUIDE.md](RATE_LIMITER_GUIDE.md)
**Rate Limiting 대응 가이드**
- IP당 요청 제한 (~150 requests/IP)
- Rate Limiter 구현 방법
- Proxy rotation 전략

#### [PACKET_MODE_TEST_REPORT.md](PACKET_MODE_TEST_REPORT.md)
**Packet Mode 테스트 결과**
- 테스트 진행 상황 기록
- Chrome 버전별 성공/실패 현황
- 통계 및 분석 데이터

#### [PRODUCT_EXPOSURE_REPORT.md](PRODUCT_EXPOSURE_REPORT.md)
**상품 노출 분석 리포트**
- 상품 중복 분석
- Unique key 전략 (3-part)
- Expected: ≤4% duplicate rate

---

## 🚀 빠른 시작

### 1. TLS 프로파일 수집
```bash
# Chrome 빌드 다운로드 및 TLS 수집
cd install
.\install-all-chrome-versions.ps1
python batch_tls_extractor.py --yes

# 캐시 생성
cd ..
node install/create_tls_cache.js
```

### 2. Chrome 버전 테스트
```bash
# 48개 Chrome 빌드로 Akamai 우회 테스트
node find-allowed-chrome-version.js

# 결과 확인
cat test_results/summary_*.json
```

### 3. 개별 테스트
```bash
# Python으로 직접 테스트
python src/tls_custom_request.py \
  "https://www.coupang.com/np/search?q=키보드&page=1" \
  "cookies/136.0.7103.113.json" \
  "136.0.7103.113"
```

---

## 📖 읽는 순서

### 처음 시작하는 경우
1. **PROJECT_POLICY.md** (필수) - 절대 규칙
2. **TLS_DIRECT_USAGE_MANUAL.md** - 사용법
3. **find-allowed-chrome-version.js** 코드 분석

### curl-cffi 학습
1. TLS_DIRECT_USAGE_MANUAL.md
2. CURL_CFFI_CUSTOM_TLS.md
3. TLS_CACHE_SYSTEM.md

### Akamai 우회 심화
1. AKAMAI_BYPASS_GUIDE.md
2. RATE_LIMITER_GUIDE.md

---

## 🔍 빠른 검색

| 궁금한 내용 | 문서 |
|------------|------|
| ❌ impersonate 사용 금지 이유? | `PROJECT_POLICY.md` |
| ✅ Direct TLS 사용법? | `TLS_DIRECT_USAGE_MANUAL.md` |
| 🔧 curl-cffi 기술 상세? | `CURL_CFFI_CUSTOM_TLS.md` |
| ⚡ TLS 캐시 시스템? | `TLS_CACHE_SYSTEM.md` |
| 🛡️ Akamai 센서 차단? | `AKAMAI_BYPASS_GUIDE.md` |
| 🚦 Rate Limiting 대응? | `RATE_LIMITER_GUIDE.md` |
| 📊 테스트 결과? | `PACKET_MODE_TEST_REPORT.md` |

---

## 📂 프로젝트 구조

```
d:\dev\git\local-packet-coupang\

├── PROJECT_POLICY.md          ⭐ 절대 규칙 (필독)

├── docs/                      📚 문서
│   ├── README.md              (이 파일)
│   ├── TLS_DIRECT_USAGE_MANUAL.md
│   ├── TLS_CACHE_SYSTEM.md
│   ├── CURL_CFFI_CUSTOM_TLS.md
│   ├── AKAMAI_BYPASS_GUIDE.md
│   ├── RATE_LIMITER_GUIDE.md
│   ├── PACKET_MODE_TEST_REPORT.md
│   ├── PRODUCT_EXPOSURE_REPORT.md
│   └── archive/               🗃️ 구버전 문서

├── install/                   🔧 설치 & 수집 도구
│   ├── install-all-chrome-versions.ps1
│   ├── batch_tls_extractor.py
│   └── create_tls_cache.js

├── chrome-versions/
│   ├── files/                 📦 48개 Chrome 빌드
│   └── tls/                   🔐 48개 TLS 프로파일
│       └── tls_profiles_cache.json  ⚡ 캐시

├── src/
│   └── tls_custom_request.py  🐍 Direct TLS 요청

├── find-allowed-chrome-version.js  🎯 메인 테스트

├── cookies/                   🍪 쿠키 저장소
└── test_results/              📊 테스트 결과
```

---

## 🎯 프로젝트 목표

**Find Chrome Build Versions that Bypass Akamai Bot Manager**

### Process
1. **Browser Mode**: Real Chrome → Get cookies
2. **Load TLS Profile**: Extract JA3 + Akamai from `chrome-versions/tls/`
3. **Packet Mode**: curl-cffi with direct TLS → Test until blocked
4. **Report**: Which Chrome versions allowed?

### Method
- ✅ Direct TLS fingerprints (JA3 + Akamai)
- ❌ NO impersonate profiles
- 🔬 Test 48 Chrome builds (120.0.6099.0 → 141.0.7390.76)

---

## ⚠️ 중요 정책

### NEVER DO THIS ❌
```python
# ❌ FORBIDDEN
response = requests.get(url, impersonate='chrome136')
```

### ALWAYS DO THIS ✅
```python
# ✅ REQUIRED
response = requests.get(url, ja3=ja3_string, akamai=akamai_string)
```

**이유**: 정확한 빌드 버전 매칭 필요 (136.0.7103.113 not just "chrome136")

---

## 📝 문서 업데이트

### 새 문서 추가 시
- 명확한 제목과 목적
- 실행 가능한 코드 예제
- PROJECT_POLICY.md와 일관성 유지

### 구버전 문서
- `docs/archive/obsolete_YYYY_MM_DD/`로 이동
- 중복 내용 병합 후 삭제

---

**Last Updated**: 2025-10-11 23:30
**Status**: Testing 48 Chrome builds for Akamai bypass
