# 🚨 HTTP Header Policy - 절대 위반 금지

**작성일**: 2025-10-10
**테스트 환경**: Windows 10, curl-cffi, Chrome 141

---

## ⚠️ 핵심 정책

### ❌ 절대 하지 말아야 할 것

1. **커스텀 헤더 추가 금지**
   - `user-agent` 커스텀 설정 ❌
   - `sec-ch-ua` 커스텀 설정 ❌
   - `sec-ch-ua-platform` 커스텀 설정 ❌
   - `sec-ch-ua-mobile` 커스텀 설정 ❌
   - 기타 모든 헤더 커스텀 ❌

2. **프로필 기본값 사용 필수**
   - curl-cffi의 `impersonate` 프로필 기본 헤더만 사용 ✅
   - 헤더를 명시적으로 추가하지 말 것 ✅

### ✅ 올바른 사용법

```python
# ✅ 올바른 방법
response = requests.get(
    url,
    impersonate='chrome124',  # 프로필만 지정
    cookies=cookie_dict,
    timeout=15
)

# ❌ 잘못된 방법
response = requests.get(
    url,
    impersonate='chrome124',
    headers={  # 헤더 추가 금지!
        'user-agent': '...',
        'sec-ch-ua': '...'
    },
    cookies=cookie_dict
)
```

---

## 📊 실험 결과

### 테스트 1: 프로필 기본 헤더 (성공)

**설정**:
```python
impersonate='chrome124'  # 헤더 추가 없음
```

**결과**:
- chrome124: ✅ 성공 (1363KB)
- chrome131: ✅ 성공 (1363KB)
- chrome120: ✅ 성공 (1363KB)

### 테스트 2: Chrome 헤더 복제 (실패)

**설정**:
```python
impersonate='chrome124'
headers={
    'sec-ch-ua': '"Google Chrome";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'user-agent': 'Mozilla/5.0 ... Chrome/141.0.0.0 ...',
    # ... 기타
}
```

**결과**:
- 모든 프로필: ❌ 차단 (1143B 차단 페이지)

### 테스트 3: 개별 헤더 영향

| 헤더 | 결과 | 비고 |
|------|------|------|
| `sec-ch-ua` | ❌ 차단 (0B) | Chrome 버전 노출 |
| `sec-ch-ua-platform` | ❌ 차단 (0B) | OS 정보 불일치 |
| `user-agent` | ❌ 차단 (0B) | TLS 지문 불일치 |
| `sec-ch-ua-mobile` | ✅ 성공 (1363KB) | 유일한 안전 헤더 |

---

## 🔍 차단 원인 분석

### Akamai 검증 로직 (추정)

```
[1단계] TLS Fingerprint 검증
   → curl-cffi 프로필의 TLS 지문

[2단계] HTTP 헤더 일관성 검증 ⚠️ 여기서 차단됨!
   → TLS 지문 vs HTTP 헤더 버전 일치 여부 확인
   → sec-ch-ua의 Chrome 버전 vs TLS 지문 버전
   → user-agent의 Chrome 버전 vs TLS 지문 버전

   불일치 감지 → 즉시 차단!
```

**예시**:
- TLS 지문: chrome124 (Chrome 124.x.x.x)
- sec-ch-ua: "Google Chrome";v="141" (Chrome 141.x.x.x)
- → **버전 불일치 감지** → 즉시 차단

### 왜 프로필 기본값은 통과하는가?

curl-cffi는 각 프로필의 TLS 지문과 **완벽하게 일치하는 HTTP 헤더**를 자동 생성합니다:

- `chrome124` 프로필 → Chrome 124.x 버전의 TLS + 헤더
- `chrome131` 프로필 → Chrome 131.x 버전의 TLS + 헤더
- → **완벽한 일관성** → 통과 ✅

---

## 📋 적용 가이드

### 모든 크롤러에 적용

1. **절대 헤더를 추가하지 말 것**
2. **프로필만 지정하고 나머지는 자동**
3. **쿠키는 실제 브라우저에서 획득**
4. **HTTP/2 SETTINGS는 조정 가능** (TLS와 무관)

### 추천 설정

```python
# 최소 설정 (가장 안전)
response = requests.get(
    url,
    impersonate='chrome124',  # 성공 확인된 프로필
    cookies=cookie_dict,
    timeout=15
)

# HTTP/2 SETTINGS 조정 (선택)
session = requests.Session()
session.curl.setopt(CurlOpt.HTTP2_SETTINGS, '1:4096;2:0;3:100;4:1572864;6:65536')
response = session.get(
    url,
    impersonate='chrome124',
    cookies=cookie_dict
)
```

---

## ⚠️ 금지 사항 요약

### 절대 하지 말 것

1. ❌ `headers` 파라미터 사용
2. ❌ `user-agent` 커스텀
3. ❌ `sec-ch-ua*` 헤더 추가
4. ❌ Chrome 브라우저 헤더 복제
5. ❌ 버전 정보 포함된 헤더 추가

### 반드시 할 것

1. ✅ `impersonate` 프로필만 사용
2. ✅ 프로필 기본 헤더 신뢰
3. ✅ 쿠키만 실제 브라우저에서 가져오기
4. ✅ HTTP/2 SETTINGS는 필요시 조정
5. ✅ 이 정책 문서를 항상 참고

---

## 📝 변경 이력

- **2025-10-10**: 초기 작성 (header_comparator.py 실험 결과 기반)

---

**중요**: 이 정책을 위반하면 100% 차단됩니다. 새로운 테스트 전에 반드시 이 문서를 확인하세요.
