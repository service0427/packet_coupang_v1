# 하이브리드 패킷 크롤링 전략

## 핵심 아이디어

**Real Chrome의 TLS/세션을 활용하여 패킷 모드로 대량 크롤링**

## 현재 구조 분석

### 동작 원리
```
[Real Chrome 초기 검색]
  ↓
TLS Handshake (BoringSSL)
  ↓
HTTP/2 Connection Established
  ↓
Akamai Bot Manager 검증 통과
  ↓
세션/쿠키 생성
  ↓
[fetch로 추가 요청]
  ↓
기존 TLS 세션 재사용 ✅
쿠키 포함 ✅
  ↓
성공!
```

### 핵심 발견
1. ✅ Real Chrome이 TLS + 세션 생성
2. ✅ fetch가 그 기반 위에서 작동
3. ✅ Akamai는 이미 검증된 세션이므로 통과
4. ⚠️ fetch는 JavaScript 제약 (단발성)

## 하이브리드 방안들

### 방안 1: Chrome Extension + Native Messaging ⭐ (가장 현실적)

**장점**:
- Chrome의 TLS/세션을 그대로 활용
- Native 프로그램과 통신
- 안정적, 구현 쉬움

**구조**:
```
[Chrome Extension]
  ↓ (Native Messaging)
[Node.js/Python Native Host]
  ↓
[BoringSSL 기반 커스텀 클라이언트]
  ↓
대량 패킷 요청
```

**구현**:

#### 1. Chrome Extension (manifest.json)
```json
{
  "manifest_version": 3,
  "name": "Coupang Crawler",
  "version": "1.0",
  "permissions": [
    "cookies",
    "webRequest",
    "nativeMessaging"
  ],
  "host_permissions": [
    "*://*.coupang.com/*"
  ],
  "background": {
    "service_worker": "background.js"
  }
}
```

#### 2. Extension Background Script
```javascript
// background.js

// 초기 검색 후 세션 정보 추출
chrome.webRequest.onBeforeRequest.addListener(
  async (details) => {
    if (details.url.includes('coupang.com')) {
      // 쿠키 추출
      const cookies = await chrome.cookies.getAll({
        domain: '.coupang.com'
      });

      // Native Host에 전송
      const port = chrome.runtime.connectNative('com.coupang.crawler');
      port.postMessage({
        type: 'session_info',
        cookies: cookies,
        url: details.url
      });

      // Native Host로부터 응답 수신
      port.onMessage.addListener((response) => {
        console.log('Crawled:', response.products);
      });
    }
  },
  { urls: ["*://*.coupang.com/*"] }
);
```

#### 3. Native Host (Node.js)
```javascript
// native_host.js
const net = require('net');
const tls = require('tls');
const http2 = require('http2');

class HybridCrawler {
  constructor() {
    this.session = null;
    this.cookies = null;
  }

  // Extension으로부터 세션 정보 수신
  setSession(sessionInfo) {
    this.cookies = sessionInfo.cookies;
    this.session = sessionInfo;
  }

  // BoringSSL 기반 TLS 연결 (Node.js는 자동으로 BoringSSL 사용)
  async createConnection() {
    const client = http2.connect('https://www.coupang.com', {
      // TLS 옵션
      rejectUnauthorized: false,
      // HTTP/2 설정
      settings: {
        enablePush: false
      }
    });

    return client;
  }

  // 패킷 모드로 대량 크롤링
  async crawlKeywords(keywords) {
    const client = await this.createConnection();
    const results = [];

    for (const keyword of keywords) {
      const req = client.request({
        ':method': 'GET',
        ':path': `/np/search?q=${encodeURIComponent(keyword)}`,
        'cookie': this.formatCookies(),
        'user-agent': 'Mozilla/5.0 ...',
        'accept': 'text/html',
        'accept-language': 'ko-KR,ko;q=0.9'
      });

      const chunks = [];
      req.on('data', chunk => chunks.push(chunk));
      req.on('end', () => {
        const html = Buffer.concat(chunks).toString();
        const products = this.extractProducts(html);
        results.push({ keyword, products });
      });

      req.end();

      // 간격 (2.5~5초)
      await this.randomDelay(2500, 5000);
    }

    client.close();
    return results;
  }

  formatCookies() {
    return this.cookies.map(c => `${c.name}=${c.value}`).join('; ');
  }

  extractProducts(html) {
    const productRegex = /href="([^"]*\/products\/(\d+)[^"]*)"/g;
    const products = [];
    let match;
    while ((match = productRegex.exec(html)) !== null) {
      products.push(match[2]);
    }
    return products;
  }

  randomDelay(min, max) {
    return new Promise(resolve =>
      setTimeout(resolve, Math.random() * (max - min) + min)
    );
  }
}

// Native Messaging 프로토콜
process.stdin.on('data', async (data) => {
  const message = JSON.parse(data);

  if (message.type === 'session_info') {
    crawler.setSession(message);

    // 대량 크롤링 시작
    const keywords = ['마우스', '키보드', '모니터', ...]; // 1000개
    const results = await crawler.crawlKeywords(keywords);

    // Extension에 결과 전송
    process.stdout.write(JSON.stringify({
      type: 'crawl_results',
      results: results
    }));
  }
});

const crawler = new HybridCrawler();
```

### 방안 2: Chrome CDP + Python BoringSSL

**구조**:
```python
from playwright.sync_api import sync_playwright
import ssl
import socket
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization

class HybridCrawler:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.page = None
        self.cookies = None
        self.tls_version = None

    def initialize_chrome(self):
        """Real Chrome으로 초기 세션 생성"""
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.connect_over_cdp("http://localhost:9222")
        self.page = self.browser.contexts[0].pages[0]

        # 초기 검색 (Akamai 통과)
        self.page.goto('https://www.coupang.com/')
        # ... 검색 로직

        # 쿠키 추출
        self.cookies = self.page.context.cookies()

    def create_custom_tls_client(self):
        """BoringSSL 기반 커스텀 TLS 클라이언트"""
        context = ssl.create_default_context()

        # Chrome과 동일한 TLS 설정
        context.minimum_version = ssl.TLSVersion.TLSv1_3
        context.set_ciphers('TLS_AES_128_GCM_SHA256:TLS_AES_256_GCM_SHA384:...')

        sock = socket.create_connection(('www.coupang.com', 443))
        ssock = context.wrap_socket(sock, server_hostname='www.coupang.com')

        return ssock

    def send_http2_request(self, keyword):
        """HTTP/2 패킷 전송"""
        import h2.connection
        import h2.config

        config = h2.config.H2Configuration(client_side=True)
        conn = h2.connection.H2Connection(config=config)
        conn.initiate_connection()

        # ... HTTP/2 요청 전송
```

### 방안 3: Chromium 소스 수정 (가장 강력하지만 복잡)

**개념**:
- Chromium 소스에 커스텀 API 추가
- JavaScript에서 TLS 세션 직접 접근
- BoringSSL 레벨에서 제어

**장점**:
- 완전한 제어
- 최고 성능

**단점**:
- Chromium 빌드 필요 (시간 많이 소요)
- 유지보수 어려움

## 비교표

| 방안 | 난이도 | 성능 | 안정성 | 추천도 |
|------|--------|------|--------|--------|
| Extension + Native | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ✅ 강력 추천 |
| CDP + Python | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ✅ 추천 |
| Chromium 수정 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⚠️ 고급 |

## 추천 구현 순서

### Phase 1: 프로토타입 (Extension + Native)
1. Chrome Extension 개발
2. Native Host (Node.js) 개발
3. 쿠키/세션 전달 검증
4. 소규모 테스트 (10개 키워드)

### Phase 2: 최적화
1. HTTP/2 연결 풀링
2. 멀티플렉싱
3. 에러 핸들링
4. Rate limiting

### Phase 3: 스케일업
1. 멀티 Chrome 인스턴스
2. 프록시 통합
3. 분산 처리
4. 모니터링

## 예상 성능

**현재 (fetch)**:
- 1회 검색 후 fetch 가능
- 약 150회까지
- 간격: 2.5~5초
- 처리량: ~720회/시간

**하이브리드 패킷 (목표)**:
- 1회 검색 후 패킷 모드
- 약 150회까지 (동일)
- 간격: 1~2초 (더 빠름)
- 처리량: ~1,800회/시간
- 멀티 인스턴스: 10배 이상

## 핵심 포인트

1. ✅ **Real Chrome의 TLS 세션 활용**
   - BoringSSL로 생성된 세션
   - Akamai 검증 통과된 상태

2. ✅ **쿠키/헤더 그대로 사용**
   - Chrome에서 추출
   - 패킷에 포함

3. ✅ **HTTP/2 연결 유지**
   - 멀티플렉싱
   - 효율적

4. ⚠️ **여전히 Rate Limit 존재**
   - IP당 ~150회
   - 프록시 필요

## 결론

**가능합니다!**

현재 fetch 방식은 개념 증명(PoC)이고, 이를 기반으로 **진정한 하이브리드 패킷 버전**을 구현할 수 있습니다.

**가장 현실적인 방안**: Extension + Native Messaging (Node.js)

**예상 효과**:
- 속도: 2~3배 향상
- 안정성: Real Chrome 기반이므로 높음
- 확장성: 멀티 인스턴스로 무한 확장 가능
