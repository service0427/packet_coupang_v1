# Chrome Build Bypass Test - 시나리오 문서

## 테스트 목적

Akamai IP 차단 상태에서 Chrome 빌드 번호를 변경하여 차단을 우회할 수 있는지 검증

## 핵심 가설

- **가설**: Chrome의 빌드 번호가 다르면 TLS 핑거프린트가 달라져서 Akamai가 "새로운 브라우저"로 인식할 수 있다
- **검증 방법**: 차단된 IP에서 다른 빌드로 쿠키를 생성하여 패킷 모드로 우회 시도

## 테스트 시나리오

### Phase 1: Initial Block (141 버전)
```
1. IP 해제 상태 확인 (verify_ip_blocked.js)
2. Chrome 141로 쿠키 생성 (검색 페이지)
3. 패킷 모드로 연속 요청
4. 차단 발생 대기 (~100 페이지)
```

### Phase 2: Build Rotation (140 → 120)
```
각 빌드마다:
1. Browser Mode: 검색 페이지 접속 시도
   - 성공 → 2단계 진행
   - 실패 → 다음 빌드로 이동 (패킷 모드 시도 안함)

2. Packet Mode: 생성된 쿠키로 패킷 요청
   - 성공 → ✅ 우회 성공! 테스트 종료
   - 실패 → 다음 빌드로 이동

3. 다음 빌드 (N-1)로 반복
```

## 성공 조건

**우회 성공**:
- 차단된 IP 상태에서
- 새로운 빌드로 검색 페이지 접속 성공 AND
- 해당 쿠키로 패킷 모드 요청 성공

**우회 실패**:
- 모든 빌드(141 → 120)에서 검색 실패 OR
- 검색은 성공하지만 패킷 모드는 모두 실패

## 테스트 파일 구조

### 1. `sequential_build_test.js` (NEW)
- 메인 테스트 로직
- 141 → 120 순차 테스트
- 성공 시 즉시 종료

### 2. `verify_ip_blocked.js` (EXISTING)
- IP 차단 상태 확인
- 테스트 전 필수 실행

### 3. `force_ip_block.js` (EXISTING)
- IP 강제 차단 (Phase 1)
- Chrome 141 사용

## Chrome Builds

```javascript
const CHROME_BUILDS = [
  { version: '141', path: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe' }, // 현재 설치된 버전
  { version: '140', path: 'D:\\dev\\git\\local-packet-coupang\\chrome-versions\\chrome-140...\\chrome.exe' },
  { version: '139', path: '...' },
  // ... 120까지
];
```

## 중요 사항

### 1. 시간 제약
- IP 차단 해제까지: 수분 ~ 수십분
- 테스트는 차단 상태가 유지되는 동안 신속히 진행

### 2. 쿠키 전략
- **Strategy**: 'search' (검색 페이지까지 진행)
- **이유**: 메인 페이지만으로는 직관적 판단 어려움

### 3. 패킷 모드 검증
- 단일 요청이 아닌 **여러 페이지** 요청 (최소 3-5페이지)
- HTTP/2 ERROR 발생 시 즉시 실패 판정

## 예상 결과

### 시나리오 A: 빌드 우회 성공
```
Chrome 141 → 차단 발생
Chrome 140 → 검색 성공 + 패킷 성공 ✅
결론: 빌드 로테이션으로 우회 가능
```

### 시나리오 B: 브라우저만 성공
```
Chrome 141 → 차단 발생
Chrome 140 → 검색 성공 + 패킷 실패
Chrome 139 → 검색 성공 + 패킷 실패
...
결론: 브라우저 모드는 우회, curl-cffi는 차단
```

### 시나리오 C: 완전 실패
```
Chrome 141 → 차단 발생
Chrome 140 → 검색 실패
Chrome 139 → 검색 실패
...
결론: 빌드 변경으로 우회 불가
```

## 데이터 수집

### 각 빌드마다 저장
```json
{
  "timestamp": "2025-10-11T...",
  "build": "140",
  "browserMode": {
    "success": true,
    "pageSize": 705000,
    "cookieCount": 63
  },
  "packetMode": {
    "success": false,
    "error": "HTTP/2 INTERNAL_ERROR",
    "pagesAttempted": 1
  }
}
```

## 실행 방법

```bash
# 1. IP 해제 상태 확인
node verify_ip_blocked.js

# 2. Chrome 141로 차단 유발 (선택사항)
node force_ip_block.js

# 3. 순차 빌드 테스트
node sequential_build_test.js
```
