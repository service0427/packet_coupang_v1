# 🔍 쿠팡 검색 traceId 생성 원리 분석

## 📋 분석 결과 요약

### 🎯 발견된 traceId 패턴

**수집된 traceId 샘플:**
- 음료수: `mg9ct4ch`
- 노트북: `mg9ct4kk`
- 마우스: `mg9ctpge`

### 📊 패턴 분석

#### 1. **기본 구조**
- **길이**: 8자리 고정
- **문자셋**: 소문자 영문 + 숫자 (a-z, 0-9)
- **공통 접두어**: `mg9ct` (5자리)
- **가변 접미어**: 3자리 (4ch, 4kk, pge)

#### 2. **생성 특징**
- **생성 간격**: 13-14초 (13935ms, 13427ms)
- **고유성**: 각 검색마다 새로운 traceId 생성
- **세션 기반**: 동일 브라우저 세션 내에서도 매번 다름

#### 3. **URL 포함 위치**
```
https://www.coupang.com/np/search?component=&q={검색어}&traceId={traceId}&channel=user
```

---

## 🕒 생성 타이밍 분석

### 검색 과정별 URL 변화
1. **검색 전**: `https://www.coupang.com/`
2. **검색 1초 후**: 동일 (메인페이지)
3. **검색 2초 후**: traceId 포함된 검색 결과 URL

### 네트워크 요청 순서
1. **검색 API 호출**: `/n-api/web-adapter/search?keyword={검색어}`
2. **Facebook 픽셀 트래킹**: traceId 정보 포함
3. **최종 검색 페이지**: traceId 포함된 URL로 리다이렉트

---

## 🧩 생성 원리 추론

### 1. **클라이언트 사이드 생성**
```javascript
// Facebook 픽셀 데이터에서 발견된 hidden input
{
  "name": "traceId",
  "tag": "input",
  "inputType": "hidden",
  "valueMeaning": "empty"
}
```

**분석**: 메인페이지에서 검색 폼에 hidden input으로 traceId 필드가 존재하지만 비어있음

### 2. **서버 사이드 생성 후 삽입**
- 검색 요청 시 서버에서 traceId 생성
- 생성된 traceId를 URL에 삽입하여 리다이렉트
- 클라이언트는 생성된 traceId가 포함된 최종 URL로 이동

### 3. **생성 알고리즘 추정**

#### A. **접두어 분석 (`mg9ct`)**
- **고정 부분**: 아마도 서버 식별자나 세션 그룹
- **가능성**:
  - 서버 인스턴스 ID
  - 시간대별 그룹 ID
  - 지역별 식별자

#### B. **접미어 분석 (3자리)**
- **가변 부분**: 개별 요청 식별자
- **패턴**:
  - `4ch` → `4kk` → `pge` (순차적이지 않음)
  - 시간 기반 + 랜덤 요소 조합으로 추정

#### C. **생성 알고리즘 가설**
```javascript
// 추정 생성 로직
function generateTraceId() {
    const prefix = 'mg9ct';  // 고정 접두어 (서버/세션 식별)
    const timestamp = Date.now().toString(36).slice(-2);  // 시간 기반
    const random = Math.random().toString(36).slice(2, 3);  // 랜덤 요소
    return prefix + timestamp + random;
}
```

---

## 🔬 기술적 구현 방식

### 1. **Hidden Form Field 방식**
```html
<!-- 메인페이지 검색 폼 -->
<form action="/np/search">
    <input name="q" type="text" />
    <input name="traceId" type="hidden" value="" />  <!-- 비어있음 -->
    <input name="channel" type="hidden" value="user" />
</form>
```

### 2. **서버 사이드 처리**
```
1. 검색 요청 수신
2. traceId 생성 (mg9ct + 3자리)
3. 생성된 traceId를 URL에 포함하여 리다이렉트
4. 클라이언트는 새 URL로 이동
```

### 3. **추적 및 분석 용도**
- **사용자 검색 행동 추적**
- **A/B 테스트 그룹 식별**
- **검색 성능 모니터링**
- **사용자 여정 분석**

---

## 🎯 패킷버전 활용 방안

### 1. **traceId 생성 시뮬레이션**
```javascript
class TraceIdGenerator {
    constructor() {
        this.prefix = 'mg9ct';  // 고정 접두어
    }

    generate() {
        const time = Date.now().toString(36).slice(-2);
        const rand = Math.random().toString(36).slice(2, 3);
        return this.prefix + time + rand;
    }
}
```

### 2. **자연스러운 검색 시뮬레이션**
- 실제와 동일한 traceId 패턴 사용
- 서버 생성 방식 모방
- 검색 행동 패턴 일치

### 3. **차단 회피 효과**
- **정상 사용자 패턴**: traceId 포함된 정상적인 검색 흐름
- **서버 인식**: 일반 웹 브라우저 검색으로 인식
- **추적 시스템 우회**: 정상적인 traceId로 이상 행동 감지 방지

---

## 📊 수집된 데이터

### traceId 샘플 (시간순)
| 시간 | 키워드 | traceId | 접두어 | 접미어 |
|------|--------|---------|--------|--------|
| 11:50:39 | 음료수 | mg9ct4ch | mg9ct | 4ch |
| 11:50:53 | 노트북 | mg9ct4kk | mg9ct | 4kk |
| 11:51:06 | 마우스 | mg9ctpge | mg9ct | pge |

### 패턴 검증
- ✅ **접두어 일관성**: 모든 traceId가 `mg9ct`로 시작
- ✅ **길이 일관성**: 모든 traceId가 8자리
- ✅ **고유성**: 각 검색마다 다른 traceId 생성
- ✅ **시간 의존성**: 생성 시간에 따라 접미어 변화

---

## 🔮 결론 및 다음 단계

### 핵심 발견
1. **traceId는 서버에서 실시간 생성**
2. **mg9ct + 3자리 가변 부분 구조**
3. **검색 시 자동으로 URL에 삽입**
4. **추적 및 분석 목적으로 사용**

### 패킷버전 적용
1. **traceId 생성기 구현**: 실제 패턴과 동일한 생성 로직
2. **자연스러운 검색 흐름**: 정상적인 사용자 행동 시뮬레이션
3. **차단 회피 향상**: 더욱 실제 브라우저에 가까운 패턴

이 분석 결과를 바탕으로 패킷버전에서 더욱 정교한 우회 시스템을 구축할 수 있습니다.

---

**분석 완료일**: 2025년 10월 2일
**분석 방법**: Real Chrome Connect
**수집 샘플**: 3개 traceId
**다음 단계**: 패킷버전 traceId 생성기 구현