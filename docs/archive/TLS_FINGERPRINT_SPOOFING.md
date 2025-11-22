# TLS Fingerprint 변조를 통한 확장 가능한 우회 전략

## 문제 상황

**사용자 시나리오**:
> Chrome 120~140 (20개 버전)을 랜덤으로 사용해도 결국 모두 차단됨

**원인**:
```
Chrome 120~140:
├─ User Agent: ✅ 다름 (표면적)
├─ TLS Fingerprint: ❌ 동일! (BoringSSL 같은 버전)
├─ HTTP/2 Fingerprint: ❌ 동일!
└─ Akamai가 진짜 추적하는 것: TLS + HTTP/2 조합
```

## Akamai의 진짜 Fingerprinting

### JA3 Fingerprint (TLS)

```
JA3 = MD5(
    TLS Version,
    Cipher Suites (순서 중요!),
    Extensions (순서 중요!),
    Elliptic Curves,
    EC Point Formats
)

Chrome 120: JA3 = "771,4865-4866-4867-49195-49199-49196-49200-52393-52392-49171-49172-156-157-47-53,0-23-65281-10-11-35-16-5-13-18-51-45-43-27-17513,29-23-24,0"

Chrome 140: JA3 = "771,4865-4866-4867-49195-49199-49196-49200-52393-52392-49171-49172-156-157-47-53,0-23-65281-10-11-35-16-5-13-18-51-45-43-27-17513,29-23-24,0"

→ 동일! (같은 BoringSSL 버전)
```

### HTTP/2 Fingerprint

```
HTTP2 Fingerprint = (
    SETTINGS Frame Order,
    Initial Window Size,
    PRIORITY Frames,
    Header Compression Table
)

Chrome 모든 버전: 동일한 HTTP/2 구현
```

## 해결 방법

### 방법 1: 커스텀 Chrome 빌드 (TLS 변조)

#### 1-1. BoringSSL Cipher Suite 순서 변조

```c
// chromium/src/third_party/boringssl/ssl/ssl_cipher.cc

// 기존 (Chrome 기본)
static const SSL_CIPHER kCiphers[] = {
    // TLS 1.3
    {TLS1_3_CK_AES_128_GCM_SHA256, "TLS_AES_128_GCM_SHA256", ...},
    {TLS1_3_CK_AES_256_GCM_SHA384, "TLS_AES_256_GCM_SHA384", ...},
    {TLS1_3_CK_CHACHA20_POLY1305_SHA256, "TLS_CHACHA20_POLY1305_SHA256", ...},
    // TLS 1.2
    {TLS1_CK_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256, ...},
    ...
};

// 변조 (순서 변경으로 다른 JA3 생성)
static const SSL_CIPHER kCiphers_Custom1[] = {
    {TLS1_3_CK_AES_256_GCM_SHA384, ...},        // 순서 변경
    {TLS1_3_CK_AES_128_GCM_SHA256, ...},
    {TLS1_3_CK_CHACHA20_POLY1305_SHA256, ...},
    ...
};

static const SSL_CIPHER kCiphers_Custom2[] = {
    {TLS1_3_CK_CHACHA20_POLY1305_SHA256, ...},  // 또 다른 순서
    {TLS1_3_CK_AES_128_GCM_SHA256, ...},
    ...
};
```

**빌드**:
```bash
# Chromium 소스 다운로드
git clone https://chromium.googlesource.com/chromium/src.git

# TLS Cipher Suite 순서 변경
vim third_party/boringssl/ssl/ssl_cipher.cc

# 여러 버전 빌드
./build_custom_chrome.sh --profile=custom1  # JA3_1
./build_custom_chrome.sh --profile=custom2  # JA3_2
./build_custom_chrome.sh --profile=custom3  # JA3_3
```

#### 1-2. HTTP/2 SETTINGS 변조

```c
// chromium/src/net/http2/http2_constants.cc

// 기존
const Http2SettingsMap kDefaultSettings = {
    {SETTINGS_HEADER_TABLE_SIZE, 65536},
    {SETTINGS_ENABLE_PUSH, 0},
    {SETTINGS_MAX_CONCURRENT_STREAMS, 1000},
    {SETTINGS_INITIAL_WINDOW_SIZE, 6291456},
    {SETTINGS_MAX_FRAME_SIZE, 16384},
    {SETTINGS_MAX_HEADER_LIST_SIZE, 262144}
};

// 변조 버전 1
const Http2SettingsMap kCustomSettings1 = {
    {SETTINGS_HEADER_TABLE_SIZE, 32768},      // 변경
    {SETTINGS_ENABLE_PUSH, 0},
    {SETTINGS_MAX_CONCURRENT_STREAMS, 500},   // 변경
    {SETTINGS_INITIAL_WINDOW_SIZE, 3145728},  // 변경
    ...
};
```

**장점**:
- 완전히 다른 TLS/HTTP2 Fingerprint 생성
- 수십~수백 개의 고유 조합 가능
- Akamai 차단 키 완전 분리

**단점**:
- Chromium 빌드 필요 (시간 소요: 2-4시간)
- 기술적 난이도 높음
- 유지보수 어려움

### 방법 2: 완전히 다른 브라우저 엔진 사용

#### 2-1. 브라우저 엔진 다양화

```javascript
const browserPool = [
    // Chromium 계열 (같은 TLS)
    { engine: 'chrome', versions: [120, 125, 130] },     // JA3_1

    // Firefox (다른 TLS 구현!)
    { engine: 'firefox', versions: [120, 121, 122] },    // JA3_2 (NSS)

    // Webkit (Safari 엔진, 다른 TLS!)
    { engine: 'webkit', versions: [17.0, 17.1] },       // JA3_3

    // Edge (Chromium 기반이지만 약간 다른 설정)
    { engine: 'msedge', versions: [120, 121] }          // JA3_4
];
```

**Firefox vs Chrome TLS 차이**:
```
Chrome (BoringSSL):
JA3 = "771,4865-4866-4867-49195-49199-49196-49200..."

Firefox (NSS):
JA3 = "771,4865-4867-4866-49195-49199-52393-52392..."
       ^^^^^ 순서가 다름!
```

#### 2-2. Playwright Multi-Browser 구현

```javascript
// src/multi_browser_rotator.js
const { chromium, firefox, webkit } = require('playwright');

class MultiBrowserRotator {
    constructor() {
        this.browsers = [];
        this.currentIndex = 0;
        this.requestCounts = new Map();
        this.maxRequestsPerBrowser = 50;
    }

    async initialize() {
        // Chrome 여러 버전
        for (let version of [120, 125, 130, 135, 140]) {
            this.browsers.push({
                type: 'chromium',
                version: version,
                launchOptions: {
                    channel: 'chrome',
                    args: [`--user-agent-version=${version}`]
                },
                fingerprint: `chrome_${version}`
            });
        }

        // Firefox
        for (let version of [120, 121, 122]) {
            this.browsers.push({
                type: 'firefox',
                version: version,
                launchOptions: {},
                fingerprint: `firefox_${version}`
            });
        }

        // Webkit (Safari)
        this.browsers.push({
            type: 'webkit',
            version: 17,
            launchOptions: {},
            fingerprint: 'webkit_17'
        });

        console.log(`✅ ${this.browsers.length}개 브라우저 프로필 준비됨`);
    }

    async getNextBrowser() {
        const browser = this.browsers[this.currentIndex];
        const count = this.requestCounts.get(browser.fingerprint) || 0;

        // 50회 사용 후 다음 브라우저로 전환
        if (count >= this.maxRequestsPerBrowser) {
            this.currentIndex = (this.currentIndex + 1) % this.browsers.length;
            console.log(`🔄 브라우저 전환: ${this.browsers[this.currentIndex].fingerprint}`);
            this.requestCounts.set(browser.fingerprint, 0);
        }

        this.requestCounts.set(browser.fingerprint, count + 1);

        // 브라우저 실행
        let browserInstance;
        if (browser.type === 'chromium') {
            browserInstance = await chromium.launch(browser.launchOptions);
        } else if (browser.type === 'firefox') {
            browserInstance = await firefox.launch(browser.launchOptions);
        } else if (browser.type === 'webkit') {
            browserInstance = await webkit.launch(browser.launchOptions);
        }

        return {
            browser: browserInstance,
            fingerprint: browser.fingerprint
        };
    }

    getStats() {
        console.log('\n📊 브라우저 사용 통계:');
        for (let [fingerprint, count] of this.requestCounts) {
            console.log(`  ${fingerprint}: ${count}회`);
        }
    }
}

// 사용 예시
async function main() {
    const rotator = new MultiBrowserRotator();
    await rotator.initialize();

    const keywords = ['물티슈', '음료수', '과자', ...]; // 1000개

    for (let keyword of keywords) {
        const { browser, fingerprint } = await rotator.getNextBrowser();
        const context = await browser.newContext();
        const page = await context.newPage();

        try {
            await page.goto('https://www.coupang.com/');
            await page.fill('input[name="q"]', keyword);
            await page.press('input[name="q"]', 'Enter');
            await page.waitForLoadState('domcontentloaded');

            console.log(`✅ ${keyword} - ${fingerprint}`);
        } finally {
            await browser.close();
        }

        await sleep(randomInt(5000, 10000));
    }

    rotator.getStats();
}

main();
```

**효과**:
```
Chrome 120-140 (5개): 5 × 50 = 250회
Firefox 120-122 (3개): 3 × 50 = 150회
Webkit 17 (1개): 1 × 50 = 50회
────────────────────────────────────
총 가능: 450회 (다른 TLS Fingerprint로 분산)
```

### 방법 3: IP + Browser 조합 (최대 확장)

#### 3-1. IP Rotation + Browser Rotation

```javascript
class SuperRotator {
    constructor() {
        this.browsers = [
            'chrome_120', 'chrome_125', 'chrome_130',
            'firefox_120', 'firefox_121',
            'webkit_17'
        ];

        this.proxies = [
            '192.168.1.1',    // 공유기 IP
            '192.168.1.2',    // 다른 디바이스
            // VPN/프록시 사용 시
            'proxy1.com:8080',
            'proxy2.com:8080',
        ];

        this.combinations = [];

        // 모든 조합 생성
        for (let browser of this.browsers) {
            for (let proxy of this.proxies) {
                this.combinations.push({ browser, proxy });
            }
        }

        console.log(`✅ ${this.combinations.length}개 조합 생성됨`);
        // 6 browsers × 4 IPs = 24 combinations
        // 24 × 50 requests = 1,200 requests
    }
}
```

### 방법 4: 현실적인 최적 전략

**가장 실용적인 접근**:

```javascript
// src/realistic_browser_strategy.js
const { chromium, firefox } = require('playwright');

class RealisticStrategy {
    constructor() {
        // Chrome 5개 + Firefox 3개 = 8개 브라우저
        this.pool = [
            { type: 'chromium', path: 'C:\\Program Files\\Google\\Chrome 120\\chrome.exe' },
            { type: 'chromium', path: 'C:\\Program Files\\Google\\Chrome 125\\chrome.exe' },
            { type: 'chromium', path: 'C:\\Program Files\\Google\\Chrome 130\\chrome.exe' },
            { type: 'firefox', path: 'C:\\Program Files\\Mozilla Firefox 120\\firefox.exe' },
            { type: 'firefox', path: 'C:\\Program Files\\Mozilla Firefox 121\\firefox.exe' },
        ];

        this.maxPerBrowser = 50;
        this.currentIndex = 0;
        this.count = 0;
    }

    async getNext() {
        if (this.count >= this.maxPerBrowser) {
            this.currentIndex = (this.currentIndex + 1) % this.pool.length;
            this.count = 0;

            // 5분 대기 (쿨다운)
            console.log('⏳ 브라우저 전환 전 5분 대기...');
            await sleep(5 * 60 * 1000);
        }

        const config = this.pool[this.currentIndex];
        this.count++;

        if (config.type === 'chromium') {
            return await chromium.launch({ executablePath: config.path });
        } else {
            return await firefox.launch({ executablePath: config.path });
        }
    }
}
```

**확장 용량**:
```
5개 브라우저 × 50회 = 250회/주기
쿨다운 (5분) × 5번 = 25분

1시간당 가능:
└─ 250회 × 2주기 = 500회/시간
```

## 추천 전략 우선순위

### 1순위: Firefox + Chrome 조합 ⭐⭐⭐
```bash
# Firefox 3개 버전 설치
# Chrome 5개 버전 설치
# → 총 8개 다른 TLS Fingerprint
# → 400회 요청 가능
```

**이유**:
- ✅ 간단한 설치로 다른 TLS 구현 확보
- ✅ 유지보수 쉬움
- ✅ 안정적

### 2순위: IP Rotation 추가
```javascript
// 공유기 여러 개 또는 모바일 핫스팟
const ips = ['192.168.1.1', '192.168.2.1', '192.168.3.1'];
// 8 browsers × 3 IPs = 24 조합 = 1,200회
```

### 3순위: 커스텀 Chrome 빌드 (고급 사용자만)
```
TLS Cipher Suite 순서 변조
→ 무제한 고유 Fingerprint 생성 가능
→ 전문 지식 필요
```

## 구현 예시

### 간단한 Multi-Browser 구현

```javascript
// src/simple_multi_browser.js
const { chromium, firefox } = require('playwright');

async function searchWithRotation(keywords) {
    const browsers = [
        { launch: () => chromium.launch({ channel: 'chrome' }), name: 'Chrome' },
        { launch: () => firefox.launch(), name: 'Firefox' }
    ];

    let browserIndex = 0;
    let requestCount = 0;
    const maxPerBrowser = 50;

    for (let keyword of keywords) {
        if (requestCount >= maxPerBrowser) {
            browserIndex = (browserIndex + 1) % browsers.length;
            requestCount = 0;
            console.log(`🔄 ${browsers[browserIndex].name}으로 전환`);
            await sleep(60000); // 1분 쿨다운
        }

        const browser = await browsers[browserIndex].launch();
        const context = await browser.newContext();
        const page = await context.newPage();

        try {
            await page.goto('https://www.coupang.com/');
            await page.fill('input[name="q"]', keyword);
            await page.press('input[name="q"]', 'Enter');
            await page.waitForLoadState('domcontentloaded');

            console.log(`✅ [${browsers[browserIndex].name}] ${keyword}`);
            requestCount++;
        } finally {
            await browser.close();
        }

        await sleep(randomInt(5000, 10000));
    }
}

function randomInt(min, max) {
    return Math.floor(Math.random() * (max - min + 1)) + min;
}

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

// 실행
const keywords = ['물티슈', '음료수', '과자', /* ... 1000개 */];
searchWithRotation(keywords);
```

## 결론

### 핵심 인사이트

1. **Chrome 120~140은 같은 TLS Fingerprint**
   - User Agent만 다름
   - JA3 (TLS) 동일
   - HTTP/2 Fingerprint 동일

2. **다른 브라우저 엔진 = 다른 TLS**
   - Chrome (BoringSSL)
   - Firefox (NSS)
   - Safari/Webkit (SecureTransport)

3. **조합의 힘**
   ```
   브라우저: 8개 × 요청: 50회 = 400회
   + IP Rotation: × 3개 = 1,200회
   + 쿨다운 & 재사용 = 무제한 확장 가능
   ```

### 최종 권장

**가장 현실적이고 효과적인 방법**:
1. **Firefox 3개 버전 + Chrome 5개 버전** 설치
2. **Smart Rotation** 구현 (50회마다 전환)
3. **가능하면 IP도 분산** (모바일 핫스팟 등)

이 방식으로 **사실상 무제한 크롤링**이 가능합니다.

---

**작성일**: 2025-10-08
**난이도**: 중급 (Firefox+Chrome) / 고급 (커스텀 빌드)
**효과**: ⭐⭐⭐⭐⭐
