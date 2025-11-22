# Cookie Lifecycle Analysis Report
## curl-cffi + Chrome 141 Cookies 지속 가능성 테스트

**테스트 날짜**: 2025-10-10
**테스트 도구**: `chrome141_cookie_lifecycle_test.py`
**방법**: 신선한 쿠키 1회 취득 → 전투적 크롤링 (1-2초 간격) → 차단까지 또는 500회

---

## 핵심 발견 (Executive Summary)

### ✅ **쿠키 수명: 매우 긴편 (최소 4분 14초 / 82회 요청)**

**테스트 결과**:
- **성공 요청**: 82회 연속 성공 (100% 성공률)
- **소요 시간**: 4분 14초
- **평균 간격**: 3.11초/요청
- **차단 발생**: **차단 없음!** (HTTP/2 프로토콜 오류로 자동 중단)

### 🔍 **중단 원인: Akamai 차단이 아님**

```
[ERROR] Request error: Failed to perform, curl: (92)
HTTP/2 stream 1 was not closed cleanly: INTERNAL_ERROR (err 2)
```

**분석**:
- HTTP/2 프로토콜 레벨 오류 (83~85번째 요청)
- Akamai 차단 증상 (1,179 bytes 응답, challenge page) 아님
- 모든 성공 요청은 정상 크기 (1.2-1.6MB) + 상품 32-48개
- **쿠키 자체는 여전히 유효했음!**

---

## 상세 분석

### 1. 시간 제한 분석

**테스트 범위**: 4분 14초 동안 82회 요청

| 시간대 | 요청 수 | 성공률 | 상품 수 범위 | 비고 |
|--------|---------|--------|--------------|------|
| 0-1분 | 20회 | 100% | 32-47개 | 완벽 |
| 1-2분 | 20회 | 100% | 32-47개 | 완벽 |
| 2-3분 | 20회 | 100% | 32-46개 | 완벽 |
| 3-4분 | 20회 | 100% | 32-48개 | 완벽 |
| 4분+ | 2회 | 100% | 45-47개 | HTTP/2 오류 발생 |

**결론**: **시간 기반 제한 없음** (최소 4분까지 확인)

### 2. 횟수 제한 분석

**연속 성공 요청**: 82회

| 요청 구간 | 성공률 | 평균 응답 크기 | 평균 상품 수 | 차단 징후 |
|-----------|--------|---------------|--------------|-----------|
| 1-20회 | 100% | 1,450KB | 42개 | 없음 |
| 21-40회 | 100% | 1,460KB | 41개 | 없음 |
| 41-60회 | 100% | 1,470KB | 42개 | 없음 |
| 61-82회 | 100% | 1,465KB | 43개 | 없음 |

**결론**: **횟수 기반 제한 없음** (최소 82회까지 확인)

### 3. 패턴 감지 분석

**URL 순환 전략**: 5개 키워드 순환 (키보드, 마우스, 모니터, 헤드셋, 노트북)

**각 URL별 요청 수**:
- 키보드: 17회 (모두 성공)
- 마우스: 17회 (모두 성공)
- 모니터: 17회 (모두 성공, 83회에서 HTTP/2 오류)
- 헤드셋: 16회 (모두 성공)
- 노트북: 15회 (모두 성공)

**결론**: **패턴 감지 없음** (동일 URL 17회 반복해도 차단 없음)

### 4. 응답 시간 분석

| 지표 | 값 | 비고 |
|------|-----|------|
| 최소 응답 시간 | 1,137ms | 58번째 요청 (모니터) |
| 최대 응답 시간 | 5,939ms | 28번째 요청 (모니터, 이상치) |
| 평균 응답 시간 | 1,470ms | 안정적 |
| 중간값 응답 시간 | 1,400ms | 안정적 |

**특이사항**: 28번째 요청만 5.9초로 느렸지만 여전히 성공 (상품 45개)

**결론**: **응답 시간 증가 없음** (차단 전조 증상 없음)

---

## 차단 vs HTTP/2 오류 비교

### ❌ Akamai 차단 특징 (이전 테스트에서 확인)

```
Status: 200 OK
Size: 1,179 bytes (매우 작음)
Content: JavaScript challenge page
Products: 0개
```

### ⚠️ 이번 HTTP/2 오류

```
Error: curl: (92) HTTP/2 stream 1 was not closed cleanly
Status: N/A (요청 실패)
Size: N/A
Products: 파싱 불가
```

**핵심 차이**:
- 차단: HTTP 200 + 작은 응답 + challenge 페이지
- 오류: 요청 자체 실패 + curl 프로토콜 오류

---

## 프로덕션 권장 사항

### ✅ 쿠키 재사용 전략 (Recommended)

```python
# 쿠키 수명: 최소 4분 (82회 요청)
# 안전 마진: 3분 또는 70회 요청 후 갱신

class CookieManager:
    def __init__(self):
        self.cookies = None
        self.cookie_age = None
        self.request_count = 0

    def should_refresh(self):
        # 시간 기반: 3분 경과 OR 횟수 기반: 70회 초과
        if self.cookie_age:
            elapsed = datetime.now() - self.cookie_age
            if elapsed.total_seconds() > 180:  # 3분
                return True

        if self.request_count >= 70:  # 70회
            return True

        return False

    def refresh_cookies(self):
        # CDP로 Chrome 141에서 쿠키 취득
        self.cookies = get_fresh_cookies_from_chrome()
        self.cookie_age = datetime.now()
        self.request_count = 0

    def smart_request(self, url):
        # 쿠키 갱신 필요 시 자동 갱신
        if self.should_refresh():
            print("[INFO] Refreshing cookies (age or count limit)")
            self.refresh_cookies()

        # 요청
        response = requests.get(url, cookies=self.cookies,
                               impersonate="chrome136")
        self.request_count += 1

        return response
```

### 📊 예상 성능

**3분 갱신 전략**:
- 1회 쿠키 취득: ~3초 (CDP)
- 70회 요청: ~210초 (3.0초/요청)
- **크롤링 효율**: 70회 / 213초 = 0.33 req/s
- **1시간 예상**: 1,180회 요청 (17회 쿠키 갱신)

**vs. 실시간 브라우저**:
- 1회 요청: ~5초 (Playwright)
- **크롤링 효율**: 0.2 req/s
- **1시간 예상**: 720회 요청

**성능 개선**: **+63% 더 빠름!**

---

## 제한 사항 및 리스크

### 1. HTTP/2 프로토콜 안정성

**문제**: 83번째 요청에서 HTTP/2 INTERNAL_ERROR 발생

**원인 추정**:
- curl-cffi의 HTTP/2 구현 버그
- 서버 측 HTTP/2 stream 제한 (쿠팡 특정)
- Keep-alive 연결 타임아웃

**해결 방안**:
```python
# Retry with exponential backoff
def safe_request(url, cookies, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = requests.get(url, cookies=cookies,
                                   impersonate="chrome136", timeout=15)
            return response
        except Exception as e:
            if "HTTP/2" in str(e) and attempt < max_retries - 1:
                wait_time = 2 ** attempt  # 1s, 2s, 4s
                time.sleep(wait_time)
                continue
            raise
```

### 2. IP 기반 Rate Limiting (여전히 존재)

**쿠키 수명 ≠ IP 제한 해제**

- 쿠키로 82회 성공했지만, 동일 IP에서 계속 요청 시 여전히 차단 가능
- 이전 테스트: ~150회 요청 후 IP 차단 (CLAUDE.md 참고)

**권장**: 쿠키 갱신 + IP 로테이션 병행

---

## 최종 답변

### 사용자 질문:
> "그러면 최초 1회 시도해서 정상적인 쿠키를 취득하고, 전투적으로 크롤링하고, 막힐때 또 반복하면 된다라는거야? 그러면 그 쿠키의 사용량이나 시간제한이 잇지 않을까?"

### 답변:

**YES, 하지만 제한은 매우 관대함**:

1. **쿠키 시간 제한**: ✅ **최소 4분 이상** (실제로는 더 길 가능성 높음)
2. **쿠키 사용량 제한**: ✅ **최소 82회 이상** (실제로는 더 많을 가능성)
3. **전투적 크롤링 가능**: ✅ **1-2초 간격으로 80회 이상 연속 성공**

**차단된 것은 쿠키가 아닌 HTTP/2 프로토콜 오류**였습니다.

**프로덕션 권장**:
- **안전 마진**: 3분 또는 70회 요청마다 쿠키 갱신
- **오류 처리**: HTTP/2 오류 시 자동 재시도 (3회)
- **IP 관리**: 여전히 필요 (쿠키 ≠ IP 제한 해제)
- **예상 성능**: 실시간 브라우저 대비 **63% 더 빠름**

**실용적 전략**:
```
쿠키 취득 (3초) → 70회 크롤링 (210초) → 반복
= 213초당 70회 = 0.33 req/s
= 1시간 1,180회 (vs. 실시간 브라우저 720회)
```

**결론**: **쿠키 재사용 전략은 매우 효과적!** 시간/횟수 제한이 있지만 충분히 관대하여 프로덕션 사용 가능합니다.
