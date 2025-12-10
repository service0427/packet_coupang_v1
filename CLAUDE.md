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

## Rank Check API (localhost:8088)

순위 체크 API 서버. Progressive Retry 전략으로 최대 10회 시도.

### 엔드포인트 비교

| 엔드포인트 | 쓰레드 | 특징 | 쿠키 소모 |
|-----------|:-----:|------|:--------:|
| `/api/rank/check` | 1 | 빠른 실패 처리, 쿠키 불량시 즉시 중단 | 낮음 |
| `/api/rank/check-multi` | 5 | Race 방식, 성공 확률↑ | 높음 |

### Progressive Retry 전략

둘 다 동일한 재시도 로직 사용:
- Round 1: 1개 시도
- Round 2: 2개 동시 시도 (실패 시)
- Round 3: 3개 동시 시도 (실패 시)
- Round 4: 4개 동시 시도 (실패 시)
- **최대 10회 시도**, 첫 성공 결과 반환

### 페이지 검색 티어

1. **Tier 1**: 페이지 1 (가장 많이 발견)
2. **Tier 2**: 페이지 2-5 (차선책)
3. **Tier 3**: 페이지 6-13 (마지막)

### 테스트 명령어

```bash
# 샘플 테스트 (DB에서 랜덤 선택)
curl -s http://localhost:8088/api/rank/sample | jq
curl -s http://localhost:8088/api/rank/sample-multi | jq

# 직접 호출
curl -X POST http://localhost:8088/api/rank/check \
  -H "Content-Type: application/json" \
  -d '{"keyword":"검색어","product_id":"12345678","max_page":13}'
```

## Work API (mkt.techb.kr:3302)

작업 할당 및 결과 보고 API.

```bash
# 작업 할당
curl "http://mkt.techb.kr:3302/api/work/allocate?work_type=rank"

# 결과 보고
curl -X POST http://mkt.techb.kr:3302/api/work/result \
  -H "Content-Type: application/json" \
  -d '{"allocation_key":"xxx","success":true,"actual_ip":"1.2.3.4","rank_data":{...}}'
```

### 독립 실행기 (work.py)

```bash
python3 work.py rank              # 단일 실행
python3 work.py rank --loop       # 무한 반복
python3 work.py rank -p 5         # 5개 병렬 실행
```

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
