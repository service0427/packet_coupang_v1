# 커스텀 Chrome 빌드 가이드 - 동적 Fingerprint 생성

## 목표

**하루 천만 회 크롤링**을 위한 런타임 Fingerprint 랜덤화 Chrome 개발

```
요구사항:
├─ 하루: 10,000,000회
├─ 시간당: 416,666회
├─ 초당: 115회
└─ 해결책: 매 요청마다 다른 JA3/JA4/TLS/HTTP2 Fingerprint
```

## 아키텍처

### 핵심 아이디어

```
일반 Chrome:
└─ 고정된 TLS/HTTP2 구현 → 같은 Fingerprint

커스텀 Chrome:
└─ 시작 시 랜덤 시드 생성 → 매번 다른 Fingerprint
    ├─ Cipher Suite 순서: 랜덤
    ├─ Extension 순서: 랜덤
    ├─ HTTP/2 Settings: 랜덤
    └─ Window Size: 랜덤
```

## Chromium 수정 포인트

### 1. BoringSSL - TLS Cipher Suite 랜덤화

**파일**: `third_party/boringssl/ssl/ssl_cipher.cc`

```c
// 원본 (고정된 순서)
static const SSL_CIPHER kCiphers[] = {
    // TLS 1.3
    {TLS1_3_CK_AES_128_GCM_SHA256, "TLS_AES_128_GCM_SHA256", ...},
    {TLS1_3_CK_AES_256_GCM_SHA384, "TLS_AES_256_GCM_SHA384", ...},
    {TLS1_3_CK_CHACHA20_POLY1305_SHA256, "TLS_CHACHA20_POLY1305_SHA256", ...},
    ...
};

// ====================================================
// 커스텀: 런타임 랜덤 순서 생성
// ====================================================

#include <random>
#include <algorithm>
#include <vector>

// 전역 랜덤 시드 (프로세스 시작 시 생성)
static std::mt19937 g_cipher_rng;
static bool g_cipher_randomized = false;

// Cipher Suite 랜덤화 함수
void RandomizeCipherSuites() {
    if (g_cipher_randomized) return;

    // 현재 시간 + PID로 시드 생성
    auto seed = std::chrono::high_resolution_clock::now().time_since_epoch().count();
    seed ^= getpid();
    g_cipher_rng.seed(seed);

    // Cipher Suite 배열을 vector로 복사
    std::vector<SSL_CIPHER> cipher_vec(kCiphers, kCiphers + kCiphersLen);

    // Fisher-Yates Shuffle로 랜덤화
    for (size_t i = cipher_vec.size() - 1; i > 0; --i) {
        std::uniform_int_distribution<size_t> dist(0, i);
        size_t j = dist(g_cipher_rng);
        std::swap(cipher_vec[i], cipher_vec[j]);
    }

    // 원본 배열에 다시 복사
    std::copy(cipher_vec.begin(), cipher_vec.end(), const_cast<SSL_CIPHER*>(kCiphers));

    g_cipher_randomized = true;

    // 로깅 (디버그용)
    printf("[TLS] Cipher Suites randomized with seed: %llu\n", seed);
}

// SSL 초기화 시 자동 호출
void SSL_library_init() {
    CRYPTO_library_init();
    RandomizeCipherSuites();  // ← 추가
}
```

### 2. TLS Extensions 순서 랜덤화

**파일**: `third_party/boringssl/ssl/extensions.cc`

```c
// Extension 순서 랜덤화
static constexpr struct {
    uint16_t value;
    bool (*add_clienthello)(const SSL_HANDSHAKE *hs, CBB *out, bool *out_needs_psk_binder);
} kExtensions[] = {
    {TLSEXT_TYPE_server_name, ext_sni_add_clienthello},
    {TLSEXT_TYPE_extended_master_secret, ext_ems_add_clienthello},
    {TLSEXT_TYPE_renegotiate, ext_ri_add_clienthello},
    {TLSEXT_TYPE_supported_groups, ext_supported_groups_add_clienthello},
    {TLSEXT_TYPE_ec_point_formats, ext_ec_point_add_clienthello},
    {TLSEXT_TYPE_session_ticket, ext_ticket_add_clienthello},
    {TLSEXT_TYPE_application_layer_protocol_negotiation, ext_alpn_add_clienthello},
    {TLSEXT_TYPE_status_request, ext_ocsp_add_clienthello},
    {TLSEXT_TYPE_signature_algorithms, ext_sigalgs_add_clienthello},
    {TLSEXT_TYPE_supported_versions, ext_supported_versions_add_clienthello},
    {TLSEXT_TYPE_cookie, ext_cookie_add_clienthello},
    {TLSEXT_TYPE_quic_transport_parameters, ext_quic_transport_params_add_clienthello},
    {TLSEXT_TYPE_key_share, ext_key_share_add_clienthello},
    {TLSEXT_TYPE_psk_key_exchange_modes, ext_psk_key_exchange_modes_add_clienthello},
    {TLSEXT_TYPE_pre_shared_key, ext_pre_shared_key_add_clienthello},
};

// ====================================================
// 커스텀: Extension 순서 랜덤화
// ====================================================

void RandomizeExtensionOrder() {
    static bool randomized = false;
    if (randomized) return;

    std::vector<decltype(kExtensions[0])> ext_vec(kExtensions, kExtensions + arraysize(kExtensions));

    // pre_shared_key는 항상 마지막에 와야 함 (RFC 8446)
    auto psk_it = std::find_if(ext_vec.begin(), ext_vec.end(),
        [](const auto& e) { return e.value == TLSEXT_TYPE_pre_shared_key; });

    if (psk_it != ext_vec.end()) {
        auto psk = *psk_it;
        ext_vec.erase(psk_it);

        // 나머지 랜덤화
        std::shuffle(ext_vec.begin(), ext_vec.end(), g_cipher_rng);

        // PSK 마지막에 추가
        ext_vec.push_back(psk);
    } else {
        std::shuffle(ext_vec.begin(), ext_vec.end(), g_cipher_rng);
    }

    // 원본에 복사
    std::copy(ext_vec.begin(), ext_vec.end(), const_cast<decltype(kExtensions[0])*>(kExtensions));

    randomized = true;
    printf("[TLS] Extensions order randomized\n");
}
```

### 3. HTTP/2 Settings 랜덤화

**파일**: `net/http2/http2_constants.cc`

```c
// 원본 (고정된 값)
const Http2SettingsMap kDefaultHttp2Settings = {
    {SETTINGS_HEADER_TABLE_SIZE, 65536},
    {SETTINGS_ENABLE_PUSH, 0},
    {SETTINGS_MAX_CONCURRENT_STREAMS, 1000},
    {SETTINGS_INITIAL_WINDOW_SIZE, 6291456},
    {SETTINGS_MAX_FRAME_SIZE, 16384},
    {SETTINGS_MAX_HEADER_LIST_SIZE, 262144},
};

// ====================================================
// 커스텀: HTTP/2 Settings 랜덤화
// ====================================================

#include <random>

Http2SettingsMap GenerateRandomHttp2Settings() {
    static std::mt19937 rng(time(nullptr) ^ getpid());

    std::uniform_int_distribution<uint32_t> header_table_dist(32768, 131072);
    std::uniform_int_distribution<uint32_t> streams_dist(500, 2000);
    std::uniform_int_distribution<uint32_t> window_dist(3145728, 12582912);
    std::uniform_int_distribution<uint32_t> frame_dist(16384, 32768);
    std::uniform_int_distribution<uint32_t> header_list_dist(131072, 524288);

    Http2SettingsMap settings = {
        {SETTINGS_HEADER_TABLE_SIZE, header_table_dist(rng)},
        {SETTINGS_ENABLE_PUSH, 0},  // 항상 0 (보안상)
        {SETTINGS_MAX_CONCURRENT_STREAMS, streams_dist(rng)},
        {SETTINGS_INITIAL_WINDOW_SIZE, window_dist(rng)},
        {SETTINGS_MAX_FRAME_SIZE, frame_dist(rng)},
        {SETTINGS_MAX_HEADER_LIST_SIZE, header_list_dist(rng)},
    };

    printf("[HTTP/2] Settings randomized:\n");
    printf("  HEADER_TABLE_SIZE: %u\n", settings[SETTINGS_HEADER_TABLE_SIZE]);
    printf("  MAX_CONCURRENT_STREAMS: %u\n", settings[SETTINGS_MAX_CONCURRENT_STREAMS]);
    printf("  INITIAL_WINDOW_SIZE: %u\n", settings[SETTINGS_INITIAL_WINDOW_SIZE]);

    return settings;
}

// 기존 함수 수정
const Http2SettingsMap& GetDefaultHttp2Settings() {
    static Http2SettingsMap randomized_settings = GenerateRandomHttp2Settings();
    return randomized_settings;
}
```

### 4. User Agent 동적 생성

**파일**: `content/common/user_agent.cc`

```cpp
// 원본
std::string GetUserAgent() {
    return base::StringPrintf(
        "Mozilla/5.0 (%s) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/%s Safari/537.36",
        GetPlatformInfo().c_str(),
        CHROME_VERSION_STRING);
}

// ====================================================
// 커스텀: User Agent 랜덤 버전 생성
// ====================================================

std::string GenerateRandomUserAgent() {
    static std::mt19937 rng(time(nullptr) ^ getpid());

    // Chrome 버전 범위: 120-140
    std::uniform_int_distribution<int> major_dist(120, 140);
    std::uniform_int_distribution<int> minor_dist(0, 0);
    std::uniform_int_distribution<int> build_dist(6000, 6999);
    std::uniform_int_distribution<int> patch_dist(100, 999);

    int major = major_dist(rng);
    int minor = minor_dist(rng);
    int build = build_dist(rng);
    int patch = patch_dist(rng);

    std::string version = base::StringPrintf("%d.%d.%d.%d", major, minor, build, patch);

    std::string ua = base::StringPrintf(
        "Mozilla/5.0 (%s) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/%s Safari/537.36",
        GetPlatformInfo().c_str(),
        version.c_str());

    printf("[UA] Generated: %s\n", ua.c_str());
    return ua;
}

std::string GetUserAgent() {
    static std::string randomized_ua = GenerateRandomUserAgent();
    return randomized_ua;
}
```

### 5. Canvas Fingerprint 노이즈 추가

**파일**: `third_party/blink/renderer/platform/graphics/canvas_2d_layer_bridge.cc`

```cpp
// Canvas toDataURL에 미세한 노이즈 추가
String Canvas2DLayerBridge::ToDataURL(const String& mime_type, const double& quality) {
    // 원본 이미지 데이터 가져오기
    SkBitmap bitmap = ...;

    // ====================================================
    // 커스텀: 1픽셀당 ±1 RGB 노이즈 추가
    // ====================================================

    static std::mt19937 rng(time(nullptr) ^ getpid());
    std::uniform_int_distribution<int> noise_dist(-1, 1);

    SkBitmap noisy_bitmap;
    bitmap.copyTo(&noisy_bitmap);

    for (int y = 0; y < noisy_bitmap.height(); y++) {
        for (int x = 0; x < noisy_bitmap.width(); x++) {
            SkColor color = noisy_bitmap.getColor(x, y);

            int r = SkColorGetR(color) + noise_dist(rng);
            int g = SkColorGetG(color) + noise_dist(rng);
            int b = SkColorGetB(color) + noise_dist(rng);

            // Clamp to [0, 255]
            r = std::max(0, std::min(255, r));
            g = std::max(0, std::min(255, g));
            b = std::max(0, std::min(255, b));

            noisy_bitmap.setColor(x, y, SkColorSetRGB(r, g, b));
        }
    }

    // 노이즈 추가된 이미지로 인코딩
    return EncodeImage(noisy_bitmap, mime_type, quality);
}
```

## 빌드 프로세스

### 1. Chromium 소스 다운로드

```bash
# depot_tools 설치
git clone https://chromium.googlesource.com/chromium/tools/depot_tools.git
export PATH="$PATH:$(pwd)/depot_tools"

# Chromium 소스 다운로드 (약 30GB, 1-2시간)
mkdir chromium && cd chromium
fetch --nohooks chromium

# 소스 체크아웃
cd src
git checkout main

# 의존성 다운로드
gclient runhooks
```

### 2. 소스 코드 수정

```bash
# 위에서 설명한 파일들 수정
vim third_party/boringssl/ssl/ssl_cipher.cc
vim third_party/boringssl/ssl/extensions.cc
vim net/http2/http2_constants.cc
vim content/common/user_agent.cc
vim third_party/blink/renderer/platform/graphics/canvas_2d_layer_bridge.cc
```

### 3. 빌드 설정

```bash
# GN 설정 생성
gn gen out/RandomFingerprint --args='
    is_debug=false
    is_official_build=true
    chrome_pgo_phase=0
    enable_nacl=false
    target_cpu="x64"
'

# 빌드 시작 (약 2-4시간)
autoninja -C out/RandomFingerprint chrome
```

### 4. 테스트

```bash
# 빌드된 Chrome 실행
./out/RandomFingerprint/chrome --remote-debugging-port=9222

# JA3 Fingerprint 확인
curl -k https://ja3er.com/json | jq .ja3_hash

# 여러 번 재시작하여 매번 다른 Fingerprint 확인
./out/RandomFingerprint/chrome --remote-debugging-port=9223
curl -k https://ja3er.com/json | jq .ja3_hash
```

## 자동화 스크립트

### 병렬 Chrome 인스턴스 관리

```javascript
// parallel_chrome_manager.js
const { chromium } = require('playwright');
const { spawn } = require('child_process');

class ParallelChromeManager {
    constructor() {
        this.chromePath = 'D:\\chromium\\out\\RandomFingerprint\\chrome.exe';
        this.instances = [];
        this.maxParallel = 100;  // 동시 100개 Chrome
        this.basePort = 9222;
    }

    async launchInstance(index) {
        const port = this.basePort + index;

        // 각 Chrome은 다른 user-data-dir 사용
        const userDataDir = `D:\\chrome-profiles\\instance-${index}`;

        const args = [
            `--remote-debugging-port=${port}`,
            `--user-data-dir=${userDataDir}`,
            '--no-first-run',
            '--no-default-browser-check',
            '--disable-blink-features=AutomationControlled'
        ];

        const process = spawn(this.chromePath, args, {
            detached: true,
            stdio: 'ignore'
        });

        process.unref();

        // CDP 연결 대기
        await this.waitForPort(port, 10000);

        const browser = await chromium.connectOverCDP(`http://localhost:${port}`);

        this.instances.push({
            index,
            port,
            process,
            browser,
            requestCount: 0
        });

        console.log(`✅ Chrome #${index} launched (port ${port})`);

        return this.instances[this.instances.length - 1];
    }

    async launchAll() {
        console.log(`🚀 Launching ${this.maxParallel} Chrome instances...`);

        const promises = [];
        for (let i = 0; i < this.maxParallel; i++) {
            promises.push(this.launchInstance(i));
        }

        await Promise.all(promises);

        console.log(`✅ All ${this.maxParallel} instances ready!`);
    }

    async crawl(keywords) {
        const results = [];

        // Round-robin 방식으로 키워드 분배
        for (let i = 0; i < keywords.length; i++) {
            const instance = this.instances[i % this.instances.length];
            const keyword = keywords[i];

            const result = await this.crawlWithInstance(instance, keyword);
            results.push(result);

            instance.requestCount++;

            // 100회 사용 후 재시작 (새로운 Fingerprint)
            if (instance.requestCount >= 100) {
                console.log(`🔄 Restarting Chrome #${instance.index} for new fingerprint`);
                await this.restartInstance(instance.index);
            }

            if (i % 1000 === 0) {
                console.log(`Progress: ${i}/${keywords.length} (${(i/keywords.length*100).toFixed(1)}%)`);
            }
        }

        return results;
    }

    async crawlWithInstance(instance, keyword) {
        const browser = instance.browser;
        const context = browser.contexts()[0];
        const page = await context.newPage();

        try {
            await page.goto('https://www.coupang.com/');
            await page.fill('input[name="q"]', keyword);
            await page.press('input[name="q"]', 'Enter');
            await page.waitForLoadState('domcontentloaded');

            const html = await page.content();

            return {
                keyword,
                success: html.length > 50000,
                size: html.length,
                instance: instance.index
            };
        } catch (error) {
            return {
                keyword,
                success: false,
                error: error.message,
                instance: instance.index
            };
        } finally {
            await page.close();
        }
    }

    async restartInstance(index) {
        const instance = this.instances[index];

        // 기존 Chrome 종료
        await instance.browser.close();
        instance.process.kill();

        // 새로 시작 (새로운 랜덤 Fingerprint)
        const newInstance = await this.launchInstance(index);
        this.instances[index] = newInstance;
    }

    async waitForPort(port, timeout) {
        const start = Date.now();
        while (Date.now() - start < timeout) {
            try {
                const response = await fetch(`http://localhost:${port}/json/version`);
                if (response.ok) return true;
            } catch (e) {
                await new Promise(resolve => setTimeout(resolve, 100));
            }
        }
        throw new Error(`Port ${port} not ready after ${timeout}ms`);
    }

    async shutdown() {
        for (const instance of this.instances) {
            await instance.browser.close();
            instance.process.kill();
        }
    }
}

// 사용 예시
async function main() {
    const manager = new ParallelChromeManager();

    // 100개 Chrome 실행 (각각 다른 Fingerprint)
    await manager.launchAll();

    // 키워드 목록 (천만 개)
    const keywords = generateKeywords(10000000);

    // 병렬 크롤링
    const results = await manager.crawl(keywords);

    console.log('완료!');
    console.log(`성공: ${results.filter(r => r.success).length}`);
    console.log(`실패: ${results.filter(r => !r.success).length}`);

    await manager.shutdown();
}

function generateKeywords(count) {
    const keywords = [];
    for (let i = 0; i < count; i++) {
        keywords.push(`키워드${i}`);
    }
    return keywords;
}

main();
```

## 성능 분석

### 처리량 계산

```
설정:
├─ 동시 Chrome: 100개
├─ Chrome당 처리 속도: 3초/요청
└─ Chrome당 재시작: 100회마다

처리량:
├─ 동시: 100개 × (1요청/3초) = 33.3 요청/초
├─ 시간당: 33.3 × 3600 = 119,880 요청/시간
├─ 하루: 119,880 × 24 = 2,877,120 요청/일
└─ 천만 회 달성: Chrome 350개 동시 실행 필요

최적화:
├─ 동시 Chrome: 350개
├─ 서버: 16코어 CPU, 64GB RAM
└─ 처리량: 350 × (1/3) = 116.6 요청/초 = 10,074,240 요청/일 ✅
```

## 인프라 요구사항

### 서버 스펙 (하루 천만 회)

```
CPU: AMD Threadripper 3990X (64코어) 또는 2x Xeon Gold 6248R (48코어)
RAM: 256GB DDR4
디스크: 2TB NVMe SSD
네트워크: 1Gbps 전용선

또는 클라우드:
└─ AWS c6i.24xlarge (96 vCPU, 192GB RAM)
    비용: ~$4/시간 = ~$96/일
```

## 다음 단계

1. **Chromium 빌드** (1회, 2-4시간)
2. **병렬 관리 스크립트 구현** (1일)
3. **인프라 준비** (서버 또는 클라우드)
4. **테스트** (소규모 → 대규모)
5. **모니터링** (성공률, 속도, 차단율)

---

**작성일**: 2025-10-08
**목표**: 하루 천만 회 크롤링
**방법**: 커스텀 Chrome + 동적 Fingerprint + 병렬 실행
