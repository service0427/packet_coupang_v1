# 패킷 레벨 분석 - 마지막 가능성

## 현재까지 발견한 사실

### Akamai Hash 구성 요소

```
Akamai Text (chrome110):
1:65536;2:0;3:1000;4:6291456;6:262144|15663105|0|m,a,s,p

해석:
1:65536      = SETTINGS_HEADER_TABLE_SIZE: 65536
2:0          = SETTINGS_ENABLE_PUSH: 0
3:1000       = SETTINGS_MAX_CONCURRENT_STREAMS: 1000
4:6291456    = SETTINGS_INITIAL_WINDOW_SIZE: 6291456
6:262144     = SETTINGS_MAX_HEADER_LIST_SIZE: 262144
|15663105    = WINDOW_UPDATE 값
|0           = ?
|m,a,s,p     = PRIORITY frame 순서
```

**핵심:** 이것은 **HTTP/2 SETTINGS 프레임**

---

## curl_cffi의 한계

### 테스트 결과

```python
# extra_fp 파라미터로 시도
extra_fp = {
    'http2_stream_weight': 512,      # ❌ 변경 안 됨
    'http2_stream_exclusive': 0,     # ❌ 변경 안 됨
    'http2_no_priority': True        # ❌ 변경 안 됨
}
```

**결과:** Akamai Text 변경 없음

**이유:** curl_cffi는 libcurl 기반이고, libcurl의 HTTP/2 구현(nghttp2)이 SETTINGS를 하드코딩

---

## 패킷 레벨 접근 가능성

### Option 1: nghttp2 소스 수정 (⚠️ 가능하지만 어려움)

**방법:**
```c
// nghttp2 소스코드에서 SETTINGS 값 수정
// src/nghttp2_session.c

static const nghttp2_settings_entry default_settings[] = {
    {NGHTTP2_SETTINGS_HEADER_TABLE_SIZE, 65536},      // ← 변경 가능
    {NGHTTP2_SETTINGS_ENABLE_PUSH, 0},                // ← 변경 가능
    {NGHTTP2_SETTINGS_MAX_CONCURRENT_STREAMS, 1000},  // ← 변경 가능
    {NGHTTP2_SETTINGS_INITIAL_WINDOW_SIZE, 6291456},  // ← 변경 가능
    {NGHTTP2_SETTINGS_MAX_HEADER_LIST_SIZE, 262144},  // ← 변경 가능
};
```

**과정:**
1. nghttp2 소스 다운로드
2. SETTINGS 값 수정
3. 컴파일
4. curl_cffi 재빌드 (nghttp2 링크)
5. Python에서 사용

**시간:** 1~2일
**난이도:** 높음
**성공률:** 80%

### Option 2: Python requests + hyper (HTTP/2 라이브러리)

**hyper 라이브러리 확인:**
```python
from hyper import HTTP20Connection

conn = HTTP20Connection('www.coupang.com:443')

# HTTP/2 SETTINGS 직접 제어 가능한가?
conn.update_settings({
    'SETTINGS_HEADER_TABLE_SIZE': 32768,  # 변경!
    'SETTINGS_ENABLE_PUSH': 1,            # 변경!
})
```

**장점:**
- Python만으로 가능
- 소스 수정 불필요

**단점:**
- TLS는 여전히 Python의 ssl 모듈 사용 (OpenSSL)
- Chrome TLS와 다름

### Option 3: mitmproxy로 중간 변조

**개념:**
```
Python → mitmproxy → Coupang

1. Python에서 일반 요청
2. mitmproxy가 가로챔
3. HTTP/2 SETTINGS 변조
4. Coupang으로 전달
```

**문제:**
- TLS는 mitmproxy가 새로 생성 (Chrome TLS 아님)
- Akamai가 감지

### Option 4: Playwright + CDP로 직접 제어

**Chrome DevTools Protocol 확인:**
```python
client = await page.context.new_cdp_session(page)

# Network domain에서 HTTP/2 제어 가능?
await client.send('Network.enable')
await client.send('Network.setExtraHTTPHeaders', {...})
```

**조사 필요:**
- CDP에 HTTP/2 SETTINGS를 변경하는 명령이 있는가?

---

## 실험 가능한 접근

### Experiment 1: hyper 라이브러리 테스트

```python
# test_hyper_http2.py

from hyper import HTTP20Connection

conn = HTTP20Connection('tls.browserleaks.com', port=443, secure=True)

# Custom SETTINGS
conn.update_settings({
    'SETTINGS_HEADER_TABLE_SIZE': 32768,
    'SETTINGS_MAX_CONCURRENT_STREAMS': 500,
})

conn.request('GET', '/json')
response = conn.get_response()

# Akamai Hash 확인
data = response.read()
print(data)
```

**기대:**
- Akamai Hash가 변경되는가?

### Experiment 2: httpx + httpcore HTTP/2

```python
# test_httpx_http2.py

import httpx

# httpx는 httpcore 사용 (h2 라이브러리)
client = httpx.Client(http2=True)

# h2 라이브러리 설정 변경 가능한가?
response = client.get('https://tls.browserleaks.com/json')

# Akamai Hash 확인
```

### Experiment 3: Scapy로 직접 패킷 생성 (극단적)

```python
# test_scapy_http2.py

from scapy.all import *

# HTTP/2 프레임 직접 생성
settings_frame = H2Frame(
    type=4,  # SETTINGS
    flags=0,
    stream_id=0,
    settings=[
        (1, 32768),   # HEADER_TABLE_SIZE
        (2, 1),       # ENABLE_PUSH
        (3, 500),     # MAX_CONCURRENT_STREAMS
    ]
)

# TLS 연결 후 전송
```

**문제:**
- TLS handshake를 직접 구현해야 함
- 너무 복잡함

---

## 현실적인 패킷 접근

### 방안 A: hyper + Chrome TLS 쿠키

**컨셉:**
```python
# 1. Playwright로 Chrome TLS handshake + 쿠키 획득
browser = p.chromium.launch()
page = browser.new_page()
page.goto('https://www.coupang.com/')
cookies = await page.context.cookies()

# 2. hyper로 HTTP/2 SETTINGS 변경 + Chrome 쿠키 사용
from hyper import HTTP20Connection

conn = HTTP20Connection('www.coupang.com', port=443)
conn.update_settings({...})  # 변경!

# 쿠키 헤더 추가
cookie_header = '; '.join([f'{c["name"]}={c["value"]}' for c in cookies])

conn.request('GET', '/np/search?q=무선청소기', headers={
    'Cookie': cookie_header
})
```

**가능성:**
- Chrome 쿠키 ✅
- HTTP/2 SETTINGS 변경 ✅
- TLS? ❌ (hyper가 자체 TLS 생성)

**결과:**
- Akamai가 TLS(hyper) vs Cookie(Chrome) 불일치 감지 가능

### 방안 B: h2 라이브러리 직접 사용

```python
# test_h2_direct.py

import h2.connection
import ssl
import socket

# TLS 연결
sock = socket.create_connection(('www.coupang.com', 443))
ctx = ssl.create_default_context()
tls_sock = ctx.wrap_socket(sock, server_hostname='www.coupang.com')

# HTTP/2 연결
conn = h2.connection.H2Connection()
conn.initiate_connection()

# Custom SETTINGS 전송
conn.update_settings({
    h2.settings.SettingCodes.HEADER_TABLE_SIZE: 32768,  # 변경!
    h2.settings.SettingCodes.MAX_CONCURRENT_STREAMS: 500,
})

tls_sock.sendall(conn.data_to_send())

# 요청
conn.send_headers(1, [
    (':method', 'GET'),
    (':path', '/np/search?q=무선청소기'),
    (':authority', 'www.coupang.com'),
    (':scheme', 'https'),
])

tls_sock.sendall(conn.data_to_send())

# 응답 수신
data = tls_sock.recv(65536)
events = conn.receive_data(data)
```

**장점:**
- HTTP/2 SETTINGS 완전 제어 ✅

**단점:**
- TLS는 Python ssl 모듈 (OpenSSL)
- Chrome TLS와 다름 (JA3 다름)

---

## 최종 검증 필요 사항

### 질문 1: Akamai는 TLS와 HTTP/2 중 무엇을 우선하는가?

**테스트:**
```
시나리오 A: Chrome TLS + Chrome HTTP/2 SETTINGS
  → 정상 작동 (확인됨)

시나리오 B: Python TLS + Chrome HTTP/2 SETTINGS
  → ?

시나리오 C: Chrome TLS + Python HTTP/2 SETTINGS
  → ?
```

**중요도:** 매우 높음

### 질문 2: h2 라이브러리로 HTTP/2 SETTINGS 변경이 실제로 되는가?

**테스트:**
```python
# h2로 요청 → tls.browserleaks.com
# Akamai Hash 확인
# 기본값과 다른가?
```

---

## 즉시 실행 가능한 테스트

### Test 1: h2 라이브러리로 Akamai Hash 변경 시도

```python
# test_h2_settings_change.py

import h2.connection
import h2.config
import ssl
import socket
import json

# 1. 기본 설정으로 요청
def test_default_settings():
    sock = socket.create_connection(('tls.browserleaks.com', 443))
    ctx = ssl.create_default_context()
    tls_sock = ctx.wrap_socket(sock, server_hostname='tls.browserleaks.com')

    config = h2.config.H2Configuration(client_side=True)
    conn = h2.connection.H2Connection(config=config)
    conn.initiate_connection()
    tls_sock.sendall(conn.data_to_send())

    conn.send_headers(1, [
        (':method', 'GET'),
        (':path', '/json'),
        (':authority', 'tls.browserleaks.com'),
        (':scheme', 'https'),
    ])
    tls_sock.sendall(conn.data_to_send())
    conn.end_stream(1)
    tls_sock.sendall(conn.data_to_send())

    # 응답 수신
    response_data = b''
    while True:
        data = tls_sock.recv(65536)
        if not data:
            break

        events = conn.receive_data(data)
        for event in events:
            if isinstance(event, h2.events.DataReceived):
                response_data += event.data

        if response_data:
            break

    result = json.loads(response_data)
    print(f'Default Akamai Hash: {result.get("akamai_hash")}')
    return result.get("akamai_hash")

# 2. 변경된 설정으로 요청
def test_custom_settings():
    sock = socket.create_connection(('tls.browserleaks.com', 443))
    ctx = ssl.create_default_context()
    tls_sock = ctx.wrap_socket(sock, server_hostname='tls.browserleaks.com')

    config = h2.config.H2Configuration(client_side=True)
    conn = h2.connection.H2Connection(config=config)
    conn.initiate_connection()

    # Custom SETTINGS 전송
    conn.update_settings({
        h2.settings.SettingCodes.HEADER_TABLE_SIZE: 32768,        # 변경!
        h2.settings.SettingCodes.ENABLE_PUSH: 1,                  # 변경!
        h2.settings.SettingCodes.MAX_CONCURRENT_STREAMS: 500,     # 변경!
        h2.settings.SettingCodes.INITIAL_WINDOW_SIZE: 5242880,    # 변경!
    })

    tls_sock.sendall(conn.data_to_send())

    # 요청
    conn.send_headers(1, [
        (':method', 'GET'),
        (':path', '/json'),
        (':authority', 'tls.browserleaks.com'),
        (':scheme', 'https'),
    ])
    tls_sock.sendall(conn.data_to_send())
    conn.end_stream(1)
    tls_sock.sendall(conn.data_to_send())

    # 응답 수신
    response_data = b''
    while True:
        data = tls_sock.recv(65536)
        if not data:
            break

        events = conn.receive_data(data)
        for event in events:
            if isinstance(event, h2.events.DataReceived):
                response_data += event.data

        if response_data:
            break

    result = json.loads(response_data)
    print(f'Custom Akamai Hash: {result.get("akamai_hash")}')
    return result.get("akamai_hash")

# 실행
default_hash = test_default_settings()
custom_hash = test_custom_settings()

if default_hash != custom_hash:
    print('\n[SUCCESS] Akamai Hash CHANGED!')
    print('          HTTP/2 SETTINGS modification WORKS!')
else:
    print('\n[FAIL] Akamai Hash unchanged')
    print('       HTTP/2 SETTINGS modification has no effect')
```

---

## 결론

### 🔬 검증 필요

**h2 라이브러리로 HTTP/2 SETTINGS 변경이 Akamai Hash를 바꿀 수 있는가?**

→ **지금 바로 테스트 가능**

### 🎯 성공 시나리오

만약 h2로 Akamai Hash 변경 성공:
```python
# 1. Playwright로 Chrome TLS + 쿠키
browser = p.chromium.launch()
cookies = get_cookies()

# 2. h2로 HTTP/2 SETTINGS 랜덤 생성
settings = random_http2_settings()

# 3. 요청
conn = h2.connection.H2Connection()
conn.update_settings(settings)
# ... 요청

# 무한 패턴!
```

### ❌ 실패 시나리오

만약 h2로도 Akamai Hash 변경 실패:
→ **패킷 레벨 접근 불가능**
→ Chrome 빌드 Pool 전환으로 회귀

---

**다음 작업:** h2 라이브러리 테스트 즉시 실행
**예상 시간:** 10분
**성공 가능성:** 50%
