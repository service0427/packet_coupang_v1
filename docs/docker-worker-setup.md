# Docker 기반 분산 워커 설정 가이드

> **상태**: 테스트 중 (성능에 따라 롤백 가능)
> **작성일**: 2025-11-28
> **목적**: curl-cffi 병렬 한계를 Docker 컨테이너 격리로 해결

---

## 1. 배경

### 문제점

| 병렬 수 | 결과 |
|:------:|------|
| p=20 | ✅ 안정 (1.79 req/s) |
| p=30 | ⚠️ PROXY_TIMEOUT 발생 |
| p=40 | ❌ 차단율 30% |
| p=50 | ❌ 코어 덤프 (Segmentation Fault) |

**원인**: curl-cffi (C 라이브러리)가 높은 병렬에서 메모리 충돌

### 해결책

Docker 컨테이너로 워커를 격리하여 각각 독립된 메모리 공간에서 실행

```
단일 프로세스 p=50 (불안정)
    ↓
Docker 컨테이너 10개 × p=20 (안정)
    ↓
처리량: 10 × 2 req/s = 20 req/s
```

---

## 2. 현재 시스템 상태

```bash
# 확인 명령어
free -h          # 메모리: 31GB
nproc            # CPU 코어 수
docker --version # Docker 설치 여부
```

### 리소스 계산

| 항목 | 값 |
|------|-----|
| 총 메모리 | 31GB |
| 워커당 메모리 | ~1GB |
| 최대 워커 수 | 20개 (여유 포함) |
| 권장 워커 수 | 10개 |
| 예상 처리량 | 20 req/s |

---

## 3. 단계별 설정

### 3.1 Docker 설치 확인

```bash
# Docker 설치 확인
docker --version

# 미설치 시
sudo apt-get update
sudo apt-get install docker.io docker-compose -y
sudo usermod -aG docker $USER
# 재로그인 필요
```

### 3.2 Dockerfile 생성

```bash
# 프로젝트 루트에 생성
cat > /home/tech/packet_coupang_v1/Dockerfile << 'EOF'
FROM python:3.10-slim

# 시스템 패키지
RUN apt-get update && apt-get install -y \
    curl \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

# 작업 디렉토리
WORKDIR /app

# 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 복사
COPY . .

# Xvfb 없이 실행 (work 명령은 브라우저 불필요)
ENV USE_XVFB=false

# 기본 명령어
CMD ["python3", "coupang.py", "work", "-t", "rank", "-n", "0", "-p", "20"]
EOF
```

### 3.3 docker-compose.yml 생성

```bash
cat > /home/tech/packet_coupang_v1/docker-compose.yml << 'EOF'
version: '3.8'

services:
  worker:
    build: .
    restart: unless-stopped
    volumes:
      # config.json 공유 (DB 접속 정보)
      - ./config.json:/app/config.json:ro
      # 로그 디렉토리 공유
      - ./logs:/app/logs
    environment:
      - PYTHONUNBUFFERED=1
    deploy:
      resources:
        limits:
          memory: 1G
        reservations:
          memory: 512M
EOF
```

### 3.4 requirements.txt 확인

```bash
# 현재 의존성 확인
pip freeze > /home/tech/packet_coupang_v1/requirements.txt

# 또는 필수 패키지만
cat > /home/tech/packet_coupang_v1/requirements.txt << 'EOF'
curl-cffi>=0.5.0
pymysql>=1.0.0
requests>=2.28.0
beautifulsoup4>=4.11.0
EOF
```

---

## 4. 테스트 단계

### 4.1 단일 컨테이너 테스트

```bash
cd /home/tech/packet_coupang_v1

# 이미지 빌드
docker build -t coupang-worker .

# 단일 컨테이너 실행 (10회만)
docker run --rm -it \
  -v $(pwd)/config.json:/app/config.json:ro \
  -v $(pwd)/logs:/app/logs \
  coupang-worker \
  python3 coupang.py work -t rank -n 10 -p 20

# 결과 확인
# - 정상 실행 여부
# - 로그 파일 생성 여부
# - 처리 속도
```

### 4.2 다중 컨테이너 테스트 (2개)

```bash
# 2개 워커로 시작
docker-compose up -d --scale worker=2

# 상태 확인
docker-compose ps

# 로그 확인 (실시간)
docker-compose logs -f

# 1분 후 결과 확인
ls -la logs/

# 중지
docker-compose down
```

### 4.3 점진적 확장 테스트

```bash
# 5개 워커
docker-compose up -d --scale worker=5
sleep 60
docker-compose logs | grep -c "✅발견"
docker-compose down

# 10개 워커
docker-compose up -d --scale worker=10
sleep 60
docker-compose logs | grep -c "✅발견"
docker-compose down
```

---

## 5. 모니터링

### 컨테이너 상태

```bash
# 실시간 리소스 사용량
docker stats

# 출력 예시:
# CONTAINER      CPU %   MEM USAGE / LIMIT
# worker-1       15%     512MB / 1GB
# worker-2       12%     480MB / 1GB
# ...
```

### 로그 확인

```bash
# 전체 로그
docker-compose logs -f

# 특정 워커 로그
docker-compose logs -f worker

# 최근 100줄만
docker-compose logs --tail=100
```

### 처리량 측정

```bash
# 1분간 발견 수 계산
docker-compose logs --since 1m | grep -c "✅발견"
```

---

## 6. 운영 명령어

### 시작/중지

```bash
# 시작 (백그라운드)
docker-compose up -d --scale worker=10

# 중지 (컨테이너 유지)
docker-compose stop

# 완전 중지 (컨테이너 삭제)
docker-compose down

# 재시작
docker-compose restart
```

### 스케일 조정

```bash
# 워커 수 변경 (실행 중에도 가능)
docker-compose up -d --scale worker=5   # 5개로 줄이기
docker-compose up -d --scale worker=15  # 15개로 늘리기
```

### 업데이트

```bash
# 코드 변경 후 재빌드
docker-compose down
docker build -t coupang-worker .
docker-compose up -d --scale worker=10
```

---

## 7. 롤백 방법

### Docker 완전 제거

```bash
# 모든 컨테이너 중지 및 삭제
docker-compose down

# 이미지 삭제
docker rmi coupang-worker

# 생성한 파일 삭제
rm /home/tech/packet_coupang_v1/Dockerfile
rm /home/tech/packet_coupang_v1/docker-compose.yml
```

### 기존 방식으로 복귀

```bash
# 단일 프로세스로 실행
python3 coupang.py work -t rank -n 0 -p 20
```

---

## 8. 예상 결과

### 성능 비교

| 방식 | 워커 | 병렬 | 처리량 | 안정성 |
|------|:----:|:----:|:-----:|:-----:|
| 현재 (단일) | 1 | p=20 | 2/초 | ✅ |
| Docker 5개 | 5 | p=20 | 10/초 | ✅ |
| Docker 10개 | 10 | p=20 | 20/초 | ✅ |
| Docker 15개 | 15 | p=20 | 30/초 | ⚠️ 테스트 필요 |

### 리소스 사용량

| 워커 수 | 메모리 | CPU |
|:------:|:-----:|:---:|
| 5개 | ~5GB | ~50% |
| 10개 | ~10GB | ~80% |
| 15개 | ~15GB | ~100% |

---

## 9. 문제 해결

### 컨테이너 시작 실패

```bash
# 로그 확인
docker-compose logs worker

# 이미지 재빌드
docker-compose build --no-cache
```

### DB 연결 실패

```bash
# config.json 마운트 확인
docker-compose exec worker cat /app/config.json
```

### 메모리 부족

```bash
# 워커 수 줄이기
docker-compose up -d --scale worker=5

# 또는 메모리 제한 조정 (docker-compose.yml)
```

---

## 10. 체크리스트

- [ ] Docker 설치 확인
- [ ] Dockerfile 생성
- [ ] docker-compose.yml 생성
- [ ] requirements.txt 확인
- [ ] 단일 컨테이너 테스트
- [ ] 2개 컨테이너 테스트
- [ ] 5개 컨테이너 테스트
- [ ] 10개 컨테이너 테스트
- [ ] 처리량 측정
- [ ] 안정성 확인 (1시간 이상)

---

## 변경 이력

| 날짜 | 내용 |
|------|------|
| 2025-11-28 | 초안 작성 |
