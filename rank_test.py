#!/usr/bin/env python3
"""
유효한 쿠키 중 1개로 rank 테스트
"""

import sys
import subprocess
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'lib'))

from db import execute_query
from usage_log import print_usage_stats
from common import DEV_PROXY, get_dev_proxy_ip


def get_valid_cookie(proxy_ip=None):
    """유효한 쿠키 1개 조회 (랜덤)

    Args:
        proxy_ip: 특정 프록시 IP의 쿠키만 조회 (None이면 전체)
    """
    if proxy_ip:
        result = execute_query("""
            SELECT id FROM cookies
            WHERE created_at >= NOW() - INTERVAL 600 SECOND
              AND use_count < 10
              AND success_count >= fail_count
              AND proxy_ip = %s
            ORDER BY RAND()
            LIMIT 1
        """, (proxy_ip,))
    else:
        result = execute_query("""
            SELECT id FROM cookies
            WHERE created_at >= NOW() - INTERVAL 600 SECOND
              AND use_count < 10
              AND success_count >= fail_count
            ORDER BY RAND()
            LIMIT 1
        """)
    return result[0]['id'] if result else None


def main():
    parser = argparse.ArgumentParser(description='쿠키 테스트')
    parser.add_argument('--stats', action='store_true', help='통계만 출력')
    parser.add_argument('--cookie-id', type=int, help='특정 쿠키 ID')
    parser.add_argument('-l', '--loop', type=int, default=1, help='반복 횟수 (기본: 1)')
    parser.add_argument('-p', '--max-page', type=int, default=13, help='최대 페이지 (기본: 13)')
    parser.add_argument('--batch', action='store_true', help='점진적 배치 검색 (1→2-3→4-13)')
    parser.add_argument('--random', action='store_true', help='DB에서 키워드 선택')
    parser.add_argument('--pl-id', type=int, help='product_list ID (--random과 함께 사용)')
    parser.add_argument('--dev', action='store_true', help='개발용 프록시 사용')
    args = parser.parse_args()

    # 개발 프록시 설정
    dev_proxy_ip = None
    proxy_arg = []
    if args.dev:
        dev_proxy_ip = get_dev_proxy_ip()
        if not dev_proxy_ip:
            print("❌ 개발 프록시 IP 확인 실패")
            return
        print(f"🔧 개발 프록시: {DEV_PROXY['socks5']} (IP: {dev_proxy_ip})")
        proxy_arg = ['--proxy', DEV_PROXY['socks5']]

    # 통계만 출력
    if args.stats:
        print_usage_stats()
        return

    for i in range(1, args.loop + 1):
        if args.loop > 1:
            print(f"\n{'='*60}")
            print(f"[{i}/{args.loop}]")
            print('='*60)

        # 쿠키 선택
        if args.cookie_id:
            cookie_id = args.cookie_id
        else:
            cookie_id = get_valid_cookie(dev_proxy_ip)

        if not cookie_id:
            if dev_proxy_ip:
                print(f"❌ 유효한 쿠키 없음 (IP: {dev_proxy_ip})")
            else:
                print("❌ 유효한 쿠키 없음")
            return

        print(f"🔄 쿠키 {cookie_id} 테스트")

        cmd = ['python3', 'coupang.py', 'rank', '--cookie-id', str(cookie_id), '--max-page', str(args.max_page)]
        if args.batch:
            cmd.append('--batch')
        if args.random:
            cmd.append('--random')
        if args.pl_id:
            cmd.extend(['--pl-id', str(args.pl_id)])
        if proxy_arg:
            cmd.extend(proxy_arg)

        subprocess.run(cmd, cwd=str(Path(__file__).parent))

    if args.loop > 1:
        print(f"\n{'='*60}")
        print(f"완료: {args.loop}회 실행")
        print('='*60)


if __name__ == '__main__':
    main()
