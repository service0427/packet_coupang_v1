# 런타임 Fingerprint 변경 전략

## 목표

**차단 시 브라우저 재시작 없이 fingerprint를 변경하여 우회**

```
검색 1~150회 (Chrome 빌드 A)
  ↓
차단 감지
  ↓
같은 Chrome 프로세스 유지
  ↓
내부 fingerprint 변경 (Chrome 빌드 B처럼)
  ↓
검색 151~300회 성공
```

---

## 변경 가능한 항목 분석

### 1. User-Agent (✅ 가능)

```python
# 런타임 중 변경 가능
await context.set_extra_http_headers({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
})
```

**효과:** HTTP 헤더만 변경, TLS/HTTP/2는 그대로

### 2. navigator.userAgent (⚠️ 어려움)

```javascript
// JavaScript로 덮어쓰기 시도
Object.defineProperty(navigator, 'userAgent', {
    get: () => 'Chrome/120.0.0.0'
});
```

**문제:** Akamai가 `navigator.userAgent`와 실제 TLS를 비교하면 불일치 감지

### 3. TLS Fingerprint (❌ 불가능)

**이유:**
- TLS는 BoringSSL이 처리
- 브라우저 시작 시 결정됨
- **런타임 중 변경 불가능**

### 4. HTTP/2 Settings (❌ 불가능)

**이유:**
- Chromium 내부 하드코딩
- 연결 시작 시 전송됨
- **런타임 중 변경 불가능**

### 5. JavaScript 환경 (✅ 가능)

```javascript
// 변경 가능한 속성들
navigator.platform
navigator.hardwareConcurrency
navigator.deviceMemory
navigator.languages
screen.width
screen.height
window.outerWidth
window.outerHeight
```

**효과:** JavaScript fingerprint만 변경

---

## Akamai가 보는 정보

### Layer 1: TLS (최우선)
```
- JA3 Hash (TLS ClientHello)
- Akamai Hash (HTTP/2 SETTINGS)
→ BoringSSL 수준, 런타임 변경 불가
```

### Layer 2: HTTP Headers
```
- User-Agent
- Accept
- Accept-Language
→ 런타임 변경 가능
```

### Layer 3: JavaScript
```
- navigator.*
- screen.*
- window.*
→ 런타임 변경 가능
```

**결론:** Layer 1 (TLS)이 고정되면 **다른 브라우저로 속일 수 없음**

---

## 실현 가능한 대안

### Option 1: 브라우저 재시작 (빌드 변경)

```python
# 차단 감지 시
browser.close()

# 다른 Chrome 빌드로 재시작
browser = p.chromium.launch(
    channel='chrome',  # 또는 chrome-beta, chrome-dev
    executable_path='C:/Program Files/Google/Chrome Beta/Application/chrome.exe'
)
```

**장점:**
- TLS fingerprint 완전히 변경됨
- Akamai 입장에서 다른 사용자

**단점:**
- 브라우저 재시작 필요 (쿠키/세션 유지 필요)
- 시간 소요 (~5초)

### Option 2: 컨텍스트 교체 (세션 변경)

```python
# 차단 감지 시
old_context.close()

# 새 컨텍스트 생성
new_context = browser.new_context(
    user_agent='...',  # 다른 UA
    viewport={'width': 1920, 'height': 1080},
    locale='ko-KR',
    timezone_id='Asia/Seoul'
)
```

**장점:**
- 브라우저 재시작 불필요
- 빠름 (~1초)

**단점:**
- TLS는 여전히 동일 (같은 브라우저 프로세스)
- Akamai Hash 변경 안 됨

### Option 3: CDP를 통한 속성 조작

```python
# Chrome DevTools Protocol로 직접 조작
client = await page.context.new_cdp_session(page)

# User-Agent Override
await client.send('Network.setUserAgentOverride', {
    'userAgent': 'Mozilla/5.0 ...',
    'platform': 'Win32'
})

# JavaScript 환경 조작
await page.add_init_script("""
    Object.defineProperty(navigator, 'platform', {
        get: () => 'Linux x86_64'
    });
""")
```

**장점:**
- 런타임 중 변경 가능
- JavaScript fingerprint 변경

**단점:**
- TLS/HTTP/2는 여전히 고정
- Akamai가 불일치 감지 가능

---

## 현실적인 해결책

### 방안 A: 빌드 Pool 순환 (추천)

```python
chrome_builds = [
    'C:/Program Files/Google/Chrome/Application/chrome.exe',           # Stable
    'C:/Program Files/Google/Chrome Beta/Application/chrome.exe',      # Beta
    'C:/Program Files/Google/Chrome Dev/Application/chrome.exe',       # Dev
    'C:/Users/[user]/AppData/Local/Chromium/Application/chrome.exe',  # Chromium
]

current_build_index = 0

def get_next_browser():
    global current_build_index
    build = chrome_builds[current_build_index]
    current_build_index = (current_build_index + 1) % len(chrome_builds)
    return build

# 차단 시
browser.close()
new_build = get_next_browser()
browser = p.chromium.launch(executable_path=new_build)
```

**예상 효과:**
- 4개 빌드 × 150회 = 600회/IP
- IP 필요: 100,000 / 600 = 167개

### 방안 B: Playwright + Rebrowser Patches

**Rebrowser가 런타임 변경을 지원하는지 확인 필요**

```bash
# Rebrowser 설치
npx rebrowser-patches@latest patch --packageName playwright-core
```

**테스트 필요:**
- Rebrowser가 Runtime.Enable을 동적으로 제어하는가?
- CDP 신호를 런타임에 제거할 수 있는가?

### 방안 C: 쿠키 이전 + 빠른 재시작

```python
# 1. 쿠키 저장
cookies = await context.cookies()

# 2. 브라우저 종료
await browser.close()

# 3. 다른 빌드로 재시작
browser = p.chromium.launch(executable_path=next_build)
context = await browser.new_context()
await context.add_cookies(cookies)

# 4. 계속 크롤링
```

**시간 최적화:**
- 브라우저 재시작: ~3초
- 쿠키 복원: ~1초
- 총: ~4초 (vs 차단 대기 시간)

---

## 테스트 계획

### Test 1: 빌드 전환 테스트

```python
# test_build_switching.py

# 1. Chrome Stable로 100회 검색
# 2. 차단 감지
# 3. Chrome Beta로 전환
# 4. 추가 100회 검색
# 5. 차단 없이 성공하는가?
```

### Test 2: CDP 속성 변경 효과

```python
# test_cdp_override.py

# 1. Chrome으로 검색
# 2. CDP로 User-Agent, platform 변경
# 3. 추가 검색
# 4. Akamai가 감지하는가?
```

### Test 3: Rebrowser Runtime 모드

```javascript
// test_rebrowser_runtime.js

// Rebrowser의 Runtime fix mode를 동적으로 전환
// 차단 시 모드 변경으로 우회 가능한가?
```

---

## 즉시 테스트 가능한 방법

### 1. 빌드 전환 스크립트

```python
# test_build_switch.py

from patchright.sync_api import sync_playwright
import time

builds = [
    None,  # 기본 Chromium
    'chrome',  # channel='chrome'
    'chrome-beta',
    'msedge'
]

with sync_playwright() as p:
    for build_name in builds:
        print(f'\n[TEST] Using build: {build_name}')

        if build_name == 'chrome':
            browser = p.chromium.launch(headless=False, channel='chrome')
        elif build_name == 'chrome-beta':
            browser = p.chromium.launch(headless=False, channel='chrome-beta')
        elif build_name == 'msedge':
            browser = p.chromium.launch(headless=False, channel='msedge')
        else:
            browser = p.chromium.launch(headless=False)

        page = browser.new_page()

        # 검색 테스트
        page.goto('https://www.coupang.com/')
        time.sleep(3)

        # ... 검색 로직

        # Fingerprint 확인
        page.goto('https://tls.browserleaks.com/json')
        time.sleep(2)

        content = page.content()
        # Akamai Hash 추출

        browser.close()
```

### 2. 쿠키 이전 테스트

```python
# test_cookie_transfer.py

# Browser A로 로그인/검색
browser_a = p.chromium.launch(channel='chrome')
cookies = await context.cookies()
await browser_a.close()

# Browser B로 쿠키 복원
browser_b = p.chromium.launch(channel='chrome-beta')
await context.add_cookies(cookies)

# 검색 계속
```

---

## 결론

### ❌ 런타임 중 TLS 변경: 불가능

**이유:**
- TLS는 BoringSSL 레벨
- 브라우저 시작 시 결정
- CDP/JavaScript로 접근 불가

### ✅ 대안: 빠른 브라우저 전환

**방법:**
1. 차단 감지
2. 쿠키 저장
3. 다른 빌드로 재시작 (~4초)
4. 쿠키 복원
5. 계속 크롤링

**예상 효과:**
- Chrome Stable: 150회
- Chrome Beta: 150회
- Chrome Dev: 150회
- Chromium: 150회
- **총 600회/IP**

### 🎯 최적 전략

**Multi-Build Pool + 쿠키 이전:**
```python
builds = ['chrome', 'chrome-beta', 'chrome-dev', 'chromium', 'msedge']

while True:
    for build in builds:
        browser = launch(build)
        # 150회 검색
        if blocked:
            cookies = save_cookies()
            browser.close()
            continue  # 다음 빌드로
```

**예상:**
- 5개 빌드 × 150회 = 750회/IP
- 10K IP × 750회 = 750만 요청
- 일일 10만 요청 → 75일간 재사용

---

**다음 작업:** 빌드 전환 테스트 스크립트 작성 및 실행
