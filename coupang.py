#!/usr/bin/env python3
"""
Coupang CLI - 쿠키 생성 및 상품 검색

핵심 알고리즘:
  랜덤 IP (바인딩) + 랜덤 쿠키 (/24 매칭) + 랜덤 TLS = 성공
  차단 = IP Rate Limit 뿐

명령어:
  cookie - 쿠키 생성 (브라우저)
  search - 상품 검색 (curl-cffi)
"""

import sys
import argparse
from pathlib import Path

# lib 경로 추가
sys.path.insert(0, str(Path(__file__).parent / 'lib'))


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

  # 상품 검색 (기본: 호박 달빛식혜)
  python3 coupang.py search
  python3 coupang.py search --product-id 12345678 --query "검색어"

  # DB에서 랜덤 키워드 검색
  python3 coupang.py search --random
"""
    )

    subparsers = parser.add_subparsers(dest='command', help='명령어')

    # Cookie subcommand - 쿠키 생성 (브라우저)
    cookie_parser = subparsers.add_parser('cookie', help='쿠키 생성 (브라우저)')
    cookie_parser.add_argument('-t', '--threads', type=int, help='쓰레드 수 (기본: 프록시 수)')
    cookie_parser.add_argument('-l', '--loop', type=int, default=1, help='조합당 쿠키 수 (기본: 1)')
    cookie_parser.add_argument('-v', '--version', help='특정 Chrome 버전')
    cookie_parser.add_argument('-p', '--proxy', help='특정 프록시')
    cookie_parser.add_argument('--dev', action='store_true', help='개발용 프록시 사용')
    cookie_parser.add_argument('--toggle', action='store_true', help='개발 프록시 IP 토글')

    # Search subcommand - 상품 검색 (curl-cffi)
    search_parser = subparsers.add_parser('search', help='상품 검색 (curl-cffi)')
    search_parser.add_argument('--cookie-id', type=int, help='쿠키 ID (생략 시 IP 바인딩 자동 선택)')
    search_parser.add_argument('--random', action='store_true', help='DB에서 키워드 랜덤 선택')
    search_parser.add_argument('--pl-id', type=int, help='product_list ID (--random과 함께)')
    search_parser.add_argument('--product-id', default='9024146312', help='상품 ID (기본: 호박 달빛식혜)')
    search_parser.add_argument('--query', default='호박 달빛식혜', help='검색어')
    search_parser.add_argument('--max-page', type=int, default=13, help='최대 페이지')
    search_parser.add_argument('--no-click', action='store_true', help='클릭/직접접속 건너뛰기')
    search_parser.add_argument('--proxy', help='프록시 URL 직접 지정')
    search_parser.add_argument('--screenshot', action='store_true', help='상품 발견 시 스크린샷 저장')
    search_parser.add_argument('--exclude-subnets', help='제외할 서브넷 (쉼표 구분, 예: 110.70.14,39.7.47)')

    args = parser.parse_args()

    if args.command == 'cookie':
        from browser.cookie_cmd import run_cookie
        run_cookie(args)
    elif args.command == 'search':
        from cffi.search_cmd import run_search
        run_search(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
