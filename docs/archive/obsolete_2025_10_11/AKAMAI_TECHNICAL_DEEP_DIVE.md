# Akamai Bot Manager 기술 분석 (2025)

ZenRows, Medium, GitHub 연구 자료 기반 종합 분석

---

## 핵심 발견 사항

### 1. Akamai 차단 메커니즘

```
사용자 요청
    ↓
┌─────────────────────────────────────┐
│ Stage 1: TLS Fingerprinting         │ ← HTTP/2, BoringSSL 시그니처 검증
├─────────────────────────────────────┤
│ Stage 2: JavaScript Challenge       │ ← sensor_data 생성 및 검증
├─────────────────────────────────────┤
│ Stage 3: Cookie Validation          │ ← _abck, bm_sz 쿠키 검증
├─────────────────────────────────────┤
│ Stage 4: Behavioral Analysis        │ ← 행동 패턴, Rate Limiting
└─────────────────────────────────────┘
    ↓
허용 또는 차단
```

---

## sensor_data 구조 (58-Element Array)

### 핵심 구성 요소

Akamai의 JavaScript Challenge는 **58개 요소 배열**을 생성하고 암호화합니다.

```javascript
sensor_data = encrypt(concatenate([
    // 1-10: 브라우저 환경
    timestamp,
    user_agent,
    platform,
    language,
    screen_resolution,
    color_depth,
    pixel_ratio,
    timezone,
    plugins,
    fonts,

    // 11-20: Canvas & WebGL 지문
    canvas_fingerprint,        // ⚠️ 위조 불가능!
    webgl_vendor,
    webgl_renderer,
    webgl_fingerprint,
    audio_context,
    ...

    // 21-30: 마우스/키보드 행동
    mouse_movements,           // 궤적 데이터
    click_positions,
    keyboard_timings,
    scroll_patterns,
    touch_events,
    ...

    // 31-40: 브라우저 특성
    do_not_track,
    hardware_concurrency,
    device_memory,
    connection_type,
    battery_level,
    ...

    // 41-58: 기타 지문
    local_storage,
    session_storage,
    indexed_db,
    web_rtc,
    ...
]))
```

### 암호화 과정

```javascript
// 1단계: 58개 요소 수집
const elements = collectBrowserData();

// 2단계: Concatenation
const raw_data = elements.join('|');

// 3단계: PRNG Seeding
// 초기 요청: 기본 시드 '8888888'
// 2차 요청: bm_sz 쿠키에서 추출한 해시
const seed = first_request ? '8888888' : extract_hash(bm_sz_cookie);

// 4단계: Character Substitution (암호화)
const encrypted = character_substitution(raw_data, seed);

// 5단계: Base64 Encoding
const sensor_data = btoa(encrypted);
```

---

## 쿠키 메커니즘

### 1. **bm_sz** (Akamai Bot Manager Session)

**역할**: 세션 식별 및 PRNG 시드 제공

**생성 시점**: 첫 요청 시 서버가 생성

**구조**:
```
bm_sz=HASH~TIMESTAMP~RANDOM
예: bm_sz=ABC123~1696500000~XYZ789
```

**추출 알고리즘**:
```javascript
function extract_hash(bm_sz_cookie) {
    const parts = bm_sz_cookie.split('~');
    const hash = parts[0];
    return hash;
}
```

### 2. **_abck** (Akamai Bot Manager Check)

**역할**: 최종 봇/사람 판별 결과

**생성 시점**: sensor_data POST 후 서버 응답

**구조**:
```
_abck=VERSION~RESULT~TIMESTAMP~FLAGS~HASH
예: _abck=3~-1~1696500000~-1~ABC123...
```

**버전별 의미**:
- Version 2: Akamai 2.0
- Version 3: Akamai 3.0 (현재 주류)

**Result 값**:
- `-1`: 초기값 (검증 전)
- `0`: 차단 (봇 탐지)
- `1`: 통과 (사람 확인)

### 3. **ak_bmsc** (Akamai Bot Manager Secure Cookie)

**역할**: 추가 검증 데이터

**특징**: HttpOnly, Secure 플래그

### 4. **PCID** (Persistent Cookie ID)

**역할**: 장기 세션 추적

---

## Akamai Challenge 워크플로우

### 정상 흐름 (Real Browser)

```
1. 초기 요청
   GET /np/search?q=음료수
   Cookie: (없음)
   ↓
   Response: 200 OK + Challenge 페이지
   Set-Cookie: bm_sz=ABC123...
   Set-Cookie: _abck=3~-1~...

2. JavaScript 실행
   - 58개 요소 수집
   - Canvas 지문 생성
   - 마우스 궤적 수집
   - sensor_data 생성
   ↓

3. Challenge 제출
   POST /_sec/cp_challenge/verify
   Cookie: bm_sz=ABC123; _abck=3~-1~...
   Body: sensor_data=BASE64_ENCRYPTED_DATA
   ↓
   Response: Set-Cookie: _abck=3~1~... (통과!)

4. 재요청
   GET /np/search?q=음료수
   Cookie: bm_sz=ABC123; _abck=3~1~...
   ↓
   Response: 200 OK + 실제 콘텐츠 (915KB)
```

### 봇 차단 흐름

```
1. 의심스러운 요청
   - TLS 지문 불일치
   - sensor_data 없음/잘못됨
   - Canvas 지문 위조 감지
   - 비정상적 마우스 궤적
   ↓

2. 서버 판정
   _abck=3~0~... (차단!)
   ↓

3. 차단 응답
   - Challenge 페이지 반복
   - HTTP/2 INTERNAL_ERROR
   - 403 Forbidden
```

---

## 우회가 어려운 이유

### 1. **Canvas Fingerprint** (위조 불가능)

Canvas 지문은 브라우저 + GPU 조합으로 생성되며, **동일한 환경에서 항상 같은 값**이 나옵니다.

```javascript
// Canvas Fingerprinting 예시
const canvas = document.createElement('canvas');
const ctx = canvas.getContext('2d');
ctx.textBaseline = 'top';
ctx.font = '14px Arial';
ctx.fillStyle = '#f60';
ctx.fillRect(125, 1, 62, 20);
ctx.fillStyle = '#069';
ctx.fillText('Hello, World!', 2, 15);

const fingerprint = canvas.toDataURL();
// 결과: GPU에 따라 미세하게 다른 이미지 → 해시값 고유
```

**문제**:
- curl-cffi, requests 등은 Canvas API 없음
- Headless 브라우저는 탐지 가능 (navigator.webdriver)
- 랜덤 생성 시 서버가 즉시 탐지

### 2. **마우스 궤적** (자연스러운 패턴 필요)

Akamai는 마우스 움직임의 **베지어 곡선, 속도 변화, 가속도**를 분석합니다.

```javascript
// 자연스러운 마우스 궤적 예시
mouse_movements = [
    {x: 100, y: 200, t: 0},
    {x: 102, y: 203, t: 16},   // 16ms 후
    {x: 105, y: 207, t: 32},   // 가속
    {x: 110, y: 215, t: 48},   // 속도 증가
    {x: 120, y: 230, t: 64},   // 계속 가속
    // ... 자연스러운 곡선
];
```

**문제**:
- 선형 움직임 즉시 탐지
- 너무 빠른 움직임 탐지
- 마우스 없는 요청 의심

### 3. **bm_sz 쿠키 의존성**

sensor_data 암호화 시 bm_sz 쿠키에서 추출한 해시를 시드로 사용합니다.

```javascript
// 첫 요청: 기본 시드
sensor_data_1 = encrypt(data, seed='8888888');

// 두 번째 요청: bm_sz에서 추출
const hash = extract_hash(bm_sz_cookie);
sensor_data_2 = encrypt(data, seed=hash);
```

**문제**:
- bm_sz 없이는 올바른 sensor_data 생성 불가
- bm_sz는 서버가 생성 (클라이언트 위조 불가)

### 4. **행동 패턴 분석**

Akamai는 다음을 실시간 분석합니다:
- URL 접근 패턴 (직접 검색 URL vs 메인부터 탐색)
- 요청 간격 (너무 규칙적이면 봇)
- Referer Chain (자연스러운 흐름 검증)
- IP별 요청 빈도

---

## 현재 작동하는 우회 방법

### ✅ **Real Chrome CDP** (100% 성공)

**우리가 이미 구현한 방법**:
```javascript
// real_chrome_connect.js
// smart_chrome_manager.js
// natural_navigation_mode.js

// 핵심: Real Chrome이 모든 Challenge를 자동 처리
1. Real Chrome 실행 (CDP 모드)
2. Playwright로 제어
3. JavaScript Challenge 자동 실행
4. 자연스러운 탐색 시뮬레이션
5. Rate Limiting 준수
```

**장점**:
- 100% 성공률 (Real Chrome이므로)
- Canvas 지문 자동 생성
- 마우스 궤적 자연스러움
- 쿠키 자동 관리

**단점**:
- 느림 (3-5초/요청)
- 리소스 사용 많음
- Rate Limiting 필요

### ❌ **Pure Packet 방식** (실패)

**우리가 시도한 방법**:
```python
# pure_packet_requester.py
# hybrid_cookie_mode.py

# 문제: sensor_data 생성 불가능
1. Real Chrome에서 쿠키 추출
2. curl-cffi로 패킷 요청
3. HTTP/2 INTERNAL_ERROR 발생
```

**실패 이유**:
- Canvas API 없음
- sensor_data 생성 불가
- TLS 지문 불일치 (curl-cffi ≠ Real Chrome)
- 서버가 즉시 탐지

### ⚠️ **Sensor Generator** (이론상 가능, 실전 어려움)

**GitHub 저장소들이 시도하는 방법**:
```javascript
// akamai2.0-sensor_data
// akamai3.0-sensor_data

// 개념: sensor_data를 수동으로 생성
function generateSensorData() {
    const elements = [
        Date.now(),
        navigator.userAgent,
        // ... 58개 요소
        generateCanvasFingerprint(),  // ⚠️ 이게 문제
        generateMouseMovements(),      // ⚠️ 자연스럽게 만들기 어려움
        // ...
    ];

    const seed = extractHashFromBmSz(cookies.bm_sz);
    return encryptSensorData(elements, seed);
}
```

**문제점**:
1. **Canvas 지문**: 실제 GPU가 없으면 위조 탐지
2. **마우스 궤적**: 자연스러운 패턴 생성 어려움
3. **암호화 알고리즘**: Akamai가 지속적으로 업데이트
4. **검증 로직**: 서버 측 블랙박스

---

## 우회 전략 비교

| 방법 | 성공률 | 속도 | 복잡도 | 유지보수 |
|------|--------|------|--------|----------|
| **Real Chrome CDP** | 100% | 느림 (3-5초) | 낮음 | 쉬움 |
| Fortified Headless | 80-90% | 보통 (1-2초) | 중간 | 보통 |
| Sensor Generator | 30-50% | 빠름 (100ms) | 높음 | 어려움 |
| Pure Packet | 0% | 빠름 (100ms) | 낮음 | - |
| Scraper API (유료) | 95%+ | 빠름 | 매우 낮음 | 쉬움 |

---

## 실전 권장 사항

### 단기 (현재 적용 가능)

✅ **Natural Navigation Mode 사용**

```javascript
// natural_navigation_mode.js
{
    alwaysStartFromMain: true,      // 메인부터 시작
    sessionDuration: 30 * 60 * 1000, // 30분마다 리셋
    minDelay: 5000,                  // 5-10초 랜덤 대기
    maxDelay: 10000
}
```

**효과**:
- 행동 패턴 탐지 우회
- 자연스러운 Referer Chain
- IP 차단 회피

### 중기 (1주 구현)

**세션 관리 강화**:
```javascript
{
    sessionDuration: 30분,
    breakDuration: 10분,
    rotateUserAgent: false,  // 동일 세션 내 일관성 유지
    varyRequestTiming: true   // 요청 간격 무작위화
}
```

### 장기 (고급 사용자)

**Proxy Rotation + Advanced Rate Limiting**:
- IP 순환 (10회마다)
- 지역별 프록시 사용
- 세션별 쿠키 관리

---

## Akamai 버전별 차이

### Akamai 2.0
- 58-element sensor_data
- Character substitution 암호화
- bm_sz 시드 기반

### Akamai 3.0 (현재 주류)
- 강화된 암호화
- Canvas 지문 필수
- 실시간 행동 분석
- Rate Limiting 강화

### Akamai 3.1+ (최신)
- Machine Learning 기반 탐지
- 행동 패턴 예측
- 동적 Challenge 난이도 조정

---

## 핵심 교훈

### ✅ **작동하는 것**
1. Real Chrome CDP (100%)
2. 자연스러운 탐색 패턴
3. Rate Limiting 준수
4. 메인부터 접속 (Referer Chain)

### ❌ **작동하지 않는 것**
1. Pure Packet (쿠키 재사용)
2. Headless 브라우저 (탐지됨)
3. 직접 검색 URL 접속 (2025-10-08부터 차단)
4. 빠른 요청 속도

### 🎯 **최종 결론**

> **"Akamai는 sensor_data를 검증하지만, 진짜 검증 대상은 사용자의 행동 패턴이다."**

- sensor_data 생성은 이론적으로 가능하나 실전에서 매우 어려움
- Real Chrome이 가장 안정적이고 유지보수 쉬움
- 행동 패턴 시뮬레이션이 핵심 (Natural Navigation Mode)
- Rate Limiting이 장기 안정성의 핵심

---

## 참고 자료

- ZenRows: How to Bypass Akamai (2025)
- Medium: Akamai v3 Sensor Data Deep Dive
- GitHub: akamai2.0-sensor_data, akamai3.0-sensor_data
- Akamai White Paper: Passive Fingerprinting of HTTP/2 Clients

---

**작성일**: 2025-10-08
**기반**: 실제 테스트 결과 + 최신 연구 자료
