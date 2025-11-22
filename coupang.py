#!/usr/bin/env python3
"""
Coupang CLI - 쿠키 생성 및 상품 등수 체크
"""

import sys
import argparse

def main():
    parser = argparse.ArgumentParser(
        description='Coupang Akamai Bypass CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  # 쿠키 생성 (프록시당 1개씩)
  python3 coupang.py cookie

  # 쿠키 생성 (쓰레드/조합 지정)
  python3 coupang.py cookie -t 2 -l 5

  # 상품 등수 체크 (기본: 호박 달빛식혜)
  python3 coupang.py rank
  python3 coupang.py rank --product-id 12345678 --query "검색어"
"""
    )

    subparsers = parser.add_subparsers(dest='command', help='명령어')

    # Cookie subcommand
    cookie_parser = subparsers.add_parser('cookie', help='쿠키 생성')
    cookie_parser.add_argument('-t', '--threads', type=int, help='쓰레드 수 (기본: 프록시 수)')
    cookie_parser.add_argument('-l', '--loop', type=int, default=1, help='조합당 쿠키 수 (기본: 1)')
    cookie_parser.add_argument('-v', '--version', help='특정 Chrome 버전')
    cookie_parser.add_argument('-p', '--proxy', help='특정 프록시')

    # Rank subcommand
    rank_parser = subparsers.add_parser('rank', help='상품 등수 체크')
    rank_parser.add_argument('--cookie-id', type=int, help='쿠키 ID (생략 시 최신)')
    rank_parser.add_argument('--product-id', default='9024146312', help='상품 ID (기본: 호박 달빛식혜)')
    rank_parser.add_argument('--query', default='호박 달빛식혜', help='검색어')
    rank_parser.add_argument('--max-page', type=int, default=13, help='최대 페이지')
    rank_parser.add_argument('--no-click', action='store_true', help='클릭 건너뛰기')
    rank_parser.add_argument('--proxy', help='프록시 URL')
    rank_parser.add_argument('--platform', default='u22', help='TLS 플랫폼')
    # TODO: --item-id, --vendor-item-id 완전매칭 옵션 추가 예정

    args = parser.parse_args()

    if args.command == 'cookie':
        from lib.cookie_cmd import run_cookie
        run_cookie(args)
    elif args.command == 'rank':
        from lib.rank_cmd import run_rank
        run_rank(args)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
