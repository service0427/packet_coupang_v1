# Manual TLS Configuration Guide

## 개요

curl-cffi의 고정 프로필(chrome120, chrome124 등)에 의존하지 않고, **직접 TLS 파라미터를 조정**하여 Akamai 우회를 시도합니다.

## 문제점: curl-cffi 프로필의 한계

```
Chrome 실제 릴리즈: 매달 업데이트 (141, 142, 143...)
curl-cffi 프로필: 업데이트 느림 (최신: chrome136)

→ 최신 Chrome을 사용해도 curl-cffi 프로필이 없음
→ 미세한 TLS 차이로 Akamai 탐지 가능
```

## 해결책: Manual TLS Configuration

Real Chrome의 TLS 파라미터를 추출하여 curl-cffi에 직접 적용

```
1. Real Chrome → TLS 핑거프린트 추출
2. JSON 설정 파일 생성
3. curl-cffi → 설정 파일 로드 → 요청
```

## 워크플로우

### Step 1: Real Chrome TLS 추출

```bash
# Chrome 124의 TLS 파라미터 추출
python extract_browser_tls.py "D:\chrome-124\chrome.exe" tls_configs/chrome124_manual.json

# 추출되는 정보:
# - TLS Version (1.2, 1.3)
# - Cipher Suites (암호화 스위트 목록)
# - Signature Algorithms (서명 알고리즘)
# - Supported Curves (지원 타원곡선)
# - HTTP/2 Settings (SETTINGS 프레임)
# - JA3 Hash (TLS 핑거프린트)
```

### Step 2: 설정 파일 구조

`tls_configs/chrome124_manual.json`:
```json
{
  "chrome_path": "D:\\chrome-124\\chrome.exe",
  "raw_fingerprints": {
    "https://tls.browserleaks.com/json": { ... },
    "https://tls.peet.ws/api/all": { ... }
  },
  "manual_tls_config": {
    "tls_version": "TLS 1.3",
    "ciphers": [
      "TLS_AES_128_GCM_SHA256",
      "TLS_AES_256_GCM_SHA384",
      "TLS_CHACHA20_POLY1305_SHA256",
      ...
    ],
    "signature_algorithms": [
      "ecdsa_secp256r1_sha256",
      "rsa_pss_rsae_sha256",
      ...
    ],
    "curves": [
      "X25519",
      "secp256r1",
      "secp384r1"
    ],
    "http2_settings": {
      "HEADER_TABLE_SIZE": 65536,
      "INITIAL_WINDOW_SIZE": 6291456,
      ...
    },
    "ja3_hash": "...",
    "ja3_string": "..."
  }
}
```

### Step 3: Manual TLS 요청

```bash
# 기본 Chrome 124 설정 사용
python src/manual_tls_request.py "https://www.coupang.com/..." cookies.json

# 커스텀 설정 파일 사용
python src/manual_tls_request.py "https://www.coupang.com/..." cookies.json tls_configs/chrome124_manual.json
```

## 미세 조정 전략

### 1차 조정: Cipher Suite 순서 변경

```json
{
  "ciphers": [
    "TLS_AES_128_GCM_SHA256",  // ← 순서 변경
    "TLS_CHACHA20_POLY1305_SHA256",
    "TLS_AES_256_GCM_SHA384"
  ]
}
```

### 2차 조정: HTTP/2 SETTINGS 값 변경

```json
{
  "http2_settings": {
    "INITIAL_WINDOW_SIZE": 6291456,  // ← 값 조정 (±10%)
    "MAX_CONCURRENT_STREAMS": 1000,
    "MAX_FRAME_SIZE": 16384
  }
}
```

### 3차 조정: GREASE 값 추가/변경

```json
{
  "enable_grease": true,
  "grease_values": [0x0a0a, 0x1a1a, ...]  // ← 랜덤 GREASE
}
```

### 4차 조정: 타원곡선 순서 변경

```json
{
  "curves": [
    "X25519",     // ← 순서 변경
    "secp384r1",
    "secp256r1"
  ]
}
```

## 통합 테스트 스크립트

### A/B 테스트 자동화

```javascript
// manual_tls_ab_test.js
const variants = [
  'tls_configs/chrome124_variant_a.json',  // 원본
  'tls_configs/chrome124_variant_b.json',  // Cipher 순서 변경
  'tls_configs/chrome124_variant_c.json',  // HTTP/2 값 조정
  'tls_configs/chrome124_variant_d.json',  // Curve 순서 변경
];

for (const config of variants) {
  const result = await testTLSConfig(config);
  if (result.success) {
    console.log(`✅ Success with ${config}`);
    break;
  }
}
```

## 장점

1. **크롬 업데이트 대응**: curl-cffi 업데이트를 기다리지 않음
2. **미세 조정 가능**: 파라미터를 직접 수정하여 실험 가능
3. **버전 관리**: TLS 설정을 Git으로 관리 가능
4. **다중 프로필**: 여러 Chrome 버전의 설정을 동시 관리

## 실전 예시

```bash
# 1. Chrome 124 TLS 추출
python extract_browser_tls.py "D:\chrome-124\chrome.exe" tls_configs/chrome124.json

# 2. Chrome 123 TLS 추출 (비교용)
python extract_browser_tls.py "D:\chrome-123\chrome.exe" tls_configs/chrome123.json

# 3. 차이점 비교
diff tls_configs/chrome124.json tls_configs/chrome123.json

# 4. 미세 조정
# tls_configs/chrome124_variant.json 수동 편집

# 5. 테스트
node manual_tls_test.js
```

## curl-cffi 내부 동작 이해

curl-cffi는 내부적으로:
```python
# 1. impersonate 프로필 선택
session.get(url, impersonate='chrome124')

# 2. 프로필에서 TLS 파라미터 로드
# - Cipher suite list
# - TLS extensions
# - HTTP/2 settings

# 3. libcurl에 파라미터 전달
# CURLOPT_SSL_CIPHER_LIST
# CURLOPT_HTTP_VERSION
# CURLOPT_HTTP2_SETTINGS
```

우리는 이 파라미터를 **직접 제어**합니다.

## 다음 단계

1. ✅ TLS 추출 스크립트 작성
2. ✅ Manual TLS 요청 스크립트 작성
3. ⏳ A/B 테스트 자동화 (다음 작업)
4. ⏳ 성공한 설정 문서화
5. ⏳ 프로덕션 적용

## 예상 효과

- **성공 시**: curl-cffi로 Akamai 우회 가능 → 하이브리드 모드 실현
- **실패 시**: Chrome의 어떤 TLS 특성이 중요한지 파악 가능
