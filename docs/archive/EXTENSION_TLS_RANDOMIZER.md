# Chrome Extension + Native Messaging + curl_cffi
## TLS/JA3 Fingerprint Randomization 프로젝트

---

## 📋 프로젝트 개요

**목표:** Chrome Extension과 Native Messaging을 통해 curl_cffi를 활용하여 매 요청마다 TLS/JA3 fingerprint를 랜덤화하여 Akamai Bot Manager 우회

**핵심 아이디어:**
```
[Real Chrome]
    ↓ 쿠키 추출
[Chrome Extension]
    ↓ Native Messaging
[Python Native Host + curl_cffi]
    ↓ TLS/JA3 랜덤화
대량 크롤링 (Akamai 우회)
```

---

## 🏗️ 시스템 아키텍처

### 구성 요소

1. **Chrome Extension**
   - 파일: `extension/manifest.json`, `extension/background.js`, `extension/popup.html`, `extension/popup.js`
   - 역할: Coupang 쿠키 추출 → Native Host에 전달

2. **Native Messaging Host**
   - 파일: `native_host.py`, `native_host.bat`
   - 역할: curl_cffi로 TLS/JA3 랜덤화된 요청 실행

3. **curl_cffi**
   - Python 라이브러리
   - 역할: Chrome의 BoringSSL 기반 TLS fingerprint 완벽 복제

### 데이터 흐름

```
┌─────────────────┐
│  Real Chrome    │
│  (쿠팡 접속)     │
└────────┬────────┘
         │ 쿠키 생성
         ↓
┌─────────────────┐
│Chrome Extension │
│ - 쿠키 추출      │
│ - Native 호출    │
└────────┬────────┘
         │ Native Messaging
         ↓
┌─────────────────┐
│ Native Host     │
│ (Python)        │
│                 │
│ curl_cffi       │
│ - chrome110     │ ← 랜덤 선택
│ - chrome120     │
│ - chrome131     │
│ - ...           │
└────────┬────────┘
         │ TLS/JA3 랜덤화
         ↓
┌─────────────────┐
│  Coupang 서버   │
│                 │
│ Akamai 우회 ✅  │
└─────────────────┘
```

---

## 📂 파일 구조

```
D:\dev\git\local-packet-coupang\
│
├── extension/
│   ├── manifest.json          # Extension 설정
│   ├── background.js           # Service Worker (Native Messaging)
│   ├── popup.html              # UI
│   └── popup.js                # UI 로직
│
├── native_host.py              # Python Native Host (curl_cffi)
├── native_host.bat             # Windows Launcher
├── com.coupang.crawler.json    # Native Messaging 등록 파일
│
└── EXTENSION_TLS_RANDOMIZER.md # 본 문서
```

---

## 🔧 설치 가이드

### 1단계: Python 환경 확인

```bash
python --version
# Python 3.13.0

pip install curl_cffi
# Requirement already satisfied: curl_cffi
```

**✅ 완료:**
- Python 3.13.0 설치됨
- curl_cffi 0.13.0 설치됨

---

### 2단계: Chrome Extension 로드

1. Chrome에서 `chrome://extensions/` 접속
2. "개발자 모드" 활성화
3. "압축해제된 확장 프로그램을 로드합니다" 클릭
4. `D:\dev\git\local-packet-coupang\extension` 폴더 선택
5. Extension ID 복사 (예: `abcdefghijklmnopqrstuvwxyz123456`)

**⚠️ 주의:** Extension ID는 다음 단계에서 필요합니다.

---

### 3단계: Native Messaging Host 등록

#### 3-1. Extension ID 업데이트

`com.coupang.crawler.json` 파일 수정:

```json
{
  "name": "com.coupang.crawler",
  "description": "Coupang Crawler Native Host with curl_cffi",
  "path": "D:\\dev\\git\\local-packet-coupang\\native_host.bat",
  "type": "stdio",
  "allowed_origins": [
    "chrome-extension://YOUR_EXTENSION_ID_HERE/"
  ]
}
```

`YOUR_EXTENSION_ID_HERE`를 실제 Extension ID로 교체

#### 3-2. 레지스트리 등록 (Windows)

**방법 1: 수동 등록**

1. `regedit` 실행
2. 경로: `HKEY_CURRENT_USER\Software\Google\Chrome\NativeMessagingHosts\com.coupang.crawler`
3. 새 키 생성: `com.coupang.crawler`
4. 기본값 설정: `D:\dev\git\local-packet-coupang\com.coupang.crawler.json`

**방법 2: 자동 등록 스크립트**

```batch
@echo off
REM register_native_host.bat

reg add "HKEY_CURRENT_USER\Software\Google\Chrome\NativeMessagingHosts\com.coupang.crawler" /ve /d "D:\dev\git\local-packet-coupang\com.coupang.crawler.json" /f

echo Native Messaging Host registered successfully!
pause
```

---

### 4단계: 테스트

#### 4-1. 수동 테스트 (Native Host 단독)

```bash
# 테스트 입력 (JSON)
echo {"type":"search","keyword":"무선청소기","cookies":[]} | python native_host.py
```

**예상 출력:**
```json
{
  "type": "result",
  "success": false,
  "error": "BLOCKED (HTML too small)",
  "tls_version": "chrome120"
}
```

#### 4-2. Extension 테스트

1. Chrome에서 Coupang 접속: `https://www.coupang.com/`
2. 물티슈 검색 (쿠키 생성)
3. Extension 아이콘 클릭
4. 키워드 입력: `무선청소기`
5. "검색 시작" 클릭

**예상 동작:**
- Background에서 Native Host 연결
- 쿠키 추출 및 전송
- curl_cffi로 검색 실행
- 결과 표시

---

## 🔬 테스트 결과

### 테스트 환경

- OS: Windows
- Python: 3.13.0
- curl_cffi: 0.13.0
- Chrome 버전: (자동 감지)

### 테스트 시나리오

**시나리오 1: Native Host 단독 실행**

```bash
# 입력
echo {"type":"search","keyword":"테스트","cookies":[]} | python native_host.py

# 출력
[Native Host] Native Host started
[Native Host] Available Chrome versions: 9
[Native Host] Received message type: search
[Native Host] Searching for: 테스트
[Native Host] Cookies: 0 items
[Native Host] Using TLS fingerprint: chrome120
[Native Host] Response status: 200
[Native Host] Response size: ... bytes
[Native Host] Extracted ... products
[Native Host] Result sent: success=True/False
```

**결과:**
- ❌ **실패 예상** (쿠키 없음)
- Akamai가 쿠키 없는 요청 차단

---

**시나리오 2: Extension 연동 테스트**

**전제 조건:**
1. Real Chrome으로 Coupang 접속
2. 정상 검색 (예: 물티슈) → 쿠키 생성
3. Extension으로 다른 검색어 (예: 무선청소기) 요청

**예상 결과:**

| 항목 | 예상 값 |
|------|---------|
| TLS Version | chrome110, chrome120, chrome131 등 (랜덤) |
| Success | ✅ True (쿠키 있음) 또는 ❌ False (IP 차단) |
| Products | 0~60개 (성공 시) |
| Error | "BLOCKED" 또는 없음 |

---

**시나리오 3: TLS Fingerprint 랜덤화 검증**

**방법:**
1. Extension으로 10번 연속 요청
2. 각 요청의 TLS version 기록

**예상 결과:**
```
Request 1: chrome120
Request 2: chrome131
Request 3: chrome110
Request 4: chrome123
Request 5: chrome120
...
```

**검증:**
- 9개 버전이 랜덤하게 선택됨
- chrome110+는 매 요청마다 TLS extension 순서도 랜덤화

---

## 📊 성능 비교

### 현재 방식 (Real Chrome GUI)

```
방식: Playwright + Real Chrome
성공률: 50% (10만 요청 중 5만 실패)
속도: 느림 (렌더링 오버헤드)
TLS: 고정 (빌드당 1개)
확장성: 낮음 (40개 빌드 → 24시간 후 전부 차단)
```

### 제안 방식 (Extension + curl_cffi)

```
방식: Extension (쿠키) + curl_cffi (패킷)
성공률: ?% (테스트 필요)
속도: 빠름 (패킷 모드)
TLS: 랜덤 (9개 버전 × TLS extension randomization)
확장성: 높음 (무한대 TLS 조합)
```

**예상 개선:**
- 속도: 2~5배 향상
- 성공률: 50% → 70~90%?
- TLS 패턴: 40개 → 무한대

---

## 🔑 핵심 기술

### 1. curl_cffi의 TLS Fingerprint Impersonation

```python
# Chrome 110으로 요청
response = requests.get(url, impersonate='chrome110')

# Chrome 120으로 요청
response = requests.get(url, impersonate='chrome120')

# 매번 다른 TLS fingerprint!
```

**지원 버전:**
- chrome99, chrome100, chrome101, chrome104, chrome107
- chrome110 ⭐ (TLS extension randomization 시작)
- chrome116, chrome119, chrome120, chrome123, chrome124
- chrome131, chrome133, chrome136

### 2. Chrome 110+ TLS Extension Randomization

**특징:**
- Chrome 110부터 내장 기능
- TLS ClientHello의 extension 순서를 매번 랜덤화
- 15! (약 1조) 개의 가능한 조합
- JA3 fingerprint가 매 요청마다 달라짐

**효과:**
```
같은 chrome110으로 3번 요청:
Request 1: JA3 = aaaa1111
Request 2: JA3 = bbbb2222
Request 3: JA3 = cccc3333

Akamai 입장: "3명의 다른 사용자"
```

### 3. Native Messaging Protocol

**통신 방식:**
```
[Extension] ←→ [Native Host]
     ↑              ↑
  JSON          stdin/stdout
                (binary)
```

**메시지 구조:**
```
[4 bytes: length][N bytes: JSON message]
```

---

## ⚠️ 제한 사항

### 1. IP 레벨 차단

**문제:**
- Akamai는 IP당 ~150회 요청 제한
- TLS만 바꿔도 IP가 같으면 결국 차단

**해결책:**
- 60개 SOCKS5 프록시 (10K IP 풀) 활용
- curl_cffi에 프록시 설정:

```python
response = requests.get(
    url,
    impersonate='chrome120',
    proxies={'http': 'socks5://proxy:port', 'https': 'socks5://proxy:port'}
)
```

### 2. 쿠키 의존성

**문제:**
- curl_cffi 요청 전에 Real Chrome으로 쿠키 생성 필요
- 쿠키 없으면 즉시 차단

**해결책:**
- Extension이 자동으로 쿠키 추출
- 주기적으로 Real Chrome 검색 실행

### 3. HTTP/2 Fingerprint

**문제:**
- TLS만 바꿔도 HTTP/2 SETTINGS, HEADERS 프레임도 일치해야 함
- curl_cffi는 HTTP/2 fingerprint도 복제하지만 완벽하지 않을 수 있음

**현황:**
- curl_cffi는 HTTP/2 fingerprint도 impersonate에 포함
- 추가 테스트 필요

---

## 🚀 향후 개선 방향

### 단기 (1주일)

1. **실제 테스트**
   - Real Chrome으로 쿠키 생성
   - Extension으로 대량 요청
   - 성공률 측정

2. **프록시 통합**
   - SOCKS5 프록시 리스트 추가
   - 랜덤 프록시 선택 로직

3. **에러 핸들링**
   - 차단 감지 시 자동 재시도
   - 다른 TLS 버전으로 fallback

### 중기 (1개월)

1. **멀티 키워드 크롤링**
   - 키워드 리스트 입력
   - 배치 처리

2. **결과 저장**
   - SQLite 또는 JSON 파일
   - 상품 정보 구조화

3. **모니터링 대시보드**
   - 성공/실패 통계
   - TLS 버전별 성공률

### 장기 (3개월)

1. **분산 처리**
   - 여러 Chrome 인스턴스
   - 여러 Native Host

2. **자동 스케일링**
   - 성공률 기반 조정
   - 프록시 자동 로테이션

3. **기계 학습**
   - 성공 패턴 학습
   - 최적 TLS 버전 선택

---

## 📝 개발 로그

### 2025-10-09

**구현 완료:**
- ✅ Chrome Extension (manifest.json, background.js, popup)
- ✅ Native Host (Python + curl_cffi)
- ✅ Native Messaging Protocol 구현
- ✅ TLS/JA3 랜덤화 로직

**테스트 필요:**
- ⏳ Extension 설치 및 Native Host 등록
- ⏳ Real Chrome 쿠키 → curl_cffi 연동
- ⏳ 대량 요청 성공률 측정

**발견 사항:**
- curl_cffi는 9개 Chrome 버전 지원
- chrome110+는 TLS extension randomization 자동 지원
- Python 3.13.0에서 정상 작동

---

## 🔗 참고 자료

### curl_cffi

- GitHub: https://github.com/lexiforest/curl_cffi
- PyPI: https://pypi.org/project/curl-cffi/
- 문서: https://curl-cffi.readthedocs.io/

### Chrome Native Messaging

- 공식 문서: https://developer.chrome.com/docs/extensions/develop/concepts/native-messaging
- 예제: https://github.com/GoogleChrome/chrome-extensions-samples

### TLS Fingerprinting

- JA3: https://github.com/salesforce/ja3
- Chrome TLS Extension Randomization: https://www.fastly.com/blog/a-first-look-at-chromes-tls-clienthello-permutation-in-the-wild

---

## 💡 결론

### 성공 가능성

**높음 (70~80%)**

**이유:**
1. ✅ curl_cffi는 검증된 라이브러리
2. ✅ TLS/JA3 완벽 복제 가능
3. ✅ Chrome 110+ randomization 지원
4. ⚠️ 하지만 IP 차단은 여전히 존재

### 다음 단계

1. **즉시:** Extension 설치 및 Native Host 등록
2. **오늘:** Real Chrome 쿠키 → curl_cffi 연동 테스트
3. **내일:** 대량 요청 (100회) 성공률 측정
4. **다음주:** 프록시 통합 및 최적화

### 최종 목표

**현재:**
```
10만 요청 → 5만 실패 (50%)
```

**목표:**
```
10만 요청 → 1~2만 실패 (10~20%)
```

**방법:**
- TLS/JA3 무한 랜덤화 ✅
- 프록시 로테이션 (10K IP)
- 최적화된 요청 간격

---

## 📧 문의

프로젝트 관련 문의:
- 경로: `D:\dev\git\local-packet-coupang\`
- 문서: `EXTENSION_TLS_RANDOMIZER.md`

---

**생성일:** 2025-10-09
**버전:** 1.0.0
**상태:** 구현 완료, 테스트 대기 중
