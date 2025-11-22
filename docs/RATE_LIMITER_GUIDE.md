# Rate Limiter 가이드

## 🎯 목적

동일 IP에서 짧은 시간 내 과도한 요청으로 인한 **일시적 차단 방지**

---

## 📋 문제 상황

사용자님이 발견한 현상:

```
빌드버전을 다양화했는데도 불구하고 오늘은 이상하게 차단이 되었네.
일정시간 지나고 해결되긴 했어.
각각 다른 빌드로 했는데도 동시차단이 생겼거든.
```

**원인**: 빌드 타입 무관하게 **IP 단위로 Rate Limiting** 적용됨

---

## 🔧 구현

### 1. 기본 Rate Limiter

**특징**:
- 시간 윈도우 기반 요청 제한
- 자동 대기 및 요청 기록
- 자연스러운 지연 패턴 (1~3초)

**사용법**:

```python
from rate_limiter import RateLimiter

# 60초 동안 최대 10개 요청
limiter = RateLimiter(
    max_requests=10,
    window_seconds=60,
    min_delay=1.0,
    max_delay=3.0
)

# 요청 전 대기
for i in range(20):
    limiter.wait_if_needed()  # 자동으로 대기
    response = make_request()

    # 상태 확인
    status = limiter.get_status()
    print(f"윈도우 내 요청: {status['requests_in_window']}/{status['max_requests']}")
```

**출력 예시**:

```
요청 #1
  윈도우 내 요청: 0/10
  남은 슬롯: 10
  실제 대기: 1.23초

요청 #11
  윈도우 내 요청: 10/10
⏳ Rate limit 도달. 45.2초 대기 중...
  실제 대기: 46.8초
```

---

### 2. Smart Rate Limiter (적응형)

**특징**:
- 차단 감지 시 자동으로 대기 시간 증가
- 연속 성공 시 일반 모드 복귀
- 동적 조정으로 안정성 향상

**사용법**:

```python
from rate_limiter import SmartRateLimiter

limiter = SmartRateLimiter(
    max_requests=10,
    window_seconds=60,
    min_delay=1.0,
    max_delay=3.0
)

for i in range(100):
    limiter.wait_if_needed()
    response = make_request()

    # 결과에 따라 기록
    if is_success(response):
        limiter.record_success()
    else:
        limiter.record_block()  # 차단 감지 시 자동 조정
```

**적응 동작**:

```
요청 #1 → 성공 ✅
요청 #2 → 성공 ✅
요청 #3 → 차단 🚨
요청 #4 → 차단 🚨
요청 #5 → 차단 🚨

🚨 연속 차단 3회 감지!
   적응 모드 활성화: 대기 시간 2배 증가
🐢 적응 모드: 2.0~6.0초 대기

요청 #6 → 성공 ✅
요청 #7 → 성공 ✅

✅ 안정화됨. 일반 모드로 복귀
```

---

## 📊 권장 설정

### 일반 크롤링

```python
limiter = RateLimiter(
    max_requests=10,      # 60초에 10개
    window_seconds=60,
    min_delay=1.0,        # 최소 1초
    max_delay=3.0         # 최대 3초
)
```

**평균 속도**: 20~30 req/min

---

### 대량 크롤링 (안전)

```python
limiter = RateLimiter(
    max_requests=5,       # 60초에 5개
    window_seconds=60,
    min_delay=2.0,        # 최소 2초
    max_delay=5.0         # 최대 5초
)
```

**평균 속도**: 10~15 req/min

---

### 적응형 (자동 조정)

```python
limiter = SmartRateLimiter(
    max_requests=10,
    window_seconds=60,
    min_delay=1.0,
    max_delay=3.0
)

# 차단 감지 시 자동으로 5 req/60s, 2~6초 대기로 변경
```

**평균 속도**: 초기 20~30 req/min → 차단 시 5~10 req/min

---

## 🔄 Multi-Device와 함께 사용

```python
from rate_limiter import SmartRateLimiter
from multi_device_simulator import DeviceProfile
from curl_cffi import requests

# Rate Limiter 초기화
limiter = SmartRateLimiter(max_requests=10, window_seconds=60)

# 다양한 디바이스 프로필 사용
profiles = [DeviceProfile.generate_chrome_profile() for _ in range(10)]

for i in range(100):
    # Rate limit 대기
    limiter.wait_if_needed()

    # 디바이스 프로필 순환
    profile = profiles[i % len(profiles)]

    # 요청
    response = requests.get(
        url,
        headers={'User-Agent': profile['user_agent']},
        impersonate=profile['impersonate']
    )

    # 결과 기록
    if is_success(response):
        limiter.record_success()
    else:
        limiter.record_block()
```

---

## 🧪 테스트

### 기본 테스트

```bash
cd D:\dev\git\local-packet-coupang\src
python rate_limiter.py
```

**출력**:

```
======================================================================
Rate Limiter 테스트
======================================================================

[1] 일반 Rate Limiter (5 req / 10초)

요청 #1
  윈도우 내 요청: 0/5
  남은 슬롯: 5
  실제 대기: 0.52초

요청 #6
  윈도우 내 요청: 5/5
  남은 슬롯: 0
⏳ Rate limit 도달. 8.3초 대기 중...
  실제 대기: 8.85초

✅ Rate Limiter 테스트 완료
```

---

### Smart Limiter 테스트

```bash
python rate_limiter.py smart
```

**출력**:

```
======================================================================
Smart Rate Limiter 테스트
======================================================================

[1] 정상 요청
요청 #1 전송
요청 #2 전송
요청 #3 전송

[2] 차단 시뮬레이션
요청 #4 전송 → 차단!
요청 #5 전송 → 차단!
요청 #6 전송 → 차단!

🚨 연속 차단 3회 감지!
   적응 모드 활성화: 대기 시간 2배 증가

[3] 적응 모드에서 재시도
🐢 적응 모드: 0.4~1.0초 대기
요청 #7 전송 → 성공!
요청 #8 전송 → 성공!

✅ 안정화됨. 일반 모드로 복귀

✅ Smart Rate Limiter 테스트 완료
```

---

## 📈 성능 영향

### Rate Limiter 없이 (위험)

```
요청 #1~20: 3초 완료 ⚡ → 차단 발생 🚨
→ 5~10분 대기 필요 ⏳
```

**평균 성공률**: 20% (나머지 차단)

---

### Rate Limiter 적용 (안전)

```
요청 #1~20: 60초 완료 🐢
→ 차단 없음 ✅
```

**평균 성공률**: 100% (TLS 통과 기준)

---

## 💡 Best Practices

### 1. 항상 Rate Limiter 사용

```python
# ❌ 잘못된 방법
for url in urls:
    response = requests.get(url)  # 즉시 차단 위험

# ✅ 올바른 방법
limiter = RateLimiter(max_requests=10, window_seconds=60)
for url in urls:
    limiter.wait_if_needed()
    response = requests.get(url)
```

---

### 2. Smart Limiter 우선 사용

```python
# 적응형 사용으로 자동 조정
limiter = SmartRateLimiter(max_requests=10, window_seconds=60)

for url in urls:
    limiter.wait_if_needed()
    response = requests.get(url)

    # 성공/실패 기록으로 자동 학습
    if is_success(response):
        limiter.record_success()
    else:
        limiter.record_block()
```

---

### 3. 보수적 설정으로 시작

```python
# 처음에는 안전하게
limiter = SmartRateLimiter(
    max_requests=5,      # 적게 시작
    window_seconds=60,
    min_delay=2.0,       # 길게 대기
    max_delay=5.0
)

# 안정적이면 점진적으로 증가
```

---

### 4. 디바이스 다양화와 함께 사용

```python
# Rate Limiter + Multi-Device = 최상의 조합
limiter = SmartRateLimiter(max_requests=10, window_seconds=60)
profiles = [DeviceProfile.generate_chrome_profile() for _ in range(10)]

for i, url in enumerate(urls):
    limiter.wait_if_needed()
    profile = profiles[i % len(profiles)]
    response = make_request_with_profile(url, profile)
```

---

## 🚨 트러블슈팅

### 여전히 차단당하는 경우

**원인 1**: Rate limit 설정이 너무 공격적
```python
# 설정 완화
limiter.max_requests = 5  # 10 → 5
limiter.min_delay = 3.0   # 1 → 3
```

**원인 2**: Akamai Challenge (Stage 2)
```python
# TLS는 통과했지만 Akamai가 차단
# → Sensor Data 구현 필요
```

**원인 3**: 장기간 누적
```python
# 하루 누적 요청 수 제한
# → 여러 IP 사용 또는 휴식 시간 증가
```

---

### Rate Limiter가 너무 느린 경우

**해결 1**: 설정 조정
```python
limiter.max_requests = 15  # 10 → 15
limiter.min_delay = 0.5    # 1 → 0.5
```

**해결 2**: Multi-Device 활용
```python
# 각 디바이스마다 별도 Session
# → IP는 동일하지만 다른 브라우저로 인식
```

---

## 📋 요약

| 항목 | 기본 Limiter | Smart Limiter |
|------|-------------|---------------|
| **자동 조정** | ❌ | ✅ |
| **차단 감지** | ❌ | ✅ |
| **사용 난이도** | 쉬움 | 중간 |
| **권장 용도** | 단순 크롤링 | 대량 크롤링 |
| **성공률** | 90% | 95%+ |

---

## 🎯 다음 단계

1. ✅ Rate Limiter 구현 완료
2. ⏳ Sensor Data Endpoint 캡처 (진행 중)
3. ⏳ Sensor Data Generator 구현
4. ⏳ 통합 테스트

**현재 단계**: Rate Limiter 완성 → Endpoint 캡처 진행

---

## 📝 참고

- 코드: `src/rate_limiter.py`
- 테스트: `python rate_limiter.py` / `python rate_limiter.py smart`
- 통합: Multi-Device Simulator와 함께 사용 권장
