#!/usr/bin/env python3
"""
쿠키 풀 유지 스크립트
- 유효한 쿠키가 100개 이하면 쿠키 생성
- 중복 실행 방지 (lock 파일)
"""

import sys
import os
import subprocess
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent / 'lib'))

from common.db import execute_query

# 설정
LOCK_FILE = '/tmp/cookie_maintain.lock'


def get_valid_cookie_count():
    """유효한 쿠키 개수 조회 (60분 이내)"""
    result = execute_query("""
        SELECT COUNT(*) as cnt FROM cookies
        WHERE created_at >= NOW() - INTERVAL 60 MINUTE
        AND source = 'local'
    """)
    return result[0]['cnt'] if result else 0


def acquire_lock():
    """락 획득 (중복 실행 방지)"""
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, 'r') as f:
                pid = int(f.read().strip())
            os.kill(pid, 0)
            return False  # 이미 실행 중
        except (OSError, ValueError):
            pass

    with open(LOCK_FILE, 'w') as f:
        f.write(str(os.getpid()))
    return True


def release_lock():
    """락 해제"""
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)


def main():
    now = datetime.now().strftime('%H:%M:%S')

    # 락 획득
    if not acquire_lock():
        print(f"[{now}] ⚠️ 이미 실행 중")
        return

    try:
        # 유효한 쿠키 수 확인
        count = get_valid_cookie_count()

        if count > 1000:
            print(f"[{now}] ✅ 충분함 ({count}개)")
            return

        print(f"[{now}] 🔄 쿠키 부족 ({count}개) - 생성 시작")

        # 쿠키 생성
        result = subprocess.run(
            ['python3', 'coupang.py', 'cookie', '-t', '20', '-l', '1'],
            cwd=str(Path(__file__).parent),
            timeout=600
        )

        # 생성 후 확인
        new_count = get_valid_cookie_count()
        print(f"[{now}] 완료: {count} → {new_count}개")

    except subprocess.TimeoutExpired:
        print(f"[{now}] ❌ 타임아웃")
    except Exception as e:
        print(f"[{now}] ❌ 오류: {e}")
    finally:
        release_lock()


if __name__ == '__main__':
    main()
