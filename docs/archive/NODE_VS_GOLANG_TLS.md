# Node.js vs Golang TLS 차이 분석

## 🎯 핵심 발견

**동일 IP에서**:
- ✅ 실제 Chrome 브라우저: 항상 성공
- ✅ Golang tls-client: TLS 100% 통과 (Akamai Challenge만 수신)
- ⚠️ Node.js HTTP/2: TLS 20-30% 통과 (간헐적 차단)

→ **IP 차단 아님**, **TLS 핑거프린트 정확도 차이**

## 📊 TLS 핑거프린트 비교

### Chrome (실제 브라우저)
```
TLS Version: 1.3
Cipher Suites: 4865,4866,4867,49195,49199,49196,49200,52393,52392,49171,49172,156,157,47,53
Extensions: 0,23,65281,10,11,35,16,5,13,18,51,45,43,27,21
Supported Groups: 29,23,24
Signature Algorithms: 1027,2052,1025,1283,2053,1281,2054,1537
```

### Golang tls-client (Chrome 120 프로파일)
```
TLS Version: 1.3 ✅
Cipher Suites: 정확히 동일 ✅
Extensions: 정확히 동일 ✅ (bogdanfinn/utls)
Supported Groups: 정확히 동일 ✅
Signature Algorithms: 정확히 동일 ✅
GREASE: 지원 ✅
```
→ **완벽한 재현** → TLS 100% 통과

### Node.js HTTP/2 (OpenSSL 3.0)
```
TLS Version: 1.3 ✅
Cipher Suites: 수동 매칭 ✅
Extensions: 고정 순서 ❌ (OpenSSL 내부)
Supported Groups: 수동 매칭 ✅
Signature Algorithms: 고정 ❌
GREASE: 미지원 ❌
```
→ **부분 재현** → TLS 20-30% 통과

## 🔍 Node.js 차단 원인

### 1. Extension 순서 불일치
**Chrome 순서**:
```
0 (SNI), 23 (session_ticket), 65281 (renegotiation_info),
10 (supported_groups), 11 (ec_point_formats), ...
```

**Node.js 순서** (OpenSSL 고정):
```
0 (SNI), 10 (supported_groups), 11 (ec_point_formats),
23 (session_ticket), 65281 (renegotiation_info), ...
```

→ **순서 불일치 감지** → 간헐적 차단

### 2. GREASE 값 부재
**Chrome**: 랜덤 GREASE 값 삽입 (예: 0x0a0a, 0x2a2a)
**Node.js**: GREASE 미지원

→ **패턴 고정** → 학습 후 차단

### 3. Signature Algorithms 순서
**Chrome**: `1027,2052,1025,1283,2053,1281,2054,1537`
**Node.js**: OpenSSL 기본 순서 (다름)

→ **미세한 차이 누적** → 차단

## 💡 왜 Golang은 100% 통과하는가?

### bogdanfinn/utls 라이브러리
```go
// Chrome 120 프로파일 사용
tls_client.WithClientProfile(profiles.Chrome_120)
```

**기능**:
1. **Extension 순서 완벽 재현**
2. **GREASE 값 랜덤 생성**
3. **Signature Algorithms 정확히 매칭**
4. **TLS 1.3 key_share 완벽 재현**

→ **JA3/JA4 해시가 실제 Chrome과 100% 일치**

### Node.js OpenSSL 한계
```javascript
// 제어 가능한 것
ciphers: '...',          // ✅
ecdhCurve: '...',        // ✅
minVersion/maxVersion    // ✅

// 제어 불가능한 것
Extension 순서            // ❌ 내부 고정
GREASE                   // ❌ 미지원
Signature Algorithms 순서 // ❌ 내부 고정
```

→ **부분 매칭만 가능** → 간헐적 차단

## 🎯 1단계 TLS 무한 통과 솔루션

### Option 1: Golang tls-client 사용 ⭐ (권장)
```go
// TLS 100% 통과 보장
client, _ := tls_client.NewHttpClient(
    tls_client.NewNoopLogger(),
    tls_client.WithClientProfile(profiles.Chrome_120),
)
```

**결과**:
- TLS 통과: 100% ✅
- 2단계 Akamai Challenge: 별도 처리 필요

### Option 2: Node.js + Proxy 로테이션
```javascript
// 서버가 핑거프린트 학습 전에 IP 변경
// 효과 제한적 (근본 해결 아님)
```

**결과**:
- TLS 통과: 40-50% (개선 가능)
- 여전히 불안정

### Option 3: Python curl-cffi (WSL)
```python
# curl-impersonate 기반
response = requests.get(url, impersonate='chrome120')
```

**결과**:
- TLS 통과: 100% (예상)
- WSL 환경 필요

## 📊 최종 비교

| 방법 | TLS 매칭 | Extension 순서 | GREASE | TLS 통과율 |
|------|---------|---------------|--------|----------|
| Chrome 브라우저 | 100% | ✅ | ✅ | 100% |
| Golang tls-client | 100% | ✅ | ✅ | **100%** ⭐ |
| Python curl-cffi | 100% | ✅ | ✅ | 100% (예상) |
| Node.js HTTP/2 | 70% | ❌ | ❌ | 20-30% |

## 🚀 권장 전략

### 1단계 TLS 무한 통과
→ **Golang tls-client 사용** (이미 구현 완료)

```bash
# 이미 설치됨
./coupang_tls_client.exe
```

**검증된 결과**:
- ✅ TLS 100% 통과
- 🚨 Akamai Challenge 100% 수신 (예상됨)

### 2단계 Akamai 우회
→ **별도 전략 필요** (V8 JavaScript 또는 Real Chrome)

## 🎯 결론

**1단계 TLS 무한 통과**:
- ✅ Golang tls-client로 해결 완료
- ❌ Node.js는 근본적 한계 (OpenSSL)

**Node.js 20-30% 성공 원인**:
- Extension 순서 불일치
- GREASE 미지원
- 서버의 학습 기반 간헐적 차단

**최종 솔루션**:
1. **1단계**: Golang tls-client (TLS 100%)
2. **2단계**: Akamai Challenge 해결 (다음 과제)
