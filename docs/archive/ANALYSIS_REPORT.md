# 쿠팡 봇 감지 메커니즘 분석 리포트

## 실험 개요

Real Chrome + CDP 방식을 사용하여 Desktop과 Mobile User-Agent에 대한 차단 패턴을 분석

## 주요 발견사항

### 1. Chrome 플래그 감지 (Critical)

**발견**: `--user-agent` Chrome 실행 플래그 사용 시 **즉시 차단**

#### 실험 결과
```
✅ Desktop UA (플래그 없음) + 기본 뷰포트 = 정상 작동
✅ Desktop UA (플래그 없음) + 모바일 뷰포트 (375x812) = 정상 작동
🚨 Mobile UA (--user-agent 플래그) + 모바일 뷰포트 = 즉시 차단 (chrome-error)
```

#### 차단 메커니즘
- Chrome 실행 시 `--user-agent` 플래그 사용 여부 감지
- User-Agent 문자열 내용이 아닌 **플래그 존재 여부**를 감지
- 서버 측에서 Chrome DevTools Protocol 사용 감지 가능성

### 2. User-Agent 역할 분석

#### Desktop UA 동작
```javascript
// User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) ... Chrome/140.0.0.0
// 뷰포트: 375x812 (모바일 크기)

결과:
- ✅ 차단 없음
- ✅ 모바일 UI 렌더링 (뷰포트 기반)
- ❌ 모바일 배너 없음 (UA 기반 판단)
- ✅ 검색 정상 작동
```

#### Mobile UA 동작 (플래그 사용)
```javascript
// Chrome args: --user-agent=Mozilla/5.0 (iPhone...)
// 뷰포트: 375x812

결과:
- 🚨 즉시 차단 (chrome-error://chromewebdata/)
- ❌ 검색 불가
- ❌ 모든 네트워크 요청 차단
```

### 3. UI 렌더링 로직

쿠팡의 UI 렌더링은 다음 요소로 결정됨:

1. **뷰포트 크기** → 모바일 UI vs Desktop UI
2. **User-Agent 문자열** → 배너 표시 여부
3. **Chrome 플래그** → 봇 감지 및 차단

```
뷰포트 375x812 + Desktop UA:
- 모바일 레이아웃 ✅
- 모바일 검색창 ✅
- 앱 다운로드 배너 ❌
- 하단 시트 배너 ❌
```

## 기술적 분석

### Chrome DevTools Protocol (CDP) 감지

**가설**: 쿠팡은 다음 방법으로 CDP 사용을 감지할 수 있음

1. **Chrome 플래그 패턴 분석**
   - `--remote-debugging-port` 사용 감지
   - `--user-agent` 플래그 감지 (확인됨)
   - `--headless` 플래그 감지

2. **TLS/HTTP2 핑거프린트**
   - JA3/JA4 핑거프린트로 자동화 도구 식별
   - HTTP/2 SETTINGS 프레임 비정상 패턴
   - ALPN 협상 패턴

3. **브라우저 API 호출 패턴**
   - `navigator.webdriver` 플래그
   - Chrome DevTools Protocol 존재 여부
   - Window properties 이상 패턴

### Real Chrome vs Chromium 차이

**Real Chrome (`chrome.exe`)**:
- Google 공식 빌드
- 정상적인 TLS 핑거프린트
- CDP 연결 가능하지만 플래그 감지됨

**Playwright Chromium**:
- Automation-enabled 빌드
- `navigator.webdriver = true`
- 즉시 감지 가능

## V2 성공 이유 분석

`search_scenario_analyzer_v2.js`가 성공한 이유:

```javascript
// V2 Chrome 실행 args
const args = [
    '--remote-debugging-port=9222',
    '--no-first-run',
    '--no-default-browser-check',
    '--window-size=375,812',  // 모바일 뷰포트
    '--user-data-dir=...'
    // ❌ --user-agent 플래그 없음 (핵심!)
];

// Playwright 연결
const browser = await chromium.connectOverCDP(...);

// 결과: Desktop UA로 모바일 UI 렌더링
// - 차단 없음 ✅
// - 모바일 레이아웃 ✅
// - 검색 정상 ✅
```

## Intensive Test 실패 이유 분석

`mobile_intensive_test.js`가 실패한 이유:

```javascript
// Intensive Test Chrome 실행 args
const args = [
    '--remote-debugging-port=9300',
    '--window-size=375,812',
    '--user-agent=Mozilla/5.0 (iPhone...)',  // 🚨 이 플래그가 문제!
    '--user-data-dir=...'
];

// 결과: 즉시 차단
// - chrome-error://chromewebdata/
// - 모든 요청 차단
```

## 순수 패킷 모드 구현 전략

### 1단계: TLS 핑거프린트 분석

Real Chrome의 TLS ClientHello 패턴을 분석하여 동일하게 구현

```
분석 항목:
- Cipher Suites 순서
- Extensions 순서 및 값
- Signature Algorithms
- Supported Groups
- ALPN 협상 (h2, http/1.1)
```

### 2단계: HTTP/2 구현

Real Chrome과 동일한 HTTP/2 SETTINGS 프레임 사용

```
Chrome 140.0.0.0 기준:
SETTINGS_HEADER_TABLE_SIZE: 65536
SETTINGS_ENABLE_PUSH: 0
SETTINGS_MAX_CONCURRENT_STREAMS: 1000
SETTINGS_INITIAL_WINDOW_SIZE: 6291456
SETTINGS_MAX_HEADER_LIST_SIZE: 262144
```

### 3단계: User-Agent 전략

**방법 A**: Desktop UA + 모바일 뷰포트
```
장점:
- 차단 없음 ✅
- 모바일 UI 렌더링 ✅

단점:
- 모바일 배너 없음 ❌
- 배너 처리 로직 불필요 ✅
```

**방법 B**: Mobile UA + 배너 처리
```
장점:
- 완전한 모바일 경험 ✅
- 실제 모바일과 동일 ✅

단점:
- 배너 닫기 로직 필요 ⚠️
- 순수 패킷 모드에서 배너 감지 복잡 ⚠️
```

**권장**: 방법 A (Desktop UA + 모바일 뷰포트)
- 배너가 표시되지 않아 처리 로직 불필요
- 차단 위험 없음
- 검색 결과는 동일하게 수신

### 4단계: 요청 흐름 구현

```
1. TLS 연결 (Real Chrome 핑거프린트)
   ↓
2. HTTP/2 SETTINGS 프레임 (Real Chrome 패턴)
   ↓
3. GET / (Desktop UA, Mobile Viewport 힌트)
   ↓
4. DOM 파싱 (검색창 selector 찾기)
   ↓
5. POST /search (검색 요청)
   ↓
6. 결과 파싱
```

### 5단계: 검증 방법

```javascript
// 1. TLS 핑거프린트 검증
curl --tlsv1.3 --http2 -A "Desktop UA" https://www.coupang.com/

// 2. HTTP/2 프레임 검증
wireshark 캡처로 Real Chrome과 비교

// 3. 응답 검증
- Status Code 200
- 검색 결과 포함 여부
- chrome-error 없음
```

## 실험 데이터

### 테스트 환경
- **OS**: Windows 10
- **Chrome**: 140.0.0.0
- **Playwright**: Latest
- **네트워크**: 일반 인터넷

### 테스트 결과 요약

| 구성 | Desktop UA | Mobile UA (플래그) | 뷰포트 | 결과 |
|------|-----------|-------------------|--------|------|
| V2 Test 1 | ✅ | ❌ | Desktop | ✅ 성공 (3/3) |
| V2 Test 2 | ✅ | ❌ | Mobile 375x812 | ✅ 성공 (2/2) |
| Intensive | ❌ | ✅ | Mobile 375x812 | ❌ 실패 (0/10) |
| Single Test | ✅ | ❌ | Mobile 375x812 | ✅ 성공 (1/1) |
| Banner Test | ✅ | ❌ | Mobile 375x812 | ✅ 성공, 배너 없음 |

### 스크린샷 증거

**Desktop UA + 모바일 뷰포트 (375x812)**:
- `mobile_single_test/screenshots/01_main_page.png`: 모바일 UI 렌더링 확인
- `mobile_single_test/screenshots/02_before_enter.png`: 검색 자동완성 정상
- `mobile_single_test/screenshots/03_result.png`: 검색 결과 정상 수신

**배너 부재 확인**:
- `mobile_banner_test/00_immediate.png` ~ `mobile_banner_test/08_after_8s.png`
- 8초간 관찰 결과 앱 배너, 시트 배너 모두 표시 안 됨

## 결론

### 핵심 발견

1. **`--user-agent` Chrome 플래그는 절대 사용 금지**
   - 서버 측에서 플래그 감지
   - 즉시 차단 (chrome-error)

2. **Desktop UA + 모바일 뷰포트가 최적 전략**
   - 차단 없음
   - 모바일 UI 정상 렌더링
   - 배너 처리 불필요

3. **뷰포트 크기만으로 모바일 UI 렌더링 가능**
   - User-Agent는 배너 표시에만 영향
   - 검색 결과는 동일

### 다음 단계

1. **✅ 완료**: Real Chrome + CDP 차단 패턴 분석
2. **진행 중**: 순수 패킷 모드 구현 준비
3. **다음**: TLS 핑거프린트 분석 (Wireshark 캡처)
4. **다음**: HTTP/2 프레임 분석
5. **다음**: Node.js로 순수 패킷 구현

### 구현 우선순위

1. **TLS 레이어**: Real Chrome JA3/JA4 복제
2. **HTTP/2 레이어**: SETTINGS, HEADERS, DATA 프레임 구현
3. **Application 레이어**:
   - Desktop UA 사용
   - 모바일 뷰포트 힌트 (viewport meta tag 활용)
   - 검색 요청 구현

## 참고 파일

- `search_scenario_analyzer_v2.js`: 성공 케이스 (Desktop UA)
- `mobile_intensive_test.js`: 실패 케이스 (--user-agent 플래그)
- `mobile_single_test.js`: 검증 테스트 (Desktop UA + 모바일 뷰포트)
- `mobile_banner_test.js`: 배너 동작 확인

## 생성일

2025-10-08
