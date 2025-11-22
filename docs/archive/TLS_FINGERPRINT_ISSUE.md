# TLS 핑거프린트 문제 분석 (OpenSSL vs BoringSSL)

## 문제 정의

**패킷 모드 실패 이유**: Node.js는 OpenSSL 사용, Chrome은 BoringSSL 사용 → TLS 핑거프린트 불일치 → 즉시 차단

## Chrome TLS 핑거프린트 (Wireshark 분석)

### JA3/JA4 해시
- **JA3**: `ac32bbe0f9f3f7387fb0a524a48cc549`
- **JA4**: `t13d081000_48922242edce_1f22a2ca17c4`

### JA3 구성 요소 (Wireshark 추출)
```
JA3 Fullstring: 771,4865-4866-4867-49195-49199-49196-49200-255,0-11-10-35-22-23-13-43-45-51,29-23-24,0-1-2
```

**분해**:
1. **TLS Version**: `771` (TLS 1.2 = 0x0303)
2. **Cipher Suites**: `4865-4866-4867-49195-49199-49196-49200-255`
   - 4865: TLS_AES_128_GCM_SHA256 (TLS 1.3)
   - 4866: TLS_AES_256_GCM_SHA384 (TLS 1.3)
   - 4867: TLS_CHACHA20_POLY1305_SHA256 (TLS 1.3)
   - 49195: TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256
   - 49199: TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256
   - 49196: TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384
   - 49200: TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384
   - 255: TLS_EMPTY_RENEGOTIATION_INFO_SCSV
3. **Extensions**: `0-11-10-35-22-23-13-43-45-51`
   - 0: server_name (SNI)
   - 11: ec_point_formats
   - 10: supported_groups
   - 35: session_ticket
   - 22: encrypt_then_mac
   - 23: extended_master_secret
   - 13: signature_algorithms
   - 43: supported_versions
   - 45: psk_key_exchange_modes
   - 51: key_share
4. **Supported Groups**: `29-23-24`
   - 29: x25519
   - 23: secp256r1
   - 24: secp384r1
5. **EC Point Formats**: `0-1-2`
   - 0: uncompressed
   - 1: ansiX962_compressed_prime
   - 2: ansiX962_compressed_char2

## Node.js OpenSSL 차이점

### 환경
- Node.js: v22.14.0
- OpenSSL: 3.0.15+quic

### 주요 차이

#### 1. Cipher Suite 순서
**BoringSSL (Chrome)**:
- TLS 1.3 우선 (4865, 4866, 4867)
- ECDHE 우선 (Forward Secrecy)

**OpenSSL (Node.js)**:
- 구현 의존적
- 설정 가능하지만 기본값이 다름

#### 2. Extension 순서
**BoringSSL**: 고정된 순서 (0,11,10,35,22,23,13,43,45,51)
**OpenSSL**: 다른 순서 (버전 의존적)

#### 3. GREASE (Generate Random Extensions And Sustain Extensibility)
**BoringSSL**: GREASE 값 포함
**OpenSSL**: GREASE 미지원

#### 4. key_share (TLS 1.3)
**BoringSSL**: x25519만 전송
**OpenSSL**: 여러 그룹 전송 가능

## Windows에서 BoringSSL 직접 사용 불가능 이유

### 1. Node.js 바인딩 부재
- Node.js는 OpenSSL과 직접 링크됨
- BoringSSL로 교체 시 Node.js 전체 재빌드 필요
- Windows에서 빌드 환경 복잡함

### 2. 기술적 제약
```
Node.js (Windows)
  ↓
OpenSSL 3.0.15 (정적 링크)
  ↓
TLS 핸드셰이크
  ↓
❌ BoringSSL 핑거프린트 불일치
```

### 3. 대안 부재
- **curl-impersonate**: Linux 전용 (Windows 미지원)
- **tls-client (Golang)**: Node.js 바인딩 없음
- **cycletls**: 내부적으로 Golang 사용, 복잡함

## 해결 방안

### ❌ 불가능한 방법

1. **Node.js https 모듈**: OpenSSL 고정
2. **Node.js http2 모듈**: OpenSSL 고정
3. **BoringSSL 네이티브 바인딩**: 너무 복잡함
4. **Pure JavaScript TLS**: 성능 문제 + 완전성 부족

### ✅ 유일한 해결책: Real Chrome + CDP

**원리**:
```
Real Chrome (BoringSSL 내장)
  ↓
TLS 핸드셰이크 (100% 실제 브라우저)
  ↓ CDP (Chrome DevTools Protocol)
Playwright 제어
  ↓
✅ 완벽한 TLS 핑거프린트
```

**장점**:
- BoringSSL TLS 핑거프린트 100% 재현
- HTTP/2 프로토콜 완벽 재현
- ECH (Encrypted Client Hello) 250-byte 데이터 포함
- GREASE 값 자동 포함
- 모든 브라우저 API 사용 가능 (JavaScript 실행)

**단점**:
- 실제 Chrome 프로세스 필요
- 메모리 사용량 높음 (~200MB/인스턴스)
- 동시 실행 수 제한적

## Akamai Bot Manager가 감지하는 항목

### 1. TLS Layer
- ✅ **JA3 해시**: `ac32bbe0f9f3f7387fb0a524a48cc549` (Chrome 고유)
- ✅ **JA4 해시**: `t13d081000_48922242edce_1f22a2ca17c4`
- ✅ **Cipher Suite 순서**: TLS 1.3 우선
- ✅ **Extension 순서**: 0,11,10,35,22,23,13,43,45,51
- ✅ **ECH 데이터**: 250-byte Encrypted Client Hello

### 2. HTTP Layer
- ✅ **User-Agent**: Windows Chrome 140
- ✅ **sec-ch-ua**: Chromium/Chrome/Not?A_Brand 버전
- ✅ **HTTP/2 SETTINGS**: Window size, frame 순서

### 3. JavaScript Layer
- ✅ **navigator.userAgent**: HTTP 헤더와 일치
- ✅ **window.chrome**: Chrome 객체 존재
- ✅ **navigator.webdriver**: false
- ✅ **브라우저 API**: XHR, location.reload 실행 가능

## 결론

**패킷 모드는 Windows Node.js에서 불가능**

**이유**:
1. OpenSSL ≠ BoringSSL → TLS 핑거프린트 불일치
2. Akamai는 TLS Layer부터 감지
3. JavaScript 실행 환경 필수
4. Node.js에서 BoringSSL 사용 불가능 (Windows)

**유일한 해결책**: Real Chrome + CDP (`real_chrome_connect.js`)

## 참고 자료

- Wireshark 캡처: `wireshark.md`
- TLS 분석기: `tls_fingerprint_analyzer.js`
- 성공 구현: `real_chrome_connect.js`
- 실패 보고서: `FINAL_SOLUTION.md`
