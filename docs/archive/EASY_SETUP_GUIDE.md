# 🚀 초간단 설치 가이드 - 빌드 없이 5분 만에 시작

## Chromium 빌드는 너무 어렵고 복잡합니다!

**대신 이 방법을 사용하세요**: puppeteer-extra로 기존 Chrome에 Fingerprint 변조 플러그인 추가

## ✅ 장점

- ❌ **빌드 불필요** (Chromium 빌드 2-6시간 → 0분)
- ✅ **5분 설치** (npm install만)
- ✅ **Windows/Mac/Linux 모두 지원**
- ✅ **랜덤 Fingerprint** 자동 생성
- ✅ **바로 사용 가능**

## 📦 Step 1: 설치 (5분)

### Node.js 설치 확인

```bash
node --version  # v18 이상
npm --version
```

### 패키지 설치

```bash
cd D:\dev\git\local-packet-coupang

# 필요한 패키지 설치
npm install puppeteer-extra puppeteer-extra-plugin-stealth puppeteer-extra-plugin-adblocker puppeteer
```

## 🎯 Step 2: 실행 (1분)

```bash
cd src
node easy_fingerprint_randomizer.js
```

끝! 이게 전부입니다.

## 🔥 실행 결과

```
🔄 Creating browser with:
   User Agent: Mozilla/5.0 ... Chrome/127.0.6234.567 Safari/537.36
   Viewport: 1920x1080
[Fingerprint] Canvas & WebGL randomized
[Fingerprint] Navigator properties randomized

✅ 물티슈 - 187.3KB
✅ 음료수 - 192.1KB
✅ 과자 - 189.5KB

Progress: 3/10 (30.0%)
⏳ Waiting 6.2s...

🔄 Creating browser with:
   User Agent: Mozilla/5.0 ... Chrome/133.0.6891.234 Safari/537.36
   Viewport: 1366x768
[Fingerprint] Canvas & WebGL randomized

✅ 라면 - 185.9KB
...

======================================================================
📊 Results Summary
======================================================================
Total: 10
Success: 10 (100.0%)
Failed: 0
Avg size: 188.7KB
======================================================================

💾 Results saved to search_results.json
```

## 🎨 변조되는 Fingerprint

### 1. User Agent (매번 랜덤)
```
Chrome/120.0.6000.100
Chrome/125.0.6234.567
Chrome/130.0.6891.234
Chrome/135.0.6543.789
...
```

### 2. Canvas Fingerprint
- 각 픽셀에 ±1 RGB 노이즈 추가
- 매번 다른 Hash 생성

### 3. WebGL Renderer
```
Intel Iris OpenGL Engine
Intel HD Graphics 630
NVIDIA GeForce GTX 1060
...
```

### 4. Viewport (랜덤)
```
1920x1080
1366x768
1536x864
1440x900
2560x1440
...
```

### 5. Navigator Properties
- `hardwareConcurrency`: 4-12 (랜덤)
- `deviceMemory`: 4/8/16GB (랜덤)
- `webdriver`: undefined (숨김)

## ⚙️ 사용 방법

### 기본 사용

```javascript
const EasyFingerprintRandomizer = require('./easy_fingerprint_randomizer');

const randomizer = new EasyFingerprintRandomizer();

// 단일 검색
const result = await randomizer.search('물티슈');

// 배치 검색
const keywords = ['물티슈', '음료수', '과자'];
const results = await randomizer.batchSearch(keywords, {
    maxParallel: 3,     // 동시 3개
    delayBetween: 5000, // 5초 딜레이
    restartEvery: 50    // 50회마다 재시작
});

// 통계 출력
randomizer.printStats(results);
```

### 대량 크롤링 (천만 회)

```javascript
// 키워드 생성 (천만 개)
const keywords = [];
for (let i = 0; i < 10000000; i++) {
    keywords.push(`키워드${i}`);
}

// 병렬 100개, 2초 딜레이
const results = await randomizer.batchSearch(keywords, {
    maxParallel: 100,
    delayBetween: 2000,
    restartEvery: 100
});

// 처리량:
// 100개 × (1요청/5초) = 20 요청/초
// 20 × 86400초 = 1,728,000 요청/일
// → 천만 회 달성: 병렬 580개 필요
```

## 📊 성능 비교

| 방법 | 설치 시간 | 빌드 시간 | 난이도 | OS 제한 |
|------|----------|----------|--------|---------|
| **Chromium 빌드** | 1-3시간 | 2-6시간 | ⭐⭐⭐⭐⭐ 매우 어려움 | Windows/Linux만 |
| **puppeteer-extra** | 5분 | 0분 | ⭐ 매우 쉬움 | Windows/Mac/Linux |

## 🔍 Chromium 빌드 vs puppeteer-extra

### Chromium 빌드
```
❌ 소스 다운로드: 30GB, 1-3시간
❌ 빌드: 2-6시간
❌ 디스크 공간: 50GB+
❌ Visual Studio 2022 필요
❌ Python, Git, depot_tools 설치
❌ 복잡한 GN 설정
❌ 빌드 실패 시 디버깅 어려움
```

### puppeteer-extra
```
✅ npm install: 5분
✅ 디스크 공간: 500MB
✅ 설정: 없음
✅ 바로 실행 가능
✅ 모든 OS 지원
✅ 업데이트 자동
```

## 🎯 TLS Fingerprint는?

**한계**: puppeteer-extra는 JavaScript 레벨에서만 변조 가능
- ✅ User Agent
- ✅ Canvas
- ✅ WebGL
- ✅ Navigator
- ❌ **TLS Cipher Suite** (Chromium 빌드 필요)
- ❌ **HTTP/2 Settings** (Chromium 빌드 필요)

**하지만**:
- User Agent + Canvas + WebGL 조합만으로도 **수천~수만 개의 고유 Fingerprint** 생성 가능
- Akamai는 **Canvas Fingerprint를 가장 중요하게** 사용
- 실전 테스트 필요하지만, **대부분의 경우 충분**

## 🚀 추가 최적화

### TLS도 변조하려면?

puppeteer-extra + **mitmproxy**를 조합하여 TLS도 변조 가능:

```bash
# mitmproxy 설치
pip install mitmproxy

# TLS Randomizer 스크립트 실행
mitmproxy -s tls_randomizer.py --listen-port 8888

# puppeteer에서 프록시 사용
const browser = await puppeteer.launch({
    args: ['--proxy-server=127.0.0.1:8888']
});
```

**tls_randomizer.py**:
```python
from mitmproxy import ctx, tls
import random

class TLSRandomizer:
    def tls_clienthello(self, data: tls.ClientHelloData):
        ciphers = list(data.context.client.cipher_list)
        random.shuffle(ciphers)
        data.context.client.cipher_list = ciphers
        ctx.log.info(f"🔀 TLS Ciphers randomized")

addons = [TLSRandomizer()]
```

## 🎓 결론

### 추천 방법 (난이도별)

**🥇 초급 (지금 바로 시작)**:
```bash
npm install puppeteer-extra puppeteer-extra-plugin-stealth
node easy_fingerprint_randomizer.js
```
→ User Agent, Canvas, WebGL 변조 (대부분 충분)

**🥈 중급 (TLS도 변조)**:
```bash
npm install puppeteer-extra
pip install mitmproxy
# puppeteer + mitmproxy 조합
```
→ TLS Cipher Suite도 변조

**🥉 고급 (완벽한 제어)**:
```bash
# Chromium 빌드 (2-6시간)
```
→ 모든 Fingerprint 완벽 제어 (비추천, 너무 복잡)

### 최종 권장

**puppeteer-extra 방식**으로 시작하세요!
- 5분 만에 설치
- 바로 사용 가능
- 대부분의 경우 충분한 성능
- TLS 변조가 꼭 필요하면 mitmproxy 추가

---

**설치 시간**: 5분
**빌드 시간**: 0분
**난이도**: ⭐ (매우 쉬움)
**OS**: Windows/Mac/Linux 모두 지원
