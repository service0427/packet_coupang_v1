# 쿠팡 Akamai Bot Manager 우회 연구 최종 요약

## 🎯 핵심 발견

### 1. Akamai의 차단 메커니즘

**3단계 검증 시스템:**

1. **JavaScript Challenge (브라우저 검증)**
   - Playwright (리얼 브라우저): 차단됨 (`chrome-error://chromewebdata/`)
   - 하지만 **쿠키는 정상 발급됨**

2. **TLS 지문 검증 (패킷 레벨)**
   - curl-cffi + Safari TLS: 우회 성공
   - curl-cffi + Chrome TLS: 우회 성공
   - **쿠키를 발급한 브라우저 ≠ 요청 TLS 지문이어도 통과**

3. **패턴 기반 차단 (IP + TLS 조합)**
   - 동일 TLS 패턴 반복 사용 시 학습됨
   - 15페이지 크롤링 → 해당 프로필 차단
   - **차단은 IP + TLS 조합 단위**

### 2. 쿠키와 TLS 지문의 독립성

**중대한 허점 발견:**
```
Chrome 브라우저로 받은 쿠키
    ↓
Safari TLS 지문으로 요청
    ↓
✅ Akamai 우회 성공!
```

**Akamai는 쿠키를 발급한 브라우저 지문과 현재 요청의 TLS 지문을 크로스 검증하지 않음!**

### 3. 프로필 소진 패턴

**시간순 차단 패턴:**

| 시간 | 프로필 | HTTP/2 SETTINGS | 결과 | 상품 수 |
|------|--------|-----------------|------|---------|
| 14:38 | safari260 | 24576 | ✅ 4-5페이지 성공 | ~150개 |
| 14:50 | safari260 | 24576 | ❌ 1페이지부터 차단 | 0개 |
| 15:04 | safari184 | 16384 | ✅ 2/15 성공 | 82개 |
| 15:08 | safari153 | 32768 | ✅ **15/15 성공** | **519개** |
| 15:10 | safari153 | 32768 | ❌ 1페이지부터 차단 | 0개 |
| 15:15 | chrome124 | 16384 | ✅ 1페이지 성공 | 46개 |
| 15:16 | chrome124 | 16384 | ❌ 차단 | 0개 |

**학습 속도**: 15페이지 크롤링 1회 → 즉시 차단

## 성공한 기술들

### 1. curl-cffi + TLS 지문 위조

**핵심 라이브러리:**
- curl-cffi: curl-impersonate의 Python 래퍼
- BoringSSL: Chrome의 TLS 라이브러리 사용

**성공 프로필:**
- safari260, safari184, safari170, safari153
- chrome124, chrome120
- (firefox는 대부분 실패)

**HTTP/2 SETTINGS 최적화:**
```python
# HEADER_TABLE_SIZE 조정이 핵심
'1:16384;2:0;3:1000;4:6291456;6:262144'  # 1/4로 축소
'1:24576;2:0;3:1000;4:6291456;6:262144'  # 1/3로 축소
'1:32768;2:0;3:1000;4:6291456;6:262144'  # 1/2로 축소
```

### 2. 쿠키 재활용 전략

**최적 구조:**
```python
# 1. Playwright로 쿠키 1회만 획득
cookies = await get_cookies()
with open('cookies.json', 'w') as f:
    json.dump(cookies, f)

# 2. 이후 크롤링은 저장된 쿠키 재활용
cookies = json.load(open('cookies.json'))

# 3. curl-cffi로 다양한 TLS 지문 사용
response = session.get(url, impersonate='safari153', cookies=cookies)
```

**장점:**
- Playwright 매번 실행 불필요
- 빠른 크롤링 가능
- 리소스 절약

### 3. 프로필 로테이션

**전략:**
```python
profiles = [
    {'profile': 'safari153', 'settings': '1:32768;2:0;...'},
    {'profile': 'safari184', 'settings': '1:16384;2:0;...'},
    {'profile': 'chrome124', 'settings': '1:16384;2:0;...'},
]

# 매 요청마다 프로필 순환
for page in range(1, 16):
    profile = profiles[page % len(profiles)]
    result = search_page(cookies, keyword, page, profile)
```

**결과:**
- safari153 단일 사용: 15/15 성공 (519개 상품)
- 하지만 1회 사용 후 즉시 차단됨

## 최고 성과

### safari153 + HEADER_TABLE_SIZE=32768

**테스트 시간**: 2025-10-10 15:08

**설정:**
```python
PROFILE = 'safari153'
HTTP2_SETTINGS = '1:32768;2:0;3:1000;4:6291456;6:262144'
KEYWORD = '키보드'
PAGES = 1-15
DELAY = 2.5초
```

**결과:**
```
성공 페이지: 15/15 (100%)
수집 상품: 519개
평균 상품/페이지: 34.6개
응답 크기: 600-1,300KB
프로토콜: HTTP/3
```

**로그 샘플:**
```
[페이지 1/15] [OK] 45개 상품 (1,367,767 bytes)
[페이지 2/15] [OK] 34개 상품 (609,915 bytes)
...
[페이지 15/15] [OK] 35개 상품 (611,620 bytes)

저장: 키보드_safari153_20251010_150833.json
완료: 15개 페이지, 519개 상품 수집 완료
```

## 한계와 대응 방안

### 한계

1. **빠른 패턴 학습**
   - 15페이지 1회 크롤링 → 즉시 차단
   - IP + TLS 조합 단위로 차단

2. **프로필 소진**
   - Safari 계열: 모두 차단됨
   - Chrome 계열: 모두 차단됨
   - Firefox: 애초에 대부분 실패

3. **검색어 무관**
   - 검색어를 바꿔도 차단 유지
   - IP + TLS 패턴만 감지

### 대응 방안

#### 1. IP 변경
```bash
# VPN/프록시로 IP 변경
# → 차단된 프로필도 다시 사용 가능
```

#### 2. 프로필 풀 확대
```python
# 더 많은 조합 사전 탐색
profiles = generate_all_combinations()  # 수백 개
test_and_filter_working_profiles(profiles)
```

#### 3. 지능형 로테이션
```python
# 실시간 차단 감지 및 자동 전환
def smart_crawl(keyword, pages):
    for page in pages:
        result = search_with_current_profile()

        if is_blocked(result):
            switch_to_next_profile()
            result = retry_with_new_profile()
```

#### 4. 분산 크롤링
```python
# 여러 IP에서 동시 크롤링
# 각 IP당 3-5페이지씩 분산
ip_pool = ['IP1', 'IP2', 'IP3', ...]
for ip in ip_pool:
    crawl_pages(keyword, start=ip_index*3, end=ip_index*3+3)
```

## 기술적 인사이트

### 1. HTTP/2 SETTINGS의 중요성

**기본값 (차단됨):**
```
HEADER_TABLE_SIZE: 65536
```

**성공값:**
```
HEADER_TABLE_SIZE: 16384  # 1/4
HEADER_TABLE_SIZE: 24576  # 1/3
HEADER_TABLE_SIZE: 32768  # 1/2
```

**이유**: SETTINGS 프레임이 TLS 지문의 일부로 사용됨

### 2. Safari vs Chrome

**Safari:**
- safari153, safari170, safari184, safari260 모두 성공
- 가장 안정적
- 15페이지 연속 성공 기록

**Chrome:**
- chrome120, chrome124 성공
- Safari만큼 안정적
- Firefox보다 우수

**Firefox:**
- firefox133, firefox135 대부분 실패
- Akamai가 Firefox 지문 특별 감시 추정

### 3. 프로토콜 버전

**응답:**
- Protocol: HTTP/3 (대부분)
- Status: 200
- Server: envoy

**요청:**
- HTTP/2 SETTINGS 전송
- TLS 1.3
- ALPN: h2

## 실전 활용

### 추천 구성

```python
# 1. 쿠키 획득 (1회)
cookies = get_cookies_with_playwright()
save_cookies(cookies)

# 2. 프로필 풀 준비
profiles = [
    {'profile': 'safari153', 'settings': '1:32768;...'},
    {'profile': 'safari184', 'settings': '1:16384;...'},
    {'profile': 'safari170', 'settings': '1:24576;...'},
    {'profile': 'chrome124', 'settings': '1:16384;...'},
    {'profile': 'chrome120', 'settings': '1:24576;...'},
]

# 3. 지능형 크롤링
def crawl_with_rotation(keyword, max_pages=15):
    cookies = load_cookies()
    current_profile_idx = 0

    for page in range(1, max_pages + 1):
        profile = profiles[current_profile_idx]

        try:
            result = search_page(cookies, keyword, page, profile)

            if result['success']:
                yield result
                current_profile_idx = (current_profile_idx + 1) % len(profiles)
            else:
                # 차단 감지 → 다음 프로필
                current_profile_idx += 1
                if current_profile_idx >= len(profiles):
                    print('모든 프로필 소진')
                    break

        except Exception as e:
            if 'INTERNAL_ERROR' in str(e):
                current_profile_idx += 1

        time.sleep(2.5)  # 페이지 간 딜레이
```

### 성능 예측

**단일 IP + 프로필 풀 5개:**
- 예상: 5-10 페이지 안정적 수집
- 페이지당 30-40개 상품
- 총 150-400개 상품

**IP 변경 시:**
- 차단된 프로필 재사용 가능
- 거의 무한 크롤링 가능

## 결론

### 성공 요인

1. ✅ **curl-cffi의 강력한 TLS 위조 능력**
2. ✅ **Akamai의 쿠키-TLS 검증 허점**
3. ✅ **HTTP/2 SETTINGS 최적화**

### 한계

1. ❌ **빠른 패턴 학습 (15페이지 1회 → 차단)**
2. ❌ **IP 단위 차단**
3. ❌ **프로필 소진 문제**

### 최종 권장 사항

**단기 (현재 IP):**
- 새로운 프로필 조합 탐색
- 3-5페이지씩 분산 크롤링

**중기 (IP 변경):**
- VPN/프록시 활용
- 차단된 프로필 재활용

**장기 (시스템화):**
- 자동 프로필 발견 시스템
- 분산 크롤링 인프라
- 실시간 차단 감지 및 대응

---

**가장 중요한 발견**:
**쿠키를 한 번 받아서 저장하고, 다양한 TLS 프로필로 재활용하면 Playwright 없이도 대량 크롤링이 가능하다!**
