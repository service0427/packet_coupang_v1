# 헤더 로깅 기능 추가 완료

## 개요

프로토콜 차단을 정확히 판별하기 위해 `manual_test_crawler.py`에 상세한 헤더 로깅 기능을 추가했습니다.

## 추가된 로깅 기능

### 1. Playwright 응답 정보 (쿠키 획득 단계)

```
[*] Playwright 응답 정보:
      Status: 200
      Content-Type: text/html; charset=utf-8
      Content-Length: N/A
      Server: cloudflare
      Akamai/X- Headers: {헤더 정보}
      Current URL: {현재 URL}
      Page Size: {페이지 크기} bytes
```

### 2. curl-cffi 응답 정보 (크롤링 단계)

```
      curl-cffi 응답 정보:
      Status: 200
      Protocol: 3 (HTTP/2)
      Content-Type: text/html; charset=utf-8
      Content-Length: N/A
      Server: cloudflare
      Akamai/X- Headers: {헤더 정보}
      Response Size: 1,572,965 bytes
```

### 3. 리다이렉트 체인 로그

리다이렉트가 발생한 경우:
```
      Redirects: 2 redirect(s)
        [1] 301 -> https://www.coupang.com/redirect1
        [2] 302 -> https://www.coupang.com/redirect2
```

### 4. 프로토콜 오류 분류

HTTP/2 프로토콜 오류를 자동으로 분류:
```
      Exception Type: RequestsError
      Error Message: Failed to perform, curl: (92) HTTP/2 stream 1 was not closed cleanly: INTERNAL_ERROR (err 2)
      [프로토콜 차단] HTTP/2 INTERNAL_ERROR 감지
```

**감지 가능한 오류 타입:**
- `INTERNAL_ERROR` - 내부 프로토콜 오류
- `PROTOCOL_ERROR` - 프로토콜 위반
- `REFUSED_STREAM` - 스트림 거부
- `SETTINGS` - SETTINGS 프레임 문제

## 테스트 결과 (2025-01-10 14:50)

**설정:**
- Profile: safari260
- HTTP/2 SETTINGS: 1:24576;2:0;3:1000;4:6291456;6:262144
- 키워드: 노트북

**결과:**
- ✅ 5/5 페이지 성공
- ✅ 189개 상품 수집
- ✅ Protocol: 3 (HTTP/2) 확인
- ✅ Server: cloudflare 확인
- ✅ Akamai 헤더 감지: x-cp-auth-member, x-xss-protection, x-envoy-upstream-service-time

## 주요 발견 사항

### 1. 프로토콜 버전 확인
- `Protocol: 3` → HTTP/2 사용 중 (정상)
- curl-cffi가 HTTP/2로 성공적으로 통신

### 2. 서버 정보
- **Server: cloudflare** - Akamai가 Cloudflare CDN 사용
- Cloudflare를 통해 Akamai Bot Manager 동작

### 3. Akamai 관련 헤더
- `x-cp-auth-member: 0` - 비로그인 상태
- `x-xss-protection: 1; mode=block` - XSS 보호 활성화
- `x-envoy-upstream-service-time` - Envoy 프록시 응답 시간
- `x-envoy-decorator-operation: :0/*` - Envoy 라우팅 정보

### 4. 차단 판별 개선
기존 방식은 페이지 크기만으로 차단 여부 판별했으나, 이제는:
- HTTP 상태 코드
- 프로토콜 버전
- 서버 헤더
- Akamai 특정 헤더
- HTTP/2 오류 타입

모두 확인 가능하여 **정확한 프로토콜 차단 감지** 가능

## 차단 시나리오별 로그 예시

### 시나리오 1: 정상 통과
```
Status: 200
Protocol: 3
Server: cloudflare
Response Size: 1,572,965 bytes
→ 성공
```

### 시나리오 2: HTTP/2 프로토콜 차단
```
Exception Type: RequestsError
Error Message: Failed to perform, curl: (92) HTTP/2 stream 1 was not closed cleanly: INTERNAL_ERROR (err 2)
[프로토콜 차단] HTTP/2 INTERNAL_ERROR 감지
→ 프로토콜 레벨 차단
```

### 시나리오 3: 페이지 크기 차단
```
Status: 200
Protocol: 3
Response Size: 8,432 bytes
→ 작은 페이지 = Akamai JavaScript 차단 페이지
```

## 사용 방법

파일 상단에서 TLS 설정 조정:

```python
# Safari 프로필 선택
PROFILE = 'safari260'

# HTTP/2 SETTINGS
HTTP2_SETTINGS = '1:24576;2:0;3:1000;4:6291456;6:262144'

# 검색 설정
KEYWORD = '노트북'
START_PAGE = 1
END_PAGE = 5
```

실행:
```bash
python manual_test_crawler.py
```

## 다음 단계

1. **프로토콜 차단 발생 시 자동 재시도**: HTTP/2 INTERNAL_ERROR 감지 시 다른 프로필로 자동 전환
2. **헤더 기반 차단 감지**: Akamai 헤더 패턴 분석으로 사전 차단 감지
3. **응답 시간 분석**: x-envoy-upstream-service-time을 통한 서버 부하 감지
