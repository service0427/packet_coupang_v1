# Akamai Rate Limiting 분석 및 대응

## 문제 확인

### 증상
- **Real Chrome CDP 방식**: 초기에는 100% 성공하지만 일정 사용량 이후 HTTP/2 INTERNAL_ERROR 발생
- **다른 빌드 사용해도**: IP가 동일하면 차단됨
- **TLS는 통과**: Stage 1(TLS)은 문제없지만 Stage 2(Akamai)에서 차단

### 차단 메커니즘

```
TLS 통과 (✅)
  ↓
Akamai Bot Manager 검사
  ↓
┌─────────────────────────────────┐
│ 1. JavaScript Challenge (1차)   │ ← 쿠키로 통과 가능
│ 2. Rate Limiting (2차)          │ ← IP 기반, 행동 패턴 분석
│ 3. HTTP/2 Protocol Blocking (3차)│ ← 심각한 차단
└─────────────────────────────────┘
```

## Akamai가 추적하는 지표

### 1. **IP 주소** (최우선)
- 동일 IP에서의 요청 횟수
- 시간당 요청 수 (requests per hour)
- IP별 누적 사용량

### 2. **요청 패턴**
- 요청 간격 (너무 규칙적이면 봇으로 판단)
- URL 패턴 (동일 패턴 반복)
- Referer 흐름 (자연스러운 탐색 여부)

### 3. **시간 기반 제한**
- 1분당 요청 수
- 1시간당 요청 수
- 24시간 누적량

### 4. **세션 특성**
- 쿠키 수명
- User-Agent 일관성
- TLS/HTTP/2 지문 일관성

## 테스트 결과

### Real Chrome CDP (smart_chrome_manager.js)
```
초기: 5/5 성공 (100%)
   ↓
누적 사용 후: HTTP/2 INTERNAL_ERROR 발생
```

### Pure Packet (curl-cffi)
```
1차: 1/5 성공 (20%)
2-5차: HTTP/2 INTERNAL_ERROR
```

### Hybrid Cookie Mode
```
Browser: 1/1 성공
Packet (쿠키 재사용): 0/4 성공 (모두 HTTP/2 Error)
```

## 핵심 결론

**쿠키나 TLS 지문보다 IP 기반 Rate Limiting이 핵심 차단 요소입니다.**

## 대응 전략

### 전략 1: Rate Limiting 준수 (권장)
```javascript
// smart_chrome_manager.js 기반
{
  maxRequestsPerMinute: 5,        // 10 → 5로 감소
  minDelay: 5000,                 // 최소 5초 대기
  maxDelay: 10000,                // 최대 10초 대기
  randomDelay: true               // 랜덤 지연
}
```

**장점**:
- Real Chrome CDP 100% 성공률 유지
- 안정적인 장기 실행
- IP 차단 회피

**단점**:
- 속도 느림 (분당 5-6회)

### 전략 2: Proxy/VPN Rotation (고급)
```javascript
{
  proxyList: [
    'http://proxy1:port',
    'http://proxy2:port',
    'http://proxy3:port'
  ],
  rotationInterval: 10,  // 10회마다 IP 변경
  cooldownTime: 300000   // 5분 휴식
}
```

**장점**:
- IP 분산으로 차단 회피
- 높은 처리량 가능

**단점**:
- Proxy 비용
- 구현 복잡도

### 전략 3: Human-like Behavior (최선)
```javascript
{
  // 자연스러운 탐색 시뮬레이션
  randomizeSearchTerms: true,
  varyRequestTiming: true,
  includePageNavigation: true,
  simulateMouseMovement: true,

  // 휴식 시간
  sessionDuration: 30 * 60 * 1000,  // 30분 세션
  breakDuration: 10 * 60 * 1000,    // 10분 휴식
}
```

**장점**:
- 가장 자연스러움
- 장기 안정성

**단점**:
- 복잡한 구현
- 속도 제한

## 권장 솔루션

### 단기 (즉시 적용 가능)

**smart_chrome_manager.js Rate Limiter 강화**

```javascript
class SmartRateLimiter {
    constructor() {
        this.minDelay = 5000;          // 최소 5초
        this.maxDelay = 10000;         // 최대 10초
        this.requestsPerHour = 60;     // 시간당 60회
        this.hourlyRequests = [];

        // 누적 감지
        this.consecutiveErrors = 0;
        this.backoffMultiplier = 1;
    }

    async waitIfNeeded() {
        // 시간당 제한 체크
        const now = Date.now();
        const oneHourAgo = now - 3600000;
        this.hourlyRequests = this.hourlyRequests.filter(t => t > oneHourAgo);

        if (this.hourlyRequests.length >= this.requestsPerHour) {
            const waitTime = this.hourlyRequests[0] + 3600000 - now;
            console.log(`⏳ 시간당 제한 도달. ${Math.round(waitTime/1000)}초 대기...`);
            await new Promise(resolve => setTimeout(resolve, waitTime));
        }

        // 랜덤 대기 (백오프 적용)
        const baseDelay = this.minDelay + Math.random() * (this.maxDelay - this.minDelay);
        const actualDelay = baseDelay * this.backoffMultiplier;

        console.log(`⏳ ${Math.round(actualDelay/1000)}초 대기...`);
        await new Promise(resolve => setTimeout(resolve, actualDelay));

        this.hourlyRequests.push(Date.now());
    }

    recordError() {
        this.consecutiveErrors++;

        // 연속 오류 시 백오프 증가
        if (this.consecutiveErrors >= 3) {
            this.backoffMultiplier = Math.min(this.backoffMultiplier * 2, 8);
            console.log(`🚨 연속 오류 감지. 백오프: ${this.backoffMultiplier}x`);
        }
    }

    recordSuccess() {
        this.consecutiveErrors = 0;

        // 성공 시 백오프 점진적 감소
        if (this.backoffMultiplier > 1) {
            this.backoffMultiplier = Math.max(this.backoffMultiplier * 0.8, 1);
        }
    }
}
```

### 중기 (1-2일 구현)

**세션 관리 + 자동 휴식**

```javascript
class SessionManager {
    constructor() {
        this.sessionStart = Date.now();
        this.sessionDuration = 30 * 60 * 1000;  // 30분
        this.breakDuration = 10 * 60 * 1000;    // 10분
        this.requestCount = 0;
    }

    async checkSession() {
        const elapsed = Date.now() - this.sessionStart;

        // 30분 세션 종료 → 10분 휴식
        if (elapsed > this.sessionDuration) {
            console.log('🛑 세션 종료. 10분 휴식...');
            await new Promise(resolve => setTimeout(resolve, this.breakDuration));

            this.sessionStart = Date.now();
            this.requestCount = 0;
            console.log('✅ 세션 재시작');
        }
    }
}
```

### 장기 (1주 구현)

**Proxy Rotation + Human Behavior Simulation**

## 실험 데이터

### Rate Limit 추정

| 시간 윈도우 | 추정 제한 | 근거 |
|------------|----------|------|
| 1분 | ~10회 | 초과 시 Challenge 증가 |
| 1시간 | ~100회 | 초과 시 HTTP/2 Error |
| 24시간 | ~1000회 | 누적 시 IP 차단 |

**주의**: 이는 추정치이며 실제 제한은 더 복잡한 알고리즘 사용

## 다음 단계

1. ✅ **smart_chrome_manager.js에 Rate Limiter 강화** (즉시)
2. 📋 세션 관리 추가 (1-2일)
3. 📋 자동 백오프 로직 (1-2일)
4. 📋 Proxy Rotation (선택사항, 1주)

## 핵심 교훈

> **"TLS 통과는 필요조건이지만, Akamai Rate Limiting 우회가 충분조건이다."**

- TLS/HTTP/2 지문은 통과했지만 IP 기반 Rate Limiting이 핵심
- Real Chrome도 일정 사용량 이후 차단됨
- 쿠키 재사용만으로는 불충분 (HTTP/2 레벨 차단)
- **해결책**: Rate Limiting 준수 + 자연스러운 행동 패턴 시뮬레이션
