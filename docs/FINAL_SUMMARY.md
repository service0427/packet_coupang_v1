# Coupang Akamai Bypass System - 최종 정리

## 프로젝트 개요

curl-cffi를 사용한 TLS 핑거프린트 매칭 기반 Akamai 우회 시스템

**핵심 접근법**: Browser → Cookie 생성 → curl-cffi Packet Mode로 요청

---

## 검증된 핵심 요구사항

### 필수 요소 (2025-11-22 검증)

| 요소 | 필수 | 설명 |
|------|------|------|
| **Chrome 131+ JA3** | ✅ | 구버전 JA3 블랙리스트 (127-130 차단) |
| **Akamai 핑거프린트** | ✅ | HTTP/2 SETTINGS 매칭 |
| **extra_fp** | ✅ | signature_algorithms, tls_grease, tls_cert_compression |
| **sec-ch-ua 헤더** | ✅ | Client Hints 필수 |
| **신선한 쿠키** | ✅ | sensor_data 포함 |
| **IP 바인딩** | ✅ | 쿠키 생성 IP = 요청 IP |

### JA3 블랙리스트 (검증됨)

| 버전 | 결과 | 비고 |
|------|------|------|
| Chrome 127-130 | ❌ BLOCKED | JA3 블랙리스트 |
| Chrome 136+ | ✅ SUCCESS | 안정적 |

**권장 버전**: 136, 138, 140, 142

---

## 성능 지표

### 쿠키 생성

| 항목 | 값 |
|------|-----|
| 트래픽 | ~950 KB/쿠키 |
| 요청 수 | 7-9개 |
| 로드 시간 | 5-6초 |
| Akamai 쿠키 | 4개 (_abck, ak_bmsc, bm_s, bm_sz) |

### Rate Limit

| 항목 | 값 |
|------|-----|
| 검색 요청 | ~150회/IP/일 |
| 쿠키 생성 | 제한 없음 (테스트 범위 내) |
| 요청 간격 | 2-3초 권장 |

### 검증된 사실

- **쿠키 재발급만으로는 차단되지 않음** (10회 연속 테스트 성공)
- 제한은 실제 검색 요청 횟수에만 적용

---

## 주요 명령어

### 쿠키 생성

```bash
# 단일 쿠키 생성 (브라우저)
npm run coupang browser 136

# 배치 쿠키 생성
node lib/cookie-batch.js [개수] [버전] [프록시]
node lib/cookie-batch.js 10 136

# 배치 생성 + cffi 테스트
node lib/cookie-batch.js 10 136 --test
```

### curl-cffi 테스트

```bash
# 단일 테스트
npm run coupang test 136 "노트북"

# 검증
npm run verify 136 "검색어"
```

---

## 디렉토리 구조

```
local-packet-coupang/
├── coupang-test.js             # 메인 CLI
├── verify-cookie.js            # 쿠키 검증
├── lib/
│   ├── browser/
│   │   └── browser-launcher.js # 브라우저 실행기
│   ├── cookie-batch.js         # 배치 쿠키 생성기 ⭐
│   ├── cookie-ultralight.js    # 초경량 쿠키 생성기
│   ├── cookie-refresh.js       # 쿠키 리프레시 (미사용)
│   ├── curl_cffi_client.py     # Python HTTP 클라이언트
│   └── tls_rotator.py          # TLS 로테이션
├── cookies/                    # 쿠키 저장
│   └── chrome{version}_cookies.json
├── chrome-versions/
│   ├── files/                  # Chrome 실행 파일
│   │   └── chrome-{version}/chrome-win64/chrome.exe
│   └── tls/                    # TLS 프로파일
│       └── {version}.json
└── docs/                       # 문서
```

---

## curl-cffi 사용법

### 필수 코드

```python
from curl_cffi import requests

# TLS 프로파일에서 로드
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

### 금지 사항

```python
# FORBIDDEN - JA3가 실제 브라우저와 다름
response = requests.get(url, impersonate='chrome136')

# CORRECT - 직접 JA3/Akamai 지정
response = requests.get(url, ja3=ja3_text, akamai=akamai_text, extra_fp=extra_fp)
```

---

## 리눅스 이전 시 고려사항

### 파일 경로 변경

```javascript
// Windows
const chromePath = path.join(CHROME_VERSIONS_DIR, dir, 'chrome-win64', 'chrome.exe');

// Linux
const chromePath = path.join(CHROME_VERSIONS_DIR, dir, 'chrome-linux64', 'chrome');
```

### Chrome 설치

```bash
# Chrome for Testing (Linux)
npx @playwright/test install chromium
# 또는 직접 다운로드
```

### 의존성

```bash
# Node.js
npm install

# Python
pip install curl-cffi
```

---

## Producer/Consumer 아키텍처 설계

### 분리 아키텍처

```
[쿠키 생성기]              [쿠키 저장소]              [cffi 소비자]
Producer                   cookies/                   Consumer
    │                          │                          │
    └──→ 쿠키 생성 ──→ *.json ←── 쿠키 읽기 ←──┘
```

### 파일명 규칙

```
{ip}_{port}_{version}_{timestamp}.json

예: 203.45.67.89_1080_136_1732250400.json
```

### Producer 로직

```javascript
// 프록시별 쿠키 생성
for (proxy of proxies) {
  browser = launch(proxy, version)

  for (i = 0; i < cookiesPerProxy; i++) {
    clearCookies()
    reload()
    saveCookie(`${ip}_${port}_${version}_${timestamp}.json`)
  }

  browser.close()
}
```

### Consumer 로직

```javascript
// 쿠키 소비
for (file of glob('cookies/*.json')) {
  const { ip, port, version } = parseFilename(file)
  const proxy = `socks5://${ip}:${port}`

  // cffi 요청 (같은 프록시 사용)
  const result = await cffiRequest(file, version, proxy)

  // 사용 완료 마킹
  fs.renameSync(file, file.replace('.json', '.used'))
}
```

### 프록시 환경

- API: `http://mkt.techb.kr:3001/api/proxy/status?remain=120`
- 유효 시간: ~8분
- 동시 활성: 10-20개
- 최소 잔여: 120초 이상만 사용

---

## 경량화 필터 설정

### 허용 패턴 (최소)

```javascript
ALLOWED_PATTERNS = [
  '/login/login.pang',  // 메인 document
  '/wmwK3qQug',         // Akamai sensor_data 스크립트
  '/akam/',             // Akamai 픽셀/검증
]
```

### 차단 패턴

```javascript
BLOCKED_PATTERNS = [
  'qrcode', 'login.min.js', 'coupangcdn.com',
  'analytics', 'tracking', 'google', 'facebook'
]
```

### 결과

- 33개 요청 → 7-9개
- ~85% 차단율
- ~950 KB/쿠키

---

## Success Criteria

- Response size > 50,000 bytes = SUCCESS
- Response size ≤ 50,000 bytes = BLOCKED

---

## 테스트 결과 요약

### 배치 쿠키 생성 테스트 (10개)

| 항목 | 결과 |
|------|------|
| 쿠키 생성 | 10/10 성공 |
| cffi 테스트 | 10/10 성공 (30회 요청 모두 성공) |
| 총 트래픽 | 9,852 KB |
| 평균 트래픽 | 985 KB/쿠키 |
| 고유 _abck | 10/10 (모두 다름) |

### 주요 발견

1. **쿠키 재발급은 차단되지 않음** - 연속 10회 생성 성공
2. **모든 쿠키가 유효** - cffi 테스트 100% 성공
3. **Rate Limit는 검색 요청에만 적용**

---

## 다음 단계 (리눅스 이전)

1. **cookie-factory.js** 구현 - Producer 프로세스
2. **cookie-consumer.py** 구현 - Consumer 프로세스
3. **프록시 API 연동** - 자동 프록시 조회
4. **상태 관리** - Redis 또는 파일 기반
5. **모니터링** - 성공률, 트래픽, 에러 추적

---

## 문서 목록

- `CLAUDE.md` - 프로젝트 가이드
- `docs/FINAL_SUMMARY.md` - 최종 정리 (이 문서)
- `docs/IP_BINDING_TEST_RESULTS.md` - IP 바인딩 테스트
- `docs/CURL_CFFI_TEST_RESULTS.md` - curl-cffi 테스트 결과

---

*마지막 업데이트: 2025-11-22*
