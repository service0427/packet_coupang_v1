# 15페이지 크롤링 테스트 결과 (2.5초 딜레이 적용)

## 테스트 개요

**목적**: 페이지 간 딜레이(2.5초)를 추가하여 더 많은 페이지까지 크롤링 가능한지 검증

**설정**:
- 페이지 범위: 1~15 (총 15페이지)
- 페이지 간 딜레이: 2.5초
- 검색 키워드: 노트북

## 테스트 1: safari260 + HEADER_TABLE_SIZE=24576

**설정**:
```
PROFILE = 'safari260'
HTTP2_SETTINGS = '1:24576;2:0;3:1000;4:6291456;6:262144'
```

**결과**: ❌ 첫 페이지부터 차단
- 페이지 1: HTTP/2 INTERNAL_ERROR
- 수집 상품: 0개

**분석**:
- 이전 테스트에서 이 조합이 4-5페이지까지 성공했으나, 이번에는 1페이지부터 실패
- **Akamai가 이 TLS 패턴을 학습하여 차단 리스트에 추가한 것으로 추정**
- 패턴 기반 차단의 증거

## 테스트 2: safari184 + HEADER_TABLE_SIZE=16384

**설정**:
```
PROFILE = 'safari184'
HTTP2_SETTINGS = '1:16384;2:0;3:1000;4:6291456;6:262144'
```

**결과**: ✅ 2페이지 성공
```
페이지 1: 성공 (47개 상품, 1,573,493 bytes)
  - HTTP Status: 200
  - Protocol: HTTP/3
  - Server: envoy
  - x-envoy-upstream-service-time: 1189

[2.5초 대기]

페이지 2: 성공 (35개 상품, 667,547 bytes)
  - HTTP Status: 200
  - Protocol: HTTP/3
  - Server: envoy
  - x-envoy-upstream-service-time: 1027

[2.5초 대기]

페이지 3: HTTP/2 INTERNAL_ERROR ❌
  - TLS 지문 패턴 차단
```

**최종 수집**:
- 성공 페이지: 2/15 (13.3%)
- 수집 상품: 82개
- 평균 상품/페이지: 41.0개

## 핵심 발견

### 1. Akamai의 학습 능력

**이전 테스트 (2시간 전)**:
- safari260 + HEADER_TABLE_SIZE=24576 = 4-5페이지 성공

**현재 테스트**:
- safari260 + HEADER_TABLE_SIZE=24576 = 1페이지부터 차단

**결론**: Akamai는 **반복 사용되는 TLS 패턴을 학습하여 차단 리스트에 추가**

### 2. 딜레이 효과 제한적

**2.5초 딜레이 적용**:
- safari184: 페이지 1-2 성공, 페이지 3 차단
- 이전 테스트(딜레이 없음)와 큰 차이 없음

**결론**: **페이지 간 딜레이만으로는 차단 회피 불가능**
- 딜레이는 속도 제어용일 뿐, TLS 패턴 차단 회피 불가
- 근본 원인은 **동일 TLS 지문 반복 사용**

### 3. 프로토콜 차단 패턴

**차단 메커니즘**:
```
요청 1-2: TLS 패턴 확인 → 정상 응답 (HTTP/3)
요청 3:   동일 패턴 반복 감지 → HTTP/2 INTERNAL_ERROR
```

**특징**:
1. 첫 1-2개 요청은 통과 (패턴 학습 중)
2. 3번째 요청부터 차단 (패턴 확인 완료)
3. 차단은 HTTP/2 프로토콜 레벨에서 발생

### 4. Playwright 차단 vs curl-cffi 성공

**Playwright (Chrome 브라우저)**:
```
Current URL: chrome-error://chromewebdata/
Page Size: 177,423 bytes
상품 확인 불가
→ JavaScript Challenge 실패
```

**curl-cffi (Safari TLS 위조)**:
```
HTTP Status: 200
Protocol: HTTP/3
Response Size: 1,573,493 bytes
47개 상품 추출 성공
→ TLS 지문 차이로 우회 성공
```

**결론**: **Akamai는 쿠키 발급 브라우저와 요청 TLS 지문을 크로스 검증하지 않음**

## 해결 방안

### 1. 프로필 로테이션 (권장) ✅

**전략**: 매 요청마다 다른 TLS 프로필 사용

```python
profiles = [
    {'profile': 'safari184', 'settings': '1:16384;2:0;3:1000;4:6291456;6:262144'},
    {'profile': 'safari170', 'settings': '1:24576;2:0;3:1000;4:6291456;6:262144'},
    {'profile': 'safari153', 'settings': '1:16384;2:0;3:1000;4:6291456;6:262144'},
    {'profile': 'chrome124', 'settings': '1:32768;2:0;3:1000;4:6291456;6:262144'},
]

current_profile_index = 0

def get_next_profile():
    global current_profile_index
    profile = profiles[current_profile_index]
    current_profile_index = (current_profile_index + 1) % len(profiles)
    return profile
```

**예상 효과**:
- 동일 패턴 반복 회피
- 15페이지 전체 크롤링 가능할 것으로 예상

### 2. HTTP/2 SETTINGS 랜덤화

**전략**: HEADER_TABLE_SIZE를 동적으로 변경

```python
import random

def get_random_settings():
    header_sizes = [16384, 24576, 32768, 49152]
    header_size = random.choice(header_sizes)
    return f'1:{header_size};2:0;3:1000;4:6291456;6:262144'
```

### 3. 세션 재생성

**전략**: 매 요청마다 curl-cffi 세션 재생성

```python
def search_page(cookies, keyword, page, profile, http2_settings):
    # 매번 새로운 세션 생성
    session = requests.Session()
    session.curl.setopt(CurlOpt.HTTP2_SETTINGS, http2_settings)

    response = session.get(...)

    # 세션 명시적 종료
    session.close()

    return result
```

### 4. 쿠키 갱신 전략

**전략**: 3-4페이지마다 쿠키 새로 받기

```python
for page in range(1, 16):
    # 3페이지마다 쿠키 갱신
    if page % 3 == 1:
        cookies = await get_cookies()

    result = search_page(cookies, keyword, page, ...)
```

## 다음 단계

1. **프로필 로테이션 구현** - 가장 효과적인 방법
2. **15페이지 전체 크롤링 테스트**
3. **성공률 측정 및 최적화**
4. **프로덕션 크롤러에 적용**

## 참고: 로그 개선 사항

**개선된 로그 포맷**:
```
======================================================================
[페이지 1/15] 검색 시작
======================================================================

[응답 정보]
   HTTP Status: 200
   Protocol: HTTP/3
   Server: envoy
   Content-Type: text/html; charset=utf-8

[보안 헤더]
   x-xss-protection: 1; mode=block
   x-envoy-upstream-service-time: 1189
   x-akamai-transformed: 0 - 0 -

[응답 크기] 1,573,493 bytes (1536.6 KB)

[OK] 47개 상품 수집
   상품 ID 샘플: 8416720242, 8733162257, 6662026640, ...

[WAIT] 2.5초 대기 중... (다음 페이지 요청 전)
```

**장점**:
- 프로토콜 버전 확인 가능 (HTTP/3 vs HTTP/2)
- Akamai 헤더 분석 가능
- 응답 크기로 차단 여부 즉시 파악
- 페이지별 구분이 명확하여 디버깅 용이
