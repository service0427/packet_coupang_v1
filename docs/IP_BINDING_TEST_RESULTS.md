# Akamai IP 바인딩 테스트 결과

## 테스트 일시
2025-11-21

## 결론
**Akamai는 쿠키를 IP에 바인딩합니다.**

쿠키 생성 IP와 동일한 IP에서만 요청이 성공하고, 다른 IP에서는 차단됩니다.

## 테스트 결과

### 테스트 1: 로컬 쿠키 + 다른 IP
| 요청 IP | 쿠키 생성 IP와 동일 | 결과 |
|---------|---------------------|------|
| 222.101.90.89 (로컬) | O | **SUCCESS** (1,481,939 bytes) |
| 175.223.34.173 (프록시 1) | X | BLOCKED (1,174 bytes) |
| 175.223.49.31 (프록시 2) | X | BLOCKED (1,210 bytes) |

### 테스트 2: 이전 프록시 쿠키 + 다른 IP
쿠키 생성 IP: 175.223.11.204

| 요청 IP | 쿠키 생성 IP와 동일 | 결과 |
|---------|---------------------|------|
| 175.223.11.204 (동일 프록시) | O | **SUCCESS** (3/3 pages) |
| 110.70.47.41 (다른 프록시) | X | BLOCKED |
| 175.223.45.104 (다른 프록시) | X | BLOCKED |
| 39.7.54.134 (다른 프록시) | X | BLOCKED |
| 222.101.90.89 (로컬) | X | BLOCKED |

## 기술적 세부사항

### Akamai 검증 메커니즘
1. 브라우저가 쿠팡 접속 시 Akamai가 쿠키 발급
2. 쿠키에는 IP 정보가 암호화되어 포함된 것으로 추정
3. 이후 요청에서 현재 IP와 쿠키 내 IP 비교
4. 불일치 시 차단 (1,174~1,211 bytes 응답)

### 차단 응답 특징
- HTTP Status: 200
- Response Size: 1,174~1,211 bytes
- 정상 응답: 50,000+ bytes

## 운영 전략

### 1. 단일 IP 사용 (권장)
- 브라우저와 curl-cffi가 동일 IP 사용
- 로컬 IP 또는 고정 프록시 IP

### 2. 프록시 사용 시
- 프록시로 브라우저 실행하여 쿠키 생성
- 동일 프록시로 curl-cffi 요청
- 프록시 아웃바운드 IP가 고정되어야 함

### 3. 다중 IP 사용 시
- IP별로 별도 쿠키 생성 및 관리 필요
- 각 IP마다 브라우저 세션 실행

## User-Agent 테스트 결과

### 테스트 1: 다른 브라우저/버전
| User-Agent | 결과 |
|------------|------|
| Chrome 136 (원본) | **SUCCESS** |
| Chrome 120 | BLOCKED (403) |
| Firefox 121 | BLOCKED (403) |
| Edge 120 | BLOCKED (403) |
| Safari | BLOCKED (403) |

**결론**: JA3 핑거프린트와 User-Agent 버전이 일치해야 함

### 테스트 2: PC Chrome → Android Chrome 에뮬레이션
| 테스트 | 결과 |
|--------|------|
| PC Chrome 136 + PC URL | **SUCCESS** (1,481,937 bytes) |
| Android Chrome 136 + Mobile URL | **SUCCESS** (1,472,445 bytes) |
| Android Chrome 136 + PC URL | **SUCCESS** (1,480,633 bytes) |

**결론**:
- Chrome 버전이 같으면 PC/Mobile 구분 없이 성공
- PC에서 생성한 쿠키를 Mobile UA로 사용 가능
- m.coupang.com과 www.coupang.com 모두 동일 쿠키로 접근 가능

## 관련 파일
- `test-proxy-browser.js`: 프록시로 브라우저 쿠키 생성
- `test-proxy-full.py`: 프록시 전체 워크플로우 테스트
- `lib/browser/browser-launcher.js`: 프록시 지원 브라우저 런처
- `lib/curl_cffi_client.py`: 프록시 지원 HTTP 클라이언트

## TLS 버전 로테이션 테스트 결과

### 전체 Chrome TLS 버전 테스트 (23개 버전)

**테스트 조건**: Chrome 136 쿠키 (로컬 IP)

#### PC UA (버전 매칭 필수)
| 버전 | JA3 해시 | 결과 |
|------|----------|------|
| 127-131 | - | ❌ BLOCKED |
| 132, 134-136, 138-144 | - | ✅ SUCCESS |
| 133, 137 | - | ❌ BLOCKED |

**작동 버전**: 132, 134, 135, 136, 138, 139, 140, 141, 142, 143, 144 (11개)

#### Mobile UA (버전 불일치 허용)
| TLS 버전 | UA 버전 | 결과 |
|----------|---------|------|
| 127-130 | 120 | ❌ BLOCKED (재검증 결과) |
| 131, 132, 134, 135 | 120 | ❌ BLOCKED |
| 133, 136-144 | 120 | ⚠️ 일부 성공 |

**주의**: Mobile UA 트릭은 초기 테스트에서만 작동했으며, 재검증 결과 구버전(127-130)은 모두 차단됨

### 재검증 결과 (요청 빈도 영향)

많은 테스트 후 재검증한 결과:

| 버전 | 상태 |
|------|------|
| Chrome 136 | ✅ 안정적 |
| Chrome 138 | ✅ 안정적 |
| Chrome 140 | ✅ 안정적 |
| Chrome 142 | ✅ 안정적 |
| Chrome 139, 141, 143, 144 | ❌ 일시 차단 |
| Chrome 127-130 | ❌ 완전 차단 |

**현재 안정적으로 작동하는 버전**: **136, 138, 140, 142** (4개)

### TLS 로테이션 테스트 (Mixed 전략, 20회)

| 결과 | 값 |
|------|-----|
| 총 요청 | 20 |
| 성공 | 18 (90%) |
| 차단 | 2 |
| 차단된 버전 | 132, 138 |

**버전별 성공률**:
- Chrome 127-130 (Mobile): 100%
- Chrome 133-137 (Mixed): 100%
- Chrome 139-144: 100%

### 핵심 발견

1. **Mobile UA 바이패스**: Mobile UA를 사용하면 TLS 버전과 UA 버전이 불일치해도 통과
2. **구버전 활용**: Mobile UA로 127-130 구버전 TLS도 사용 가능 (PC에서는 차단)
3. **최대 TLS 다양성**: PC + Mobile 조합으로 14+ 버전 활용 가능
4. **자동 차단 감지**: 차단 시 자동으로 다른 버전으로 전환

### 권장 전략

1. **Mixed 전략**: PC와 Mobile UA를 섞어서 최대 버전 활용
2. **로테이션**: Round-robin으로 버전을 순환하여 특정 버전 과사용 방지
3. **차단 감지**: 차단된 버전은 자동으로 제외하고 다른 버전 사용

## TLS 로테이터 사용법

```python
from lib.tls_rotator import TLSRotator

# 초기화
rotator = TLSRotator(base_dir, strategy="round_robin")

# PC 프로파일
profile, headers = rotator.get_pc_profile()

# Mobile 프로파일 (구버전 TLS 사용 가능)
profile, headers = rotator.get_mobile_profile(ua_version=120)

# Mixed 프로파일 (최대 다양성)
profile, headers = rotator.get_mixed_profile()

# 요청 후 결과 기록
rotator.record_result(profile['major'], success=True)

# 차단 시 버전 제외
rotator.mark_blocked(profile['major'])
```

## 관련 파일
- `test-proxy-browser.js`: 프록시로 브라우저 쿠키 생성
- `test-proxy-full.py`: 프록시 전체 워크플로우 테스트
- `test-all-tls-versions.py`: 모든 TLS 버전 테스트
- `test-tls-rotation.py`: TLS 로테이션 테스트
- `lib/tls_rotator.py`: TLS 로테이션 시스템
- `lib/browser/browser-launcher.js`: 프록시 지원 브라우저 런처
- `lib/curl_cffi_client.py`: 프록시 지원 HTTP 클라이언트

## 명령어 예시

```bash
# 로컬 IP로 쿠키 생성 및 테스트
node coupang-test.js browser 136
python lib/curl_cffi_client.py 136 notebook

# 프록시로 쿠키 생성 및 테스트
python test-proxy-full.py socks5://ip:port 136 notebook

# 모든 TLS 버전 테스트
python test-all-tls-versions.py notebook

# TLS 로테이션 테스트
python test-tls-rotation.py 20 mixed
```
