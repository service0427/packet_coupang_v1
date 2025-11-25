# TLS Profile Configuration

## 파일 위치

```
chrome-versions/tls/{platform}/{version}.json
```

- `u22`: Ubuntu 22.04
- `win11`: Windows 11

## JSON 구조

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

## curl-cffi Custom TLS 사용법

**중요**: `impersonate` 파라미터 사용 금지. 항상 DB의 custom TLS 프로파일 사용.

```python
from curl_cffi import requests

# DB에서 fingerprint 로드 후 사용
extra_fp = {
    'tls_signature_algorithms': sig_algs,  # 이름 리스트
    'tls_grease': True,
    'tls_permute_extensions': False,
    'tls_cert_compression': 'brotli',
}

headers = {
    'User-Agent': profile['user_agent'],
    'Accept': 'text/html,application/xhtml+xml,...',
    'Accept-Language': 'ko-KR,ko;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br, zstd',
    'Referer': 'https://www.coupang.com/',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Linux"',
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
    proxy=proxy,
    timeout=30
)
```

## JA3 블랙리스트 (검증됨)

| 버전 | JA3 Hash | 결과 |
|------|----------|------|
| Chrome 127 | `32796ee1a6a63426...` | ❌ BLOCKED |
| Chrome 130 | `44cc14164e512ea1...` | ❌ BLOCKED |
| Chrome 136 | `a3280c747d07805a...` | ✅ SUCCESS |

**안정적 버전**: 136, 138, 140, 142

## VERIFIED_VERSIONS

`lib/common/fingerprint.py`에서 관리:

```python
VERIFIED_VERSIONS = [136]  # 검증된 Chrome 버전
```
