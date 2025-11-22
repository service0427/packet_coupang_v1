# BoringSSL 기반 패킷 모드 구현 방안

## 문제 요약

**Node.js 패킷 모드 실패 이유**: OpenSSL TLS 핑거프린트 ≠ Chrome BoringSSL 핑거프린트

## 해결 방안

### 🎯 방안 1: Golang tls-client (권장)

**라이브러리**: [bogdanfinn/tls-client](https://github.com/bogdanfinn/tls-client)

**장점**:
- ✅ Chrome BoringSSL TLS 핑거프린트 완벽 재현
- ✅ Windows 지원 (사전 빌드 바이너리 제공)
- ✅ HTTP/2 완벽 지원
- ✅ JA3/JA4 커스터마이징 가능
- ✅ Node.js 연동 가능 (child_process)

#### 구현 방법

**1단계: Golang tls-client 설치**

```bash
# Golang 설치 (Windows)
# https://go.dev/dl/

# tls-client 설치
go get github.com/bogdanfinn/tls-client
```

**2단계: Golang HTTP 클라이언트 작성**

```go
// coupang_client.go
package main

import (
    "fmt"
    "io"
    "log"
    tls_client "github.com/bogdanfinn/tls-client"
)

func main() {
    // Chrome 120 BoringSSL 프로파일
    options := []tls_client.HttpClientOption{
        tls_client.WithTimeoutSeconds(30),
        tls_client.WithClientProfile(tls_client.Chrome_120),
        tls_client.WithNotFollowRedirects(),
    }

    client, err := tls_client.NewHttpClient(tls_client.NewNoopLogger(), options...)
    if err != nil {
        log.Fatal(err)
    }

    // 쿠팡 검색 요청
    req, err := http.NewRequest("GET", "https://www.coupang.com/np/search?q=음료수", nil)
    if err != nil {
        log.Fatal(err)
    }

    // Chrome 헤더 추가
    req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")
    req.Header.Set("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8")
    req.Header.Set("Accept-Language", "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7")
    req.Header.Set("sec-ch-ua", `"Chromium";v="140", "Google Chrome";v="140", "Not?A_Brand";v="99"`)
    req.Header.Set("sec-ch-ua-mobile", "?0")
    req.Header.Set("sec-ch-ua-platform", `"Windows"`)

    resp, err := client.Do(req)
    if err != nil {
        log.Fatal(err)
    }
    defer resp.Body.Close()

    body, err := io.ReadAll(resp.Body)
    if err != nil {
        log.Fatal(err)
    }

    fmt.Printf("Status: %d\n", resp.StatusCode)
    fmt.Printf("Body length: %d\n", len(body))

    // 차단 여부 확인
    if bytes.Contains(body, []byte("location.reload")) {
        fmt.Println("⚠️ Bot Manager Challenge 감지")
    } else {
        fmt.Println("✅ 정상 응답")
    }
}
```

**3단계: 빌드**

```bash
# Windows 실행 파일 빌드
go build -o coupang_client.exe coupang_client.go
```

**4단계: Node.js 연동**

```javascript
// golang_packet_bridge.js
const { spawn } = require('child_process');
const fs = require('fs');

class GolangPacketBridge {
    constructor() {
        this.golangClient = './coupang_client.exe';
    }

    async search(keyword) {
        return new Promise((resolve, reject) => {
            const proc = spawn(this.golangClient, [keyword]);

            let stdout = '';
            let stderr = '';

            proc.stdout.on('data', (data) => {
                stdout += data.toString();
            });

            proc.stderr.on('data', (data) => {
                stderr += data.toString();
            });

            proc.on('close', (code) => {
                if (code === 0) {
                    resolve(stdout);
                } else {
                    reject(new Error(stderr));
                }
            });
        });
    }
}

// 사용 예시
async function main() {
    const client = new GolangPacketBridge();
    const result = await client.search('음료수');
    console.log(result);
}

main();
```

#### 예상 성공률

**이론적**: 70-80%
- ✅ TLS 핑거프린트: 완벽 (BoringSSL)
- ✅ HTTP/2 프로토콜: 완벽
- ❌ JavaScript 실행: 불가능 (Bot Manager Challenge 문제)

**실제**: Akamai Bot Manager가 JavaScript 실행을 요구하므로 **여전히 실패 가능성 높음**

---

### 🎯 방안 2: Python curl-cffi (Linux 전용)

**라이브러리**: [curl-cffi](https://github.com/yifeikong/curl-cffi)

**장점**:
- ✅ curl-impersonate 기반 (Chrome TLS 완벽 재현)
- ✅ Python 네이티브 지원

**단점**:
- ❌ **Windows 공식 미지원** (WSL 필요)
- ❌ JavaScript 실행 불가 (Bot Manager Challenge)

---

### 🎯 방안 3: Real Chrome + CDP (현재 100% 성공 방식)

**현재 구현**: `real_chrome_connect.js`

**장점**:
- ✅ TLS 핑거프린트: 100% 완벽 (BoringSSL 네이티브)
- ✅ HTTP/2: 100% 완벽
- ✅ JavaScript 실행: 가능 (Bot Manager Challenge 통과)
- ✅ 모든 브라우저 API 사용 가능
- ✅ Windows 네이티브 지원

**단점**:
- ❌ 메모리 사용량: ~200MB/인스턴스
- ❌ 동시 실행 제한: ~10-20 인스턴스 (리소스 의존)

**성공률**: **100%** ✅

---

## 최종 권장사항

### 📊 비교표

| 방안 | TLS 핑거프린트 | JavaScript | Windows | 성공률 | 난이도 |
|------|---------------|-----------|---------|--------|--------|
| **Golang tls-client** | ✅ 완벽 | ❌ 불가 | ✅ 지원 | 30-50% | 중간 |
| **Python curl-cffi** | ✅ 완벽 | ❌ 불가 | ❌ WSL만 | 30-50% | 중간 |
| **Real Chrome + CDP** | ✅ 완벽 | ✅ 가능 | ✅ 지원 | **100%** | 쉬움 |

### 🎯 추천 전략

#### 단기 (즉시 사용):
**Real Chrome + CDP** (`real_chrome_connect.js`)
- 100% 성공률 보장
- 검증 완료
- 프로덕션 준비 완료

#### 중기 (실험):
**Golang tls-client** 테스트
- BoringSSL TLS 재현 검증
- Akamai Challenge 우회 가능성 확인
- 실패 시 Real Chrome으로 폴백

#### 장기 (연구):
**JavaScript 엔진 통합**
- Golang tls-client + V8 JavaScript 엔진
- Bot Manager Challenge Script 실행
- 복잡도 매우 높음 (수개월 개발)

---

## Akamai Bot Manager 우회 한계

**근본적 문제**: Akamai는 **JavaScript 실행 환경을 필수로 요구**

```javascript
// Bot Manager Challenge Script
<script>
(function() {
    var proxied = window.XMLHttpRequest.prototype.send;
    window.XMLHttpRequest.prototype.send = function() {
        // XHR 완료 시 location.reload(true) 호출
    };
})();
</script>
```

**요구사항**:
1. `window` 객체
2. `XMLHttpRequest` 객체
3. `location.reload()` 메서드
4. JavaScript 비동기 실행

**불가능한 환경**:
- ❌ Pure HTTP 클라이언트
- ❌ Golang http.Client
- ❌ Python requests/httpx
- ❌ curl-cffi

**가능한 환경**:
- ✅ Real Browser (Chrome, Firefox)
- ✅ Headful Browser (CDP 연결)

---

## 결론

**패킷 모드는 BoringSSL TLS 핑거프린트를 재현해도 Akamai Bot Manager의 JavaScript Challenge를 통과할 수 없음**

**유일한 해결책**: Real Chrome + CDP

**이유**:
1. BoringSSL TLS 핑거프린트 필요 (✅ Golang 가능)
2. HTTP/2 프로토콜 필요 (✅ Golang 가능)
3. **JavaScript 실행 환경 필수** (❌ Golang 불가능)
4. `location.reload()` 호출 필요 (❌ Golang 불가능)

**최종 권장**: `real_chrome_connect.js` 계속 사용
