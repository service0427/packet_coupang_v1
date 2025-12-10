FROM python:3.11-slim

WORKDIR /app

# 시스템 의존성
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python 패키지
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 복사
COPY . .

# 환경변수
ENV PYTHONUNBUFFERED=1

# 기본 실행 (docker-compose에서 오버라이드 가능)
CMD ["python3", "work.py", "rank", "-p", "5"]
