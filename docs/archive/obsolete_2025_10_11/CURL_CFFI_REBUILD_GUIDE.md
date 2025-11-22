# curl-cffi 재빌드 가이드

## 결론 요약

**✅ 재빌드 가능**: libcurl-impersonate + BoringSSL 직접 컴파일
**⏱️ 예상 시간**: 1-2일 (환경 구축 포함)
**🎯 목표**: HTTP/2 SETTINGS 완전 제어 → Akamai Hash 자유롭게 생성

---

## 1. 재빌드가 해결하는 문제

### 현재 한계
```python
# ❌ 현재: 8개 프로필 = 4개 Akamai Hash만 사용 가능
profiles = ['chrome110', 'chrome116', 'chrome120', 'chrome124',
            'edge99', 'edge101', 'safari15_3', 'safari15_5']

# 4개 패턴 고정:
# Pattern A: 52d84b11737d980aef856699f885ca86
# Pattern B: a3c5e1f2b8d4...
# Pattern C: ...
# Pattern D: ...
```

### 재빌드 후
```python
# ✅ 재빌드 후: 무제한 Akamai Hash 생성 가능
def custom_http2_settings(
    header_table_size=65536,
    enable_push=0,
    max_concurrent_streams=1000,
    initial_window_size=6291456,
    max_header_list_size=262144
):
    """HTTP/2 SETTINGS 값을 자유롭게 변경"""

    # libcurl-impersonate 코드 수정:
    # nghttp2_submit_settings()에 커스텀 값 전달

    # 결과: 완전히 새로운 Akamai Hash 생성
    # Pattern X: f7e9c4a1b2d5... (독자적인 패턴)
```

---

## 2. 재빌드 아키텍처

### 컴포넌트 구조
```
curl-cffi (Python 래퍼)
    ↓
libcurl-impersonate (C 라이브러리) ← 🔧 수정 대상 1
    ↓
BoringSSL (TLS 라이브러리) ← 🔧 수정 대상 2 (선택적)
    ↓
네트워크
```

### 수정 레벨

**Level 1: HTTP/2 SETTINGS만 수정 (권장)**
- 파일: `libcurl-impersonate/lib/http2.c`
- 함수: `nghttp2_submit_settings()`
- 난이도: ⭐⭐ (중)
- 효과: Akamai Hash 완전 제어

**Level 2: TLS ClientHello도 수정 (고급)**
- 파일: `BoringSSL/ssl/handshake.cc`
- 함수: `ssl_write_client_hello()`
- 난이도: ⭐⭐⭐⭐ (고)
- 효과: JA3 Hash도 제어 가능

---

## 3. 재빌드 방법 (Step-by-Step)

### 환경 요구사항

**필수 도구**:
```bash
# Windows (WSL2 사용 권장)
- WSL2 Ubuntu 22.04
- GCC/G++ 11+
- CMake 3.20+
- Git
- Python 3.9+

# Linux (직접 빌드 가능)
- Ubuntu 22.04 / Debian 12
- GCC/G++ 11+
- CMake 3.20+
```

---

### Step 1: libcurl-impersonate 소스 받기

```bash
# 1. 저장소 클론
git clone https://github.com/lwthiker/curl-impersonate.git
cd curl-impersonate

# 2. 서브모듈 초기화 (BoringSSL 포함)
git submodule update --init --recursive

# 디렉토리 구조:
# curl-impersonate/
# ├── curl/               # libcurl 소스
# ├── boringssl/          # BoringSSL 소스
# └── chrome/             # Chrome 프로필 설정
```

---

### Step 2: HTTP/2 SETTINGS 수정 (핵심!)

**파일**: `curl-impersonate/curl/lib/http2.c`

**찾을 코드** (약 1200-1300번 줄):
```c
static CURLcode http2_submit_settings(struct Curl_easy *data,
                                       struct connectdata *conn)
{
  nghttp2_settings_entry iv[6];

  // Chrome 120 기본값
  iv[0].settings_id = NGHTTP2_SETTINGS_HEADER_TABLE_SIZE;
  iv[0].value = 65536;  // ← 수정 가능!

  iv[1].settings_id = NGHTTP2_SETTINGS_ENABLE_PUSH;
  iv[1].value = 0;      // ← 수정 가능!

  iv[2].settings_id = NGHTTP2_SETTINGS_MAX_CONCURRENT_STREAMS;
  iv[2].value = 1000;   // ← 수정 가능!

  iv[3].settings_id = NGHTTP2_SETTINGS_INITIAL_WINDOW_SIZE;
  iv[3].value = 6291456; // ← 수정 가능!

  iv[4].settings_id = NGHTTP2_SETTINGS_MAX_HEADER_LIST_SIZE;
  iv[4].value = 262144; // ← 수정 가능!

  iv[5].settings_id = NGHTTP2_SETTINGS_MAX_FRAME_SIZE;
  iv[5].value = 16384;  // ← 수정 가능!

  nghttp2_submit_settings(httpc->h2, NGHTTP2_FLAG_NONE, iv, 6);

  return CURLE_OK;
}
```

**커스텀 값으로 변경**:
```c
// 예시: 독자적인 HTTP/2 SETTINGS 패턴 생성

// Pattern X (독자 패턴 1)
iv[0].value = 32768;   // HEADER_TABLE_SIZE: 65536 → 32768
iv[1].value = 1;       // ENABLE_PUSH: 0 → 1
iv[2].value = 500;     // MAX_CONCURRENT_STREAMS: 1000 → 500
iv[3].value = 3145728; // INITIAL_WINDOW_SIZE: 6291456 → 3145728
iv[4].value = 131072;  // MAX_HEADER_LIST_SIZE: 262144 → 131072
iv[5].value = 32768;   // MAX_FRAME_SIZE: 16384 → 32768

// 결과: 완전히 새로운 Akamai Hash 생성!
// Akamai Hash = hash([32768, 1, 500, 3145728, 131072, 32768])
```

**환경변수로 동적 제어 (고급)**:
```c
// 환경변수로 런타임 변경 가능하게 수정
const char* header_table_size = getenv("HTTP2_HEADER_TABLE_SIZE");
if (header_table_size) {
  iv[0].value = atoi(header_table_size);
} else {
  iv[0].value = 65536; // 기본값
}

// Python에서 사용:
# export HTTP2_HEADER_TABLE_SIZE=32768
# export HTTP2_MAX_CONCURRENT_STREAMS=500
```

---

### Step 3: 빌드 실행

```bash
# 1. 빌드 디렉토리 생성
cd curl-impersonate
mkdir build
cd build

# 2. CMake 설정
cmake .. \
  -DCMAKE_BUILD_TYPE=Release \
  -DBUILD_SHARED_LIBS=ON

# 3. 컴파일 (약 10-30분 소요)
make -j$(nproc)

# 4. 빌드 결과 확인
ls -lh libcurl-impersonate-chrome.so
# -rwxr-xr-x 1 user user 4.2M Dec 10 12:34 libcurl-impersonate-chrome.so
```

---

### Step 4: curl-cffi Python 래퍼 빌드

```bash
# 1. curl-cffi 저장소 클론
git clone https://github.com/yifeikong/curl_cffi.git
cd curl_cffi

# 2. 커스텀 libcurl 경로 설정
export CURL_IMPERSONATE_PATH=/path/to/curl-impersonate/build

# 3. Python 패키지 빌드
pip install -e .

# 4. 설치 확인
python -c "from curl_cffi import requests; print('OK')"
```

---

### Step 5: 테스트

```python
# test_custom_akamai.py
from curl_cffi import requests

# 커스텀 빌드로 요청
response = requests.get(
    'https://tls.browserleaks.com/json',
    impersonate='chrome120'  # 내부적으로 커스텀 HTTP/2 SETTINGS 사용
)

data = response.json()

print(f"Akamai Hash: {data['akamai_hash']}")
print(f"Akamai Text: {data['akamai_text']}")

# 예상 결과:
# Akamai Hash: f7e9c4a1b2d5... (독자적인 새로운 패턴!)
# Akamai Text: 3:32768,1:1,4:500,6:3145728,5:131072,7:32768
```

---

## 4. 난이도 & 리스크 평가

### 난이도 분석

| 단계 | 난이도 | 시간 | 설명 |
|------|--------|------|------|
| 환경 구축 | ⭐⭐ | 1-2시간 | WSL2, GCC, CMake 설치 |
| 소스 다운로드 | ⭐ | 30분 | Git 클론 및 서브모듈 |
| HTTP/2 수정 | ⭐⭐ | 1-2시간 | C 코드 찾기 및 값 변경 |
| 빌드 실행 | ⭐⭐⭐ | 10-30분 | CMake 설정 및 컴파일 |
| Python 연동 | ⭐⭐ | 1시간 | curl-cffi 빌드 |
| **총 합계** | **⭐⭐** | **1-2일** | C/C++ 경험 있으면 1일 이내 |

---

### 리스크 평가

**Low Risk** ✅:
- HTTP/2 SETTINGS 값만 변경 (단순 숫자 수정)
- 컴파일 실패 시 원본 curl-cffi로 복구 가능
- 독립 환경(WSL2)에서 테스트 가능

**Medium Risk** ⚠️:
- TLS ClientHello 수정 시 (BoringSSL 코드 변경)
- 빌드 환경 문제 (의존성 충돌)
- 프로덕션 배포 시 안정성 검증 필요

**High Risk** 🚨:
- Akamai가 비정상 패턴 감지 (통계적 이상치)
- 법적 문제 (서비스 약관 위반 가능성)

---

## 5. 대안: Docker 빌드 환경

빌드 환경 구축이 복잡하면 Docker 사용:

```dockerfile
# Dockerfile
FROM ubuntu:22.04

# 빌드 도구 설치
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    python3-dev \
    python3-pip

# libcurl-impersonate 빌드
WORKDIR /build
RUN git clone https://github.com/lwthiker/curl-impersonate.git
WORKDIR /build/curl-impersonate
RUN git submodule update --init --recursive

# HTTP/2 SETTINGS 수정 (COPY로 패치 파일 적용)
COPY http2_settings.patch .
RUN patch -p1 < http2_settings.patch

# 빌드
RUN mkdir build && cd build && \
    cmake .. -DCMAKE_BUILD_TYPE=Release && \
    make -j$(nproc)

# curl-cffi 빌드
WORKDIR /app
RUN git clone https://github.com/yifeikong/curl_cffi.git
WORKDIR /app/curl_cffi
ENV CURL_IMPERSONATE_PATH=/build/curl-impersonate/build
RUN pip install -e .

CMD ["/bin/bash"]
```

```bash
# 빌드 실행
docker build -t curl-cffi-custom .

# 테스트
docker run -it curl-cffi-custom python3 test_custom_akamai.py
```

---

## 6. 실전 활용 전략

### 6.1 무제한 Akamai Hash 생성

```python
# custom_akamai_generator.py
import random
import subprocess
import json

def generate_random_http2_settings():
    """랜덤 HTTP/2 SETTINGS 생성"""

    settings = {
        'HEADER_TABLE_SIZE': random.choice([16384, 32768, 65536]),
        'ENABLE_PUSH': random.choice([0, 1]),
        'MAX_CONCURRENT_STREAMS': random.choice([100, 500, 1000]),
        'INITIAL_WINDOW_SIZE': random.choice([1048576, 3145728, 6291456]),
        'MAX_HEADER_LIST_SIZE': random.choice([65536, 131072, 262144]),
        'MAX_FRAME_SIZE': random.choice([16384, 32768]),
    }

    return settings

# 1. 랜덤 설정 생성
settings = generate_random_http2_settings()

# 2. C 코드 자동 패치
patch_http2_settings(settings)

# 3. 재빌드
subprocess.run(['make', '-C', 'build'])

# 4. 테스트
from curl_cffi import requests
response = requests.get('https://tls.browserleaks.com/json')
akamai_hash = response.json()['akamai_hash']

print(f"New Akamai Hash: {akamai_hash}")
# 매번 다른 해시 생성 가능!
```

---

### 6.2 Akamai Hash Pool 자동 생성

```bash
# build_akamai_pool.sh

# 100개의 다른 Akamai Hash 생성
for i in {1..100}; do
    # 랜덤 HTTP/2 SETTINGS 생성
    python3 generate_random_settings.py > settings_$i.json

    # C 코드 패치
    python3 patch_http2.py settings_$i.json

    # 빌드
    make -C build

    # libcurl 저장 (버전별 보관)
    cp build/libcurl-impersonate-chrome.so \
       pool/libcurl_akamai_$i.so

    # Akamai Hash 추출
    python3 extract_akamai.py >> akamai_pool.txt
done

# 결과: 100개 Akamai Hash pool
# - pool/libcurl_akamai_1.so → Hash: abc123...
# - pool/libcurl_akamai_2.so → Hash: def456...
# - ...
```

---

### 6.3 동적 라이브러리 전환 (런타임)

```python
import ctypes
import os

class DynamicAkamaiLoader:
    """런타임에 libcurl 전환하여 Akamai Hash 변경"""

    def __init__(self, pool_dir='pool/'):
        self.pool_dir = pool_dir
        self.libraries = self._load_pool()

    def _load_pool(self):
        """100개 libcurl 라이브러리 로드"""
        libs = []
        for i in range(1, 101):
            lib_path = f"{self.pool_dir}/libcurl_akamai_{i}.so"
            libs.append(lib_path)
        return libs

    def request_with_random_akamai(self, url):
        """랜덤 Akamai Hash로 요청"""

        # 랜덤 라이브러리 선택
        lib_path = random.choice(self.libraries)

        # 환경변수로 libcurl 경로 지정
        os.environ['CURL_IMPERSONATE_LIB'] = lib_path

        # 요청 (자동으로 새 libcurl 사용)
        from curl_cffi import requests
        response = requests.get(url, impersonate='chrome120')

        return response
```

---

## 7. 최종 판단

### ✅ 재빌드를 추천하는 경우

1. **Akamai Hash 제어가 필수적인 경우**
   - 8개 프로필로 부족함
   - 무제한 패턴 생성 필요

2. **장기 프로젝트**
   - 1-2일 투자 가치 있음
   - 지속적인 우회 필요

3. **C/C++ 경험이 있는 경우**
   - 빌드 과정이 익숙함
   - 문제 발생 시 디버깅 가능

---

### ❌ 재빌드를 보류하는 경우

1. **8개 프로필로 충분한 경우**
   - IP당 1200회면 충분
   - 단기 테스트만 필요

2. **C/C++ 경험이 없는 경우**
   - 빌드 환경 구축 어려움
   - 트러블슈팅 시간 예측 불가

3. **법적 리스크 회피**
   - 서비스 약관 위반 우려
   - 안전한 방법 선호

---

## 8. 다음 단계 제안

### 단계 1: 8개 프로필 먼저 테스트 (현재 방식)
```bash
# 재빌드 전에 기존 방식으로 효과 측정
python3 hybrid_tls_extractor.py

# Coupang 실제 테스트
# - 각 프로필별 요청 한계 확인
# - 어떤 Akamai Hash가 차단되는지 파악
```

**예상 결과**:
- 8개 프로필 × 150회 = 1200회/IP
- 효율적이라면 재빌드 불필요

---

### 단계 2: 필요 시 재빌드 진행
```bash
# 8개 프로필로 부족하다면:

# 1. WSL2 환경 구축 (1시간)
# 2. libcurl-impersonate 빌드 (2시간)
# 3. HTTP/2 SETTINGS 수정 (1시간)
# 4. curl-cffi 연동 (1시간)
# 5. 테스트 및 검증 (2시간)

# 총 1-2일 투자
```

---

## 9. 결론

**재빌드는 가능하며, 난이도는 중간 수준 (⭐⭐)**

**효과**:
- ✅ HTTP/2 SETTINGS 완전 제어
- ✅ 무제한 Akamai Hash 생성
- ✅ 100개 이상 패턴 Pool 구축 가능

**추천 순서**:
1. 먼저 8개 프로필로 테스트 (현재 방식)
2. 부족하면 재빌드 진행 (1-2일 투자)
3. 100개 Akamai Hash Pool 구축 (장기 운영)

재빌드를 진행하시겠습니까? 환경 구축부터 단계별로 도와드릴 수 있습니다!
