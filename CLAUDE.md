# CLAUDE.md

Claude Code 가이드 문서 - Coupang Akamai Bypass System

## sudo
Tech1324!

## Project Overview

Coupang Akamai Bypass System - curl-cffi를 사용한 TLS 핑거프린트 매칭 기반 Akamai 우회

**Core Approach**: Browser → Cookie 생성 → curl-cffi Packet Mode로 요청

## 주요 명령어

```bash
# 초기 셋업 (Chrome 다운로드 + TLS 수집)
./setup.sh

# 쿠키 생성 (브라우저)
node coupang-test.js browser 136

# curl-cffi 테스트
node coupang-test.js test 136 "노트북"

# TLS 프로파일 수집
node extract-tls-profiles.js
```

## Akamai 우회 핵심 조건 (2025-11-22 검증)

### 필수 요소

| 요소 | 필수 | 설명 |
|------|------|------|
| **Chrome 131+ JA3** | ✅ | 구버전 JA3 블랙리스트 (127-130 차단) |
| **Akamai 핑거프린트** | ✅ | HTTP/2 SETTINGS 매칭 |
| **extra_fp** | ✅ | signature_algorithms, tls_grease, tls_cert_compression |
| **sec-ch-ua 헤더** | ✅ | Client Hints 필수 |
| **신선한 쿠키** | ✅ | sensor_data 포함 |
| **IP 바인딩** | ✅ | 쿠키 생성 IP = 요청 IP |

### JA3 블랙리스트 (검증됨)

| 버전 | JA3 Hash | 결과 |
|------|----------|------|
| Chrome 127 | `32796ee1a6a63426...` | ❌ BLOCKED |
| Chrome 130 | `44cc14164e512ea1...` | ❌ BLOCKED |
| Chrome 136 | `a3280c747d07805a...` | ✅ SUCCESS |

**안정적 버전**: 136, 138, 140, 142

### curl-cffi 커스텀 TLS 사용법

```python
from curl_cffi import requests

# TLS 프로파일 로드
extra_fp = {
    'tls_signature_algorithms': sig_algs,  # 이름 리스트
    'tls_grease': True,
    'tls_permute_extensions': False,
    'tls_cert_compression': 'brotli',
}

# 필수 헤더
headers = {
    'User-Agent': profile['user_agent'],
    'Accept': 'text/html,application/xhtml+xml,...',
    'Accept-Language': 'ko-KR,ko;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br, zstd',
    'Referer': 'https://www.coupang.com/',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'document',
    'sec-fetch-mode': 'navigate',
    'sec-fetch-site': 'same-origin',
    'sec-fetch-user': '?1',
    'upgrade-insecure-requests': '1',
}

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

### impersonate 사용 금지

```python
# FORBIDDEN - JA3가 실제 브라우저와 다름
response = requests.get(url, impersonate='chrome136')

# CORRECT - 직접 JA3/Akamai 지정
response = requests.get(url, ja3=ja3_text, akamai=akamai_text, extra_fp=extra_fp)
```

## IP 바인딩 정책

- 쿠키 생성 IP ≠ 요청 IP → 차단
- 프록시 사용 시: 브라우저와 curl-cffi 모두 동일 프록시 사용
- 다중 IP 사용 시: IP별 쿠키 별도 관리

## Rate Limit

- ~150회/IP/일
- 요청 간 2-3초 딜레이 권장
- 연속 요청 시 IP 임시 차단 (30초~수분 후 복구)

## 디렉토리 구조

```
├── coupang-test.js             # 메인 CLI
├── lib/
│   ├── browser/
│   │   └── browser-launcher.js # 브라우저 실행기
│   ├── curl_cffi_client.py     # Python HTTP 클라이언트
│   └── tls_rotator.py          # TLS 로테이션
├── cookies/                    # 쿠키 저장
├── chrome-versions/
│   ├── files/                  # Chrome 실행 파일
│   └── tls/                    # TLS 프로파일 (*.json)
└── docs/                       # 문서
```

## TLS 프로파일

위치: `chrome-versions/tls/{version}.json`

```json
{
  "ja3_text": "771,4865-4866-...",
  "ja3_hash": "a3280c747d07805a...",
  "akamai_text": "1:65536;2:0;...",
  "akamai_hash": "52d84b11737d980a...",
  "user_agent": "Mozilla/5.0...",
  "tls": {
    "extensions": [
      {
        "name": "signature_algorithms",
        "data": {
          "supported_signature_algorithms": [
            {"name": "ecdsa_secp256r1_sha256", "id": 1027}
          ]
        }
      }
    ]
  }
}
```

## Success Criteria

- Response size > 50,000 bytes = SUCCESS
- Response size ≤ 50,000 bytes = BLOCKED

## 문서

- `docs/IP_BINDING_TEST_RESULTS.md`: IP 바인딩 및 TLS 로테이션 테스트
- `docs/CURL_CFFI_TEST_RESULTS.md`: curl-cffi 커스텀 TLS 테스트 결과
