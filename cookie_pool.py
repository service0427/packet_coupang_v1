#!/usr/bin/env python3
"""
쿠키 풀 유지 스크립트
- 100개 쿠키를 최신 상태로 유지
- 주기적으로 login.coupang.com 접속하여 쿠키 갱신
"""

import sys
import json
import time
import random
import argparse
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, str(Path(__file__).parent / 'lib'))

from db import execute_query
from common import (
    get_fingerprint, parse_cookies, build_extra_fp, build_headers,
    update_cookie_data, timestamp
)
from curl_cffi import requests

# 설정
POOL_SIZE = 100
REFRESH_URL = 'https://login.coupang.com/login/login.pang'
PROXY_API_URL = 'http://mkt.techb.kr:3001/api/proxy/status'


def get_proxy_from_api():
    """API에서 프록시 1개 조회"""
    try:
        resp = requests.get(f'{PROXY_API_URL}?remain=60', timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('success') and data.get('proxies'):
                proxy_info = data['proxies'][0]
                return f"socks5://{proxy_info['proxy']}"
    except Exception as e:
        print(f"프록시 API 오류: {e}")
    return None


def parse_response_cookies(resp):
    """응답에서 쿠키 파싱"""
    from http.cookies import SimpleCookie
    cookies_list = []

    if hasattr(resp, 'headers'):
        set_cookies = resp.headers.get_list('set-cookie') if hasattr(resp.headers, 'get_list') else []

        if not set_cookies:
            set_cookie = resp.headers.get('set-cookie', '')
            if set_cookie:
                set_cookies = [set_cookie]

        for sc in set_cookies:
            cookie = SimpleCookie()
            try:
                cookie.load(sc)
                for name, morsel in cookie.items():
                    result = {
                        'name': name,
                        'value': morsel.value,
                        'domain': morsel.get('domain', '.coupang.com'),
                        'path': morsel.get('path', '/'),
                    }
                    if morsel.get('max-age'):
                        try:
                            max_age = int(morsel.get('max-age'))
                            result['expires'] = time.time() + max_age
                        except:
                            pass
                    cookies_list.append(result)
            except:
                pass

    return cookies_list


def refresh_cookie(cookie_id, proxy):
    """쿠키 갱신 - login 페이지 접속"""
    # 쿠키 조회
    cookie_record = execute_query("SELECT * FROM cookies WHERE id = %s", (cookie_id,))
    if not cookie_record:
        return {'id': cookie_id, 'success': False, 'error': '쿠키 없음'}

    cookie_record = cookie_record[0]

    # 핑거프린트 조회
    fingerprint = get_fingerprint(cookie_record['chrome_version'])
    if not fingerprint:
        return {'id': cookie_id, 'success': False, 'error': '핑거프린트 없음'}

    # 쿠키 파싱
    cookies = parse_cookies(cookie_record)

    # 갱신 전 Akamai 쿠키 값 저장 (비교용)
    akamai_names = ['_abck', 'ak_bmsc', 'bm_mi', 'bm_s', 'bm_so', 'bm_sv', 'bm_sz']
    before_cookies = {name: cookies.get(name, '')[:20] for name in akamai_names if name in cookies}

    # 요청
    try:
        ja3_text = fingerprint['ja3_text']
        akamai_text = fingerprint['akamai_text']
        extra_fp = build_extra_fp(fingerprint)
        headers = build_headers(fingerprint)

        resp = requests.get(
            REFRESH_URL,
            headers=headers,
            cookies=cookies,
            ja3=ja3_text,
            akamai=akamai_text,
            extra_fp=extra_fp,
            proxy=proxy,
            timeout=30,
            verify=False
        )

        size = len(resp.content)

        if resp.status_code == 200 and size > 1000:
            # 응답 쿠키 파싱 및 업데이트
            response_cookies = parse_response_cookies(resp)

            # 갱신 후 쿠키 값 (비교용)
            after_cookies = {}
            changed_cookies = []
            for rc in response_cookies:
                name = rc.get('name')
                if name in akamai_names:
                    value = rc.get('value', '')[:20]
                    after_cookies[name] = value
                    # 변경 여부 확인
                    if name in before_cookies and before_cookies[name] != value:
                        changed_cookies.append(name)
                    elif name not in before_cookies:
                        changed_cookies.append(f"{name}(new)")

            if response_cookies:
                updated = update_cookie_data(cookie_id, response_cookies)

                # last_used_at 업데이트
                execute_query("""
                    UPDATE cookies SET last_used_at = NOW() WHERE id = %s
                """, (cookie_id,))

                return {
                    'id': cookie_id,
                    'success': True,
                    'size': size,
                    'updated': updated,
                    'before': before_cookies,
                    'after': after_cookies,
                    'changed': changed_cookies
                }
            else:
                return {
                    'id': cookie_id,
                    'success': True,
                    'size': size,
                    'updated': 0,
                    'before': before_cookies,
                    'after': {},
                    'changed': []
                }
        else:
            return {
                'id': cookie_id,
                'success': False,
                'error': f'STATUS_{resp.status_code}_{size}B'
            }

    except Exception as e:
        return {
            'id': cookie_id,
            'success': False,
            'error': str(e)[:50]
        }


def get_pool_cookies(limit=POOL_SIZE):
    """풀에서 관리할 쿠키 조회 (최신순)"""
    cookies = execute_query("""
        SELECT id, chrome_version, proxy_ip, created_at, last_used_at,
               use_count, success_count, fail_count
        FROM cookies
        ORDER BY id DESC
        LIMIT %s
    """, (limit,))
    return cookies


def run_refresh(args):
    """쿠키 갱신 실행"""
    print("=" * 60)
    print("쿠키 풀 갱신")
    print("=" * 60)
    print(f"시작: {datetime.now().strftime('%H:%M:%S')}")

    # 프록시 조회
    proxy = get_proxy_from_api()
    if not proxy:
        print("❌ 프록시 조회 실패")
        return

    print(f"프록시: {proxy}")

    # 쿠키 조회
    cookies = get_pool_cookies(args.size)
    if not cookies:
        print("❌ 쿠키 없음")
        return

    print(f"쿠키: {len(cookies)}개")
    print(f"ID 범위: {cookies[-1]['id']} ~ {cookies[0]['id']}")
    print("=" * 60)

    # 병렬 갱신
    success_count = 0
    fail_count = 0
    total_updated = 0
    all_changed = {}  # 변경된 쿠키 통계

    # 갱신할 쿠키 ID 목록
    pending_ids = [c['id'] for c in cookies]
    max_retries = 3
    retry_count = 0

    with ThreadPoolExecutor(max_workers=args.threads) as executor:
        while pending_ids and retry_count <= max_retries:
            if retry_count > 0:
                print(f"\n[재시도 #{retry_count}] {len(pending_ids)}개")

            futures = {
                executor.submit(refresh_cookie, cid, proxy): cid
                for cid in pending_ids
            }

            failed_ids = []

            for future in as_completed(futures):
                result = future.result()

                if result['success']:
                    success_count += 1
                    total_updated += result.get('updated', 0)

                    # 변경된 쿠키 수집
                    for name in result.get('changed', []):
                        all_changed[name] = all_changed.get(name, 0) + 1

                    if args.verbose:
                        changed = result.get('changed', [])
                        if changed:
                            print(f"  ✅ {result['id']}: {result.get('updated', 0)}개 ({', '.join(changed)})")
                        else:
                            print(f"  ✅ {result['id']}: {result.get('updated', 0)}개")
                else:
                    failed_ids.append(result['id'])
                    if args.verbose:
                        print(f"  ❌ {result['id']}: {result.get('error')}")

            # 다음 재시도를 위해 실패 목록 갱신
            pending_ids = failed_ids
            retry_count += 1

        # 최종 실패
        fail_count = len(pending_ids)
        if pending_ids:
            print(f"\n⚠️  최종 실패: {pending_ids}")

    print("\n" + "=" * 60)
    print("결과")
    print("=" * 60)
    print(f"성공: {success_count}")
    print(f"실패: {fail_count}")
    print(f"쿠키 갱신: {total_updated}개")

    # 변경된 쿠키 통계 출력
    if all_changed:
        print(f"\n변경된 쿠키:")
        for name, count in sorted(all_changed.items(), key=lambda x: -x[1]):
            print(f"  {name}: {count}회")

    print(f"\n완료: {datetime.now().strftime('%H:%M:%S')}")


def run_daemon(args):
    """데몬 모드 - 주기적 갱신"""
    print("=" * 60)
    print("쿠키 풀 데몬")
    print("=" * 60)
    print(f"풀 크기: {args.size}")
    print(f"갱신 주기: {args.interval}분")
    print(f"쓰레드: {args.threads}")
    print("=" * 60)

    try:
        while True:
            run_refresh(args)

            next_run = datetime.now().strftime('%H:%M:%S')
            print(f"\n다음 갱신: {args.interval}분 후")
            print("-" * 60)

            time.sleep(args.interval * 60)

    except KeyboardInterrupt:
        print("\n중단됨")


def run_status(args):
    """풀 상태 조회"""
    cookies = get_pool_cookies(args.size)

    if not cookies:
        print("쿠키 없음")
        return

    print("=" * 60)
    print(f"쿠키 풀 상태 ({len(cookies)}개)")
    print("=" * 60)

    now = datetime.now()
    fresh = 0  # 1시간 이내
    stale = 0  # 1시간 초과

    for c in cookies:
        if c['last_used_at']:
            age = (now - c['last_used_at']).total_seconds()
            if age < 3600:
                fresh += 1
            else:
                stale += 1
        else:
            # last_used_at이 없으면 created_at 기준
            age = (now - c['created_at']).total_seconds()
            if age < 3600:
                fresh += 1
            else:
                stale += 1

    print(f"신선 (1시간 이내): {fresh}")
    print(f"오래됨 (1시간 초과): {stale}")
    print(f"ID 범위: {cookies[-1]['id']} ~ {cookies[0]['id']}")

    # 최근 5개 상세
    print("\n최근 5개:")
    for c in cookies[:5]:
        last = c['last_used_at'] or c['created_at']
        age_min = int((now - last).total_seconds() / 60)
        print(f"  {c['id']}: Chrome {c['chrome_version']}, {age_min}분 전, "
              f"사용 {c['use_count']}회 (성공 {c['success_count']})")


def main():
    parser = argparse.ArgumentParser(
        description='쿠키 풀 유지 관리',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  # 1회 갱신
  python3 cookie_pool.py refresh

  # 데몬 모드 (10분마다)
  python3 cookie_pool.py daemon --interval 10

  # 상태 확인
  python3 cookie_pool.py status
"""
    )

    subparsers = parser.add_subparsers(dest='command', help='명령어')

    # refresh
    refresh_parser = subparsers.add_parser('refresh', help='1회 갱신')
    refresh_parser.add_argument('-s', '--size', type=int, default=POOL_SIZE, help=f'풀 크기 (기본: {POOL_SIZE})')
    refresh_parser.add_argument('-t', '--threads', type=int, default=10, help='쓰레드 수 (기본: 10)')
    refresh_parser.add_argument('-v', '--verbose', action='store_true', help='상세 출력')

    # daemon
    daemon_parser = subparsers.add_parser('daemon', help='데몬 모드')
    daemon_parser.add_argument('-s', '--size', type=int, default=POOL_SIZE, help=f'풀 크기 (기본: {POOL_SIZE})')
    daemon_parser.add_argument('-i', '--interval', type=int, default=10, help='갱신 주기 (분, 기본: 10)')
    daemon_parser.add_argument('-t', '--threads', type=int, default=10, help='쓰레드 수 (기본: 10)')
    daemon_parser.add_argument('-v', '--verbose', action='store_true', help='상세 출력')

    # status
    status_parser = subparsers.add_parser('status', help='상태 확인')
    status_parser.add_argument('-s', '--size', type=int, default=POOL_SIZE, help=f'풀 크기 (기본: {POOL_SIZE})')

    args = parser.parse_args()

    if args.command == 'refresh':
        run_refresh(args)
    elif args.command == 'daemon':
        run_daemon(args)
    elif args.command == 'status':
        run_status(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
