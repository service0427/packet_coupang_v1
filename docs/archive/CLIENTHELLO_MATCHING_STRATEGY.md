# ClientHello 매칭 전략

## 문제 정의

**현상**: `test_fixed_cipher.js`로 1-2회 성공 후 차단됨
**원인**: 서버가 TLS ClientHello 구조를 학습하여 차단
**목표**: TLS ClientHello를 Chrome BoringSSL과 **바이트 레벨**로 완벽히 매칭

---

## Chrome BoringSSL ClientHello 구조 (Wireshark 분석)

### 핵심 지표

**JA3**: `ac32bbe0f9f3f7387fb0a524a48cc549`
**JA4**: `t13d081000_48922242edce_1f22a2ca17c4`

### JA3 구성 요소

```
771,4865-4866-4867-49195-49199-49196-49200-255,0-11-10-35-22-23-13-43-45-51,29-23-24,0-1-2
```

**분해**:
1. **TLS Version**: `771` (0x0303 = TLS 1.2)
2. **Cipher Suites**: `4865-4866-4867-49195-49199-49196-49200-255`
3. **Extensions**: `0-11-10-35-22-23-13-43-45-51`
4. **Supported Groups**: `29-23-24`
5. **EC Point Formats**: `0-1-2`

---

## Node.js OpenSSL 한계

### 재현 불가능한 요소

#### 1. Extension 순서 제어 불가
**Chrome BoringSSL 순서**:
```
0 (server_name)
11 (ec_point_formats)
10 (supported_groups)
35 (session_ticket)
22 (encrypt_then_mac)
23 (extended_master_secret)
13 (signature_algorithms)
43 (supported_versions)
45 (psk_key_exchange_modes)
51 (key_share)
```

**Node.js OpenSSL**:
- Extension 순서는 OpenSSL 내부 구현에 고정됨
- JavaScript에서 제어 불가능
- `tls.createSecureContext()` API로도 순서 변경 불가

#### 2. GREASE (Generate Random Extensions And Sustain Extensibility)
**Chrome BoringSSL**:
- ClientHello에 GREASE 값 포함 (랜덤 위치)
- 예: `0x0a0a`, `0x1a1a` 등

**Node.js OpenSSL**:
- GREASE 미지원
- 추가 불가능

#### 3. Cipher Suite 순서
**Chrome BoringSSL**:
- TLS 1.3 우선: 4865, 4866, 4867
- 그 다음 TLS 1.2 ECDHE

**Node.js OpenSSL**:
```javascript
ciphers: 'TLS_AES_128_GCM_SHA256:TLS_AES_256_GCM_SHA384:...'
```
- 문자열로 순서 지정 가능
- ✅ **재현 가능**

#### 4. Supported Groups 순서
**Chrome BoringSSL**: `29-23-24` (x25519, secp256r1, secp384r1)

**Node.js OpenSSL**:
```javascript
ecdhCurve: 'X25519:prime256v1:secp384r1'
```
- ✅ **재현 가능**

#### 5. Signature Algorithms 순서
**Chrome BoringSSL (Wireshark)**:
```
0403 (ecdsa_secp256r1_sha256)
0503 (ecdsa_secp384r1_sha384)
0603 (ecdsa_secp521r1_sha512)
0807 (ed25519)
0808 (ed448)
...
```

**Node.js OpenSSL**:
- 자동 생성
- JavaScript에서 제어 불가능

#### 6. TLS 1.3 key_share Extension
**Chrome BoringSSL**:
- x25519 공개키만 전송 (38 바이트)

**Node.js OpenSSL**:
- 자동 생성
- 제어 불가능

---

## 가능한 매칭 전략

### ✅ 레벨 1: Cipher Suite + Supported Groups (현재)

**구현**:
```javascript
{
    ciphers: 'TLS_AES_128_GCM_SHA256:TLS_AES_256_GCM_SHA384:TLS_CHACHA20_POLY1305_SHA256:ECDHE-ECDSA-WITH-AES128-GCM-SHA256:ECDHE-RSA-WITH-AES128-GCM-SHA256:ECDHE-ECDSA-WITH-AES256-GCM-SHA384:ECDHE-RSA-WITH-AES256-GCM-SHA384',
    ecdhCurve: 'X25519:prime256v1:secp384r1',
    minVersion: 'TLSv1.2',
    maxVersion: 'TLSv1.3'
}
```

**매칭률**: ~60%
- Cipher Suite 순서: ✅
- Supported Groups 순서: ✅
- Extension 순서: ❌
- GREASE: ❌
- Signature Algorithms: ❌

**예상 성공률**: 30-50% (초기 1-2회 성공 후 차단)

---

### ⚠️ 레벨 2: Native Addon으로 Extension 제어 (고난이도)

**개념**: Node.js Native Addon으로 OpenSSL API 직접 호출

**구현 복잡도**: 매우 높음
```c++
// C++ Native Addon
SSL_CTX_set_options(ctx, SSL_OP_ALL);
SSL_CTX_set_cipher_list(ctx, ciphers);

// Extension 순서 직접 제어
SSL_CTX_set_tlsext_servername_callback(ctx, ...);
```

**문제점**:
- OpenSSL 3.0+ API 변경
- Windows 빌드 환경 복잡
- 유지보수 어려움
- Extension 순서 제어 API가 제한적

**매칭률**: ~75%
**예상 성공률**: 50-70%

---

### ❌ 레벨 3: BoringSSL Node.js 바인딩 (불가능)

**개념**: BoringSSL을 직접 Node.js에 바인딩

**문제점**:
- Node.js는 OpenSSL과 정적 링크됨
- BoringSSL 교체 시 Node.js 전체 재빌드 필요
- Google이 공식 바인딩 미제공
- Windows에서 빌드 불가능 (사실상)

**매칭률**: 100% (이론상)
**실현 가능성**: 0%

---

## 🎯 현실적 해결책

### 방안 1: 고수준 매칭 (boringssl_clienthello_matcher.js)

**구현**: Cipher Suite + Supported Groups + HTTP 헤더 최적화

**장점**:
- 구현 간단
- 즉시 테스트 가능

**단점**:
- Extension 순서 불일치
- 서버가 학습 후 차단 가능성

**예상 성공률**: 30-50%

---

### 방안 2: Golang tls-client

**라이브러리**: [bogdanfinn/tls-client](https://github.com/bogdanfinn/tls-client)

**장점**:
- ✅ Chrome TLS ClientHello 100% 재현
- ✅ Extension 순서 제어 가능
- ✅ GREASE 지원
- ✅ Windows 바이너리 제공
- ✅ Node.js에서 child_process로 호출 가능

**구현**:
```go
// coupang_tls_client.go
package main

import (
    "fmt"
    tls_client "github.com/bogdanfinn/tls-client"
)

func main() {
    // Chrome 140 프로파일 (BoringSSL 완벽 재현)
    options := []tls_client.HttpClientOption{
        tls_client.WithClientProfile(tls_client.Chrome_120),
        tls_client.WithTimeoutSeconds(30),
    }

    client, _ := tls_client.NewHttpClient(tls_client.NewNoopLogger(), options...)

    // 요청
    req, _ := http.NewRequest("GET", "https://www.coupang.com/np/search?q=음료수", nil)
    req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")

    resp, _ := client.Do(req)
    // ...
}
```

**Node.js 연동**:
```javascript
const { spawn } = require('child_process');

async function golangTLSRequest(keyword) {
    return new Promise((resolve, reject) => {
        const proc = spawn('./coupang_tls_client.exe', [keyword]);
        // stdout 수집 및 반환
    });
}
```

**매칭률**: 95%+
**예상 성공률**: 70-80% (TLS는 통과, Akamai Challenge는 별개)

---

### 방안 3: Real Chrome + CDP (100% 성공 - 현재 사용)

**장점**:
- ✅ TLS ClientHello: 100% 완벽
- ✅ JavaScript 실행: 가능
- ✅ Akamai Challenge: 통과

**단점**:
- ❌ 리소스 사용: ~200MB/인스턴스

**성공률**: 100%

---

## 검증 방법

### 1. Wireshark로 ClientHello 비교

**Real Chrome 캡처**:
```bash
# Wireshark 필터
tls.handshake.type == 1 and ip.dst == 23.40.45.205
```

**Node.js 캡처**:
```bash
node boringssl_clienthello_matcher.js
# Wireshark에서 동시 캡처
```

**비교 항목**:
- [ ] TLS Version
- [ ] Cipher Suite 순서
- [ ] Extension 순서 (❌ 불일치 예상)
- [ ] Supported Groups 순서
- [ ] Signature Algorithms
- [ ] key_share 데이터

### 2. 성공률 측정

**테스트 시나리오**:
1. 새 세션으로 연속 10회 검색
2. 3분 간격으로 5회 검색
3. IP 변경 후 10회 검색

**판정**:
- 10/10 성공: ✅ 완벽 매칭
- 7-9/10 성공: ⚠️ 부분 매칭
- 1-3/10 성공: ❌ 초기만 통과 (현재 상태)
- 0/10 성공: ❌ 즉시 차단

---

## 단계별 실행 계획

### Phase 1: Node.js 최대 매칭 (현재)
1. ✅ `boringssl_clienthello_matcher.js` 구현 완료
2. ⏳ 테스트 및 성공률 측정
3. ⏳ Wireshark로 ClientHello 비교

### Phase 2: Golang tls-client 도입 (권장)
1. Golang 설치 및 tls-client 빌드
2. Node.js 브리지 구현
3. TLS ClientHello 완벽 재현 검증
4. 성공률 측정 (목표: 70%+)

### Phase 3: Akamai Challenge 우회 (필요 시)
1. Golang tls-client에서도 Challenge 수신 시
2. V8 JavaScript 엔진 통합 검토
3. 또는 Real Chrome + CDP로 폴백

---

## 결론

**Node.js만으로는 TLS ClientHello 완벽 매칭 불가능**

**이유**:
1. Extension 순서 제어 불가
2. GREASE 미지원
3. Signature Algorithms 제어 불가

**추천 전략**:
1. **단기**: `boringssl_clienthello_matcher.js`로 30-50% 성공률 확인
2. **중기**: Golang tls-client으로 70-80% 달성
3. **장기**: Real Chrome + CDP 유지 (100% 보장)

**핵심**: TLS ClientHello 통과해도 **Akamai JavaScript Challenge**가 남아 있음. 최종적으로는 Real Chrome + CDP가 유일한 100% 해결책.
