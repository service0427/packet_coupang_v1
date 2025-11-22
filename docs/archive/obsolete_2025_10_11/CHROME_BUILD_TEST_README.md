# Chrome Build Test - Quick Start Guide

Chrome 빌드별 Akamai 우회 테스트를 위한 빠른 시작 가이드

## 📋 목차

1. [개요](#개요)
2. [설치된 Chrome 빌드](#설치된-chrome-빌드)
3. [빠른 실행](#빠른-실행)
4. [단계별 실행](#단계별-실행)
5. [결과 해석](#결과-해석)
6. [문제 해결](#문제-해결)

## 개요

**목적**: 차단된 IP에서 다른 Chrome 빌드로 우회 가능한지 테스트

**원리**: Akamai는 IP + Browser + Action을 학습
- IP는 변경 불가
- Action은 변경 불가 (메인 → 검색)
- **Browser는 변경 가능** ✅

→ Chrome 빌드를 바꾸면 새로운 TLS 지문으로 인식되어 우회 가능

## 설치된 Chrome 빌드

```
D:\dev\git\local-packet-coupang\chrome-versions\
├── chrome-120.0.6099.109\
├── chrome-121.0.6167.85\
├── chrome-122.0.6261.94\
├── chrome-123.0.6312.86\
├── chrome-124.0.6367.60\
├── chrome-125.0.6422.60\
└── chrome-126.0.6478.61\
```

**총 7개 빌드** (Chrome 120 ~ 126)

## 빠른 실행

### 방법 1: 자동 실행 (추천)

```bash
# PowerShell
.\run_chrome_build_test.ps1

# 또는 Node.js
node run_full_test.js
```

**실행 순서**:
1. IP 강제 차단
2. 차단 상태 확인
3. Chrome 빌드 테스트

**소요 시간**: 약 5~10분

### 방법 2: 단계별 수동 실행

```bash
# 1단계: IP 차단
node force_ip_block.js

# 2단계: 차단 확인
node verify_ip_blocked.js

# 3단계: 빌드 테스트 (1분 이내 실행!)
node test_chrome_builds.js
```

**⚠️  중요**: 2단계와 3단계는 **1분 이내**에 연속 실행해야 합니다!

## 단계별 실행

### 1단계: IP 강제 차단

**스크립트**: `force_ip_block.js`

**동작**:
- 검색 페이지 쿠키 생성
- 10개 키워드로 연속 검색
- HTTP/2 ERROR 발생 시 즉시 중단

**예상 출력**:
```
[KEYWORD 1/10] "게이밍마우스": 10/10 pages ✅
[KEYWORD 2/10] "무선마우스": 10/10 pages ✅
...
[KEYWORD 5/10] "헤드폰":
  [Page 8] ✅ Success
  [Page 9] 🚨 HTTP/2 ERROR

🚨 IP BLOCKED!
Total Pages Requested: 49개
Time to Block: 102.45s

✅ IP is now in BLOCKED state.
Next step: Run verify_ip_blocked.js to confirm.
```

**결과 파일**: `results/force_block_YYYY-MM-DDTHH-MM-SS.json`

### 2단계: 차단 상태 확인

**스크립트**: `verify_ip_blocked.js`

**동작**:
- 검색 요청 1회
- 차단 여부 확인

**예상 출력 (차단됨)**:
```
[VERIFY IP BLOCK STATUS]
[REQUEST] Testing IP block status...
[RESPONSE] Size: 183,621 bytes
[RESULT] ❌ BLOCKED - Response size indicates blocking page

[✅ CONFIRMED] IP is BLOCKED

[NEXT STEP]
Run Chrome build test immediately (within 1 minute):
  node test_chrome_builds.js

[WARNING]
IP block may be released after a few minutes.
Execute Chrome build test as soon as possible!
```

**예상 출력 (차단 안됨)**:
```
[RESULT] ✅ NOT BLOCKED - Request succeeded
Products: 63 ranking + 9 ads

[⚠️  WARNING] IP is NOT BLOCKED

[ACTION REQUIRED]
1. Run force_ip_block.js to block the IP first
```

**결과 파일**: `results/verify_block_YYYY-MM-DDTHH-MM-SS.json`

### 3단계: Chrome 빌드 테스트

**스크립트**: `test_chrome_builds.js`

**동작**:
- Chrome 120~126 순차 테스트
- 각 빌드로 검색 쿠키 생성
- 차단되면 다음 빌드로
- 성공하면 즉시 중단

**예상 출력 (성공)**:
```
[BUILD 1] Chrome 120.0.6099.109
  Browser Mode: ❌ BLOCKED (183KB)

[BUILD 2] Chrome 121.0.6167.85
  Browser Mode: ❌ BLOCKED (183KB)

[BUILD 3] Chrome 122.0.6261.94
  Browser Mode: ✅ SUCCESS (699KB)
  Packet Mode: ✅ SUCCESS (811KB)

🎉 SUCCESS! Found working Chrome build!
Chrome Version: 122.0.6261.94
Ranking Products: 63
Ad Products: 9
```

**예상 출력 (IP 해제됨 - 잘못된 테스트)**:
```
[BUILD 1] Chrome 120.0.6099.109
  Browser Mode: ✅ SUCCESS (699KB)
  Packet Mode: ✅ SUCCESS (811KB)

🎉 SUCCESS! Found working Chrome build!
```
→ **문제**: IP가 이미 해제되어 빌드 효과인지 구분 불가

**결과 파일**: `results/chrome_build_test_YYYY-MM-DDTHH-MM-SS.json`

## 결과 해석

### Case 1: 특정 빌드 성공 (정상)

```
Chrome 120: ❌ BLOCKED
Chrome 121: ❌ BLOCKED
Chrome 122: ✅ SUCCESS  ← 이 빌드로 우회 가능!
```

**의미**: Chrome 122가 차단을 우회할 수 있음

**전략**:
1. Chrome 122를 메인 크롤러로 사용
2. Chrome 122 차단 시 123, 124로 순환
3. 빌드 풀 관리 (120~126 순환)

### Case 2: 모든 빌드 실패

```
Chrome 120: ❌ BLOCKED
Chrome 121: ❌ BLOCKED
...
Chrome 126: ❌ BLOCKED
```

**의미**: Chrome 빌드 변경으로는 우회 불가

**대안**:
1. 프록시 IP 변경 필요
2. IP 풀 구축
3. IP당 요청 제한 관리

### Case 3: 첫 빌드 즉시 성공 (의심)

```
Chrome 120: ✅ SUCCESS (즉시)
```

**의심**: IP가 이미 해제되었을 가능성

**검증**:
1. `verify_ip_blocked.js` 재실행
2. IP 해제 확인 시 처음부터 다시 시작

## 문제 해결

### Q1: IP가 차단되지 않음

**증상**:
```
[KEYWORD 10/10] "충전기": 10/10 pages ✅
[⚠️  WARNING] IP was NOT blocked
```

**원인**: 요청량이 부족

**해결**:
1. `force_ip_block.js`를 다시 실행
2. 또는 `parallel_block_checker.js` 실행 (더 많은 요청)

### Q2: 차단 확인 후 빌드 테스트에서 모두 성공

**증상**:
```
verify_ip_blocked.js: ❌ BLOCKED
test_chrome_builds.js: Chrome 120 ✅ SUCCESS
```

**원인**: verify와 test 사이에 시간이 지나 IP 해제됨

**해결**:
1. 두 스크립트를 **1분 이내**에 연속 실행
2. 또는 `run_full_test.js` 자동 실행 사용

### Q3: 쿠키 파일이 없다는 에러

**증상**:
```
[ERROR] Cookie file not found!
Expected: D:\...\cookies\force_block_test.json
```

**원인**: `force_ip_block.js`를 먼저 실행하지 않음

**해결**:
```bash
node force_ip_block.js
```

### Q4: Chrome 실행 파일을 찾을 수 없음

**증상**:
```
[ERROR] Failed to launch Chrome
Path: D:\...\chrome-versions\chrome-120...
```

**원인**: Chrome 빌드가 설치되지 않음

**해결**:
```powershell
# 특정 버전 설치
.\install-chrome-simple.ps1 -Version "120.0.6099.109"

# 또는 모든 버전 설치
.\install-chrome-builds.ps1 all
```

## 결과 파일 위치

```
D:\dev\git\local-packet-coupang\results\
├── force_block_2025-01-11T08-15-30.json
├── verify_block_2025-01-11T08-17-45.json
└── chrome_build_test_2025-01-11T08-18-20.json
```

**파일 내용**:
- 타임스탬프
- 차단 여부
- 요청 수
- 성공/실패 상세 정보

## 추가 정보

- 상세 프로세스: [CHROME_BUILD_TEST_PROCESS.md](CHROME_BUILD_TEST_PROCESS.md)
- Chrome 빌드 관리: [../install-chrome-builds.ps1](../install-chrome-builds.ps1)
- 쿠키 생성 모듈: [../lib/browser/cookie-generator.js](../lib/browser/cookie-generator.js)
