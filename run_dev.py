#!/usr/bin/env python3
"""
개발용 테스트 스크립트
- 개발 프록시 IP 토글
- 새 쿠키 생성
- rank 테스트 실행
"""

import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'lib'))

from common import DEV_PROXY, toggle_dev_proxy, get_dev_proxy_ip


def main():
    parser = argparse.ArgumentParser(description='개발용 테스트')
    subparsers = parser.add_subparsers(dest='command', help='명령어')

    # IP 토글
    toggle_parser = subparsers.add_parser('toggle', help='프록시 IP 토글')

    # IP 확인
    ip_parser = subparsers.add_parser('ip', help='현재 프록시 IP 확인')

    # 쿠키 생성 + 테스트
    test_parser = subparsers.add_parser('test', help='IP 토글 → 쿠키 생성 → rank 테스트')
    test_parser.add_argument('--chrome', default='136.0.7103.113', help='Chrome 버전')
    test_parser.add_argument('--product-id', default='9024146312', help='상품 ID')
    test_parser.add_argument('--query', default='호박 달빛식혜', help='검색어')

    # 쿠키만 생성
    cookie_parser = subparsers.add_parser('cookie', help='개발 프록시로 쿠키 생성')
    cookie_parser.add_argument('--chrome', default='136.0.7103.113', help='Chrome 버전')

    args = parser.parse_args()

    if args.command == 'toggle':
        print("🔄 프록시 IP 토글 중...")
        result = toggle_dev_proxy()
        if result.get('success'):
            print(f"✅ 새 IP: {result['ip']}")
            print(f"   Step: {result['step']}")
        else:
            print(f"❌ 실패: {result.get('error')}")

    elif args.command == 'ip':
        print("🔍 현재 프록시 IP 확인 중...")
        ip = get_dev_proxy_ip()
        if ip:
            print(f"✅ 현재 IP: {ip}")
            print(f"   프록시: {DEV_PROXY['socks5']}")
        else:
            print("❌ IP 조회 실패")

    elif args.command == 'cookie':
        # IP 토글 후 쿠키 생성
        print("=" * 60)
        print("개발용 쿠키 생성")
        print("=" * 60)

        # 1. IP 토글
        print("\n1️⃣ 프록시 IP 토글...")
        result = toggle_dev_proxy()
        if not result.get('success'):
            print(f"❌ IP 토글 실패: {result.get('error')}")
            return

        new_ip = result['ip']
        print(f"   새 IP: {new_ip}")

        # 2. 쿠키 생성
        print(f"\n2️⃣ 쿠키 생성 중... (Chrome {args.chrome})")
        from cookie_loop import generate_cookies_loop

        results = generate_cookies_loop(
            version=args.chrome,
            proxy=DEV_PROXY['socks5'],
            loop_count=1
        )

        if results and results[0].get('cookie_id'):
            cookie_id = results[0]['cookie_id']
            print(f"✅ 쿠키 생성 완료")
            print(f"   쿠키 ID: {cookie_id}")
        else:
            print(f"❌ 쿠키 생성 실패")

    elif args.command == 'test':
        # IP 토글 → 쿠키 생성 → rank 테스트
        print("=" * 60)
        print("개발 테스트 (IP 토글 → 쿠키 생성 → Rank)")
        print("=" * 60)

        # 1. IP 토글
        print("\n1️⃣ 프록시 IP 토글...")
        result = toggle_dev_proxy()
        if not result.get('success'):
            print(f"❌ IP 토글 실패: {result.get('error')}")
            return

        new_ip = result['ip']
        print(f"   새 IP: {new_ip}")

        # 2. 쿠키 생성
        print(f"\n2️⃣ 쿠키 생성 중... (Chrome {args.chrome})")
        from cookie_loop import generate_cookies_loop

        results = generate_cookies_loop(
            version=args.chrome,
            proxy=DEV_PROXY['socks5'],
            loop_count=1
        )

        if not results or not results[0].get('cookie_id'):
            print(f"❌ 쿠키 생성 실패")
            return

        cookie_id = results[0]['cookie_id']
        print(f"   쿠키 ID: {cookie_id}")

        # 3. Rank 테스트
        print(f"\n3️⃣ Rank 테스트...")
        import subprocess
        cmd = [
            'python3', 'coupang.py', 'rank',
            '--cookie-id', str(cookie_id),
            '--product-id', args.product_id,
            '--query', args.query
        ]
        subprocess.run(cmd)

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
