# Browser Module

브라우저 초기화 및 관리 모듈

## ⚠️ 중요: BrowserFactory 사용 필수!

**절대 직접 `chromium.launch()` 호출 금지!**

### ❌ 잘못된 방법 (Akamai 차단됨)

```javascript
// ❌ 방법 1: Firefox 사용
const { firefox } = require('playwright');
const browser = await firefox.launch({ headless: false });

// ❌ 방법 2: Safari 사용
const { webkit } = require('playwright');
const browser = await webkit.launch({ headless: false });

// ❌ 방법 3: args 추가/수정
const { chromium } = require('playwright');
const browser = await chromium.launch({
  headless: false,
  args: [
    '--disable-blink-features=AutomationControlled',
    '--no-first-run',
    '--disable-web-security',  // ❌ 추가 금지!
    '--user-agent=...'         // ❌ 추가 금지!
  ]
});

// ❌ 방법 4: 일반 컨텍스트 (시크릿 모드 아님)
const page = await browser.newPage();  // ❌ context 없이 직접 생성
```

### ✅ 올바른 방법 (BrowserFactory 사용)

```javascript
const BrowserFactory = require('./lib/browser/browser-factory');

// ✅ headless만 조정 가능
const { browser, context, page } = await BrowserFactory.createBrowser({
  headless: false  // 또는 true
});

// 작업 수행...
await page.goto('https://www.coupang.com/');

// 종료
await BrowserFactory.closeBrowser(browser);
```

## 왜 BrowserFactory를 사용해야 하나?

### 1. Akamai 탐지 방지

Akamai는 다음을 감지합니다:
- **브라우저 종류**: Chromium만 허용 (Firefox/Safari 차단)
- **Args 정확성**: 정확히 2개만 허용
  - `--disable-blink-features=AutomationControlled`
  - `--no-first-run`
- **컨텍스트**: 반드시 시크릿 모드 (Incognito)

### 2. 고정된 설정

BrowserFactory는 설정을 고정합니다:
```javascript
// 절대 변경 불가능한 설정
const browser = await chromium.launch({
  headless: headless,  // ✅ 이것만 조정 가능
  args: [
    '--disable-blink-features=AutomationControlled',  // 고정
    '--no-first-run'                                  // 고정
  ]
});

const context = await browser.newContext();  // 시크릿 모드 고정
```

### 3. 안전한 사용 보장

- **실수 방지**: 다른 브라우저 사용 불가
- **설정 보호**: args 추가/수정 불가
- **시크릿 모드 강제**: 일반 컨텍스트 사용 불가

## 모듈 구조

```
lib/browser/
├── browser-factory.js       # ⭐ 안전한 브라우저 팩토리
├── playwright-browser.js     # BrowserFactory 사용
└── packet-mode.js            # curl-cffi 패킷 모드
```

## 사용 예제

### 1. BrowserFactory 직접 사용

```javascript
const BrowserFactory = require('./lib/browser/browser-factory');

async function crawl() {
  const { browser, context, page } = await BrowserFactory.createBrowser({
    headless: true
  });

  try {
    // 쿠팡 접속
    await page.goto('https://www.coupang.com/');
    await page.waitForTimeout(3000);

    // 검색
    const searchInput = await page.waitForSelector('input[name="q"]');
    await searchInput.click();
    await searchInput.type('키보드', { delay: 150 });
    await page.keyboard.press('Enter');
    await page.waitForTimeout(5000);

    // 쿠키 추출
    const cookies = await BrowserFactory.getCookies(context);
    console.log(`Cookies: ${cookies.length}`);

  } finally {
    await BrowserFactory.closeBrowser(browser);
  }
}
```

### 2. PlaywrightBrowser 래퍼 사용

```javascript
const PlaywrightBrowser = require('./lib/browser/playwright-browser');

async function crawl() {
  const browser = new PlaywrightBrowser({ headless: true });

  await browser.launch();  // 내부적으로 BrowserFactory 사용
  await browser.goto('https://www.coupang.com/');
  await browser.performSearch('키보드', { typingDelay: 150 });

  const cookies = await browser.getCookies();
  await browser.close();
}
```

### 3. 예제 실행

```bash
# BrowserFactory 테스트
node examples/test_browser_factory.js

# PlaywrightBrowser 테스트
node examples/test_browser_mode.js

# 메인 크롤러 (BrowserFactory 사용)
node multi_page_crawler_playwright.js
```

## API Reference

### BrowserFactory

#### `BrowserFactory.createBrowser(options)`
- **Parameters**:
  - `options.headless` (boolean): true/false만 가능 (기본: false)
- **Returns**: `{ browser, context, page }`

#### `BrowserFactory.closeBrowser(browser)`
- **Parameters**:
  - `browser`: createBrowser()로 생성한 브라우저

#### `BrowserFactory.getCookies(context)`
- **Parameters**:
  - `context`: createBrowser()로 생성한 컨텍스트
- **Returns**: 쿠키 배열

## 보안 규칙

### ✅ 허용되는 것
- `headless: true/false` 조정

### ❌ 절대 금지
- Chromium 외 다른 브라우저 (Firefox, Safari, Edge)
- args 추가/수정/제거
- 일반 컨텍스트 사용 (시크릿 모드 필수)
- User-Agent 수정
- 프록시 설정 (args 통해)
- 웹 보안 비활성화

## 문제 해결

### 문제: "ERR_HTTP2_PROTOCOL_ERROR"
**원인**: 잘못된 브라우저 설정

**해결**:
```javascript
// ❌ 직접 chromium.launch() 사용
// ✅ BrowserFactory.createBrowser() 사용
```

### 문제: "Akamai 차단됨"
**원인**: args 추가 또는 Firefox/Safari 사용

**해결**: BrowserFactory만 사용

### 문제: "traceId가 생성되지 않음"
**원인**: 시크릿 모드가 아님

**해결**: BrowserFactory는 자동으로 시크릿 모드 설정

## 참고

- `examples/test_browser_factory.js` - 안전/위험 예제 비교
- `../CLAUDE.md` - 전체 프로젝트 가이드
- `docs/MASTER_GUIDE.md` - 기술 상세 문서
