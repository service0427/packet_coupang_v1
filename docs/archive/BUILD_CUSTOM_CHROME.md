# 커스텀 Chrome 빌드 실행 가이드

## 목표

오리지널 Chrome과 독립적으로 작동하는 **랜덤 Fingerprint 생성 Chrome** 빌드

## Step 1: 환경 준비

### Windows에서 Chromium 빌드 환경 구축

```powershell
# Visual Studio 2022 설치 확인 (Community 버전 가능)
# 필요한 컴포넌트:
# - Desktop development with C++
# - Windows 10/11 SDK

# Git 설치 확인
git --version

# Python 3.11 설치 확인
python --version
```

### depot_tools 설치

```powershell
# 작업 디렉토리 생성
mkdir D:\chromium-build
cd D:\chromium-build

# depot_tools 다운로드
git clone https://chromium.googlesource.com/chromium/tools/depot_tools.git

# PATH 추가 (현재 세션)
$env:Path = "D:\chromium-build\depot_tools;$env:Path"

# PATH 영구 추가 (시스템 환경변수)
[Environment]::SetEnvironmentVariable("Path", "D:\chromium-build\depot_tools;$env:Path", "User")

# 설정 환경변수
$env:DEPOT_TOOLS_WIN_TOOLCHAIN = 0
$env:vs2022_install = "C:\Program Files\Microsoft Visual Studio\2022\Community"
```

## Step 2: Chromium 소스 다운로드

```powershell
cd D:\chromium-build

# Chromium 소스 가져오기 (약 30GB, 1-3시간 소요)
fetch chromium

# 소스 디렉토리 이동
cd src

# 최신 stable 버전 체크아웃
git checkout main
gclient sync
```

## Step 3: 소스 코드 수정

### 3-1. TLS Cipher Suite 랜덤화

**파일 생성**: `D:\chromium-build\src\custom_fingerprint_randomizer.h`

```cpp
#ifndef CUSTOM_FINGERPRINT_RANDOMIZER_H_
#define CUSTOM_FINGERPRINT_RANDOMIZER_H_

#include <random>
#include <chrono>
#include <algorithm>

namespace custom_fp {

class FingerprintRandomizer {
 public:
  static FingerprintRandomizer& Instance() {
    static FingerprintRandomizer instance;
    return instance;
  }

  uint64_t GetSeed() const { return seed_; }
  std::mt19937& GetRNG() { return rng_; }

  // User Agent 버전 랜덤 생성
  std::string GetRandomChromeVersion() {
    std::uniform_int_distribution<int> major_dist(120, 140);
    std::uniform_int_distribution<int> build_dist(6000, 6999);
    std::uniform_int_distribution<int> patch_dist(100, 999);

    int major = major_dist(rng_);
    int build = build_dist(rng_);
    int patch = patch_dist(rng_);

    char version[32];
    snprintf(version, sizeof(version), "%d.0.%d.%d", major, build, patch);
    return std::string(version);
  }

  // HTTP/2 Settings 랜덤 값
  uint32_t GetRandomHeaderTableSize() {
    std::uniform_int_distribution<uint32_t> dist(32768, 131072);
    return dist(rng_);
  }

  uint32_t GetRandomMaxConcurrentStreams() {
    std::uniform_int_distribution<uint32_t> dist(500, 2000);
    return dist(rng_);
  }

  uint32_t GetRandomInitialWindowSize() {
    std::uniform_int_distribution<uint32_t> dist(3145728, 12582912);
    return dist(rng_);
  }

 private:
  FingerprintRandomizer() {
    // 시간 + PID 기반 시드
    auto now = std::chrono::high_resolution_clock::now();
    seed_ = now.time_since_epoch().count();

#ifdef _WIN32
    seed_ ^= GetCurrentProcessId();
#else
    seed_ ^= getpid();
#endif

    rng_.seed(seed_);

    // 콘솔에 시드 출력 (디버깅용)
    printf("[CustomChrome] Fingerprint seed: %llu\n", seed_);
  }

  uint64_t seed_;
  std::mt19937 rng_;
};

}  // namespace custom_fp

#endif  // CUSTOM_FINGERPRINT_RANDOMIZER_H_
```

### 3-2. BoringSSL Cipher Suite 수정

**파일**: `D:\chromium-build\src\third_party\boringssl\ssl\ssl_cipher.cc`

파일 최상단에 추가:

```cpp
// === CUSTOM FINGERPRINT: 시작 ===
#include "custom_fingerprint_randomizer.h"
#include <vector>
#include <algorithm>

static bool g_ciphers_randomized = false;

static void RandomizeCipherSuites(const SSL_CIPHER** cipher_array, size_t num_ciphers) {
  if (g_ciphers_randomized) return;

  std::vector<const SSL_CIPHER*> cipher_vec(cipher_array, cipher_array + num_ciphers);

  auto& rng = custom_fp::FingerprintRandomizer::Instance().GetRNG();
  std::shuffle(cipher_vec.begin(), cipher_vec.end(), rng);

  std::copy(cipher_vec.begin(), cipher_vec.end(), cipher_array);

  g_ciphers_randomized = true;
  printf("[BoringSSL] Cipher suites randomized\n");
}
// === CUSTOM FINGERPRINT: 끝 ===
```

함수 `ssl_create_cipher_list` 내부에서 cipher list 생성 직후에 추가:

```cpp
Span<const SSL_CIPHER> SSL_CTX::ssl_cipher_list() {
  // 기존 코드...

  // === CUSTOM FINGERPRINT: Cipher Suite 랜덤화 ===
  if (!g_ciphers_randomized && cipher_list_.size() > 0) {
    RandomizeCipherSuites(const_cast<const SSL_CIPHER**>(cipher_list_.data()),
                          cipher_list_.size());
  }
  // === CUSTOM FINGERPRINT: 끝 ===

  return cipher_list_;
}
```

### 3-3. HTTP/2 Settings 수정

**파일**: `D:\chromium-build\src\net\spdy\spdy_session.cc`

```cpp
// 파일 상단에 추가
#include "custom_fingerprint_randomizer.h"

// SpdySession 생성자 내부에서 SETTINGS 프레임 전송 부분 수정
void SpdySession::SendInitialSettings() {
  // === CUSTOM FINGERPRINT: HTTP/2 Settings 랜덤화 ===
  auto& fp = custom_fp::FingerprintRandomizer::Instance();

  spdy::SettingsMap settings;
  settings[spdy::SETTINGS_HEADER_TABLE_SIZE] = fp.GetRandomHeaderTableSize();
  settings[spdy::SETTINGS_ENABLE_PUSH] = 0;
  settings[spdy::SETTINGS_MAX_CONCURRENT_STREAMS] = fp.GetRandomMaxConcurrentStreams();
  settings[spdy::SETTINGS_INITIAL_WINDOW_SIZE] = fp.GetRandomInitialWindowSize();
  settings[spdy::SETTINGS_MAX_FRAME_SIZE] = 16384;
  settings[spdy::SETTINGS_MAX_HEADER_LIST_SIZE] = 262144;

  printf("[HTTP/2] Settings randomized: TABLE=%u STREAMS=%u WINDOW=%u\n",
         settings[spdy::SETTINGS_HEADER_TABLE_SIZE],
         settings[spdy::SETTINGS_MAX_CONCURRENT_STREAMS],
         settings[spdy::SETTINGS_INITIAL_WINDOW_SIZE]);
  // === CUSTOM FINGERPRINT: 끝 ===

  // 기존 SendSettings 호출
  SendSettings(settings);
}
```

### 3-4. User Agent 수정

**파일**: `D:\chromium-build\src\content\common\user_agent.cc`

```cpp
// 파일 상단에 추가
#include "custom_fingerprint_randomizer.h"

// GetUserAgent() 함수 수정
std::string GetUserAgent() {
  // === CUSTOM FINGERPRINT: User Agent 버전 랜덤화 ===
  static std::string random_version =
      custom_fp::FingerprintRandomizer::Instance().GetRandomChromeVersion();

  std::string user_agent = base::StringPrintf(
      "Mozilla/5.0 (%s) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/%s Safari/537.36",
      BuildOSCpuInfo().c_str(),
      random_version.c_str());

  printf("[UserAgent] %s\n", user_agent.c_str());
  // === CUSTOM FINGERPRINT: 끝 ===

  return user_agent;
}
```

## Step 4: 빌드 설정

### GN 빌드 설정 파일 생성

```powershell
cd D:\chromium-build\src

# GN 빌드 디렉토리 생성
gn gen out\CustomChrome --args="is_debug=false is_official_build=false target_cpu=\"x64\" chrome_pgo_phase=0 is_component_build=false symbol_level=0"
```

### args.gn 직접 편집 (선택사항)

**파일**: `D:\chromium-build\src\out\CustomChrome\args.gn`

```gn
is_debug = false
is_official_build = false
target_cpu = "x64"
chrome_pgo_phase = 0
is_component_build = false
symbol_level = 0

# 빌드 속도 향상
enable_nacl = false
enable_widevine = false

# 커스텀 빌드 표시
chrome_version_string = "CustomFingerprint"
```

## Step 5: 빌드 실행

```powershell
cd D:\chromium-build\src

# 빌드 시작 (2-6시간 소요, CPU 성능에 따라 다름)
autoninja -C out\CustomChrome chrome

# 빌드 성공 확인
dir out\CustomChrome\chrome.exe
```

## Step 6: 테스트

### 커스텀 Chrome 실행

```powershell
# CDP 모드로 실행
.\out\CustomChrome\chrome.exe --remote-debugging-port=9222 --user-data-dir="D:\chrome-custom-profile"
```

### Fingerprint 확인

```javascript
// fingerprint_test.js
const { chromium } = require('playwright');

async function testFingerprint() {
    // 커스텀 Chrome에 연결
    const browser = await chromium.connectOverCDP('http://localhost:9222');
    const context = browser.contexts()[0];
    const page = await context.newPage();

    // JA3 확인
    await page.goto('https://tls.browserleaks.com/json');
    const tls = await page.evaluate(() => document.body.innerText);
    console.log('TLS Fingerprint:', JSON.parse(tls));

    // User Agent 확인
    const ua = await page.evaluate(() => navigator.userAgent);
    console.log('User Agent:', ua);

    // Canvas Fingerprint 확인
    const canvas = await page.evaluate(() => {
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        ctx.textBaseline = 'top';
        ctx.font = '14px Arial';
        ctx.fillText('test', 2, 2);
        return canvas.toDataURL();
    });
    console.log('Canvas hash:', canvas.substring(0, 50) + '...');

    await browser.close();
}

testFingerprint();
```

### 여러 번 재시작하여 다른 Fingerprint 확인

```powershell
# 1차 실행
.\out\CustomChrome\chrome.exe --remote-debugging-port=9222 --user-data-dir="D:\profile1"
node fingerprint_test.js

# Chrome 종료 후 2차 실행
.\out\CustomChrome\chrome.exe --remote-debugging-port=9222 --user-data-dir="D:\profile2"
node fingerprint_test.js

# Fingerprint가 다르게 나오는지 확인
```

## Step 7: 병렬 실행 스크립트

```javascript
// custom_chrome_pool.js
const { chromium } = require('playwright');
const { spawn } = require('child_process');
const path = require('path');

class CustomChromePool {
    constructor(chromePath, poolSize = 10) {
        this.chromePath = chromePath;
        this.poolSize = poolSize;
        this.instances = [];
        this.basePort = 9222;
    }

    async start() {
        console.log(`🚀 Starting ${this.poolSize} Custom Chrome instances...`);

        for (let i = 0; i < this.poolSize; i++) {
            const port = this.basePort + i;
            const userDataDir = `D:\\chrome-pool\\instance-${i}`;

            // Chrome 프로세스 시작
            const process = spawn(this.chromePath, [
                `--remote-debugging-port=${port}`,
                `--user-data-dir=${userDataDir}`,
                '--no-first-run',
                '--no-default-browser-check',
                '--disable-blink-features=AutomationControlled'
            ], {
                detached: true,
                stdio: 'ignore'
            });

            process.unref();

            // CDP 연결 대기
            await this.waitForPort(port);

            // Playwright 연결
            const browser = await chromium.connectOverCDP(`http://localhost:${port}`);

            this.instances.push({
                index: i,
                port,
                process,
                browser,
                available: true
            });

            console.log(`✅ Instance ${i} ready (port ${port})`);
        }

        console.log(`✅ All ${this.poolSize} instances started!`);
    }

    async getAvailableInstance() {
        // Round-robin 방식
        for (let instance of this.instances) {
            if (instance.available) {
                instance.available = false;
                return instance;
            }
        }

        // 모두 사용 중이면 대기
        await new Promise(resolve => setTimeout(resolve, 100));
        return this.getAvailableInstance();
    }

    releaseInstance(instance) {
        instance.available = true;
    }

    async search(keyword) {
        const instance = await this.getAvailableInstance();

        try {
            const context = instance.browser.contexts()[0];
            const page = await context.newPage();

            await page.goto('https://www.coupang.com/');
            await page.fill('input[name="q"]', keyword);
            await page.press('input[name="q"]', 'Enter');
            await page.waitForLoadState('domcontentloaded');

            const html = await page.content();
            const success = html.length > 50000;

            await page.close();

            console.log(`${success ? '✅' : '❌'} [Instance ${instance.index}] ${keyword}`);

            return { keyword, success, instance: instance.index };
        } catch (error) {
            console.log(`❌ [Instance ${instance.index}] ${keyword} - ${error.message}`);
            return { keyword, success: false, error: error.message };
        } finally {
            this.releaseInstance(instance);
        }
    }

    async batchSearch(keywords) {
        const results = [];

        for (let i = 0; i < keywords.length; i++) {
            const result = await this.search(keywords[i]);
            results.push(result);

            if ((i + 1) % 100 === 0) {
                console.log(`Progress: ${i + 1}/${keywords.length}`);
            }
        }

        return results;
    }

    async waitForPort(port, timeout = 30000) {
        const start = Date.now();
        while (Date.now() - start < timeout) {
            try {
                const response = await fetch(`http://localhost:${port}/json/version`);
                if (response.ok) return;
            } catch (e) {
                await new Promise(resolve => setTimeout(resolve, 100));
            }
        }
        throw new Error(`Port ${port} not ready`);
    }

    async shutdown() {
        console.log('Shutting down all instances...');
        for (const instance of this.instances) {
            await instance.browser.close();
            instance.process.kill();
        }
    }
}

// 사용 예시
async function main() {
    const pool = new CustomChromePool(
        'D:\\chromium-build\\src\\out\\CustomChrome\\chrome.exe',
        10  // 10개 인스턴스
    );

    await pool.start();

    const keywords = ['물티슈', '음료수', '과자', '라면', '샴푸'];  // 테스트용
    const results = await pool.batchSearch(keywords);

    console.log('\n=== Results ===');
    console.log(`Success: ${results.filter(r => r.success).length}/${results.length}`);

    await pool.shutdown();
}

main();
```

## Step 8: 실행

```powershell
# Node.js 의존성 설치
npm install playwright

# 풀 시작
node custom_chrome_pool.js
```

## 빌드 시간 단축 팁

### 증분 빌드 활성화

```powershell
# 첫 빌드 후 소스 수정 시
autoninja -C out\CustomChrome chrome

# 변경된 부분만 재빌드 (5-30분)
```

### ccache 사용 (선택사항)

```powershell
# ccache 설치 (빌드 캐싱)
# https://ccache.dev/download.html

# GN args에 추가
gn gen out\CustomChrome --args="cc_wrapper=\"ccache\""
```

## 문제 해결

### 빌드 실패 시

```powershell
# 의존성 재설치
gclient sync -D

# 빌드 디렉토리 정리
rm -r out\CustomChrome
gn gen out\CustomChrome

# 재빌드
autoninja -C out\CustomChrome chrome
```

### CDP 연결 실패 시

```powershell
# 방화벽 확인
netsh advfirewall firewall add rule name="Chrome CDP" dir=in action=allow protocol=TCP localport=9222-9300

# 포트 사용 확인
netstat -ano | findstr :9222
```

## 다음 단계

1. ✅ 커스텀 Chrome 빌드 완료
2. ✅ Fingerprint 랜덤화 확인
3. ✅ 병렬 실행 스크립트 작성
4. 🔄 대규모 테스트 (1,000-10,000 요청)
5. 🔄 Akamai 우회 성공률 측정
6. 🔄 최적화 (속도, 안정성)

---

**예상 소요 시간**:
- 환경 구축: 1시간
- 소스 다운로드: 1-3시간
- 소스 수정: 30분
- 빌드: 2-6시간
- 테스트: 1시간
**총**: 5-11시간

**빌드 후 재사용**: 빌드는 1회만 하면 되며, 이후 계속 사용 가능
