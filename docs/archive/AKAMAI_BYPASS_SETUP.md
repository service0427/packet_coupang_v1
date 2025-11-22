# Akamai Bypass 구현 가이드

## 🎯 목표

**Stage 1 (TLS)**: ✅ 완료 (100% 통과)
**Stage 2 (Akamai)**: ⏳ 진행 중

---

## 📦 필수 라이브러리 설치

### Python 라이브러리

```bash
# 기본 HTTP 클라이언트 (TLS 100% 보장)
pip install curl-cffi

# Browser 자동화 (Challenge 통과용)
pip install playwright
playwright install chromium

# JavaScript 분석
pip install jsbeautifier

# 암호화 (Sensor Data)
pip install pycryptodome

# 유틸
pip install beautifulsoup4
pip install lxml
```

### Node.js (선택사항 - JavaScript 분석용)

```bash
npm install -g js-beautify
npm install -g prettier
```

---

## 🚀 단계별 실행 가이드

### Phase 1: Challenge 구조 분석

**목적**: Akamai Challenge JavaScript 구조 파악

```bash
cd D:\dev\git\local-packet-coupang\src
python akamai_challenge_analyzer.py
```

**출력**:
- `results/akamai_challenge.html` - Challenge HTML
- `results/akamai_sensor.js` - Challenge JavaScript (난독화됨)
- `results/akamai_analysis.json` - 분석 결과

**다음 단계**:
1. `akamai_sensor.js` 파일을 https://beautifier.io/ 에 업로드
2. Beautify 결과를 `akamai_sensor_beautified.js`로 저장
3. JavaScript 코드에서 다음 항목 찾기:
   - XMLHttpRequest.send() 호출
   - Sensor Data 생성 로직
   - Challenge verify endpoint

### Phase 2: Hybrid Bypass 테스트

**목적**: Browser로 Challenge 통과 → 쿠키 재사용

```bash
cd D:\dev\git\local-packet-coupang\src
python akamai_bypass_hybrid.py
```

**작동 방식**:
1. Playwright로 Chromium 실행
2. Challenge 페이지 로드
3. JavaScript 실행 (5초 대기)
4. 쿠키 추출 (_abck, bm_sz 등)
5. curl-cffi로 빠른 요청 (쿠키 재사용)
6. 5회 연속 테스트

**예상 결과**:
- 첫 요청: Browser (5-10초)
- 이후 요청: curl-cffi (100-200ms)
- 성공률: 80-100% (쿠키 유효 시간)

### Phase 3: 순수 패킷 모드 (고급)

**목적**: Browser 없이 Sensor Data 생성 및 전송

**단계**:

#### 1. JavaScript 역분석

```bash
# beautified JavaScript 분석
code results/akamai_sensor_beautified.js
```

**찾아야 할 것**:
- Sensor Data 형식
- 암호화 알고리즘 (AES, RSA 등)
- Challenge verify endpoint
- 필수 헤더

#### 2. Sensor Data Generator 구현

```python
# 예시 구조
class AkamaiSensorGenerator:
    def generate_sensor_data(self):
        # 브라우저 지문 생성
        fingerprint = {
            'screen': '1920x1080x24',
            'ua': 'Mozilla/5.0...',
            'lang': 'ko-KR',
            'tz': -480,
            'plugins': [...],
            'fonts': [...],
        }

        # Behavioral data 생성
        behavioral = {
            'mouse': self.generate_mouse_pattern(),
            'keyboard': self.generate_keyboard_pattern(),
            'timing': self.generate_timing_data()
        }

        # 암호화 및 인코딩
        sensor_data = self.encrypt(fingerprint, behavioral)

        return sensor_data
```

#### 3. Challenge Verify 요청

```python
from curl_cffi import requests

# Sensor Data 전송
response = session.post(
    'https://www.coupang.com/_sec/cp_challenge/verify',
    json={
        'sensor_data': sensor_data,
        'token': challenge_token
    },
    impersonate='chrome120'
)

# _abck 쿠키 확인
if '_abck' in session.cookies:
    print("✅ Challenge 통과!")
```

---

## 📊 현재 사용 가능한 도구

### 1. akamai_challenge_analyzer.py

**용도**: Challenge 구조 분석

```bash
python akamai_challenge_analyzer.py
```

**출력**:
- Challenge HTML
- Challenge JavaScript
- 분석 리포트

### 2. akamai_bypass_hybrid.py

**용도**: Browser + curl-cffi Hybrid

```bash
python akamai_bypass_hybrid.py
```

**장점**:
- 즉시 사용 가능
- Challenge 통과 보장
- 쿠키 재사용으로 효율적

**단점**:
- Browser 오버헤드
- Playwright 설치 필요

### 3. 실제 브라우저 (CDP) - 이미 100% 작동

**위치**: `D:\dev\git\local-packet-coupang\real_chrome_connect.js`

**장점**:
- 100% 성공률 보장
- Challenge 자동 처리

**단점**:
- 리소스 많이 사용
- 속도 느림

---

## 🎯 권장 진행 순서

### 즉시 사용 (개발/테스트)

```bash
# 방법 1: Hybrid (권장)
python akamai_bypass_hybrid.py

# 방법 2: 실제 브라우저 (CDP)
node real_chrome_connect.js
```

### 중기 목표 (1-2주)

1. Challenge JavaScript 역분석
2. Sensor Data 형식 파악
3. Sensor Data Generator 구현
4. curl-cffi 전용 버전 완성

### 장기 목표 (프로덕션)

1. 순수 패킷 모드 100% 달성
2. Golang 버전 구현
3. 대량 요청 최적화

---

## 💡 디버깅 가이드

### Challenge 통과 실패 시

#### 1. Browser 방식 확인

```bash
python akamai_bypass_hybrid.py
```

- 성공하면: Browser 작동 OK, 쿠키 문제
- 실패하면: Challenge 변경됨, JavaScript 업데이트 필요

#### 2. 쿠키 확인

```python
# 중요 쿠키
_abck: Akamai Bot Manager 쿠키 (필수)
bm_sz: Bot Manager size
ak_bmsc: Akamai Bot Manager session
PCID: PC ID
```

#### 3. Network 패킷 비교

```bash
# 실제 브라우저 패킷 캡처
# Burp Suite / Fiddler 사용

# curl-cffi 패킷과 비교
# 차이점 파악
```

#### 4. JavaScript 실행 시간

```python
# Challenge JavaScript는 특정 시간 필요
# 너무 빠르면 실패

# 권장: 3-5초 대기
page.wait_for_timeout(5000)
```

---

## 📈 성공률 예상

| 방법 | TLS 통과 | Akamai 통과 | 총 성공률 | 속도 |
|------|---------|------------|----------|------|
| **Real Chrome (CDP)** | 100% | 100% | **100%** | 느림 (3-5초) |
| **Hybrid (Browser+curl-cffi)** | 100% | 80-100% | **80-100%** | 보통 (1-2초) |
| **순수 패킷 (Sensor Generator)** | 100% | ?% | **?%** | 빠름 (100ms) |

---

## 🔧 문제 해결

### Playwright 설치 오류

```bash
pip install playwright
playwright install chromium

# 오류 발생 시
playwright install --force chromium
```

### curl-cffi HTTP/3 오류

```bash
# HTTP/2로 fallback
response = requests.get(url, impersonate='chrome120', http_version=2)
```

### JavaScript 난독화 해제 실패

```bash
# Online tool 사용
https://beautifier.io/
https://deobfuscate.io/

# 또는 Chrome DevTools
# F12 → Sources → {} (Pretty print)
```

---

## 📚 참고 문서

1. **TLS 통과 전략**: `docs/TLS_PROTOCOL_REQUIREMENT.md`
2. **Golang vs Python 비교**: `docs/GOLANG_VS_PYTHON_COMPARISON.md`
3. **Akamai Bypass 전략**: `docs/AKAMAI_BYPASS_STRATEGY.md`
4. **BoringSSL 설명**: `docs/BORINGSSL_VS_OPENSSL_TRUTH.md`

---

## 🚀 Quick Start

```bash
# 1. 라이브러리 설치
pip install curl-cffi playwright
playwright install chromium

# 2. Challenge 분석
cd src
python akamai_challenge_analyzer.py

# 3. Hybrid Bypass 테스트
python akamai_bypass_hybrid.py

# 4. 결과 확인
cd ../results
# akamai_bypass_success.html 확인
```

---

## 💬 다음 단계 선택

**즉시 사용하고 싶다면**:
```bash
python akamai_bypass_hybrid.py
```

**Challenge 구조를 분석하고 싶다면**:
```bash
python akamai_challenge_analyzer.py
```

**순수 패킷 모드를 구현하고 싶다면**:
1. Challenge JavaScript 역분석
2. Sensor Data Generator 구현
3. 테스트 및 최적화

어떤 방향으로 진행하시겠습니까?
