#!/usr/bin/env python3
"""
데이터베이스 테이블 생성 스크립트
- fingerprints: TLS 핑거프린트 저장
- cookies: 브라우저 생성 쿠키 저장
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'lib'))
from db import get_cursor, test_connection

def create_tables():
    """테이블 생성"""

    # fingerprints 테이블
    fingerprints_sql = """
    CREATE TABLE IF NOT EXISTS fingerprints (
        id INT AUTO_INCREMENT PRIMARY KEY,

        -- Chrome 버전 정보
        chrome_version VARCHAR(50) NOT NULL COMMENT '전체 버전 (136.0.7103.113)',
        chrome_major INT NOT NULL COMMENT '메이저 버전 (136)',
        platform VARCHAR(20) NOT NULL COMMENT 'u22, win11 등',

        -- curl-cffi 필수 파라미터
        ja3_text TEXT NOT NULL COMMENT 'JA3 문자열',
        ja3_hash VARCHAR(64) NOT NULL COMMENT 'JA3 해시',
        akamai_text TEXT NOT NULL COMMENT 'Akamai HTTP/2 핑거프린트',
        akamai_hash VARCHAR(64) NOT NULL COMMENT 'Akamai 해시',
        user_agent TEXT NOT NULL COMMENT 'User-Agent 문자열',

        -- extra_fp용 추출 데이터
        signature_algorithms JSON COMMENT 'signature_algorithms 이름 배열',

        -- 원본 데이터 보존
        raw_data JSON NOT NULL COMMENT '원본 TLS 프로파일 전체',

        -- 메타데이터
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

        -- 인덱스
        UNIQUE KEY uk_version_platform (chrome_version, platform),
        INDEX idx_chrome_major (chrome_major),
        INDEX idx_ja3_hash (ja3_hash)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    COMMENT='TLS 핑거프린트 저장';
    """

    # cookies 테이블
    cookies_sql = """
    CREATE TABLE IF NOT EXISTS cookies (
        id INT AUTO_INCREMENT PRIMARY KEY,

        -- IP 바인딩 (핵심!)
        proxy_ip VARCHAR(45) NOT NULL COMMENT '프록시 외부 IP (쿠키 생성 시)',
        proxy_url VARCHAR(255) COMMENT '프록시 URL (socks5://host:port)',

        -- Chrome 버전 정보
        chrome_version VARCHAR(50) NOT NULL COMMENT '쿠키 생성에 사용된 Chrome 버전',
        chrome_major INT NOT NULL COMMENT '메이저 버전',

        -- 핑거프린트 연결
        fingerprint_id INT COMMENT 'fingerprints 테이블 FK',

        -- 쿠키 데이터
        cookie_data JSON NOT NULL COMMENT '전체 쿠키 배열',
        cookie_count INT DEFAULT 0 COMMENT '쿠키 개수',

        -- Akamai 쿠키 검증
        abck_value TEXT COMMENT '_abck 쿠키 값',
        abck_valid BOOLEAN DEFAULT FALSE COMMENT '_abck에 ~-1~ 포함 여부',

        -- 도메인 정보
        source_domain VARCHAR(100) DEFAULT 'www.coupang.com' COMMENT '쿠키 생성 도메인',

        -- 사용 통계
        use_count INT DEFAULT 0 COMMENT '사용 횟수',
        success_count INT DEFAULT 0 COMMENT '성공 횟수',
        fail_count INT DEFAULT 0 COMMENT '실패 횟수',
        last_used_at TIMESTAMP NULL COMMENT '마지막 사용 시간',
        last_result VARCHAR(50) COMMENT '마지막 결과 (SUCCESS, BLOCKED 등)',

        -- 상태 관리
        status ENUM('active', 'expired', 'blocked', 'exhausted') DEFAULT 'active',
        expires_at TIMESTAMP NULL COMMENT '만료 시간',

        -- 메타데이터
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

        -- 인덱스
        INDEX idx_proxy_ip (proxy_ip),
        INDEX idx_status (status),
        INDEX idx_chrome_major (chrome_major),
        INDEX idx_created_at (created_at),
        FOREIGN KEY (fingerprint_id) REFERENCES fingerprints(id) ON DELETE SET NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    COMMENT='브라우저 생성 쿠키 저장 (IP 바인딩 포함)';
    """

    # 테이블 생성 실행
    with get_cursor() as cursor:
        print("Creating fingerprints table...")
        cursor.execute(fingerprints_sql)
        print("✅ fingerprints 테이블 생성 완료")

        print("\nCreating cookies table...")
        cursor.execute(cookies_sql)
        print("✅ cookies 테이블 생성 완료")

        # 생성된 테이블 확인
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        print("\n현재 테이블 목록:")
        for table in tables:
            table_name = list(table.values())[0]
            cursor.execute(f"SELECT COUNT(*) as cnt FROM {table_name}")
            count = cursor.fetchone()['cnt']
            print(f"  - {table_name}: {count} rows")

def main():
    print("=" * 60)
    print("데이터베이스 테이블 생성")
    print("=" * 60)

    # 연결 테스트
    if not test_connection():
        print("❌ 데이터베이스 연결 실패")
        return

    print("✅ 데이터베이스 연결 성공\n")

    # 테이블 생성
    create_tables()

    print("\n" + "=" * 60)
    print("테이블 생성 완료")
    print("=" * 60)

if __name__ == '__main__':
    main()
