# Coupang TLS Bypass Project

쿠팡 TLS ClientHello 우회 및 Bot Detection 분석 프로젝트

## 📁 프로젝트 구조

```
local-packet-coupang/
├── tls_bypass.js              # 🎯 메인: TLS 우회 클라이언트
├── real_chrome_connect.js     # ✅ 프로덕션: Real Chrome + CDP (100%)
├── src/                       # 소스 코드
│   ├── nodejs_http2_boringssl.js      # Node.js HTTP/2 구현
│   ├── nodejs_http2_improved.js       # 개선 버전
│   ├── python_curl_cffi_client.py     # Python curl-cffi
│   └── golang_tls_client.go           # Golang tls-client
├── results/                   # 테스트 결과
│   ├── *.html                # 응답 HTML
│   ├── *.json                # 테스트 리포트
│   └── tls_bypass_*.json     # TLS 우회 결과
├── docs/                      # 문서
│   ├── BLOCKING_PATTERNS.md  # 차단 패턴 분석
│   ├── PACKET_MODE_RESULTS.md # 패킷 모드 결과
│   ├── TLS_FINGERPRINT_ISSUE.md
│   └── *.md                  # 기타 문서
├── archive/                   # 아카이브
│   ├── failed_attempts/      # 실패한 시도들
│   └── *.js                  # 구버전 파일들
└── package.json              # 프로젝트 설정
```

## 🎯 주요 파일

### 1. `tls_bypass.js` - TLS 우회 클라이언트 (현재 작업)
**목적**: 1단계(TLS ClientHello) 무한 통과

**전략**:
- 매 요청마다 완전히 새로운 TLS 세션
- User-Agent 로테이션 (Chrome 138-141)
- 쿠키 재사용 안함
- Cipher Suite + Supported Groups 완벽 매칭

**실행**:
```bash
node tls_bypass.js
```

**예상 결과**:
- TLS 통과율: 100%
- Akamai Challenge: 수신 (2단계)
- 완전 성공: 변동 (0-33%)

### 2. `real_chrome_connect.js` - 프로덕션 솔루션
**성공률**: 100% (검증 완료)

**실행**:
```bash
node real_chrome_connect.js
```

## 🔬 차단 단계 분석

### 1단계: TLS ClientHello 필터링
- **기준**: JA3/JA4 핑거프린트, Cipher Suite 순서, Extension 순서
- **차단 시**: 연결 즉시 종료 (ERR_HTTP2_STREAM_ERROR)
- **우회**: ✅ 가능 (Cipher + Groups 매칭)

### 2단계: Akamai Bot Manager
- **기준**: JavaScript 실행, 브라우저 특성
- **차단 시**: HTTP 200 + 1.2KB Challenge Script
- **우회**: ❌ 불가능 (V8 엔진 필요)

## 📊 테스트 결과

### Node.js HTTP/2
- TLS 통과: ✅ (첫 요청)
- 세션 재사용: ❌ (핑거프린트 학습)
- 성공률: **33.3%**

### Golang tls-client
- TLS 통과: ✅ (완벽 재현)
- Akamai Challenge: 🚨 (모든 요청)
- 성공률: **0%**

### Real Chrome + CDP
- TLS 통과: ✅
- Akamai 우회: ✅
- 성공률: **100%**

## 🚀 사용 방법

### 1. TLS 우회 테스트
```bash
# 10회 연속 TLS 통과 테스트
node tls_bypass.js
```

### 2. 프로덕션 실행
```bash
# 100% 성공률 보장
node real_chrome_connect.js
```

### 3. 결과 확인
```bash
# 결과 폴더 확인
ls results/

# 최신 리포트 확인
cat results/tls_bypass_*.json | tail -1
```

## 📈 개발 로드맵

### Phase 1: TLS 우회 (현재)
- [x] TLS ClientHello 분석
- [x] Node.js HTTP/2 구현
- [x] Golang tls-client 구현
- [x] 차단 패턴 분석
- [ ] 무한 TLS 통과 구현

### Phase 2: Akamai 우회 (다음)
- [ ] V8 JavaScript 엔진 통합
- [ ] Challenge Script 실행
- [ ] 브라우저 특성 재현

### Phase 3: 프로덕션 최적화
- [ ] 성공률 70%+ 달성 또는
- [ ] Real Chrome + CDP 유지

## 📚 문서

- **차단 분석**: `docs/BLOCKING_PATTERNS.md`
- **테스트 결과**: `docs/PACKET_MODE_RESULTS.md`
- **TLS 이슈**: `docs/TLS_FINGERPRINT_ISSUE.md`

## 🔧 요구사항

- Node.js 22+
- Golang 1.25+ (선택)
- Python 3 + curl-cffi (선택, WSL)

## 📝 라이선스

MIT
