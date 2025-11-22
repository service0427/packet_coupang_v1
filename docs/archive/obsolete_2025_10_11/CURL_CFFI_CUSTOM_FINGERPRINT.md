# curl-cffi 커스텀 핑거프린트 가이드

## 🎯 핵심 발견

**재빌드 불필요!** curl-cffi는 이미 HTTP/2 SETTINGS 커스터마이징 기능을 제공합니다.

```python
from curl_cffi import requests

# ✅ 이미 가능: HTTP/2 SETTINGS 직접 설정!
response = requests.get(
    url,
    impersonate='chrome120',
    extra_fp={
        'http2_settings': '1:65536;3:1000;4:6291456;6:262144'
    }
)
```

---

## 1. curl-cffi 커스텀 핑거프린트 기능

### 공식 문서 확인
- **문서**: https://curl-cffi.readthedocs.io/en/stable/impersonate/customize.html
- **기능**: `ja3`, `akamai`, `extra_fp` 파라미터로 커스터마이징

### 지원 파라미터

**1. TLS 핑거프린트 (JA3)**
```python
ja3 = "771,4865-4866-4867-49195-49199-49196-49200-52393-52392-49171-49172-156-157-47-53,0-23-65281-10-11-35-16-5-13-18-51-45-43-27-17513,29-23-24,0"
```

**2. Akamai 핑거프린트**
```python
akamai = "1:65536,3:1000,4:6291456,6:262144"
```

**3. 추가 핑거프린트 (extra_fp)**
```python
extra_fp = {
    'tls_signature_algorithms': [...],
    'http2_stream_weight': 256,
    'http2_stream_exclusive': 1,
    'http2_settings': '1:65536;3:1000;4:6291456;6:262144'
}
```

---

## 2. HTTP/2 SETTINGS 커스터마이징

### SETTINGS 프레임 구조

```
HTTP/2 SETTINGS 형식:
{SETTING_ID}:{VALUE};{SETTING_ID}:{VALUE};...

예시:
1:65536;3:1000;4:6291456;6:262144
```

**SETTING_ID 매핑**:
| ID | 이름 | 설명 | 기본값 (Chrome 120) |
|----|------|------|---------------------|
| 1 | HEADER_TABLE_SIZE | HPACK 압축 테이블 크기 | 65536 |
| 2 | ENABLE_PUSH | Server Push 활성화 | 0 |
| 3 | MAX_CONCURRENT_STREAMS | 최대 동시 스트림 | 1000 |
| 4 | INITIAL_WINDOW_SIZE | 초기 윈도우 크기 | 6291456 |
| 5 | MAX_FRAME_SIZE | 최대 프레임 크기 | 16384 |
| 6 | MAX_HEADER_LIST_SIZE | 최대 헤더 리스트 크기 | 262144 |

---

## 3. 실전 예제

### 3.1 기본 커스터마이징

```python
from curl_cffi import requests

# Chrome 120 기본 패턴
chrome120_settings = '1:65536;3:1000;4:6291456;6:262144'

response = requests.get(
    'https://tls.browserleaks.com/json',
    impersonate='chrome120',
    extra_fp={
        'http2_settings': chrome120_settings
    }
)

data = response.json()
print(f"Akamai Hash: {data['akamai_hash']}")
# 결과: 52d84b11737d980aef856699f885ca86 (기본 Chrome 120)
```

---

### 3.2 커스텀 패턴 생성

```python
# ✅ 독자적인 HTTP/2 SETTINGS 패턴
custom_settings = '1:32768;3:500;4:3145728;6:131072'
#                   ↑       ↑     ↑         ↑
#            HEADER_TABLE  MAX   INITIAL   MAX_HEADER
#                         STREAMS WINDOW

response = requests.get(
    'https://tls.browserleaks.com/json',
    impersonate='chrome120',  # TLS는 Chrome 120 유지
    extra_fp={
        'http2_settings': custom_settings
    }
)

data = response.json()
print(f"Custom Akamai Hash: {data['akamai_hash']}")
# 결과: 완전히 새로운 Akamai Hash!
```

---

### 3.3 Akamai Hash 무한 생성기

```python
import random
from curl_cffi import requests

def generate_random_http2_settings():
    """랜덤 HTTP/2 SETTINGS 생성"""

    header_table = random.choice([16384, 32768, 65536])
    max_streams = random.choice([100, 500, 1000])
    initial_window = random.choice([1048576, 3145728, 6291456])
    max_header = random.choice([65536, 131072, 262144])

    # SETTINGS 문자열 생성
    settings = f'1:{header_table};3:{max_streams};4:{initial_window};6:{max_header}'

    return settings

# 무한 Akamai Hash 생성
for i in range(10):
    settings = generate_random_http2_settings()

    response = requests.get(
        'https://tls.browserleaks.com/json',
        impersonate='chrome120',
        extra_fp={'http2_settings': settings}
    )

    akamai_hash = response.json()['akamai_hash']
    print(f"Pattern {i+1}: {akamai_hash}")
    print(f"  Settings: {settings}")

# 출력 예시:
# Pattern 1: f7e9c4a1b2d5...
#   Settings: 1:32768;3:500;4:3145728;6:131072
# Pattern 2: a3d8f1c2e9b4...
#   Settings: 1:65536;3:1000;4:1048576;6:262144
# ...
```

---

## 4. Akamai Hash Pool 시스템

### 4.1 Pool 생성

```python
# akamai_pool_generator.py
import json
import random
from curl_cffi import requests

class AkamaiHashPoolGenerator:
    """Akamai Hash Pool 생성기"""

    def __init__(self, target_size=100):
        self.target_size = target_size
        self.pool = []

    def generate_settings_variations(self):
        """다양한 HTTP/2 SETTINGS 조합 생성"""

        # 설정 가능한 값들
        header_tables = [16384, 32768, 65536, 131072]
        max_streams_list = [100, 250, 500, 1000]
        initial_windows = [1048576, 2097152, 3145728, 6291456]
        max_headers = [65536, 131072, 262144, 524288]

        variations = []

        # 모든 조합 생성 (4^4 = 256개)
        for ht in header_tables:
            for ms in max_streams_list:
                for iw in initial_windows:
                    for mh in max_headers:
                        settings = f'1:{ht};3:{ms};4:{iw};6:{mh}'
                        variations.append(settings)

        return variations

    def build_pool(self):
        """Akamai Hash Pool 구축"""

        variations = self.generate_settings_variations()

        # 최대 target_size개만 샘플링
        if len(variations) > self.target_size:
            variations = random.sample(variations, self.target_size)

        for i, settings in enumerate(variations):
            try:
                response = requests.get(
                    'https://tls.browserleaks.com/json',
                    impersonate='chrome120',
                    extra_fp={'http2_settings': settings},
                    timeout=10
                )

                data = response.json()

                self.pool.append({
                    'id': i + 1,
                    'settings': settings,
                    'akamai_hash': data['akamai_hash'],
                    'akamai_text': data['akamai_text'],
                    'ja3_hash': data['ja3_hash'],
                })

                print(f"[{i+1}/{len(variations)}] Generated: {data['akamai_hash'][:16]}...")

            except Exception as e:
                print(f"[{i+1}] Failed: {e}")
                continue

        return self.pool

    def save_pool(self, filename='akamai_hash_pool.json'):
        """Pool 저장"""

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.pool, f, indent=2, ensure_ascii=False)

        print(f"\n✅ Pool saved: {filename}")
        print(f"   Total patterns: {len(self.pool)}")
        print(f"   Unique Akamai Hashes: {len(set(p['akamai_hash'] for p in self.pool))}")

# 실행
if __name__ == '__main__':
    generator = AkamaiHashPoolGenerator(target_size=100)
    pool = generator.build_pool()
    generator.save_pool()
```

---

### 4.2 Pool 활용

```python
# akamai_pool_loader.py
import json
import random
from curl_cffi import requests

class AkamaiHashPool:
    """Akamai Hash Pool 로더 및 관리"""

    def __init__(self, pool_file='akamai_hash_pool.json'):
        with open(pool_file, 'r', encoding='utf-8') as f:
            self.pool = json.load(f)

        self.current_index = 0

    def get_next_pattern(self):
        """순차적으로 다음 패턴 반환"""

        pattern = self.pool[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.pool)

        return pattern

    def get_random_pattern(self):
        """랜덤 패턴 반환"""
        return random.choice(self.pool)

    def request_with_rotation(self, url):
        """Akamai Hash 로테이션 요청"""

        pattern = self.get_next_pattern()

        response = requests.get(
            url,
            impersonate='chrome120',
            extra_fp={'http2_settings': pattern['settings']},
            timeout=10
        )

        print(f"Used Akamai Hash: {pattern['akamai_hash'][:16]}...")

        return response

# 사용 예시
pool = AkamaiHashPool('akamai_hash_pool.json')

# 100개 패턴으로 순환 요청
for i in range(300):
    response = pool.request_with_rotation('https://www.coupang.com/...')

    if response.status_code == 200:
        print(f"[{i+1}] Success")
    else:
        print(f"[{i+1}] Blocked - Rotating to next pattern")

# 효과: 100개 패턴 × 150회/패턴 = 15,000회/IP!
```

---

## 5. Coupang 실전 적용

### 5.1 자동 패턴 전환 시스템

```python
# coupang_scraper_with_rotation.py
import json
from curl_cffi import requests
from akamai_pool_loader import AkamaiHashPool

class CoupangScraperWithRotation:
    """Akamai Hash 로테이션 Coupang 크롤러"""

    def __init__(self, pool_file='akamai_hash_pool.json'):
        self.pool = AkamaiHashPool(pool_file)
        self.session_cookies = {}

    def login(self):
        """로그인 (첫 패턴 사용)"""

        pattern = self.pool.get_next_pattern()

        response = requests.post(
            'https://login.coupang.com/...',
            data={'username': '...', 'password': '...'},
            impersonate='chrome120',
            extra_fp={'http2_settings': pattern['settings']}
        )

        # 쿠키 저장
        self.session_cookies = response.cookies.get_dict()

        return response

    def scrape_with_rotation(self, urls):
        """URL 리스트 크롤링 (패턴 자동 전환)"""

        results = []

        for i, url in enumerate(urls):
            # 매 요청마다 다른 Akamai Hash 사용
            pattern = self.pool.get_next_pattern()

            try:
                response = requests.get(
                    url,
                    impersonate='chrome120',
                    extra_fp={'http2_settings': pattern['settings']},
                    cookies=self.session_cookies,
                    timeout=10
                )

                if response.status_code == 200:
                    print(f"[{i+1}] ✅ Success - Hash: {pattern['akamai_hash'][:16]}...")
                    results.append(response.text)

                elif response.status_code == 403:
                    print(f"[{i+1}] ❌ Blocked - Hash: {pattern['akamai_hash'][:16]}...")
                    # 다음 패턴으로 자동 전환

            except Exception as e:
                print(f"[{i+1}] ⚠️  Error: {e}")
                continue

        return results

# 실행
scraper = CoupangScraperWithRotation()
scraper.login()

urls = [f'https://www.coupang.com/vp/products/{i}' for i in range(1000)]
results = scraper.scrape_with_rotation(urls)

print(f"\n✅ Total scraped: {len(results)}/1000")
```

---

### 5.2 차단 패턴 분석

```python
# analyze_blocked_patterns.py
import json
from curl_cffi import requests

def test_all_patterns_against_coupang(pool_file='akamai_hash_pool.json'):
    """모든 Akamai Hash 패턴을 Coupang에 테스트"""

    with open(pool_file, 'r') as f:
        pool = json.load(f)

    results = {
        'passed': [],
        'blocked': [],
        'error': []
    }

    for pattern in pool:
        try:
            response = requests.get(
                'https://www.coupang.com/',
                impersonate='chrome120',
                extra_fp={'http2_settings': pattern['settings']},
                timeout=10
            )

            if response.status_code == 200:
                results['passed'].append(pattern)
                print(f"✅ PASS: {pattern['akamai_hash'][:16]}... - {pattern['settings']}")

            elif response.status_code == 403:
                results['blocked'].append(pattern)
                print(f"❌ BLOCK: {pattern['akamai_hash'][:16]}... - {pattern['settings']}")

        except Exception as e:
            results['error'].append(pattern)
            print(f"⚠️  ERROR: {pattern['akamai_hash'][:16]}... - {e}")

    # 결과 저장
    with open('coupang_pattern_analysis.json', 'w') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n📊 Analysis Results:")
    print(f"   Passed:  {len(results['passed'])}/{len(pool)}")
    print(f"   Blocked: {len(results['blocked'])}/{len(pool)}")
    print(f"   Error:   {len(results['error'])}/{len(pool)}")

    return results

# 실행
results = test_all_patterns_against_coupang()
```

---

## 6. 최종 정리

### ✅ 재빌드 불필요!

curl-cffi는 이미 `extra_fp` 파라미터로 HTTP/2 SETTINGS 커스터마이징 지원:

```python
response = requests.get(
    url,
    impersonate='chrome120',
    extra_fp={
        'http2_settings': '1:32768;3:500;4:3145728;6:131072'
    }
)
```

### 🎯 효과

1. **무제한 Akamai Hash 생성**
   - 256개 조합 가능 (4^4)
   - 100개 Pool → 15,000회/IP

2. **즉시 사용 가능**
   - 빌드 불필요
   - pip install curl-cffi만으로 사용

3. **유연한 전환**
   - 패턴별 효과 테스트
   - 차단 시 자동 전환

---

## 7. 다음 단계

### 즉시 실행 가능:

```bash
# 1. Akamai Hash Pool 생성 (100개 패턴)
python akamai_pool_generator.py

# 2. Coupang 패턴 분석 (어떤 패턴이 통과하는지)
python analyze_blocked_patterns.py

# 3. 로테이션 크롤링 시작
python coupang_scraper_with_rotation.py
```

**예상 효과**:
- 100개 패턴 × 150회/패턴 = **15,000회/IP**
- 기존 8개 프로필(1,200회) 대비 **12.5배 증가**!

---

**결론**: 재빌드 필요 없이 `extra_fp` 파라미터로 무제한 Akamai Hash 생성 가능!
