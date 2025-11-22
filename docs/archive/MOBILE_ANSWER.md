# 모바일 조합 가능 여부 답변

## 질문
모바일로 조합해서는 가능한가?

## 답변
**불가능**. Mobile User-Agent를 사용하면 즉시 차단됨.

## 검증 결과 (5가지 조합 테스트)

### ✅ 성공한 조합 (3/5)

1. **Desktop UA + Desktop Viewport**
   - User-Agent: Windows Desktop Chrome
   - 뷰포트: 2560x1305
   - 결과: ✅ 성공

2. **Desktop UA + Mobile Viewport** ⭐ 권장
   - User-Agent: Windows Desktop Chrome
   - 뷰포트: 375x812 (모바일 크기)
   - 결과: ✅ 성공
   - 특징: 모바일 UI 렌더링됨

3. **Mobile Device Emulation (Playwright)**
   - User-Agent: Windows Desktop Chrome (자동)
   - 뷰포트: 375x812
   - 결과: ✅ 성공

### ❌ 실패한 조합 (2/5)

4. **Mobile UA (헤더) + Mobile Viewport**
   - User-Agent: iPhone Safari (setExtraHTTPHeaders)
   - 뷰포트: 375x812
   - 결과: ❌ `ERR_HTTP2_PROTOCOL_ERROR`
   - 차단 메커니즘: Mobile UA 헤더 감지

5. **Android UA (헤더) + Mobile Viewport**
   - User-Agent: Android Chrome (setExtraHTTPHeaders)
   - 뷰포트: 412x915
   - 결과: ❌ `ERR_HTTP2_PROTOCOL_ERROR`
   - 차단 메커니즘: Mobile UA 헤더 감지

## 차단 메커니즘 분석

### Playwright `setExtraHTTPHeaders`로 Mobile UA 설정 시

```javascript
await page.setExtraHTTPHeaders({
    'User-Agent': 'Mozilla/5.0 (iPhone; ...) Mobile Safari/604.1'
});

// 검색 요청
await page.goto('https://www.coupang.com/np/search?q=...');

// 결과: ERR_HTTP2_PROTOCOL_ERROR
```

**왜 차단되는가?**:
1. Playwright `setExtraHTTPHeaders`는 HTTP 헤더만 변경
2. `navigator.userAgent` (JavaScript)는 여전히 Desktop
3. **User-Agent 불일치 감지**:
   - HTTP Header: Mobile
   - JavaScript API: Desktop
   - → Akamai Bot Manager가 불일치 탐지

### Chrome `--user-agent` 플래그 사용 시

```bash
chrome.exe --user-agent="Mozilla/5.0 (iPhone...) Mobile Safari/604.1"
```

**결과**: 즉시 차단 (이전 테스트에서 검증)
- `mobile_intensive_test.js`: 0/10 성공
- Chrome 플래그 자체를 감지

## 모바일 UI가 필요한 경우 해결책

### ⭐ 권장 방법: Desktop UA + Mobile Viewport

```javascript
// Chrome 실행 (Desktop UA 유지)
const args = [
    '--remote-debugging-port=9222',
    '--window-size=375,812',  // 모바일 뷰포트
    '--user-data-dir=...'
    // ❌ --user-agent 사용 금지!
];

// Playwright 연결
const browser = await chromium.connectOverCDP('http://localhost:9222');
const page = (await browser.contexts()[0].pages())[0];

// 뷰포트만 모바일 크기로 설정
await page.setViewportSize({ width: 375, height: 812 });
```

**장점**:
- ✅ 차단 없음
- ✅ 모바일 UI 렌더링
- ✅ 검색 정상 작동
- ✅ 배너 없음 (Desktop UA)

**단점**:
- ❌ `navigator.userAgent`는 Desktop
- ❌ 모바일 배너 표시 안 됨

## 모바일 배너가 필요한 경우

**해결책 없음**. Mobile UA 사용 시 무조건 차단됨.

**대안**:
1. Desktop UA로 진행 (배너 없음)
2. 수동으로 모바일 배너 HTML 추출하여 처리
3. Real Mobile 디바이스 사용 (하지만 자동화 어려움)

## 최종 결론

| 요구사항 | 가능 여부 | 방법 |
|---------|----------|------|
| 모바일 UI | ✅ 가능 | Desktop UA + Mobile Viewport (375x812) |
| 모바일 User-Agent | ❌ 불가능 | 즉시 차단됨 (HTTP2 에러) |
| 모바일 배너 | ❌ 불가능 | Mobile UA 필요하지만 차단됨 |
| 검색 기능 | ✅ 가능 | Desktop UA 사용 |

**답**: 모바일 **UI**는 가능하지만, 모바일 **User-Agent**는 불가능. Desktop UA + Mobile Viewport 조합만 작동.

## 파일 참조

- ✅ `mobile_combination_test.js`: 5가지 조합 검증
- ✅ `mobile_combination_report.json`: 테스트 결과
- 📊 `search_scenario_analyzer_v2.js`: 작동하는 구현 (Desktop UA)

## 날짜

2025-10-08
