# CLAUDE.md

Coupang Akamai Bypass System - curl-cffi 기반 TLS 핑거프린트 매칭

## Credentials

```bash
# sudo
Tech1324!

## 주요 명령어

```bash
# 쿠키 생성
python3 coupang.py cookie
python3 coupang.py cookie -t 4 -l 2  # 4 스레드, 조합당 2개

# 상품 검색
python3 coupang.py search
python3 coupang.py search --product-id 12345678 --query "검색어"
python3 coupang.py search --random              # DB에서 랜덤 키워드
python3 coupang.py search --screenshot          # 스크린샷 저장
```

## 핵심 조건

| 요소 | 필수 | 설명 |
|------|------|------|
| Chrome 131+ JA3 | ✅ | 구버전 블랙리스트 (127-130 차단) |
| Akamai 핑거프린트 | ✅ | HTTP/2 SETTINGS 매칭 |
| extra_fp | ✅ | signature_algorithms, tls_grease |
| sec-ch-ua 헤더 | ✅ | Client Hints 필수 |
| 신선한 쿠키 | ✅ | `_abck`에 `~-1~` 포함 |
| IP 바인딩 | ✅ | 쿠키 생성 IP = 요청 IP (/24 서브넷) |

## Success Criteria

- Response size > 50,000 bytes = SUCCESS
- Response size ≤ 50,000 bytes = BLOCKED (Challenge 페이지)

## 프록시 API

```bash
curl "http://mkt.techb.kr:3001/api/proxy/status?remain=60"
```

## 디렉토리 구조

```
lib/
├── common/          # DB, 프록시, 핑거프린트
├── browser/         # Playwright 쿠키 생성
├── cffi/            # curl-cffi 검색/클릭
├── extractor/       # HTML 파싱
└── screenshot/      # 스크린샷
```

## Docker 분산 워커

> curl-cffi는 C 라이브러리 특성상 p=50 이상에서 코어 덤프 발생. Docker 컨테이너 격리로 해결.

### 기본 명령어

```bash
# 이미지 빌드
sg docker -c "docker build -t coupang-worker ."

# 워커 실행 (N개 컨테이너, 각 p=20)
sg docker -c "docker-compose up -d --scale worker=5"   # 5개 = 총 p=100
sg docker -c "docker-compose up -d --scale worker=10"  # 10개 = 총 p=200

# 상태 확인
sg docker -c "docker-compose ps"
sg docker -c "docker stats"

# 로그 확인
sg docker -c "docker-compose logs -f"
sg docker -c "docker-compose logs --tail=100"

# 중지
sg docker -c "docker-compose down"
```

### 병렬 수 변경

Dockerfile CMD에서 `-p` 값 수정:

```dockerfile
CMD ["python3", "coupang.py", "work", "-t", "rank", "-n", "0", "-p", "20"]
```

### 성능 참고

| 방식 | 워커 | 처리량 | 안정성 |
|------|:----:|:-----:|:-----:|
| 단일 프로세스 p=20 | 1 | 2/초 | ✅ |
| Docker 5개 × p=20 | 5 | 10/초 | ✅ |
| Docker 10개 × p=20 | 10 | 20/초 | ✅ |

> 상세: [docs/docker-worker-setup.md](docs/docker-worker-setup.md)

## 상세 문서 (docs/)

- [docs/database-schema.md](docs/database-schema.md) - DB 테이블 스키마
- [docs/tls-profile.md](docs/tls-profile.md) - TLS 프로파일 설정
- [docs/kt-proxy-ip.md](docs/kt-proxy-ip.md) - KT 모바일 IP 대역
- [docs/docker-worker-setup.md](docs/docker-worker-setup.md) - Docker 분산 워커 설정
