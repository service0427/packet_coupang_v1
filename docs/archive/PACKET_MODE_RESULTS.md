# 패킷 모드 테스트 결과

## 테스트 일시

**2025-10-08**

---

## 방법 1: Node.js HTTP/2 + BoringSSL 매칭

### 실행 결과

```
성공: 1/3 (33.3%)
차단: 0/3 (0.0%)
```

### 상세 결과

1. **✅ 음료수** - 성공
   - 상태: 200
   - 크기: 888.5KB
   - 응답 시간: 1210ms
   - 프로토콜: HTTP/2
   - 쿠키: 9개 (PCID, _abck, bm_sz 등)
   - **정상 검색 결과 수신**

2. **❌ 노트북** - 실패
   - 오류: `ERR_HTTP2_STREAM_ERROR`
   - 응답 시간: 46ms
   - 원인: 쿠키 재사용 시 서버가 HTTP/2 스트림 종료

3. **❌ 키보드** - 실패
   - 오류: `ERR_HTTP2_STREAM_ERROR`
   - 응답 시간: 51ms
   - 원인: 동일 세션 재사용 차단

### 분석

**성공 요인**:
- ✅ TLS ClientHello 통과 (Cipher Suite 매칭)
- ✅ HTTP/2 프로토콜 지원
- ✅ 첫 번째 요청 성공

**실패 요인**:
- ❌ 세션 재사용 시 서버가 패턴 감지
- ❌ `test_fixed_cipher.js`와 동일한 문제 (1-2회 성공 후 차단)
- ❌ Extension 순서 불일치로 인한 핑거프린트 차이

### 결론

**성공률: 33.3%** (1회 성공 후 차단)

**문제점**: 세션 재사용 시 서버가 TLS 핑거프린트 학습하여 차단

---

## 방법 2: Python curl-cffi (미실행)

### 상태
- ⏳ WSL 설치 필요
- 📋 구현 완료 (`python_curl_cffi_client.py`)

### 예상 성공률
**70-80%** (curl-impersonate 기반 완벽 TLS 재현)

### 다음 단계
1. WSL Ubuntu 설치: `wsl --install -d Ubuntu-22.04`
2. curl-cffi 설치: `pip3 install curl-cffi`
3. 실행 및 결과 비교

---

## 방법 3: Golang tls-client (실행 완료)

### 설치 및 실행
- ✅ Golang 1.25.2 설치 (winget)
- ✅ tls-client 의존성 설치
- ✅ 빌드 완료: `coupang_tls_client.exe`

### 실행 결과

```
성공: 0/3 (0.0%)
차단: 3/3 (100.0%)
```

### 상세 결과

1. **🚨 음료수** - Akamai Challenge
   - 상태: 200
   - 크기: 1.2KB
   - 응답 시간: 212ms
   - 프로토콜: HTTP/2
   - **Bot Manager Challenge 수신**

2. **🚨 노트북** - Akamai Challenge
   - 상태: 200
   - 크기: 1.2KB
   - 응답 시간: 83ms

3. **🚨 키보드** - Akamai Challenge
   - 상태: 200
   - 크기: 1.2KB
   - 응답 시간: 147ms

### 분석

**성공 요인**:
- ✅ TLS ClientHello 통과 (200 응답)
- ✅ HTTP/2 프로토콜 지원
- ✅ Chrome 120 프로파일 정확히 재현

**실패 요인**:
- ❌ **Akamai Bot Manager JavaScript Challenge**
- ❌ TLS 레벨은 통과했으나 JavaScript 실행 불가
- ❌ Node.js보다 오히려 더 강력한 차단 (첫 요청부터 차단)

### 결론

**성공률: 0%** (예상 70-80% → 실제 0%)

**문제점**: Chrome 120 TLS 완벽 재현에도 불구하고 Akamai가 JavaScript Challenge로 차단. TLS 핑거프린트만으로는 불충분.

---

## 핵심 발견사항

### 1. TLS ClientHello 레벨 통과 ✅

**증거**:
- Node.js HTTP/2로 첫 번째 요청 **성공**
- 888KB 정상 검색 결과 수신
- HTTP/2 프로토콜 협상 성공
- Akamai 쿠키 정상 수신 (bm_sz, _abck, PCID)

**결론**: Cipher Suite + Supported Groups 매칭만으로도 **TLS 레벨 통과 가능**

### 2. 세션 재사용 시 차단 패턴 발견

**패턴**:
```
요청 1 (새 세션): ✅ 성공 (888KB, 1210ms)
요청 2 (쿠키 재사용): ❌ 실패 (ERR_HTTP2_STREAM_ERROR, 46ms)
요청 3 (쿠키 재사용): ❌ 실패 (ERR_HTTP2_STREAM_ERROR, 51ms)
```

**원인 가설**:
1. 서버가 TLS 핑거프린트 기록
2. 동일 핑거프린트 + 쿠키 재사용 → 봇 판정
3. HTTP/2 GOAWAY 프레임 전송하여 연결 종료

### 3. Node.js OpenSSL의 한계 확인

**재현 가능**:
- ✅ Cipher Suite 순서
- ✅ Supported Groups 순서
- ✅ TLS 버전 (1.2/1.3)
- ✅ HTTP/2 프로토콜

**재현 불가능**:
- ❌ Extension 순서 (OpenSSL 내부 고정)
- ❌ GREASE 값
- ❌ Signature Algorithms 순서
- ❌ TLS 1.3 key_share 세부 설정

---

## 비교 분석

### TLS 핑거프린트 매칭률

| 방법 | Cipher | Groups | Extension 순서 | GREASE | 예상 TLS 매칭 |
|------|--------|--------|---------------|--------|--------------|
| Node.js HTTP/2 | ✅ | ✅ | ❌ | ❌ | **~70%** |
| Python curl-cffi | ✅ | ✅ | ✅ | ✅ | **~95%** |
| Golang tls-client | ✅ | ✅ | ✅ | ✅ | **~95%** |

### 예상 성공률

| 방법 | 첫 요청 | 재사용 | 멀티 세션 | 전체 성공률 |
|------|--------|--------|----------|-----------|
| Node.js HTTP/2 | 80% | 20% | 40% | **30-50%** |
| Python curl-cffi | 95% | 80% | 85% | **70-80%** |
| Golang tls-client | 95% | 80% | 85% | **70-80%** |

---

## 개선 전략

### 단기 (Node.js HTTP/2 개선) - ❌ 실패

**문제**: 세션 재사용 시 차단

**시도한 해결 방안**:
1. **각 요청마다 새 HTTP/2 세션 생성** - ❌ 효과 없음
   - 구현: `nodejs_http2_improved.js`
   - 결과: 33.3% 동일
   - 원인: 서버가 TLS 핑거프린트 자체를 학습

2. **User-Agent 로테이션** - ❌ 효과 없음
   - Chrome 140/139/141 버전 순환
   - 결과: 차단 패턴 동일

3. **요청 간 딜레이 증가** - ❌ 효과 없음
   - 3초 → 10-15초 랜덤 딜레이
   - 결과: 여전히 2번째 요청부터 차단

**결론**: Node.js OpenSSL의 TLS 핑거프린트가 서버에 학습되어 차단됨. Extension 순서와 GREASE 부재가 근본 원인.

**예상 개선**: ~~33% → 50-60%~~ → **개선 불가 (33% 유지)**

### 중기 (curl-cffi / Golang 도입)

**우선순위**:
1. **Python curl-cffi** (WSL)
   - 설치 시간: 10분
   - 70-80% 성공률 예상

2. **Golang tls-client** (Windows)
   - 설치 시간: 20분
   - 70-80% 성공률 예상

**권장**: 둘 다 테스트하여 성공률 비교

### 장기 (완벽한 해결책)

**Option 1: Akamai Challenge 우회**
- V8 JavaScript 엔진 통합
- Challenge Script 실행
- 개발 기간: 1-2주

**Option 2: Real Chrome + CDP** (현재 100% 성공)
- 보장된 성공률
- 리소스: 200MB/인스턴스
- 프로덕션 검증 완료

---

## 권장사항

### 즉시 실행 가능

**1단계: Node.js HTTP/2 개선** (오늘)
- 각 요청마다 새 세션 생성
- 딜레이 증가
- 성공률 50-60% 목표

**2단계: curl-cffi 또는 Golang 테스트** (내일)
- WSL 또는 Golang 설치
- 70-80% 성공률 검증
- 프로덕션 적용 검토

### OS 변경 필요 여부

**Windows만 사용**:
- Node.js HTTP/2 (개선 버전)
- Golang tls-client (Golang 설치 필요)
- 예상 성공률: 50-80%

**WSL 추가** (권장):
- Python curl-cffi 추가
- 더 안정적인 TLS 재현
- 예상 성공률: 70-80%

**네이티브 Linux** (최고):
- 모든 방법 최적 성능
- curl-cffi, Golang 모두 안정적
- 예상 성공률: 80-90%

### 최종 판단

**70%+ 성공 시**: 해당 방법 채택
**<70% 성공 시**: Real Chrome + CDP 유지 (100% 보장)

---

## 다음 단계

### Phase 1: Node.js 개선 (완료)
- [x] HTTP/2 모듈 구현
- [x] TLS 레벨 통과 확인
- [x] 세션 재사용 문제 파악

### Phase 2: 추가 방법 테스트
- [ ] Python curl-cffi 설치 및 실행
- [ ] Golang tls-client 설치 및 실행
- [ ] 성공률 비교

### Phase 3: 프로덕션 결정
- [ ] 70%+ 방법 선택 또는
- [ ] Real Chrome + CDP 유지

---

## 파일 목록

### 구현 완료
- ✅ `nodejs_http2_boringssl.js` - 33.3% 성공 (테스트 완료)
- ✅ `python_curl_cffi_client.py` - 구현 완료 (미실행)
- ✅ `golang_tls_client.go` - 구현 완료 (미실행)

### 문서
- ✅ `PACKET_MODE_COMPLETE_GUIDE.md` - 완전 가이드
- ✅ `CLIENTHELLO_MATCHING_STRATEGY.md` - 전략 문서
- ✅ `TLS_FINGERPRINT_ISSUE.md` - 기술 분석
- ✅ `BORINGSSL_PACKET_SOLUTION.md` - 솔루션 가이드
- ✅ `PACKET_MODE_RESULTS.md` - 이 파일

### 수집된 데이터
- ✅ `nodejs_http2_음료수_1759904188902.html` - 888KB 정상 검색 결과

---

## 결론

### 최종 테스트 결과

| 방법 | TLS 통과 | Akamai 우회 | 성공률 | 상태 |
|------|---------|------------|--------|------|
| Node.js HTTP/2 | ✅ | ⚠️ (1회만) | 33.3% | 세션 재사용 차단 |
| Golang tls-client | ✅ | ❌ | 0% | JavaScript Challenge |
| Real Chrome + CDP | ✅ | ✅ | 100% | 프로덕션 검증 완료 |

### 핵심 발견

1. **TLS ClientHello 레벨 통과 가능** ✅
   - Node.js: Cipher Suite + Supported Groups 매칭만으로 통과
   - Golang: Chrome 120 완벽 재현으로 통과

2. **Akamai Bot Manager가 핵심 장애물** 🚨
   - TLS 통과 후 JavaScript Challenge 발동
   - V8 엔진 없이는 Challenge 해결 불가
   - Node.js는 1회 통과 후 핑거프린트 학습으로 차단
   - Golang은 첫 요청부터 Challenge 수신

3. **패킷 모드의 한계 확인**
   - TLS 레벨 우회: 가능
   - JavaScript Challenge 우회: **불가능** (V8 엔진 필요)

### 최종 권장사항

**프로덕션 환경**: Real Chrome + CDP 유지 (100% 성공)
- 검증된 안정성
- Akamai Challenge 자동 처리
- 200MB/인스턴스 리소스 사용

**패킷 모드**: 실용성 없음 (0-33% 성공률)
- TLS 우회만으로는 불충분
- JavaScript Challenge 우회 불가
- 추가 개발 비용 대비 효과 미미

**결론**: **Real Chrome + CDP 방식 계속 사용 권장** ✅
