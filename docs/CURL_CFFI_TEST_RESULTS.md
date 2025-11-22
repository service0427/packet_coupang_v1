# curl-cffi 커스텀 TLS 테스트 결과

## 테스트 일시
2025-11-22

## 핵심 결론

### JA3 블랙리스트 확정

Akamai는 JA3 해시로 Chrome 버전을 식별하고 구버전(127-130)을 차단합니다.

| 버전 | JA3 Hash | 결과 |
|------|----------|------|
| **Chrome 127** | `32796ee1a6a63426eee3f2e9a52768be` | ❌ BLOCKED (383 bytes) |
| **Chrome 130** | `44cc14164e512ea1236aa79286bc249a` | ❌ BLOCKED |
| **Chrome 136** | `a3280c747d07805a510516a46e4a9b63` | ✅ SUCCESS (1,342,661 bytes) |

### impersonate vs 커스텀 TLS

**impersonate JA3 ≠ 실제 브라우저 JA3**

| 방식 | Chrome 136 JA3 |
|------|----------------|
| impersonate | `c0d6045aedf807b16aa29675b4beb175` |
| 실제 브라우저 | `a3280c747d07805a510516a46e4a9b63` |

→ Extensions 순서가 다름. **impersonate 사용 금지**

## 커스텀 TLS 필수 요소

### 1. TLS 매개변수

```python
extra_fp = {
    'tls_signature_algorithms': [
        'ecdsa_secp256r1_sha256',
        'rsa_pss_rsae_sha256',
        'rsa_pkcs1_sha256',
        # ... 전체 리스트는 TLS 프로파일에서 추출
    ],
    'tls_grease': True,
    'tls_permute_extensions': False,
    'tls_cert_compression': 'brotli',
}
```

### 2. 필수 헤더

```python
headers = {
    'User-Agent': profile['user_agent'],
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'ko-KR,ko;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br, zstd',
    'Referer': 'https://www.coupang.com/',
    'sec-ch-ua-mobile': '?0',           # 필수
    'sec-ch-ua-platform': '"Windows"',  # 필수
    'sec-fetch-dest': 'document',
    'sec-fetch-mode': 'navigate',
    'sec-fetch-site': 'same-origin',
    'sec-fetch-user': '?1',
    'upgrade-insecure-requests': '1',
}
```

**주의**: `sec-ch-ua-*` 헤더 없으면 차단됨

### 3. 요청 예시

```python
from curl_cffi import requests

response = requests.get(
    url,
    headers=headers,
    cookies=cookies,
    ja3=ja3_text,
    akamai=akamai_text,
    extra_fp=extra_fp,
    timeout=30
)
```

## TLS 프로파일에서 signature_algorithms 추출

```python
def extract_signature_algorithms_names(profile: dict) -> list:
    tls = profile.get('tls', {})
    extensions = tls.get('extensions', [])

    for ext in extensions:
        if ext.get('name') == 'signature_algorithms':
            data = ext.get('data', {})
            algs = data.get('supported_signature_algorithms', [])
            return [a['name'] for a in algs]
    return []
```

**주의**: ID 숫자가 아닌 **이름 문자열** 사용

## Rate Limit 테스트

### 관찰된 동작

1. 연속 요청 시 IP 임시 차단 (모든 버전 차단)
2. 30초~1분 대기 후 복구
3. 반복 차단 시 장기 블랙리스트 위험

### 권장 설정

- 요청 간 딜레이: 2-3초
- IP당 일일 한도: ~150회
- 버전 로테이션으로 부하 분산

## 버전 다양화 전략

단일 버전으로 수백만 트래픽 → 패턴 학습 및 차단 위험

### 권장 버전 풀

**안정적으로 확인된 버전** (IP_BINDING_TEST_RESULTS.md 기준):
- Chrome 136, 138, 140, 142

**추가 테스트 필요**:
- Chrome 131, 132, 133, 134, 135, 137, 139, 141, 143, 144

### 로테이션 전략

```python
from lib.tls_rotator import TLSRotator

rotator = TLSRotator(base_dir, strategy="round_robin")
profile, headers = rotator.get_pc_profile()
```

## 테스트 환경

- curl-cffi: 0.14.0b4
- Python: 3.13
- OS: Windows
- 테스트 URL: `https://www.coupang.com/np/search?q=notebook&channel=user&page=1`

## 관련 파일

### 테스트 스크립트
- `test-custom-127-vs-136.py`: 버전 비교 테스트
- `test-full-custom-tls.py`: 완전 커스텀 TLS 테스트
- `test-ja3-comparison-detail.py`: JA3 비교 분석

### 핵심 라이브러리
- `coupang-test.js`: 메인 CLI
- `lib/curl_cffi_client.py`: Python HTTP 클라이언트
- `lib/tls_rotator.py`: TLS 로테이션 시스템

### TLS 프로파일
- `chrome-versions/tls/{version}.json`: 23개 버전 프로파일

## 명령어 예시

```bash
# 쿠키 생성
npm run coupang browser 136

# 테스트 실행
npm run coupang test 136 "노트북"

# 직접 Python 테스트
python test-custom-127-vs-136.py
```
