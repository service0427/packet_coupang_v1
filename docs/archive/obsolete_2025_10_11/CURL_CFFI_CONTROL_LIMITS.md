# curl-cffi 제어 한계 (빌드 없이)

## 결론 요약

**✅ 조정 가능한 레벨**:
- HTTP 레벨 (헤더, 쿠키, 파라미터)
- Impersonate 프로필 선택 (8개 프로필)
- 리퀘스트 타이밍 & 순서

**❌ 조정 불가능한 레벨** (BoringSSL 빌드에 하드코딩):
- TLS ClientHello (Cipher Suites, Extensions 순서)
- HTTP/2 SETTINGS 프레임 값
- ALPN 협상 우선순위
- GREASE 값 생성 로직

---

## 1. 조정 가능한 파라미터 (빌드 불필요)

### 1.1 Impersonate 프로필 전환 (핵심!)

**8개 프로필 = 4개 Akamai Hash 패턴**

```python
from curl_cffi import requests

# ✅ 가능: 프로필 선택으로 Akamai Hash 변경
profiles = [
    'chrome110',  # Akamai Hash: Pattern A
    'chrome116',  # Akamai Hash: Pattern A
    'chrome120',  # Akamai Hash: Pattern B
    'chrome124',  # Akamai Hash: Pattern C
    'edge99',     # Akamai Hash: Pattern A
    'edge101',    # Akamai Hash: Pattern A
    'safari15_3', # Akamai Hash: Pattern D
    'safari15_5', # Akamai Hash: Pattern D
]

# 차단 시 프로필 전환
for profile in profiles:
    response = requests.get(
        'https://www.coupang.com/...',
        impersonate=profile
    )
    if response.status_code == 200:
        break
```

**예상 효과**:
- IP당 150회 → 8 profiles × 150회 = **1200회/IP**
- 8배 효율 증가

---

### 1.2 HTTP 헤더 조작

```python
# ✅ 가능: HTTP 헤더 추가/변경
headers = {
    'User-Agent': '...',  # 이미 impersonate로 설정됨 (덮어쓰기 가능)
    'Accept': 'text/html,application/xhtml+xml,...',
    'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Referer': 'https://www.coupang.com/',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'same-origin',
    'Sec-Fetch-User': '?1',
    'Upgrade-Insecure-Requests': '1',

    # 커스텀 헤더 추가
    'X-Custom-Header': 'value'
}

response = requests.get(url, headers=headers, impersonate='chrome120')
```

**주의사항**:
- `User-Agent` 덮어쓰기 시 TLS(BoringSSL)와 불일치 가능성
- 대부분의 헤더는 impersonate 프로필에 이미 포함됨

---

### 1.3 쿠키 & 세션 관리

```python
# ✅ 가능: 쿠키 저장/복원
session = requests.Session()

# 1. 로그인으로 쿠키 획득
response = session.post(
    'https://login.coupang.com/...',
    data={'username': '...', 'password': '...'},
    impersonate='chrome120'
)

# 2. 쿠키 저장
cookies = session.cookies.get_dict()
# {'session_id': '...', 'auth_token': '...'}

# 3. 다른 프로필로 전환 시 쿠키 복원
new_session = requests.Session()
for name, value in cookies.items():
    new_session.cookies.set(name, value)

response = new_session.get(
    'https://www.coupang.com/...',
    impersonate='chrome116'  # 프로필 변경
)
```

---

### 1.4 리퀘스트 타이밍 & 순서

```python
import time
import random

# ✅ 가능: 요청 간 딜레이 조정
def human_like_crawl(urls):
    for url in urls:
        # 랜덤 딜레이 (1-3초)
        delay = random.uniform(1.0, 3.0)
        time.sleep(delay)

        response = requests.get(url, impersonate='chrome120')

        # 페이지 내 리소스 로딩 (이미지, CSS, JS)
        # 실제 브라우저처럼 보이기 위해
        fetch_resources(response)
```

---

### 1.5 Proxy 설정

```python
# ✅ 가능: Proxy 서버 사용
proxies = {
    'http': 'http://proxy.example.com:8080',
    'https': 'https://proxy.example.com:8080'
}

response = requests.get(
    url,
    proxies=proxies,
    impersonate='chrome120'
)
```

---

### 1.6 DNS 설정

```python
# ✅ 가능: DNS over HTTPS (DoH)
response = requests.get(
    url,
    impersonate='chrome120',
    # curl-cffi는 curl의 --doh-url 옵션 지원
    # (하지만 Python wrapper에서는 제한적)
)
```

**제한사항**: curl-cffi Python wrapper는 curl의 모든 옵션을 노출하지 않음.

---

## 2. 조정 불가능한 파라미터 (빌드 필요)

### 2.1 TLS ClientHello

**❌ 불가능**: Cipher Suite 순서, Extension 순서, GREASE 값

```python
# ❌ 불가능 (BoringSSL 내부 하드코딩)
#
# TLS ClientHello 구조:
# - Cipher Suites: [0x1301, 0x1302, 0x1303, ...]
# - Extensions: [server_name, ALPN, supported_groups, ...]
# - GREASE 값: 랜덤 생성 (BoringSSL 내부)
#
# 이를 변경하려면 BoringSSL C 코드 수정 후 재빌드 필요
```

**이유**:
- BoringSSL은 Chrome의 TLS 라이브러리
- ClientHello 구조는 BoringSSL `ssl/handshake.cc`에 하드코딩
- curl-cffi → libcurl-impersonate → BoringSSL 순으로 호출
- Python 레벨에서 접근 불가능

---

### 2.2 HTTP/2 SETTINGS 프레임

**❌ 불가능**: HEADER_TABLE_SIZE, MAX_CONCURRENT_STREAMS 등

```python
# ❌ 불가능 (libcurl-impersonate 하드코딩)
#
# HTTP/2 SETTINGS:
# - HEADER_TABLE_SIZE: 65536
# - ENABLE_PUSH: 0
# - MAX_CONCURRENT_STREAMS: 1000
# - INITIAL_WINDOW_SIZE: 6291456
# - MAX_HEADER_LIST_SIZE: 262144
#
# 이를 변경하려면 libcurl-impersonate 재빌드 필요
```

**Akamai Hash 결정 요소**:
```
Akamai Hash = hash(HTTP/2 SETTINGS 값들)

chrome120:
  SETTINGS = [65536, 0, 1000, 6291456, 262144]
  → Akamai Hash = 52d84b11737d980aef856699f885ca86

chrome110:
  SETTINGS = [65536, 0, 1000, 6291456, 262144]  # 동일
  → Akamai Hash = 52d84b11737d980aef856699f885ca86 (동일)
```

**결론**: HTTP/2 SETTINGS는 프로필마다 다르지만, Python 레벨에서 변경 불가.

---

### 2.3 ALPN 협상 우선순위

**❌ 불가능**: HTTP/2 vs HTTP/1.1 우선순위

```python
# ❌ 불가능 (BoringSSL 설정)
#
# ALPN 협상:
# Chrome: ["h2", "http/1.1"]  # HTTP/2 우선
# curl-cffi: 동일 (BoringSSL이 처리)
#
# 변경하려면 BoringSSL 재빌드
```

---

### 2.4 TLS Extension 값

**❌ 불가능**: Supported Groups, Signature Algorithms 등

```python
# ❌ 불가능
#
# Supported Groups (타원곡선):
# - X25519
# - secp256r1
# - secp384r1
#
# Signature Algorithms:
# - ecdsa_secp256r1_sha256
# - rsa_pss_rsae_sha256
# - rsa_pkcs1_sha256
#
# BoringSSL이 내부적으로 설정, Python 접근 불가
```

---

## 3. curl-cffi 내부 구조

```
Python 코드
    ↓
curl_cffi.requests.get(impersonate='chrome120')
    ↓
libcurl-impersonate (C 라이브러리)
    ↓
BoringSSL (TLS 라이브러리)
    ↓
네트워크 (실제 패킷 전송)
```

**레벨별 제어 가능 여부**:

| 레벨 | 제어 가능? | 방법 |
|------|-----------|------|
| Python (HTTP 헤더, 쿠키) | ✅ 가능 | `headers={}`, `cookies={}` |
| libcurl (프로필 선택) | ✅ 가능 | `impersonate='chrome120'` |
| libcurl (HTTP/2 SETTINGS) | ❌ 불가능 | 재빌드 필요 |
| BoringSSL (TLS) | ❌ 불가능 | 재빌드 필요 |

---

## 4. 실전 활용 전략

### 4.1 프로필 풀 운영

```python
class CurlCffiProfilePool:
    """curl-cffi 프로필 풀 관리"""

    def __init__(self):
        self.profiles = [
            'chrome110', 'chrome116', 'chrome120', 'chrome124',
            'edge99', 'edge101', 'safari15_3', 'safari15_5'
        ]
        self.current_index = 0

    def get_next_profile(self):
        """차단 시 다음 프로필로 전환"""
        profile = self.profiles[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.profiles)
        return profile

    def request_with_fallback(self, url):
        """프로필 전환 자동 재시도"""
        for _ in range(len(self.profiles)):
            profile = self.get_next_profile()

            try:
                response = requests.get(
                    url,
                    impersonate=profile,
                    timeout=10
                )

                if response.status_code == 200:
                    return response

            except Exception as e:
                continue

        raise Exception("All profiles failed")
```

---

### 4.2 쿠키 보존 프로필 전환

```python
def switch_profile_preserve_cookies(session, new_profile):
    """쿠키를 유지하면서 프로필 전환"""

    # 1. 현재 쿠키 저장
    cookies = session.cookies.get_dict()

    # 2. 새 세션 생성 (새 프로필)
    new_session = requests.Session()

    # 3. 쿠키 복원
    for name, value in cookies.items():
        new_session.cookies.set(name, value)

    # 4. 새 프로필로 요청
    response = new_session.get(
        url,
        impersonate=new_profile
    )

    return new_session, response
```

---

### 4.3 인간처럼 보이는 요청 패턴

```python
import random
import time

def human_like_request(url, profile='chrome120'):
    """인간처럼 보이는 요청 패턴"""

    # 1. 랜덤 딜레이 (1-3초)
    time.sleep(random.uniform(1.0, 3.0))

    # 2. Referer 설정 (이전 페이지)
    headers = {
        'Referer': 'https://www.coupang.com/',
        'Accept-Language': 'ko-KR,ko;q=0.9',
    }

    # 3. 요청
    response = requests.get(
        url,
        headers=headers,
        impersonate=profile,
        timeout=10
    )

    # 4. 페이지 내 리소스 일부 로딩 (선택적)
    # fetch_page_resources(response)

    return response
```

---

## 5. 최종 결론

### ✅ 현실적으로 가능한 최대 제어

1. **프로필 전환** (8개 프로필 = 8배 효율)
2. **HTTP 헤더 조작** (User-Agent, Referer, Accept 등)
3. **쿠키 관리** (세션 유지, 프로필 간 이동)
4. **타이밍 조절** (인간처럼 보이는 딜레이)
5. **Proxy 사용** (IP 분산)

### ❌ 불가능한 것들 (재빌드 필요)

1. **TLS ClientHello 수정** (Cipher, Extensions)
2. **HTTP/2 SETTINGS 변경** (Akamai Hash 직접 생성)
3. **ALPN 우선순위 조정**
4. **GREASE 값 제어**

---

## 6. 다음 단계 제안

### 즉시 테스트 가능:
1. **8개 프로필로 Coupang 테스트**
   - 각 프로필별 요청 한계 측정
   - 어떤 Akamai Hash가 통과하는지 확인

2. **프로필 풀 자동 전환 시스템 구현**
   - 차단 감지 시 자동 프로필 전환
   - 쿠키 보존하여 세션 유지

3. **인간 패턴 모방**
   - 랜덤 딜레이, Referer 체인
   - 페이지 리소스 일부 로딩

### 장기적으로 고려:
1. **libcurl-impersonate 커스텀 빌드**
   - HTTP/2 SETTINGS 값 변경
   - 완전한 Akamai Hash 제어
   - 개발 기간: 1-2주

---

**요약**: 빌드 없이는 **프로필 전환(8배 효율)**이 최대. HTTP/2 SETTINGS 직접 제어는 재빌드 필요.
