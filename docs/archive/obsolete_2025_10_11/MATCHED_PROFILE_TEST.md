# Matched Profile Test - Browser + curl-cffi 프로필 매칭

## 핵심 발견 (Sequential Build Test)

이전 테스트에서:
- **Browser Mode**: Chrome 123~120으로 차단 우회 성공 ✅
- **Packet Mode**: 모든 빌드에서 실패 ❌

## 새로운 가설

**문제점**: Browser와 curl-cffi의 TLS 핑거프린트 불일치

```
Browser: Chrome 123 → Akamai 통과
curl-cffi: chrome120 프로필 사용 → Akamai 차단

불일치 탐지: 같은 쿠키인데 TLS 핑거프린트가 다름 → 의심 → 차단
```

**해결책**: Browser 빌드와 curl-cffi 프로필 매칭

```
Browser: Chrome 123
curl-cffi: chrome123 프로필
→ TLS 핑거프린트 일치 → Akamai 통과 가능성 ⬆️
```

## curl-cffi 지원 프로필

```python
chrome99, chrome100, chrome101, chrome104, chrome107, chrome110,
chrome116, chrome119, chrome120, chrome123, chrome124,
chrome131, chrome133a, chrome136
```

## 테스트 매칭 조합

| Browser | curl-cffi Profile | 매칭 상태 | 우선순위 |
|---------|-------------------|-----------|----------|
| Chrome 123 | chrome123 | ✅ 정확 매칭 | 1 (최우선) |
| Chrome 124 | chrome124 | ✅ 정확 매칭 | 2 |
| Chrome 122 | chrome120 | ⚠️ 근사 매칭 | 3 |
| Chrome 121 | chrome120 | ⚠️ 근사 매칭 | 4 |
| Chrome 120 | chrome120 | ✅ 정확 매칭 | 5 |
| Chrome 141 | chrome131 | ⚠️ 근사 매칭 | 6 |

## 예상 시나리오

### 시나리오 A: 정확 매칭 성공 🎯
```
Browser: Chrome 123
curl-cffi: chrome123
→ Browser Mode: ✅ 성공
→ Packet Mode: ✅ 성공 (TLS 핑거프린트 일치)
→ 결론: 하이브리드 모드 가능!
```

### 시나리오 B: 근사 매칭 성공
```
Browser: Chrome 122
curl-cffi: chrome120
→ Browser Mode: ✅ 성공
→ Packet Mode: ✅ 성공 (충분히 유사한 핑거프린트)
→ 결론: 2버전 차이까지 허용
```

### 시나리오 C: 매칭해도 실패
```
모든 조합에서 Packet Mode 실패
→ 결론: Akamai는 쿠키와 TLS 외에 다른 요소도 검증
→ 순수 Browser Mode만 가능
```

## 실행 방법

```bash
# 1. IP가 차단된 상태에서 시작 (중요!)
node verify_ip_blocked.js

# 2. 매칭 프로필 테스트 실행
node matched_profile_test.js
```

## 성공 시 활용 방안

### 하이브리드 모드 (Browser + Packet)
```javascript
// Phase 1: Browser Mode로 쿠키 생성
const cookies = await generateCookies({
  browserVersion: '123',
  strategy: 'search'
});

// Phase 2: Packet Mode로 고속 크롤링
const results = await packetCrawl({
  cookies: cookies,
  curlProfile: 'chrome123',  // ← 매칭된 프로필 사용
  pages: 100
});
```

### 빌드 로테이션 전략
```
1. Chrome 123 + chrome123 → 100 페이지 크롤링
2. 차단 발생
3. Chrome 124 + chrome124 → 100 페이지 크롤링
4. 차단 발생
5. Chrome 120 + chrome120 → 100 페이지 크롤링
...
```

## 기대 효과

- **성공 시**: 하이브리드 모드 가능 → 3-5배 속도 향상
- **실패 시**: Browser Mode만 사용 + 빌드 로테이션으로 처리량 증가
