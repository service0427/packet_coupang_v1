#!/usr/bin/env python3
"""
Rank 테스트 루프
python3 rank_test.py -n 10
"""

import sys
import subprocess
import argparse
import time
import re
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'lib'))
from common.db import insert_one, execute_query

def parse_result(output):
    """출력에서 결과 파싱"""
    result = {}

    # 키워드 파싱: "🎲 랜덤 선택 [PL#2362]: 수세미솔 (상품 ID: 8805482155)"
    match = re.search(r'\[PL#(\d+)\]: (.+?) \(상품 ID: (\d+)\)', output)
    if match:
        result['pl_id'] = match.group(1)
        result['keyword'] = match.group(2)
        result['product_id'] = match.group(3)

    # 순위 파싱: "실제 순위: 7등" (미발견 시 0)
    match = re.search(r'실제 순위: (\d+)등', output)
    if match:
        result['rank'] = int(match.group(1))
    else:
        result['rank'] = 0

    # 쿠키 ID 파싱: "✅ 쿠키:3381"
    match = re.search(r'쿠키:(\d+)', output)
    if match:
        result['cookie_id'] = int(match.group(1))

    # IP 파싱: "현재 IP: 175.223.38.238"
    match = re.search(r'현재 IP: ([\d.]+)', output)
    if match:
        result['proxy_ip'] = match.group(1)

    return result

def main():
    parser = argparse.ArgumentParser(description='Rank 테스트 루프')
    parser.add_argument('-n', '--count', type=int, default=10, help='반복 횟수 (기본: 10)')
    parser.add_argument('--delay', type=int, default=2, help='딜레이 초 (기본: 2)')
    args = parser.parse_args()

    print(f"루프: {args.count}회 | 딜레이: {args.delay}초")
    print("=" * 60)

    saved_count = 0
    found_count = 0

    for i in range(1, args.count + 1):
        print(f"\n[{i}/{args.count}] {datetime.now().strftime('%H:%M:%S')}")

        result = subprocess.run(
            ['python3', 'coupang.py', 'search', '--random'],
            capture_output=True,
            text=True
        )
        print(result.stdout)

        # 쿠키 없으면 중단
        if '쿠키 없음' in result.stdout:
            print("\n❌ 쿠키 없음 - 중단")
            break

        # 차단이 아닌 경우만 DB 저장
        if '차단됨' not in result.stdout and 'BLOCKED' not in result.stdout and 'CHALLENGE' not in result.stdout:
            parsed = parse_result(result.stdout)
            if parsed.get('keyword'):
                # use_count, cookie_age 조회
                use_count = 1
                cookie_age = 0
                if parsed.get('cookie_id'):
                    cookie_result = execute_query(
                        'SELECT success_count, TIMESTAMPDIFF(SECOND, created_at, NOW()) as age FROM cookies WHERE id = %s',
                        (parsed.get('cookie_id'),)
                    )
                    if cookie_result:
                        use_count = cookie_result[0]['success_count'] + 1
                        cookie_age = cookie_result[0]['age']

                insert_one("""
                    INSERT INTO rank_test_logs
                    (pl_id, keyword, product_id, rank, cookie_id, use_count, cookie_age, proxy_ip)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    parsed.get('pl_id'),
                    parsed.get('keyword'),
                    parsed.get('product_id'),
                    parsed.get('rank', 0),
                    parsed.get('cookie_id'),
                    use_count,
                    cookie_age,
                    parsed.get('proxy_ip')
                ))
                saved_count += 1
                if parsed.get('rank', 0) > 0:
                    found_count += 1

        if i < args.count:
            time.sleep(args.delay)

    # 결과 요약
    print(f"\n{'=' * 60}")
    print(f"📊 결과: {saved_count}건 저장 (발견: {found_count})")
    print(f"완료: {args.count}회")

if __name__ == '__main__':
    main()
