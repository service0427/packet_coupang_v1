# 패킷 모드 완전 가이드

**목표**: TLS ClientHello 레벨에서 차단 우회
**전략**: 3가지 방법을 모두 구현하여 성공률 비교

---

## 방법 1: Node.js HTTP/2 + BoringSSL 매칭

### 장점
- ✅ 추가 설치 불필요 (Node.js만 있으면 됨)
- ✅ Windows 네이티브 지원
- ✅ 빠른 테스트 가능

### 단점
- ❌ Extension 순서 제어 불가
- ❌ GREASE 미지원
- ❌ Signature Algorithms 제어 불가

### 예상 성공률
**30-50%** (TLS Cipher/Groups 매칭, HTTP/2 지원)

### 실행

```bash
# Windows (현재 환경)
node nodejs_http2_boringssl.js
```

**파일**: `nodejs_http2_boringssl.js`

---

## 방법 2: Python curl-cffi (BoringSSL 완벽 재현)

### 장점
- ✅ curl-impersonate 기반 (Chrome TLS 100% 재현)
- ✅ Extension 순서 완벽 매칭
- ✅ GREASE 지원
- ✅ HTTP/2 네이티브

### 단점
- ❌ Windows 공식 미지원 (WSL 필요)
- ⚠️ JavaScript Challenge는 여전히 문제

### 예상 성공률
**70-80%** (TLS 완벽 재현, Akamai Challenge 제외)

### 설치 및 실행

#### Option A: WSL (Windows Subsystem for Linux) - 권장

**1. WSL 설치** (관리자 PowerShell):
```powershell
wsl --install -d Ubuntu-22.04
```

**2. WSL 재시작 후 Ubuntu 접속**:
```bash
wsl
```

**3. Python 환경 설정**:
```bash
# Ubuntu 내부에서
sudo apt update
sudo apt install python3 python3-pip -y

# curl-cffi 설치
pip3 install curl-cffi
```

**4. 파일 복사** (Windows PowerShell):
```powershell
# WSL 파일 시스템 접근
copy D:\dev\git\local-packet-coupang\python_curl_cffi_client.py \\wsl$\Ubuntu-22.04\home\%USERNAME%\
```

**5. 실행** (WSL Ubuntu):
```bash
cd ~
python3 python_curl_cffi_client.py
```

#### Option B: 네이티브 Linux (Ubuntu VM 또는 듀얼부팅)

**더 나은 성능**, WSL보다 안정적

```bash
# Ubuntu 22.04/24.04
sudo apt update
sudo apt install python3 python3-pip git -y

# 프로젝트 클론 또는 파일 복사
git clone <your-repo> || scp python_curl_cffi_client.py user@linux-machine:~

# curl-cffi 설치
pip3 install curl-cffi

# 실행
python3 python_curl_cffi_client.py
```

**파일**: `python_curl_cffi_client.py`

---

## 방법 3: Golang tls-client (BoringSSL + 최고 성능)

### 장점
- ✅ Chrome TLS ClientHello 100% 재현
- ✅ Extension 순서 완벽 제어
- ✅ GREASE 지원
- ✅ HTTP/2 네이티브
- ✅ Windows/Linux 모두 지원
- ✅ 최고 성능 (네이티브 바이너리)

### 단점
- ⚠️ Golang 설치 필요
- ⚠️ JavaScript Challenge는 여전히 문제

### 예상 성공률
**70-80%** (TLS 완벽 재현, Akamai Challenge 제외)

### 설치 및 실행

#### Windows

**1. Golang 설치**:
- https://go.dev/dl/ 에서 Windows installer 다운로드
- `go1.23.windows-amd64.msi` 실행

**2. 환경 설정** (설치 후 재시작):
```powershell
# 확인
go version
```

**3. 프로젝트 초기화**:
```powershell
cd D:\dev\git\local-packet-coupang

# go.mod 생성
go mod init coupang-tls-client

# 의존성 설치
go get github.com/bogdanfinn/tls-client
go get github.com/bogdanfinn/tls-client/profiles
```

**4. 빌드 및 실행**:
```powershell
# 빌드
go build -o coupang_tls_client.exe golang_tls_client.go

# 실행
.\coupang_tls_client.exe
```

#### Linux (더 안정적)

```bash
# Golang 설치 (Ubuntu)
sudo apt update
sudo apt install golang-go -y

# 프로젝트 디렉토리
cd ~/coupang-tls-client
cp /mnt/d/dev/git/local-packet-coupang/golang_tls_client.go .

# 초기화
go mod init coupang-tls-client
go get github.com/bogdanfinn/tls-client
go get github.com/bogdanfinn/tls-client/profiles

# 빌드
go build -o coupang_tls_client golang_tls_client.go

# 실행
./coupang_tls_client
```

**파일**: `golang_tls_client.go`

---

## 비교 실행 및 결과 분석

### 전체 테스트 실행

**1. Node.js HTTP/2 테스트**:
```bash
node nodejs_http2_boringssl.js > nodejs_http2_result.txt 2>&1
```

**2. Python curl-cffi 테스트** (WSL):
```bash
wsl
python3 python_curl_cffi_client.py > curl_cffi_result.txt 2>&1
```

**3. Golang tls-client 테스트**:
```bash
# Windows
.\coupang_tls_client.exe > golang_tls_result.txt 2>&1

# Linux
./coupang_tls_client > golang_tls_result.txt 2>&1
```

### 결과 비교 기준

**성공 판정**:
- ✅ **성공**: 정상 검색 결과 수신 (>50KB, 검색결과 포함)
- 🚨 **차단**: Bot Manager Challenge 수신 (`location.reload`)
- ❌ **실패**: TLS 핸드셰이크 실패 또는 기타 오류

**예상 결과**:

| 방법 | TLS 매칭 | HTTP/2 | GREASE | Extension 순서 | 예상 성공률 |
|------|---------|--------|--------|---------------|-----------|
| Node.js HTTP/2 | 70% | ✅ | ❌ | ❌ | **30-50%** |
| Python curl-cffi | 100% | ✅ | ✅ | ✅ | **70-80%** |
| Golang tls-client | 100% | ✅ | ✅ | ✅ | **70-80%** |

---

## 다음 단계: Akamai Challenge 우회

**문제**: TLS 통과해도 JavaScript Challenge 수신 가능

### Challenge 예시
```html
<script>
(function() {
    var proxied = window.XMLHttpRequest.prototype.send;
    window.XMLHttpRequest.prototype.send = function() {
        // 완료 시 location.reload(true) 호출
    };
})();
</script>
```

### 해결 방안

**Option 1: V8 JavaScript 엔진 통합** (고난이도)
- Golang tls-client + V8 엔진
- Challenge Script 실행 가능
- 개발 기간: 1-2주

**Option 2: Real Chrome + CDP** (현재 100% 성공)
- `real_chrome_connect.js` 유지
- 보장된 성공률
- 리소스 사용: 200MB/인스턴스

---

## 권장 전략

### 단계별 접근

**Phase 1: TLS 레벨 검증 (현재)** ✅
1. Node.js HTTP/2 실행 → 30-50% 예상
2. Python curl-cffi 실행 (WSL) → 70-80% 예상
3. Golang tls-client 실행 → 70-80% 예상

**Phase 2: 결과 분석**
- 성공률이 높은 방법 선택
- TLS 통과 vs Akamai Challenge 구분

**Phase 3: 최종 선택**
- **70%+ 성공**: 해당 방법 채택
- **<70% (Challenge 다수)**: Real Chrome + CDP로 폴백

### 최적 구성

**개발/테스트**:
- Golang tls-client (빠른 프로토타이핑)

**프로덕션**:
- Golang tls-client (리소스 효율적)
- 실패 시 Real Chrome + CDP 폴백

---

## 트러블슈팅

### Node.js HTTP/2

**문제**: `ERR_HTTP2_ERROR`
- **원인**: TLS 핸드셰이크 실패
- **해결**: Cipher Suite 순서 확인

### Python curl-cffi

**문제**: WSL 연결 실패
```bash
wsl --list --verbose
wsl --shutdown
wsl
```

**문제**: `ImportError: No module named 'curl_cffi'`
```bash
pip3 install --upgrade curl-cffi
```

### Golang tls-client

**문제**: `go: module not found`
```bash
go clean -modcache
go mod tidy
go get -u github.com/bogdanfinn/tls-client
```

**문제**: Windows 빌드 실패
- Visual Studio C++ Build Tools 설치
- 또는 Linux에서 빌드

---

## 결과 리포트 생성

각 방법은 자동으로 JSON 리포트 생성:

- `nodejs_http2_result.txt`
- `curl_cffi_report_<timestamp>.json`
- `golang_tls_report_<timestamp>.json`

**통합 분석**:
```bash
# 성공률 비교
grep "성공:" *_result.txt *_report*.json
```

---

## 최종 권장사항

### OS 변경 필요 여부

**Windows만 사용**:
- Node.js HTTP/2 (즉시 가능)
- Golang tls-client (Golang 설치 필요)

**WSL 추가** (권장):
- Python curl-cffi 추가
- 더 나은 성공률 기대

**네이티브 Linux** (최고):
- 모든 방법 최적 성능
- curl-cffi, Golang 모두 안정적
- 프로덕션 환경 권장

### 즉시 실행 가능한 순서

1. **Node.js HTTP/2** (지금 바로)
   ```bash
   node nodejs_http2_boringssl.js
   ```

2. **Golang 설치 후** (20분)
   - https://go.dev/dl/ 설치
   - `go build && ./coupang_tls_client.exe`

3. **WSL 설정 후** (30분)
   - `wsl --install -d Ubuntu-22.04`
   - `pip3 install curl-cffi`
   - `python3 python_curl_cffi_client.py`

---

## 파일 목록

- ✅ `nodejs_http2_boringssl.js` - Node.js HTTP/2 구현
- ✅ `python_curl_cffi_client.py` - Python curl-cffi 구현
- ✅ `golang_tls_client.go` - Golang tls-client 구현
- ✅ `PACKET_MODE_COMPLETE_GUIDE.md` - 이 파일

**다음**: 3가지 방법 모두 실행하여 성공률 비교!
