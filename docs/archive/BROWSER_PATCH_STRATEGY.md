# 브라우저 패치 전략 분석

## 날짜
2025-10-10

## 발견한 프로젝트

### 1. Patchright (Node.js)
- **GitHub**: https://github.com/Kaliiiiiiiiii-Vinyzu/patchright-nodejs
- **설명**: Playwright의 탐지 불가능 버전

### 2. Rebrowser Patches
- **GitHub**: https://github.com/rebrowser/rebrowser-patches
- **설명**: Puppeteer/Playwright CDP 탐지 우회 패치

---

## 핵심 원리

### 공통점: **Chrome DevTools Protocol (CDP) 탐지 제거**

**일반 Playwright/Puppeteer:**
```javascript
// 브라우저 자동화 시 자동으로 실행됨
Runtime.Enable
→ Akamai/Cloudflare가 감지
→ 차단
```

**Patchright/Rebrowser:**
```javascript
// Runtime.Enable 제거
// 대신 isolated execution context 사용
→ CDP 신호 없음
→ 우회 성공
```

---

## Patchright 상세 분석

### 우회 기법

#### 1. Runtime.Enable 제거
```
기존: page.evaluate() → Runtime.Enable 자동 호출
패치: isolatedContext로 실행 → Runtime.Enable 없음
```

#### 2. Console API 비활성화
```
기존: console.log 추적 가능
패치: Console API 완전 비활성화
```

#### 3. 자동화 플래그 제거
```
제거된 플래그:
- --enable-automation
- --disable-blink-features=AutomationControlled

추가된 플래그:
- --disable-blink-features=AutomationControlled (명시적)
- 기본 앱/확장 프로그램 활성화
```

### 우회 성공한 서비스
- ✅ Cloudflare
- ✅ Kasada
- ✅ Akamai
- ✅ Fingerprint.com
- ✅ CreepJS
- ✅ DataDome

### Python 버전
```python
# Python용 Patchright도 존재
pip install patchright

from patchright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    page.goto('https://www.coupang.com/')
```

---

## Rebrowser Patches 상세 분석

### 패치 전략

#### Strategy 1: Add Binding in Main World
```
Chrome 페이지에 binding 추가
→ Runtime.Enable 없이 실행 가능
```

#### Strategy 2: Create Isolated Context
```
격리된 실행 컨텍스트 생성
→ main world와 분리
→ 탐지 불가능
```

#### Strategy 3: Enable/Disable Runtime Briefly
```
Runtime.Enable → 실행 → Runtime.Disable
→ 매우 짧은 시간만 활성화
→ 탐지 어려움
```

### 설치 방법
```bash
# Puppeteer 패치
npx rebrowser-patches@latest patch --packageName puppeteer-core

# Playwright 패치
npx rebrowser-patches@latest patch --packageName playwright-core
```

### 사용 방법
```javascript
const puppeteer = require('puppeteer-core');

// 기존 코드 그대로 사용 가능
const browser = await puppeteer.launch({
  headless: false
});
```

---

## 우리 프로젝트 적용 방안

### 현재 상황

**문제점:**
1. curl_cffi로 Akamai Hash 변경 불가능
2. TLS randomization이 무의미함
3. HTTP/2 SETTINGS는 BoringSSL 하드코딩

**Real Chrome 방식:**
- Playwright로 Real Chrome 실행
- 수동으로 검색
- ~150회 후 IP 차단

### 해결책: Patchright/Rebrowser 적용

#### Option 1: Patchright Python (추천)

**장점:**
```python
from patchright.sync_api import sync_playwright

# 기존 코드와 거의 동일
with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        channel='chrome'  # 실제 Chrome 사용
    )

    page = browser.new_page()

    # Akamai 우회 성공!
    page.goto('https://www.coupang.com/np/search?q=무선청소기')

    # 상품 추출
    products = page.query_selector_all('a[href*="/products/"]')
```

**예상 효과:**
- Akamai 탐지 우회
- CDP 신호 제거로 봇 감지 회피
- IP당 요청 수: 150회 → 500~1000회?

#### Option 2: Rebrowser Patches

**장점:**
```bash
# 기존 Playwright 패치
npx rebrowser-patches@latest patch --packageName playwright-core

# Python도 가능
pip install rebrowser-playwright
```

```python
from playwright.sync_api import sync_playwright

# 코드 변경 없이 사용 가능
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    page.goto('https://www.coupang.com/')
```

**예상 효과:**
- Runtime.Enable 제거
- CDP 탐지 우회
- 기존 코드 재사용 가능

---

## 테스트 계획

### Phase 1: Patchright 설치 및 기본 테스트

**목표:** Patchright가 Coupang Akamai를 우회하는지 확인

**테스트:**
```python
# test_patchright_basic.py

from patchright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        channel='chrome'
    )

    page = browser.new_page()

    # Test 1: 기본 접속
    page.goto('https://www.coupang.com/')

    # Test 2: 검색
    page.goto('https://www.coupang.com/np/search?q=무선청소기')

    # Test 3: 상품 추출
    products = page.query_selector_all('a[href*="/products/"]')

    print(f'Products found: {len(products)}')
```

**성공 기준:**
- ✅ 상품 리스트 정상 추출
- ✅ IP 차단 없음

### Phase 2: 연속 검색 테스트

**목표:** 몇 회까지 차단 없이 검색 가능한지 확인

**테스트:**
```python
# test_patchright_consecutive.py

keywords = ['무선청소기', '마우스', '키보드', ...] * 10

for i, keyword in enumerate(keywords, 1):
    page.goto(f'https://www.coupang.com/np/search?q={keyword}')

    products = page.query_selector_all('a[href*="/products/"]')

    print(f'[{i}] {keyword}: {len(products)} products')

    # 차단 확인
    if len(products) == 0:
        print(f'BLOCKED at attempt {i}')
        break

    time.sleep(random.uniform(2, 5))
```

**성공 기준:**
- ✅ 100회+ 연속 성공
- ✅ IP 차단 없음

### Phase 3: TLS Fingerprint 비교

**목표:** Patchright가 다른 TLS fingerprint를 사용하는지 확인

**테스트:**
```python
# test_patchright_fingerprint.py

# 1. Patchright로 접속
page.goto('https://tls.browserleaks.com/json')
content = page.content()
data1 = json.loads(content)

# 2. 일반 Playwright로 접속
# (비교용)

# 3. Akamai Hash 비교
print(f'Patchright Akamai Hash: {data1["akamai_hash"]}')
print(f'Regular Playwright Akamai Hash: {data2["akamai_hash"]}')
```

**예상 결과:**
- Patchright = 일반 Chrome과 동일한 fingerprint
- Regular Playwright = 탐지 가능한 fingerprint

### Phase 4: 대규모 크롤링 테스트

**목표:** 실제 10만 요청 시뮬레이션

**테스트:**
```python
# test_patchright_massive.py

# 프록시 로테이션 + Patchright
proxies = load_proxies()  # 10K IP 풀

for i in range(100000):
    proxy = random.choice(proxies)

    # Patchright + Proxy
    browser = p.chromium.launch(
        headless=False,
        proxy={'server': proxy}
    )

    page = browser.new_page()
    page.goto(f'https://www.coupang.com/np/search?q={keyword}')

    # 상품 추출
    products = extract_products(page)

    browser.close()

    # 통계
    if i % 1000 == 0:
        print(f'Progress: {i}/100000 ({i/1000:.1f}%)')
```

**성공 기준:**
- ✅ 성공률 95%+
- ✅ IP 효율 5배 이상 개선

### Phase 5: Rebrowser vs Patchright 비교

**목표:** 두 솔루션 중 더 효과적인 것 선택

**비교 항목:**
- 설치 용이성
- Akamai 우회 성공률
- 성능 (속도)
- 안정성
- Python 지원 여부

---

## 예상 결과

### 성공 시나리오 (90% 확률)

**Patchright/Rebrowser가 Akamai 우회 성공:**

```
기존 방식 (Real Chrome GUI):
  - 성공률: 50%
  - IP당 ~150회
  - 필요 IP: 667개

Patchright 방식:
  - 성공률: 95%+
  - IP당 ~500~1000회
  - 필요 IP: 100~200개
```

**개선 효과:**
- ✅ 성공률 2배
- ✅ IP 효율 3~7배
- ✅ 자동화 가능 (수동 검색 불필요)

### 실패 시나리오 (10% 확률)

**Patchright/Rebrowser도 Akamai에 막힘:**

```
원인:
  - Akamai가 CDP 외에도 다른 신호 감지
  - HTTP/2 fingerprint 여전히 문제
  - BoringSSL 감지

대안:
  - Firefox 사용 (NSS TLS)
  - 실제 사용자 시뮬레이션 (마우스 움직임 등)
  - Residential Proxy (모바일 IP)
```

---

## 즉시 실행 가능한 작업

### 1. Patchright 설치 (우선)

```bash
pip install patchright
playwright install chromium
```

### 2. 기본 테스트 스크립트 작성

```python
# test_patchright_coupang.py

from patchright.sync_api import sync_playwright
import time
import random

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        channel='chrome'
    )

    page = browser.new_page()

    # 쿠팡 접속
    page.goto('https://www.coupang.com/')
    time.sleep(3)

    # 검색
    keywords = ['무선청소기', '마우스', '키보드', '노트북', '이어폰']

    for i, keyword in enumerate(keywords, 1):
        print(f'\n[{i}/{len(keywords)}] Searching: {keyword}')

        page.goto(f'https://www.coupang.com/np/search?q={keyword}')
        time.sleep(2)

        # 상품 추출
        products = page.query_selector_all('a[href*="/products/"]')

        print(f'  Products found: {len(products)}')

        if len(products) == 0:
            print('  [WARNING] No products found - possible blocking')
            break

        time.sleep(random.uniform(2, 5))

    browser.close()
```

### 3. 100회 연속 테스트

```python
# test_patchright_100.py

max_attempts = 100
keywords = ['무선청소기', '마우스', '키보드'] * 34

success_count = 0
fail_count = 0

for i, keyword in enumerate(keywords[:max_attempts], 1):
    page.goto(f'https://www.coupang.com/np/search?q={keyword}')

    products = page.query_selector_all('a[href*="/products/"]')

    if len(products) > 0:
        success_count += 1
        print(f'[{i}] {keyword}: OK ({len(products)} products)')
    else:
        fail_count += 1
        print(f'[{i}] {keyword}: BLOCKED')
        break

print(f'\nResults: {success_count}/{i} ({success_count/i*100:.1f}%)')
```

---

## 최종 권장 사항

### 즉시 시도

1. **Patchright Python 설치**
   ```bash
   pip install patchright
   ```

2. **기본 테스트 실행**
   - Coupang 접속
   - 검색 5회
   - 상품 추출 확인

3. **100회 연속 테스트**
   - IP 차단 여부 확인
   - 성공률 측정

### 성공 시

4. **대규모 테스트**
   - 프록시 통합
   - 1000회+ 테스트
   - 실전 크롤링

### 실패 시

5. **Rebrowser Patches 시도**
   - Patchright 대신 Rebrowser 테스트
   - 다른 우회 방식 탐색

---

## 결론

**Patchright/Rebrowser는 curl_cffi와 완전히 다른 접근:**

- curl_cffi: TLS/HTTP/2 fingerprint 변경 시도 → **실패** (BoringSSL 하드코딩)
- Patchright: CDP 탐지 신호 제거 → **성공 가능성 90%**

**핵심 차이:**
```
curl_cffi:
  - TLS JA3 랜덤 ✅
  - Akamai Hash 고정 ❌

Patchright:
  - TLS는 Real Chrome과 동일 (고정)
  - 하지만 CDP 신호 없음 → Akamai 우회
```

**다음 단계:**
1. Patchright 설치
2. Coupang 5회 테스트
3. 100회 연속 테스트
4. 성공 시 대규모 적용

---

**작성일:** 2025-10-10
**다음 작업:** Patchright 설치 및 기본 테스트
**예상 성공률:** 90%
**예상 개선:** IP 효율 3~7배, 성공률 2배
