#!/usr/bin/env python3
"""
Coupang CLI - 쿠키 생성 및 상품 검색

핵심 알고리즘:
  랜덤 IP (바인딩) + 랜덤 쿠키 (/24 매칭) + 랜덤 TLS = 성공
  차단 = IP Rate Limit 뿐

명령어:
  cookie - 쿠키 생성 (브라우저)
  search - 상품 검색 (curl-cffi)
  work   - 작업 할당 API 기반 검색
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
  # 쿠키 생성
  python3 coupang.py cookie
  python3 coupang.py cookie -t 2 -l 5    # 2스레드, 조합당 5개

  # 상품 검색
  python3 coupang.py search
  python3 coupang.py search --product-id 12345678 --query "검색어"

  # 작업 실행 (기본: 무한 루프, 병렬 2)
  python3 coupang.py work                # rank, 무한, 병렬 2
  python3 coupang.py work -t click       # click 타입
  python3 coupang.py work -n 10          # 10회만 실행
  python3 coupang.py work -p 5           # 병렬 5
  python3 coupang.py work -n 10 -p 3     # 10회, 병렬 3

  # 특정 작업 ID (1회 실행)
  python3 coupang.py work --id 123
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
    search_parser.add_argument('--product-id', default='9024146312', help='상품 ID (기본: 호박 달빛식혜)')
    search_parser.add_argument('--query', default='호박 달빛식혜', help='검색어')
    search_parser.add_argument('--max-page', type=int, default=13, help='최대 페이지')
    search_parser.add_argument('--no-click', action='store_true', help='클릭/직접접속 건너뛰기')
    search_parser.add_argument('--proxy', help='프록시 URL 직접 지정')
    search_parser.add_argument('--screenshot', action='store_true', help='상품 발견 시 스크린샷 저장')
    search_parser.add_argument('--exclude-subnets', help='제외할 서브넷 (쉼표 구분, 예: 110.70.14,39.7.47)')

    # Work subcommand - 작업 할당 API 기반 검색
    work_parser = subparsers.add_parser('work', help='작업 할당 API 기반 검색')
    work_parser.add_argument('-t', '--type', choices=['rank', 'click', 'filter'], default='rank', help='작업 타입 (기본: rank)')
    work_parser.add_argument('--id', type=int, help='특정 작업 ID 조회 (1회 실행)')
    work_parser.add_argument('--max-page', type=int, default=13, help='최대 검색 페이지')
    work_parser.add_argument('--no-click', action='store_true', help='클릭 건너뛰기')
    work_parser.add_argument('-n', '--count', type=int, default=0, help='실행 횟수 (0=무한, 기본: 무한)')
    work_parser.add_argument('-p', '--parallel', type=int, default=2, help='병렬 수 (기본: 2)')
    work_parser.add_argument('--delay', type=float, default=0, help='실행 간격 초 (기본: 0)')
    work_parser.add_argument('--min-remain', type=int, default=30, help='프록시 최소 남은 시간 초 (기본: 30)')

    args = parser.parse_args()

    if args.command == 'cookie':
        from browser.cookie_cmd import run_cookie
        run_cookie(args)
    elif args.command == 'search':
        from cffi.search_cmd import run_search
        run_search(args)
    elif args.command == 'work':
        from cffi.work_cmd import run_work, run_work_loop, run_filter
        if args.type == 'filter':
            run_filter(args)
        elif args.id:
            # 특정 ID는 1회만 실행
            run_work(args)
        else:
            # 기본: 병렬 루프 (n=0이면 무한, n>0이면 횟수 제한)
            run_work_loop(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
