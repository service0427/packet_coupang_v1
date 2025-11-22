# Coupang Akamai 우회 크롤링 - 마스터 가이드

쿠팡 Akamai Bot Manager 우회 시스템의 전체 연구 기록 및 최종 솔루션

---

## 📋 목차

1. [프로젝트 개요](#프로젝트-개요)
2. [핵심 발견사항](#핵심-발견사항)
3. [Akamai 탐지 메커니즘](#akamai-탐지-메커니즘)
4. [최종 솔루션](#최종-솔루션)
5. [Browser Mode](#browser-mode)
6. [Packet Mode (개발 중)](#packet-mode)
7. [실패한 접근 방법](#실패한-접근-방법)
8. [다음 단계](#다음-단계)

---

## 프로젝트 개요

### 목표
쿠팡(coupang.com) 검색 결과를 Akamai Bot Manager 탐지 없이 안정적으로 크롤링

### 핵심 도전과제
1. **2단계 탐지 시스템**
   - TLS Layer: BoringSSL 핑거프린트 검증
   - Akamai Layer: JavaScript 센서 기반 행동 분석

2. **제약사항**
   - HTTP/2 필수 (HTTP/1.1 즉시 차단)
   - User-Agent는 `Chrome/140.0.0.0` 정확히 매칭
   - BoringSSL 서명 필요 (Safari/Firefox 차단)

### 현재 성과
- ✅ **Browser Mode**: 100% 우회 성공 (Playwright)
- 🔄 **Packet Mode**: 개발 중 (curl-cffi 기반)

---

## 핵심 발견사항

### 1. Akamai 센서 스크립트 차단 = 100% 우회

**발견**: Playwright의 `page.route()`로 Akamai 센서 스크립트를 로드 전에 차단하면 탐지를 완전히 우회할 수 있다.

**차단 대상 패턴**:
```javascript
const akamaiPatterns = [
    /\/akam\//,
    /\/akamai\//,
    /akamaihd\.net/,
    /sensor/,
    /bmak/,
    /bot-manager/,
    /fingerprint/
];
```

**결과**:
- traceId 정상 생성 ✅
- 검색 결과 정상 반환 ✅
- 안정적인 멀티페이지 크롤링 ✅

---

### 2. TLS 핑거프린트 우회

**문제**: Python ssl 모듈은 OpenSSL 기반이라 Chrome의 BoringSSL 서명을 재현할 수 없음

**솔루션 1 - curl-cffi (Python)**:
```python
from curl_cffi import requests

response = requests.get(
    'https://www.coupang.com/',
    impersonate='chrome120'  # BoringSSL 서명 포함
)
```

**솔루션 2 - tls-client (Golang)**:
```go
client, _ := tls_client.NewHttpClient(tls_client.NewNoopLogger())
client.SetClientProfile(tls_client.Chrome_120)
```

**결과**:
- ✅ TLS Layer 100% 통과
- ✅ HTTP/2 SETTINGS 자동 처리
- ⚠️ Akamai Layer는 여전히 쿠키 필요

---

### 3. 자연스러운 검색 흐름의 중요성

**실패 패턴**:
```javascript
// ❌ 직접 URL 접근
await page.goto('https://www.coupang.com/np/search?q=키보드');
// 결과: ERR_HTTP2_PROTOCOL_ERROR
```

**성공 패턴**:
```javascript
// ✅ 자연스러운 사용자 흐름
await page.goto('https://www.coupang.com/');
const searchInput = await page.waitForSelector('input[name="q"]');
await searchInput.click();
await page.keyboard.press('Control+A');
await searchInput.type('키보드', { delay: 150 });  // 글자당 150ms
await page.keyboard.press('Enter');
```

**결과**:
- traceId 자동 생성 ✅
- 정상적인 검색 결과 ✅

---

## Akamai 탐지 메커니즘

### 1. TLS Layer (1차 필터)

**검증 항목**:
- BoringSSL 서명 (`Chrome`, `Edge`만 허용)
- HTTP/2 SETTINGS 프레임
- GREASE (Generate Random Extensions And Sustain Extensibility)
- Extension 순서

**우회 방법**:
- curl-cffi의 `impersonate='chrome120'`
- tls-client의 `Chrome_120` 프로파일

---

### 2. Akamai Sensor Layer (2차 필터)

**데이터 수집 항목**:
- Canvas/WebGL 핑거프린트
- 마우스/키보드 이벤트 패턴
- 타이밍 데이터 (페이지 로드, 스크립트 실행)
- 네트워크 타이밍
- 브라우저 환경 정보

**차단 전략**:
- IP당 ~150개 요청 후 차단
- 센서 데이터 부족 시 challenge 페이지
- 비정상 행동 패턴 감지 시 즉시 차단

**우회 방법**:
1. **Browser Mode**: Akamai 스크립트 차단 (100% 성공)
2. **Packet Mode**: Real Browser의 쿠키 재사용 (개발 중)

---

## 최종 솔루션

### Browser Mode (현재 사용 중)

**기술 스택**: Playwright + Chromium (Incognito)

**장점**:
- ✅ 100% Akamai 우회
- ✅ traceId 자동 생성
- ✅ 안정적인 멀티페이지 크롤링
- ✅ 쿠키 자동 수집

**단점**:
- ⚠️ 느린 속도 (3-5초/페이지)
- ⚠️ 높은 리소스 사용

**사용법**:
```bash
node examples/test_browser_mode.js
```

**코드 예제**:
```javascript
const PlaywrightBrowser = require('./lib/browser/playwright-browser');

const browser = new PlaywrightBrowser({ headless: false });
await browser.launch();
await browser.goto('https://www.coupang.com/');
await browser.performSearch('키보드');
await browser.setListSize(72);

const cookies = await browser.getCookies();
await browser.close();
```

**결과**:
- 3페이지 × 63개 = 189개 랭킹 상품
- 181개 고유 상품 (8개 중복 = 4.2%, 쿠팡 정상 동작)
- 70-71개 쿠키 수집

---

### Packet Mode (개발 중)

**기술 스택**: curl-cffi + Browser 쿠키

**장점**:
- ⚡ 빠른 속도 (100-200ms/요청)
- ⚡ 낮은 리소스 사용

**단점**:
- ⚠️ 쿠키 필요 (Browser Mode에서 획득)
- ⚠️ 쿠키 만료 (10-30분)

**현재 상태**: 모듈 준비 완료, 테스트 필요

**사용법** (예정):
```bash
# 1. Browser Mode로 쿠키 획득
node examples/test_browser_mode.js

# 2. Packet Mode로 빠른 요청
node examples/test_packet_mode.js
```

**코드 예제**:
```javascript
const PacketMode = require('./lib/browser/packet-mode');

const packet = new PacketMode();
const html = await packet.request(url, 1);  // page1_cookies.json 사용
```

---

### Hybrid Mode (권장 전략)

**개념**: Browser Mode로 쿠키 획득 → Packet Mode로 대량 요청

**전략**:
```
1. 초기 쿠키 획득: Browser Mode (3-5초)
   ↓
2. 빠른 반복 요청: Packet Mode (100-200ms × N)
   ↓
3. 쿠키 만료 감지: 자동 Browser Mode 재실행
   ↓
4. 반복
```

**예상 성능**:
- 평균 500ms/요청
- 80-100% 우회율
- IP당 ~150개 요청

---

## 실패한 접근 방법

### 1. Python ssl 모듈로 TLS 수정 시도 ❌

**시도**: Python `ssl` 모듈로 HTTP/2 SETTINGS 프레임 수정

**실패 이유**:
- Python ssl은 OpenSSL 기반
- Chrome은 BoringSSL 기반
- JA3 핑거프린트가 달라서 Akamai가 탐지

**결론**: 패킷 레벨 수정은 Python으로 불가능

**관련 문서**: `PACKET_APPROACH_CONCLUSION.md`

---

### 2. h2/httpcore 라이브러리 사용 ❌

**시도**: h2, httpcore로 HTTP/2 프레임 직접 조작

**실패 이유**:
- State machine 에러 (h2)
- Connection termination (httpcore)
- 여전히 OpenSSL 기반이라 TLS 서명 불일치

**결론**: 라이브러리 레벨에서도 근본적 한계

---

### 3. Chrome 커스텀 빌드 시도 ❌

**시도**: Chromium 소스 수정하여 HTTP/2 SETTINGS 변경

**실패 이유**:
- 빌드 시간 너무 길음 (수 시간)
- 유지보수 어려움
- Real Chrome 사용이 더 간단

**결론**: Over-engineering, 실용적이지 않음

---

## Packet Mode 개발 가이드 (curl-cffi 우회 전략)

### 배경

**문제**: curl-cffi로 TLS는 통과하지만, Akamai Sensor 데이터가 없어서 차단됨

**목표**: 동일 IP에서 차단되었을 때 센서 우회 전략 개발

---

### 과거 연구 (미완성)

**시도했던 방법**:
1. HTTP/2 SETTINGS 파라미터 변경 (HEADER_TABLE_SIZE 등)
2. 다양한 curl-cffi 프로파일 테스트 (chrome120, chrome124, safari 등)
3. 커스텀 HTTP/2 설정 조합 생성

**부분적 성과**:
- 일부 파라미터 조합으로 10-30% 우회 성공
- 하지만 안정적이지 않음 (재현 어려움)

**미완성 이유**:
- Browser Mode가 100% 성공하면서 우선순위 낮아짐
- Packet Mode는 쿠키 재사용으로 충분히 실용적

---

### 재개발 전략 (Packet Mode v2)

**시나리오**: Packet Mode로 요청 중 차단되었을 때

**단계별 우회 전략**:

#### 1단계: 프로파일 로테이션
```python
profiles = ['chrome120', 'chrome124', 'chrome131', 'safari17_2']

for profile in profiles:
    response = requests.get(url, impersonate=profile, cookies=cookies)
    if is_success(response):
        return response
```

#### 2단계: HTTP/2 SETTINGS 미세 조정
```python
from curl_cffi.requests import Session

session = Session()
session.curl.setopt(
    pycurl.HTTP2_SETTINGS,
    [
        (pycurl.HTTP2_SETTINGS_HEADER_TABLE_SIZE, 65536),
        (pycurl.HTTP2_SETTINGS_MAX_CONCURRENT_STREAMS, 100),
        (pycurl.HTTP2_SETTINGS_INITIAL_WINDOW_SIZE, 6291456),
    ]
)
```

#### 3단계: IP 쿨다운 대기
```python
def wait_for_cooldown(ip_address, wait_time=300):
    """
    차단된 IP는 5분 대기 후 재시도
    """
    blocked_ips[ip_address] = time.time()
    time.sleep(wait_time)
```

#### 4단계: Browser Mode로 쿠키 갱신
```python
def refresh_cookies_with_browser():
    """
    최후의 수단: Browser Mode로 새 쿠키 획득
    """
    browser = PlaywrightBrowser()
    await browser.launch()
    await browser.goto('https://www.coupang.com/')
    cookies = await browser.getCookies()
    await browser.close()
    return cookies
```

---

### 개발 우선순위

**Phase 1** (1주일): 기본 Packet Mode
- curl-cffi + 쿠키 재사용
- 성공/실패 감지
- 자동 재시도

**Phase 2** (2주일): 우회 전략
- 프로파일 로테이션
- HTTP/2 SETTINGS 조정
- 성공 패턴 학습

**Phase 3** (1개월): Hybrid 자동화
- 쿠키 만료 감지
- 자동 Browser Mode 전환
- Rate Limiter 통합

---

## 다음 단계

### 단기 (1주일)
1. ✅ 프로젝트 정리 완료
2. ✅ 모듈화 완료
3. 🔄 Packet Mode 기본 구현
4. 🔄 성공/실패 감지 로직

### 중기 (1개월)
1. Packet Mode 우회 전략
2. Hybrid Mode 자동화
3. Rate Limiter 통합
4. Proxy Pool 연동 (선택)

### 장기 (3개월)
1. 분산 크롤링 시스템
2. 모니터링 대시보드
3. API 서버 구축
4. 대규모 인프라

---

## 참고 문서

### 필수 문서
- `AKAMAI_BYPASS_GUIDE.md` - Akamai 우회 핵심 방법
- `PACKET_APPROACH_CONCLUSION.md` - 패킷 레벨 실패 이유
- `CURL_CFFI_CUSTOM_FINGERPRINT.md` - curl-cffi 사용법

### 기술 문서
- `examples/README.md` - 사용법 가이드
- `PROJECT_STRUCTURE.md` - 프로젝트 구조
- `CLAUDE.md` - 전체 개요

### 아카이브 (참고용)
- `docs/archive/` - 과거 실험 기록들
- 실패한 접근 방법들의 상세 기록

---

## 성능 지표

### Browser Mode
- **속도**: 3-5초/페이지
- **우회율**: 100%
- **리소스**: 높음
- **용도**: 초기 쿠키 획득, 안정적 크롤링

### Packet Mode (목표)
- **속도**: 100-200ms/요청
- **우회율**: 80-100% (with 쿠키)
- **리소스**: 낮음
- **용도**: 대량 빠른 요청

### Hybrid Mode (권장)
- **속도**: 평균 500ms
- **우회율**: 85-95%
- **리소스**: 중간
- **용도**: 실전 운영

---

## 기술 스택

### Browser Mode
- Playwright (Node.js)
- Chromium (BoringSSL)

### Packet Mode
- curl-cffi (Python)
- BoringSSL impersonation

### 데이터 처리
- jsdom (HTML 파싱)
- 커스텀 ProductExtractor

### 인프라 (예정)
- Docker
- PostgreSQL
- Redis (쿠키 캐시)
- Proxy Pool (선택)

---

**최종 업데이트**: 2025-10-11
