# Akamai Bot Manager Challenge 통과 전략

## 🎯 현재 상황

### Stage 1: TLS ClientHello ✅ 완료
- Golang tls-client: 100% 통과
- Python curl-cffi: 100% 통과

### Stage 2: Akamai Bot Manager ⏳ 진행 필요

**Challenge 응답 구조**:
```html
<script src="/EmMdAPxL/vlKvy6z/rlRYzJQ/0B/ckiah87m5Ji1/JUJyGlxE/dyAYCUoi/aXhrAQ?v=1f1f4da8-1ab8-7b76-a13c-4f3c12f11741&t=975548756"></script>
<script>
    // location.reload(true) 실행
</script>
```

**Challenge 작동 방식**:
1. JavaScript 파일 로드
2. Sensor Data 수집 (브라우저 지문)
3. XMLHttpRequest로 전송
4. `location.reload()` 실행
5. _abck 쿠키 생성

---

## 🔍 Akamai Bot Manager 분석

### 수집하는 정보

**1. Browser Fingerprint**
```javascript
// Screen 정보
screen.width, screen.height
screen.colorDepth
screen.pixelDepth

// Navigator 정보
navigator.userAgent
navigator.platform
navigator.language
navigator.hardwareConcurrency
navigator.deviceMemory

// WebGL Fingerprint
WebGL renderer string
WebGL vendor string

// Canvas Fingerprint
Canvas rendering hash

// Audio Fingerprint
AudioContext properties

// Timezone
new Date().getTimezoneOffset()

// Plugins
navigator.plugins (deprecated)

// Fonts
Installed fonts detection

// Battery
navigator.getBattery()
```

**2. Behavioral Data**
```javascript
// Mouse 이동
mousemove events
click patterns

// Keyboard
keydown/keyup timing

// Scroll
scroll events
scroll speed

// Touch (모바일)
touch events

// Performance
performance.timing
resource load times
```

**3. JavaScript 실행 환경**
```javascript
// Automation 감지
window.navigator.webdriver
window.chrome.runtime
window.document.$cdc_
window.callPhantom
window._phantom

// Headless 감지
navigator.maxTouchPoints === 0
navigator.connection.rtt === 0
Chrome PDF Viewer 없음
```

**4. Sensor Data**
```javascript
// Akamai 전용 데이터
- 마우스 이동 패턴
- 키보드 타이밍
- JavaScript 실행 시간
- 메모리 사용 패턴
- 네트워크 타이밍
```

---

## 🚀 통과 전략 (패킷 모드)

### 전략 1: Sensor Data 생성 및 전송 (권장) ⭐

**핵심**: JavaScript 실행 없이 Sensor Data만 생성하여 전송

**단계**:

#### 1. Challenge JavaScript 다운로드 및 분석

```python
from curl_cffi import requests
import re

# Challenge 받기
response = requests.get(url, impersonate='chrome120')
html = response.text

# JavaScript URL 추출
script_url_match = re.search(r'src="(/[^"]+\?v=[^"]+&t=[^"]+)"', html)
if script_url_match:
    script_url = 'https://www.coupang.com' + script_url_match.group(1)

    # JavaScript 다운로드
    js_response = requests.get(script_url, impersonate='chrome120')
    js_code = js_response.text

    # 저장 및 분석
    with open('akamai_sensor.js', 'w') as f:
        f.write(js_code)
```

#### 2. JavaScript 디컴파일 및 Sensor 로직 추출

**필요 도구**:
```bash
npm install -g js-beautify
npm install -g @javascript-obfuscator/javascript-obfuscator

# 또는
pip install jsbeautifier
```

**분석**:
```javascript
// Akamai Sensor Data 구조 (예시)
{
    "sensor_data": "2,3,-94,-100,Mozilla/5.0...",
    "timestamp": 1234567890,
    "mouse_movements": "12,45;23,67;...",
    "keyboard_events": "k:65,t:123;...",
    "execution_times": "init:45,sensor:120,..."
}
```

#### 3. Sensor Data Generator 구현

**Python 구현**:
```python
import time
import random
import json
from datetime import datetime

class AkamaiSensorGenerator:
    def __init__(self):
        self.start_time = int(time.time() * 1000)

    def generate_mouse_movements(self, count=50):
        """가짜 마우스 이동 생성"""
        movements = []
        x, y = 100, 100

        for i in range(count):
            # 자연스러운 이동 (Bezier curve 근사)
            dx = random.randint(-20, 20)
            dy = random.randint(-20, 20)
            x = max(0, min(1920, x + dx))
            y = max(0, min(1080, y + dy))
            timestamp = int(time.time() * 1000) - self.start_time + i * 50
            movements.append(f"{x},{y},{timestamp}")

        return ";".join(movements)

    def generate_keyboard_events(self, count=10):
        """가짜 키보드 이벤트 생성"""
        events = []
        keys = [65, 66, 67, 68, 69]  # A, B, C, D, E

        for i in range(count):
            key = random.choice(keys)
            timestamp = int(time.time() * 1000) - self.start_time + i * 100
            events.append(f"k:{key},t:{timestamp}")

        return ";".join(events)

    def generate_sensor_data(self):
        """Sensor Data 메인 생성"""
        # Akamai Sensor Data 형식 (실제는 더 복잡)
        sensor_parts = [
            "2",  # Version
            "3",  # Type
            str(int(time.time() * 1000) - self.start_time),  # Execution time
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
            "1920,1080,24",  # screen.width, height, colorDepth
            "en-US",  # navigator.language
            "8",  # navigator.hardwareConcurrency
            "8",  # navigator.deviceMemory
            "-480",  # timezone offset
            self.generate_mouse_movements(),
            self.generate_keyboard_events(),
        ]

        return ",".join(sensor_parts)

    def generate_payload(self):
        """최종 Payload 생성"""
        return {
            "sensor_data": self.generate_sensor_data(),
            "timestamp": int(time.time() * 1000)
        }
```

#### 4. Sensor Data 전송

```python
from curl_cffi import requests

# 1. Challenge 받기
session = requests.Session()
response = session.get(
    'https://www.coupang.com/np/search?q=음료수',
    impersonate='chrome120'
)

# 2. Challenge script URL 추출
import re
script_match = re.search(r'src="(/[^"]+\?v=[^"]+&t=([^"]+))"', response.text)
script_url = 'https://www.coupang.com' + script_match.group(1)
challenge_token = script_match.group(2)

# 3. JavaScript 다운로드 (필수 - 쿠키 설정됨)
js_response = session.get(script_url, impersonate='chrome120')

# 4. Sensor Data 생성
generator = AkamaiSensorGenerator()
sensor_payload = generator.generate_payload()

# 5. Sensor Data 전송 (추정 endpoint)
sensor_response = session.post(
    'https://www.coupang.com/_sec/cp_challenge/verify',
    json=sensor_payload,
    headers={
        'Content-Type': 'application/json',
        'X-Challenge-Token': challenge_token
    },
    impersonate='chrome120'
)

# 6. 다시 원래 페이지 요청
final_response = session.get(
    'https://www.coupang.com/np/search?q=음료수',
    impersonate='chrome120'
)

print(f"Final Status: {final_response.status_code}")
print(f"Size: {len(final_response.content)}")
print(f"Success: {len(final_response.content) > 50000}")
```

---

### 전략 2: JavaScript 엔진 통합 (복잡하지만 확실)

**필요 라이브러리**:

**Python**:
```bash
pip install pyppeteer  # Puppeteer for Python
pip install playwright  # 또는 Playwright
pip install selenium-wire  # Selenium + 패킷 조작
pip install js2py  # JavaScript to Python
```

**Node.js**:
```bash
npm install puppeteer-extra
npm install puppeteer-extra-plugin-stealth
npm install playwright
```

**방법**:

#### Option A: Headless Browser (Stealth 모드)

```python
from playwright.sync_api import sync_playwright

def bypass_akamai_with_browser():
    with sync_playwright() as p:
        # Stealth 모드로 브라우저 시작
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox'
            ]
        )

        # Context 생성 (User-Agent 등 설정)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            locale='ko-KR',
            timezone_id='Asia/Seoul'
        )

        # Automation 감지 우회
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });

            window.chrome = {
                runtime: {}
            };
        """)

        page = context.new_page()

        # Challenge 페이지 로드
        page.goto('https://www.coupang.com/np/search?q=음료수')

        # JavaScript 실행 대기 (Challenge 처리)
        page.wait_for_load_state('networkidle')

        # 3초 대기 (Sensor Data 수집)
        page.wait_for_timeout(3000)

        # 쿠키 추출
        cookies = context.cookies()
        abck_cookie = next((c for c in cookies if c['name'] == '_abck'), None)

        browser.close()

        return abck_cookie
```

#### Option B: 하이브리드 (Browser + curl-cffi)

```python
from playwright.sync_api import sync_playwright
from curl_cffi import requests

def hybrid_bypass():
    # 1. Browser로 Challenge 통과
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        page.goto('https://www.coupang.com/np/search?q=음료수')
        page.wait_for_load_state('networkidle')
        page.wait_for_timeout(3000)

        # 쿠키 추출
        cookies = context.cookies()
        browser.close()

    # 2. curl-cffi로 빠른 요청 (쿠키 포함)
    cookie_dict = {c['name']: c['value'] for c in cookies}

    response = requests.get(
        'https://www.coupang.com/np/search?q=음료수',
        cookies=cookie_dict,
        impersonate='chrome120'
    )

    return response
```

---

### 전략 3: Akamai Sensor Solver 라이브러리 사용

**기존 솔루션**:

```bash
# Python
pip install akamai-sensor-solver  # (존재 시)
pip install anticaptchaofficial  # Captcha 서비스

# Node.js
npm install akamai-sensor-data
npm install @antiadblock/akamai-sensor-data
```

**예시 (가상)**:
```python
from akamai_solver import AkamaiSolver

solver = AkamaiSolver()
sensor_data = solver.generate_sensor_data(
    user_agent='Mozilla/5.0...',
    url='https://www.coupang.com/np/search?q=음료수'
)

response = requests.post(
    sensor_endpoint,
    json={'sensor_data': sensor_data},
    impersonate='chrome120'
)
```

---

### 전략 4: Reverse Engineering (고급)

**단계**:

#### 1. JavaScript 파일 분석

```bash
# 다운로드
curl 'https://www.coupang.com/EmMdAPxL/vlKvy6z/rlRYzJQ/0B/ckiah87m5Ji1/JUJyGlxE/dyAYCUoi/aXhrAQ?v=...' -o akamai.js

# Beautify
js-beautify akamai.js > akamai_beautified.js

# 분석 (Chrome DevTools)
node --inspect-brk analyze.js
```

#### 2. Sensor Data 형식 추출

```javascript
// Chrome DevTools에서 breakpoint 설정
// XMLHttpRequest.send() 호출 시점에 멈춤
// payload 확인

// 예상 구조:
{
    "sensor_data": "encrypted_base64_string",
    "token": "challenge_token",
    "timestamp": 1234567890
}
```

#### 3. 암호화 알고리즘 역분석

```python
# Sensor Data는 일반적으로 암호화됨
# AES, RSA 등 사용

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import base64

def encrypt_sensor_data(data, key, iv):
    cipher = AES.new(key, AES.MODE_CBC, iv)
    encrypted = cipher.encrypt(pad(data.encode(), AES.block_size))
    return base64.b64encode(encrypted).decode()
```

#### 4. Python으로 재구현

```python
class AkamaiSensorReversed:
    def __init__(self):
        self.key = b'extracted_key'
        self.iv = b'extracted_iv'

    def collect_sensor_data(self):
        # 역분석한 로직 구현
        data = {
            'ua': 'Mozilla/5.0...',
            'screen': '1920x1080x24',
            'lang': 'ko-KR',
            'tz': -480,
            'mouse': self.generate_mouse_pattern(),
            'keyboard': self.generate_keyboard_pattern(),
            'timing': self.generate_timing_data()
        }
        return json.dumps(data)

    def encrypt_and_encode(self, data):
        encrypted = encrypt_sensor_data(data, self.key, self.iv)
        return encrypted
```

---

## 🛠️ 실전 구현 로드맵

### Phase 1: Challenge 구조 분석 (1-2일)

```python
# 1. Challenge response 저장
# 2. JavaScript 다운로드
# 3. Beautify 및 분석
# 4. Sensor Data endpoint 찾기
```

**도구**:
- Chrome DevTools (Network 탭)
- Burp Suite / Fiddler
- JavaScript beautifier

### Phase 2: Sensor Data 생성 (3-5일)

```python
# 1. Sensor Data 형식 파악
# 2. 생성 로직 구현
# 3. 암호화 알고리즘 역분석
# 4. Python/Golang으로 재구현
```

**도구**:
- js2py
- Node.js (JavaScript 실행)
- Crypto libraries

### Phase 3: 통합 및 테스트 (2-3일)

```python
# 1. curl-cffi/tls-client에 통합
# 2. 쿠키 관리 구현
# 3. 성공률 테스트
# 4. 최적화
```

---

## 📦 필수 설치 라이브러리

### Python

```bash
# 기본
pip install curl-cffi
pip install requests

# JavaScript 실행
pip install playwright
pip install pyppeteer
pip install js2py

# 암호화
pip install pycryptodome
pip install cryptography

# 분석
pip install beautifulsoup4
pip install lxml
pip install jsbeautifier

# 유틸
pip install faker  # 가짜 데이터 생성
```

### Node.js

```bash
# Puppeteer
npm install puppeteer
npm install puppeteer-extra
npm install puppeteer-extra-plugin-stealth

# Playwright
npm install playwright

# 유틸
npm install js-beautify
npm install axios
```

### Golang

```go
// Playwright for Go
go get github.com/playwright-community/playwright-go

// JavaScript 실행
go get github.com/robertkrimen/otto

// 암호화
go get golang.org/x/crypto
```

---

## 🎯 권장 접근 방법

### 1단계: 빠른 프로토타입 (Playwright)

```python
from playwright.sync_api import sync_playwright
from curl_cffi import requests

def quick_prototype():
    # Browser로 Challenge 통과
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto('https://www.coupang.com/np/search?q=음료수')
        page.wait_for_load_state('networkidle')
        cookies = page.context.cookies()
        browser.close()

    # 쿠키로 빠른 요청
    response = requests.get(
        url,
        cookies={c['name']: c['value'] for c in cookies},
        impersonate='chrome120'
    )

    return response
```

**장점**: 빠르게 작동 확인
**단점**: Browser 오버헤드

### 2단계: Sensor Data 생성 (순수 패킷)

```python
# 1. Challenge JavaScript 분석
# 2. Sensor Data Generator 구현
# 3. curl-cffi로 전송
```

**장점**: 리소스 효율, 빠른 속도
**단점**: 분석 시간 필요

---

## 💡 핵심 포인트

### 성공 조건

1. ✅ TLS ClientHello 통과 (이미 100% 달성)
2. ⏳ JavaScript 실행 (또는 Sensor Data 생성)
3. ⏳ _abck 쿠키 획득
4. ⏳ 올바른 Sensor Data 전송

### 실패 가능성

- ❌ Sensor Data 형식 불일치
- ❌ 암호화 키 추출 실패
- ❌ 타이밍 문제 (너무 빠름)
- ❌ Behavioral data 부족

### 디버깅 방법

```python
# 1. 실제 브라우저와 비교
# 2. Network 패킷 비교 (Burp Suite)
# 3. 쿠키 비교
# 4. Sensor Data 비교
```

---

## 🚀 즉시 시작 가능한 코드

다음 파일을 생성하겠습니다:
1. `akamai_challenge_analyzer.py` - Challenge 구조 분석
2. `akamai_sensor_generator.py` - Sensor Data 생성
3. `akamai_bypass_hybrid.py` - Hybrid 방식 (Browser + curl-cffi)

작성해드릴까요?
