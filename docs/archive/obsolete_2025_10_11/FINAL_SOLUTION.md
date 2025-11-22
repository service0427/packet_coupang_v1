# 🎯 최종 해결책: 쿠키 재활용 + 프로필 로테이션

## 핵심 발견

### 1. Akamai의 차단 메커니즘

**차단 대상**: IP + TLS 지문 패턴 조합
- Safari 프로필들: 15페이지 테스트 후 학습되어 모두 차단됨
- Chrome 프로필: 아직 차단되지 않음 ✅
- Firefox: 차단됨

**쿠키와 TLS 지문의 분리**:
- ✅ **Akamai는 쿠키를 발급한 브라우저와 요청 TLS 지문을 크로스 검증하지 않음**
- Chrome 브라우저로 받은 쿠키 + Safari/Chrome 패킷 = 우회 성공
- **쿠키는 한 번만 받으면 계속 재활용 가능!**

## 최종 성공 조합

### 테스트 결과 (2025-10-10 15:15)

**저장된 쿠키 사용 + 10개 프로필 조합 테스트:**

| 프로필 | HEADER_TABLE_SIZE | 결과 | 상품 수 |
|--------|------------------|------|---------|
| safari170 | 16384 | ❌ 차단 | - |
| safari170 | 24576 | ❌ 차단 | - |
| safari170 | 32768 | ❌ 차단 | - |
| safari153 | 49152 | ❌ 차단 | - |
| safari184 | 32768 | ❌ 차단 | - |
| **chrome124** | **16384** | ✅ 성공 | 46개 |
| **chrome124** | **32768** | ✅ 성공 | 46개 |
| **chrome120** | **24576** | ✅ 성공 | 46개 |
| firefox135 | 16384 | ❌ 차단 | - |
| firefox133 | 24576 | ❌ 차단 | - |

**성공률: 3/10 (30%)**

## 최적 구성

### best_config.json

```json
{
  "best_combination": {
    "profile": "chrome124",
    "http2_settings": "1:16384;2:0;3:1000;4:6291456;6:262144",
    "products": 46,
    "html_size": 1372687
  }
}
```

### 프로덕션 설정

```python
# 1. 쿠키는 한 번만 받기
COOKIE_FILE = 'cookies/coupang_cookies.json'

# 2. 성공한 Chrome 프로필들 사용
PROFILES = [
    {'profile': 'chrome124', 'settings': '1:16384;2:0;3:1000;4:6291456;6:262144'},
    {'profile': 'chrome124', 'settings': '1:32768;2:0;3:1000;4:6291456;6:262144'},
    {'profile': 'chrome120', 'settings': '1:24576;2:0;3:1000;4:6291456;6:262144'},
]

# 3. 매 요청마다 프로필 로테이션
current_index = 0
profile = PROFILES[current_index]
current_index = (current_index + 1) % len(PROFILES)
```

## 구현 전략

### 1단계: 쿠키 획득 (1회만)

```python
# Playwright로 쿠키 한 번 받기
async def get_cookies_once():
    # 브라우저 열고 검색
    cookies = await context.cookies()

    # 쿠키 파일로 저장
    with open('cookies/coupang_cookies.json', 'w') as f:
        json.dump(cookies, f)

    return cookies
```

### 2단계: 쿠키 재활용 + 프로필 로테이션

```python
# 저장된 쿠키 로드
with open('cookies/coupang_cookies.json', 'r') as f:
    cookies = json.load(f)

# 프로필 로테이션하면서 크롤링
for page in range(1, 16):
    profile_config = get_next_profile()  # 순환

    session = requests.Session()
    session.curl.setopt(CurlOpt.HTTP2_SETTINGS, profile_config['settings'])

    response = session.get(
        url,
        impersonate=profile_config['profile'],
        cookies=cookie_dict
    )
```

### 3단계: 15페이지 크롤링

- 페이지 간 2.5초 딜레이
- 프로필 3개를 순환 사용
- 차단 시 다음 프로필로 자동 전환

## 테스트 결과

### Safari 조합 (이전 성공 → 현재 차단)

**safari153 + HEADER_TABLE_SIZE=32768:**
- 이전: 15/15 페이지 성공, 519개 상품
- 현재: 1페이지부터 HTTP/2 INTERNAL_ERROR

**원인**: 15페이지 테스트로 Akamai가 패턴 학습

### Chrome 조합 (현재 성공)

**chrome124 + HEADER_TABLE_SIZE=16384:**
- 현재: 1페이지 성공, 46개 상품
- 15페이지 테스트 필요

## 핵심 인사이트

### 1. 브라우저 vs 패킷의 차이

**Playwright (Chrome 브라우저):**
```
chrome-error://chromewebdata/
177KB 에러 페이지
JavaScript Challenge 실패
```

**curl-cffi (Chrome TLS 위조):**
```
HTTP 200
1.3MB 정상 페이지
46개 상품 추출 성공
```

**결론**: 동일한 Chrome인데 브라우저는 차단, 패킷은 성공!

### 2. 쿠키의 독립성

- Playwright로 받은 쿠키 = 유효함
- 해당 쿠키 + 다른 TLS 지문 = 우회 성공
- **쿠키를 발급한 브라우저와 사용하는 TLS 지문이 달라도 무관**

### 3. 프로필 소진 패턴

1. 특정 프로필로 많이 사용 (15페이지 테스트)
2. Akamai가 해당 프로필 패턴 학습
3. 해당 IP + 프로필 조합 차단
4. **다른 프로필로 전환하면 우회 가능**

## 다음 단계

### 1. Chrome 조합으로 15페이지 테스트

```bash
# manual_test_crawler.py 설정
PROFILE = 'chrome124'
HTTP2_SETTINGS = '1:16384;2:0;3:1000;4:6291456;6:262144'
KEYWORD = '마우스'
END_PAGE = 15
```

**예상 결과**: 15/15 성공 가능

### 2. 프로필 로테이션 시스템 구축

```python
# 3개 Chrome 프로필 순환
profiles = [
    'chrome124 + 16384',
    'chrome124 + 32768',
    'chrome120 + 24576',
]

# 매 요청마다 다른 프로필 사용
for page in range(1, 16):
    profile = profiles[page % 3]
    # ...
```

### 3. 자동 프로필 발견 시스템

```python
# 주기적으로 새로운 조합 탐색
def find_working_profiles():
    test_cases = generate_all_combinations()
    for case in test_cases:
        if test_profile(case):
            add_to_pool(case)
```

## 결론

### 성공 요인

1. ✅ **쿠키 재활용**: Playwright 없이도 계속 크롤링 가능
2. ✅ **프로필 다양성**: Safari 차단되어도 Chrome 사용 가능
3. ✅ **TLS 지문 변조**: curl-cffi로 다양한 브라우저 흉내

### 안정성 향상 방안

1. **프로필 풀 확대**: 더 많은 프로필 조합 확보
2. **지능형 로테이션**: 차단 감지 시 자동 전환
3. **쿠키 갱신 전략**: 특정 조건에서만 쿠키 새로 받기

### 최종 권장 구성

```python
# 쿠키: 1회만 획득, 파일로 저장
cookies = load_saved_cookies()

# 프로필: 3개 Chrome 조합 순환
profiles = [
    {'profile': 'chrome124', 'settings': '1:16384;...'},
    {'profile': 'chrome124', 'settings': '1:32768;...'},
    {'profile': 'chrome120', 'settings': '1:24576;...'},
]

# 크롤링: 프로필 로테이션 + 딜레이
for page in range(1, 16):
    profile = profiles[page % 3]
    result = search_page(cookies, keyword, page, profile)
    time.sleep(2.5)
```

**예상 성능**: 15/15 페이지, 500+ 상품 안정적 수집 가능
