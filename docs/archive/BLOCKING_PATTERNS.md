# 차단 패턴 분석 - TLS vs Akamai

## 차단 방식 구분

쿠팡은 **2단계 차단 시스템**을 사용합니다:
1. **TLS ClientHello 레벨 차단** (1단계)
2. **Akamai Bot Manager Challenge** (2단계)

---

## 1. TLS ClientHello 레벨 차단 ❌

### 차단 증상
- 연결 즉시 종료 (handshake 실패)
- HTTP 응답 없음
- 오류 코드: `ERR_HTTP2_STREAM_ERROR`, `EPROTO`, `ERR_SSL_PROTOCOL_ERROR`

### 오류 메시지 예시
```
❌ 클라이언트 오류: ERR_HTTP2_STREAM_ERROR (46ms)
❌ 요청 오류: NGHTTP2_INTERNAL_ERROR
❌ TLS 프로토콜 오류 - ClientHello 거부
```

### 발생 시점
- **첫 연결 시도부터** 차단
- TLS 핸드셰이크 단계에서 즉시 종료
- 응답 본문 없음

### 차단 기준
- JA3/JA4 TLS 핑거프린트 불일치
- Cipher Suite 순서 불일치
- Extension 순서 불일치
- GREASE 값 부재
- Supported Groups 불일치

### 우회 가능 여부
✅ **우회 가능**
- Node.js HTTP/2: Cipher + Groups 매칭으로 통과
- Golang tls-client: Chrome 120 프로파일로 통과
- Python curl-cffi: curl-impersonate로 통과

---

## 2. Akamai Bot Manager Challenge 🚨

### 차단 증상
- TLS 핸드셰이크 **성공**
- HTTP 200 응답 수신
- 매우 작은 HTML 응답 (1.2KB)
- `location.reload` JavaScript 포함

### 응답 예시
```html
<html>
   <body>
      <script src="/EmMdAPxL/vlKvy6z/rlRYzJQ/0B/ckiah87m5Ji1/JUJyGlxE/fUoXXR8j/FQBsAQ?v=3b198cde-19ab-f5dd-fe1a-4c2ec4871741&t=312395698"></script>
      <script>
         (function() {
             var chlgeId = '';
             var scripts = document.getElementsByTagName('script');
             for (var i = 0; i < scripts.length; i++) {
                 if (scripts[i].src && scripts[i].src.match(/t=([^&#]*)/)) {
                     chlgeId = scripts[i].src.match(/t=([^&#]*)/)[1];
                 }
             }
             var proxied = window.XMLHttpRequest.prototype.send;
             window.XMLHttpRequest.prototype.send = function() {
                 var pointer = this
                 var intervalId = window.setInterval(function() {
                     if (pointer.readyState === 4 && pointer.responseURL && pointer.responseURL.indexOf('t=' + chlgeId) > -1) {
                         location.reload(true);
                         clearInterval(intervalId);
                     }
                 }, 1);
                 return proxied.apply(this, [].slice.call(arguments));
             };
         })();
      </script>
   </body>
</html>
```

### 발생 시점
- TLS 통과 **후** 발동
- HTTP 200 응답으로 위장
- 정상 응답 크기: 800KB+ → Challenge: 1.2KB

### 차단 기준
- JavaScript 실행 환경 부재
- 브라우저 특성 불일치
- 행동 패턴 분석 (속도, 순서 등)
- 세션 핑거프린트 학습

### 우회 가능 여부
❌ **우회 불가능** (V8 JavaScript 엔진 필요)
- Node.js/Golang/Python: JavaScript 실행 불가
- Challenge Script를 해결할 수 없음
- Real Chrome만 자동 처리 가능

---

## 테스트 결과 비교

### Node.js HTTP/2 (BoringSSL 매칭)

**요청 1: 음료수**
```
[1] HTTP/2 요청
  ✅ 200 | 1210ms | HTTP/2
  🍪 PCID, _abck, bm_sz (9개 쿠키)
  📦 888.5KB
  ✅ 정상 검색 결과 확인
```
→ **TLS 통과 ✅ + Akamai 우회 ✅ = 성공**

**요청 2: 노트북**
```
[2] HTTP/2 요청
  ❌ 요청 오류: ERR_HTTP2_STREAM_ERROR (46ms)
```
→ **TLS 차단 ❌** (세션 재사용 감지)

**요청 3: 키보드**
```
[3] HTTP/2 요청
  ❌ 요청 오류: ERR_HTTP2_STREAM_ERROR (51ms)
```
→ **TLS 차단 ❌** (핑거프린트 학습)

### Golang tls-client (Chrome 120 완벽 재현)

**모든 요청 (1, 2, 3)**
```
[1-3] tls-client 요청
  ✅ 200 | 83-212ms | HTTP/2.0
  🍪 _abck, ak_bmsc, bm_sz (7-8개 쿠키)
  📦 1.2KB
  🚨 차단 감지 (Bot Manager Challenge)
```
→ **TLS 통과 ✅ + Akamai Challenge 🚨 = 실패**

---

## 차단 구분 방법

### 1. 응답 코드 확인
- **TLS 차단**: 오류 코드 (ERR_HTTP2_STREAM_ERROR, EPROTO 등)
- **Akamai 차단**: HTTP 200 정상 응답

### 2. 응답 크기 확인
- **TLS 차단**: 응답 없음 (0 바이트)
- **Akamai 차단**: 1.2KB 작은 HTML

### 3. 응답 시간 확인
- **TLS 차단**: 매우 빠름 (40-80ms, 핸드셰이크 실패)
- **Akamai 차단**: 정상 (80-300ms, 처리 후 차단)

### 4. 응답 내용 확인
- **TLS 차단**: 응답 본문 없음
- **Akamai 차단**: `location.reload` JavaScript 포함

### 5. 쿠키 수신 여부
- **TLS 차단**: 쿠키 없음
- **Akamai 차단**: Akamai 쿠키 수신 (_abck, bm_sz, ak_bmsc)

---

## 실전 판별 가이드

### ✅ 정상 응답
```
상태: 200
크기: 800KB+ (검색 결과)
시간: 1000-2000ms
쿠키: 9개+
내용: search-product, 검색결과, productList
```

### ❌ TLS 레벨 차단
```
상태: 오류 (ERR_HTTP2_STREAM_ERROR 등)
크기: 0 바이트
시간: 40-80ms
쿠키: 없음
내용: 없음
```

### 🚨 Akamai Challenge 차단
```
상태: 200
크기: 1.2KB
시간: 80-300ms
쿠키: 7-8개 (_abck, bm_sz 등)
내용: location.reload, Challenge Script
```

---

## 결론

### 차단 단계별 분석

**1단계: TLS ClientHello 필터링**
- JA3/JA4 핑거프린트 검증
- Node.js: 1회 통과 후 학습으로 차단
- Golang: 완벽 재현으로 항상 통과

**2단계: Akamai Bot Manager**
- JavaScript Challenge 발동
- V8 엔진 없이는 해결 불가
- Real Chrome만 자동 우회 가능

### 최종 결론

**패킷 모드의 한계**:
- TLS 레벨: 우회 가능 ✅
- Akamai 레벨: 우회 불가능 ❌
- **결론**: 패킷 모드로는 실용적 성공률 달성 불가

**Real Chrome + CDP**:
- TLS 레벨: 자동 통과 ✅
- Akamai 레벨: 자동 해결 ✅
- **결론**: 유일하게 안정적인 100% 솔루션
