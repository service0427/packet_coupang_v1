# Chrome Build Test Process

Chrome 빌드별 Akamai 우회 테스트 프로세스 문서

## 테스트 목적

차단된 IP 상태에서 다른 Chrome 빌드로 쿠키를 생성하면 우회 가능한지 검증

## 핵심 원리

**Akamai 학습 메커니즘**: IP + Browser + Action

- **IP**: 변경 불가 (프록시 없이 테스트)
- **Action**: 변경 불가 (메인 → 검색 패턴)
- **Browser**: 변경 가능 ✅ (다른 Chrome 빌드 사용)

→ Chrome 빌드를 바꾸면 **새로운 TLS 지문**으로 인식되어 우회 가능성 존재

## 중요: IP 차단 상태 유지 필수

### ⚠️ 잘못된 테스트 예시

```bash
# 1단계: IP 차단 유도
node parallel_block_checker.js
# → 100페이지 성공... IP 해제된 상태!

# 2단계: Chrome 빌드 테스트
node test_chrome_builds.js
# → Chrome 120 즉시 성공... 하지만 이미 IP 해제된 상태!
```

**문제점**: IP가 해제되어 빌드 효과인지 IP 해제 효과인지 구분 불가

### ✅ 올바른 테스트 프로세스

```bash
# 1단계: IP 강제 차단 (차단될 때까지 실행)
node force_ip_block.js
# → HTTP/2 INTERNAL_ERROR 발생 시까지 반복
# → 차단 확인 후 즉시 중단

# 2단계: 차단 상태 확인
node verify_ip_blocked.js
# → 차단되었는지 1회 검증

# 3단계: Chrome 빌드 테스트 (즉시 실행)
node test_chrome_builds.js
# → 차단된 IP에서 다른 빌드로 우회 시도
```

## 테스트 단계별 상세

### 1단계: IP 강제 차단 (`force_ip_block.js`)

**목적**: IP를 확실히 차단 상태로 만들기

**전략**:
- 검색 페이지에서 쿠키 생성 (첫 키워드)
- 나머지 키워드로 연속 검색
- HTTP/2 ERROR 발생 시 즉시 중단

**중단 조건**:
- `HTTP/2 INTERNAL_ERROR` 감지
- 응답 크기 < 50KB (차단 페이지)
- 에러 발생

**예상 결과**:
```
[KEYWORD 1/10] "게이밍마우스": 10/10 pages ✅
[KEYWORD 2/10] "무선마우스": 10/10 pages ✅
...
[KEYWORD 5/10] "헤드폰": 8/10 pages
  [Page 8] ✅ Success
  [Page 9] 🚨 HTTP/2 ERROR - IP BLOCKED!

[RESULT] IP successfully blocked at page 49
```

### 2단계: 차단 상태 확인 (`verify_ip_blocked.js`)

**목적**: IP가 차단되었는지 검증

**전략**:
- 검색 페이지 1회 요청 (Packet Mode)
- 차단 여부만 확인

**예상 결과**:
```
[VERIFY] Testing IP block status...
[Packet] Request: 테스트키보드
[Result] ❌ BLOCKED - HTTP/2 INTERNAL_ERROR

IP is confirmed BLOCKED. Proceed to Chrome build test.
```

**비차단 시**:
```
[Result] ✅ SUCCESS - 811KB response

⚠️  WARNING: IP is NOT blocked!
Please run force_ip_block.js first.
```

### 3단계: Chrome 빌드 테스트 (`test_chrome_builds.js`)

**목적**: 차단된 IP에서 다른 Chrome 빌드로 우회 가능한지 테스트

**전략**:
1. Chrome 120~126 순차 테스트
2. 각 빌드로 검색 페이지 쿠키 생성
3. 생성 즉시 차단되면 다음 빌드로
4. Packet Mode 테스트
5. 성공하면 즉시 중단

**예상 결과 (차단된 IP)**:
```
[BUILD 1] Chrome 120.0.6099.109
  Browser Mode: ❌ BLOCKED (183KB)
  Skip packet test

[BUILD 2] Chrome 121.0.6167.85
  Browser Mode: ❌ BLOCKED (183KB)
  Skip packet test

[BUILD 3] Chrome 122.0.6261.94
  Browser Mode: ✅ SUCCESS (699KB)
  Packet Mode: ✅ SUCCESS (811KB)

🎉 Chrome 122 bypasses IP block!
```

**예상 결과 (IP 해제된 경우 - 잘못된 테스트)**:
```
[BUILD 1] Chrome 120.0.6099.109
  Browser Mode: ✅ SUCCESS (699KB)
  Packet Mode: ✅ SUCCESS (811KB)

🎉 Chrome 120 works!
```
→ **문제**: 빌드 효과인지 IP 해제 효과인지 알 수 없음

## 실행 스크립트

### 전체 자동 실행

```bash
# Windows PowerShell
.\run_chrome_build_test.ps1

# 또는 Node.js
node run_full_test.js
```

### 단계별 수동 실행

```bash
# 1단계: IP 차단
node force_ip_block.js

# 2단계: 차단 확인
node verify_ip_blocked.js

# 3단계: 빌드 테스트 (차단 확인 후 즉시 실행)
node test_chrome_builds.js
```

## 결과 해석

### Case 1: 모든 빌드 실패
```
Chrome 120: ❌ BLOCKED
Chrome 121: ❌ BLOCKED
Chrome 122: ❌ BLOCKED
...
Chrome 126: ❌ BLOCKED

결론: Chrome 빌드 변경으로는 우회 불가
대안: 프록시 IP 변경 필요
```

### Case 2: 특정 빌드 성공
```
Chrome 120: ❌ BLOCKED
Chrome 121: ❌ BLOCKED
Chrome 122: ✅ SUCCESS

결론: Chrome 122 빌드가 차단 우회 가능
전략: Chrome 122를 메인 크롤러로 사용
      Chrome 122 차단 시 123, 124로 순환
```

### Case 3: 첫 번째 빌드 즉시 성공
```
Chrome 120: ✅ SUCCESS (즉시)

⚠️  경고: IP가 이미 해제되었을 가능성
검증: verify_ip_blocked.js 재실행
조치: force_ip_block.js 먼저 실행
```

## IP 차단 지속 시간

**관찰 결과**:
- **단기 차단**: 수 분 ~ 30분
- **중기 차단**: 30분 ~ 2시간
- **장기 차단**: 2시간 이상

**테스트 타이밍**:
1. IP 차단 후 **즉시** 빌드 테스트 실행
2. 5분 이상 지연 시 IP 해제 가능성 있음
3. 차단 확인 → 빌드 테스트는 **1분 이내** 연속 실행

## 파일 구조

```
D:\dev\git\local-packet-coupang\
├── force_ip_block.js              # IP 강제 차단 스크립트
├── verify_ip_blocked.js           # 차단 상태 확인 스크립트
├── test_chrome_builds.js          # Chrome 빌드 테스트
├── run_full_test.js               # 전체 자동 실행
├── run_chrome_build_test.ps1      # PowerShell 자동 실행
├── lib/
│   └── browser/
│       └── cookie-generator.js    # 쿠키 생성 모듈
├── docs/
│   └── CHROME_BUILD_TEST_PROCESS.md  # 이 문서
└── results/
    ├── force_block_TIMESTAMP.json
    ├── verify_block_TIMESTAMP.json
    └── chrome_build_test_TIMESTAMP.json
```

## 주의사항

1. **IP 해제 오판 방지**: 차단 → 검증 → 테스트를 연속으로 실행
2. **빌드 순서**: 120부터 순차적으로 테스트 (이전 버전이 더 안정적)
3. **쿠키 전략**: 검색 페이지 쿠키 사용 (메인 페이지보다 안정적)
4. **결과 저장**: 모든 단계의 결과를 JSON으로 저장하여 재현 가능
5. **시간 기록**: 각 단계의 타임스탬프 기록으로 IP 해제 여부 판단

## 다음 단계

테스트 결과에 따른 전략:

### 빌드 우회 성공 시
1. 성공한 빌드로 메인 크롤러 구성
2. 빌드 풀 관리 (120~126 순환)
3. 각 빌드당 차단 임계값 측정

### 빌드 우회 실패 시
1. 프록시 IP 풀 구축
2. IP당 요청 제한 관리
3. IP 순환 전략 수립
