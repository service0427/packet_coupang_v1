#!/usr/bin/env python3
"""
작업 실행 - 직접 연결 방식 (쿠키/프록시 미사용)

Flow:
1. 할당: GET http://mkt.techb.kr:3302/api/work/allocate?work_type=rank
2. 체크: lib/api/rank_checker_direct.check_rank() 직접 호출
3. 결과: POST http://mkt.techb.kr:3302/api/work/result

사용법:
  python3 work_direct.py rank              # rank 작업 (단일)
  python3 work_direct.py rank --loop       # 무한 반복
  python3 work_direct.py rank -p 5         # 5개 병렬 실행
  python3 work_direct.py rank -n 100       # 100번 실행 후 종료

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️  직접 연결 모드
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- 쿠키 API (5151) 미사용
- 프록시 미사용 (본인 IP로 직접 연결)
- Chrome 143 Mobile TLS 핑거프린트

❌ 대량 요청 시 IP 차단 위험!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import warnings
warnings.filterwarnings('ignore')

import sys
import os

# lib 폴더를 path에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib'))

import time
import argparse
import requests
import threading
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 직접 연결 모듈 import
from api.rank_checker_direct import check_rank as _check_rank, get_public_ip

# API 설정
WORK_API = 'http://mkt.techb.kr:3302'
CHROME_VERSION = '143.0.0.0'

# 쓰레드별 세션
_thread_local = threading.local()


def get_session():
    """쓰레드별 재사용 가능한 requests 세션"""
    if not hasattr(_thread_local, 'session'):
        _thread_local.session = requests.Session()
        retry = Retry(total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry, pool_connections=50, pool_maxsize=50)
        _thread_local.session.mount('http://', adapter)
    return _thread_local.session


def allocate_work(work_type='rank', task_id=None, user_folder=None, verbose=True, debug=False):
    """작업 할당 (3302) - 프록시 미사용"""
    try:
        url = f"{WORK_API}/api/work/allocate?work_type={work_type}&proxy=false"
        if task_id:
            url += f"&task_id={task_id}"
        if user_folder:
            url += f"&user_folder={user_folder}"
        if verbose:
            print(f"GET {url}")
        resp = get_session().get(url, timeout=15)
        data = resp.json()
        if debug:
            import json
            print(f"[DEBUG] allocate: {json.dumps(data, ensure_ascii=False)}")
        return data if data.get('success') else None
    except Exception as e:
        if debug:
            print(f"[DEBUG] allocate error: {e}")
        return None


def check_rank(keyword, product_id, item_id=None, vendor_item_id=None, max_page=13, verbose=True):
    """순위 체크 (직접 연결)"""
    try:
        result = _check_rank(
            keyword=keyword,
            product_id=str(product_id),
            item_id=str(item_id) if item_id else None,
            vendor_item_id=str(vendor_item_id) if vendor_item_id else None,
            max_page=max_page
        )

        # HTTP API 응답 형식으로 변환
        if result.get('error_code'):
            return {
                'success': False,
                'error': {
                    'code': result['error_code'],
                    'message': result.get('error_message', ''),
                    'detail': result.get('error_detail')
                },
                'meta': {
                    'pages_searched': result.get('pages_searched', 0),
                    'elapsed_ms': result.get('elapsed_ms', 0),
                    'chrome_version': result.get('chrome_version')
                }
            }

        return {
            'success': True,
            'data': {
                'keyword': keyword,
                'product_id': product_id,
                'item_id': item_id,
                'vendor_item_id': vendor_item_id,
                'found': result['found'],
                'rank': result.get('rank'),
                'page': result.get('page'),
                'rating': result.get('rating'),
                'review_count': result.get('review_count'),
                'id_match_type': result.get('id_match_type')
            },
            'meta': {
                'pages_searched': result.get('pages_searched', 0),
                'elapsed_ms': result.get('elapsed_ms', 0),
                'chrome_version': result.get('chrome_version')
            }
        }

    except Exception as e:
        import traceback
        print(f"\n[ERROR] check_rank 내부 치명적 에러 발생: {e}")
        traceback.print_exc()
        return {"success": False, "error": {"code": "MODULE_ERROR", "message": str(e)[:100]}}


def report_result(allocation_key, success, actual_ip, rank_data, chrome_version=None,
                  rating=None, review_count=None,
                  error_type=None, error_message=None, verbose=True, debug=False):
    """결과 보고 (3302)"""
    import json as _json
    url = f"{WORK_API}/api/work/result"

    if success:
        payload = {
            'allocation_key': allocation_key,
            'success': True,
            'actual_ip': actual_ip,
            'rank_data': rank_data
        }
        if rating is not None:
            payload['rating'] = rating
        if review_count is not None:
            payload['review_count'] = review_count
    else:
        payload = {
            'allocation_key': allocation_key,
            'success': False,
            'actual_ip': actual_ip,
            'error_type': error_type or 'blocked',
            'error_message': error_message or 'Request blocked'
        }

    if chrome_version:
        payload['chrome_version'] = chrome_version

    if debug:
        print(f"[DEBUG] report POST: {_json.dumps(payload, ensure_ascii=False)}")

    if verbose:
        print(f"POST {url}")

    try:
        resp = get_session().post(url, json=payload, timeout=15)
        return resp.json()
    except:
        return None


def run_work(args):
    """작업 실행"""
    verbose = getattr(args, 'verbose', True)
    debug = getattr(args, 'debug', False)
    start_time = time.time()

    if verbose:
        print("=" * 60)
        print(f"직접 연결 워커 [{args.work_type}]")
        print("=" * 60)

    # 공인 IP 조회
    actual_ip = get_public_ip()
    if verbose:
        print(f"\n📡 공인 IP: {actual_ip}")

    # 1. 작업 할당
    if verbose:
        print(f"\n📥 작업 할당...")

    user_folder = getattr(args, 'user_folder', None) or 'wk_d0'
    alloc = allocate_work(args.work_type, getattr(args, 'task_id', None), user_folder, verbose, debug)

    if not alloc:
        if verbose:
            print("❌ 작업 없음")
        return None

    if verbose:
        import json
        print(json.dumps(alloc, ensure_ascii=False, indent=2))

    key = alloc['allocation_key']
    keyword = alloc['keyword']
    product_id = str(alloc['product_id'])
    item_id = alloc.get('item_id')
    vendor_item_id = alloc.get('vendor_item_id')

    # 2. 순위 체크
    if verbose:
        print(f"\n🔍 순위 체크 (직접 연결)...")

    result = check_rank(keyword, product_id, item_id, vendor_item_id, args.max_page, verbose)

    if result is None:
        result = {"success": False, "error": {"code": "NULL_RESPONSE", "message": "Module returned null"}}

    if debug:
        import json
        print(f"[DEBUG] check_rank: {json.dumps(result, ensure_ascii=False)}")

    if verbose:
        import json
        print(json.dumps(result, ensure_ascii=False, indent=2))

    success = result.get('success', False)
    data = result.get('data') or {}
    meta = result.get('meta') or {}

    found = data.get('found', False)
    rank = data.get('rank') or 0
    page = data.get('page') or 0
    pages_searched = meta.get('pages_searched', 0) or 0
    id_match_type = data.get('id_match_type', '')
    chrome = meta.get('chrome_version', CHROME_VERSION)
    rating = data.get('rating')
    review_count = data.get('review_count')

    error_info = result.get('error') or {}
    error_code = error_info.get('code', '')
    error_message = error_info.get('message', '')

    elapsed_ms = meta.get('elapsed_ms', 0)
    total_elapsed_ms = int((time.time() - start_time) * 1000)
    elapsed_ms = elapsed_ms if elapsed_ms > 0 else total_elapsed_ms

    # 3. 결과 보고
    if success:
        if found:
            rank_data = {'rank': rank, 'page': page, 'listSize': 72}
        else:
            rank_data = {'rank': 0, 'page': pages_searched, 'listSize': 72}
    else:
        rank_data = {'rank': 0, 'page': 0, 'listSize': 72}

    if verbose:
        import json
        print(f"\n📤 결과 보고...")
        if success and found:
            print(f"   ✅ 발견: {rank}위 (페이지 {page})")
        elif success:
            print(f"   ❌ 미발견 ({pages_searched}페이지 검색)")
        else:
            print(f"   🚫 실패: {error_code}")

    resp = report_result(
        key, success, actual_ip, rank_data, chrome,
        rating=rating if found else None,
        review_count=review_count if found else None,
        error_type=error_code if not success else None,
        error_message=error_message if not success else None,
        verbose=verbose,
        debug=debug
    )

    if verbose:
        import json
        if resp:
            print(f"   → {json.dumps(resp, ensure_ascii=False)}")
        else:
            print(f"   → ⚠️ 보고 실패")

    report_success = resp.get('success', False) if resp else False
    report_msg = resp.get('message', '') or resp.get('error', '') if resp else 'no response'

    return {
        'success': success, 'found': found, 'rank': rank, 'page': page,
        'keyword': keyword, 'product_id': product_id,
        'item_id': item_id, 'vendor_item_id': vendor_item_id,
        'id_match_type': id_match_type,
        'pages_searched': pages_searched,
        'error_code': error_code,
        'elapsed_ms': elapsed_ms,
        'report_success': report_success,
        'report_msg': report_msg
    }


def run_loop(args):
    """무한 반복"""
    stats = {'found': 0, 'not_found': 0, 'failed': 0}
    count = 0

    print(f"\n🔄 무한 반복 (Ctrl+C 종료)")
    print("=" * 60)

    try:
        while True:
            count += 1
            print(f"\n[#{count}] {time.strftime('%H:%M:%S')}")
            result = run_work(args)

            if result is None:
                print("   작업 없음 - 10초 대기...")
                time.sleep(10)
            elif not result['success']:
                stats['failed'] += 1
            elif result['found']:
                stats['found'] += 1
            else:
                stats['not_found'] += 1

            if count % 10 == 0:
                print(f"\n📊 {count}회 | 발견:{stats['found']} 미발견:{stats['not_found']} 실패:{stats['failed']}")
    except KeyboardInterrupt:
        print(f"\n\n중단. {count}회 | 발견:{stats['found']} 미발견:{stats['not_found']} 실패:{stats['failed']}")


def run_count(args):
    """N번 실행"""
    stats = {'found': 0, 'not_found': 0, 'failed': 0, 'no_task': 0}
    total = args.count

    print(f"\n🔢 {total}번 실행")
    print("=" * 60)

    for i in range(total):
        print(f"\n[{i+1}/{total}] {time.strftime('%H:%M:%S')}")
        result = run_work(args)

        if result is None:
            stats['no_task'] += 1
            print("   작업 없음")
        elif not result['success']:
            stats['failed'] += 1
        elif result['found']:
            stats['found'] += 1
        else:
            stats['not_found'] += 1

    print(f"\n\n완료. {total}회 | 발견:{stats['found']} 미발견:{stats['not_found']} 실패:{stats['failed']} 없음:{stats['no_task']}")


def run_parallel(args):
    """병렬 실행"""
    parallel = args.parallel
    stats = {'total': 0, 'found': 0, 'not_found': 0, 'failed': 0, 'no_task': 0}
    stats_lock = threading.Lock()

    actual_ip = get_public_ip()

    print(f"\n🚀 병렬 모드 ({parallel}개) | IP: {actual_ip}")
    print("=" * 60)

    def worker_loop(wid):
        a = argparse.Namespace(**vars(args))
        a.verbose = False
        a.user_folder = f"dk_{wid:02d}"

        while True:
            r = run_work(a)

            should_sleep = False
            with stats_lock:
                stats['total'] += 1
                now = time.time()
                ts = time.strftime('%H:%M:%S', time.localtime(now))

                if r is None:
                    stats['no_task'] += 1
                    print(f"[{ts}][D{wid:02d}] ⏸️ 없음", flush=True)
                    should_sleep = True
                elif not r['success']:
                    stats['failed'] += 1
                    err = r.get('error_code', 'UNKNOWN')[:15]
                    pages = r.get('pages_searched', 0)
                    print(f"[{ts}][D{wid:02d}] 🚫 {err} P{pages} | {r['elapsed_ms']/1000:.1f}s | {r['keyword'][:25]}", flush=True)
                elif r['found']:
                    stats['found'] += 1
                    print(f"[{ts}][D{wid:02d}] ✅ P{r['page']:2d} #{r['rank']:3d} | {r['elapsed_ms']/1000:.1f}s | {r['keyword'][:30]}", flush=True)
                else:
                    stats['not_found'] += 1
                    pages = r.get('pages_searched', 0)
                    print(f"[{ts}][D{wid:02d}] ❌ 미발견 P{pages:2d} | {r['elapsed_ms']/1000:.1f}s | {r['keyword'][:30]}", flush=True)

            if should_sleep:
                time.sleep(10)
            elif not r['success'] and r.get('error_code') in ('INTERNAL_ERROR', 'MODULE_ERROR'):
                print(f"[{ts}][D{wid:02d}] ⏳ 60초 휴식 (INTERNAL_ERROR 방지)", flush=True)
                time.sleep(60)

    threads = []
    try:
        for i in range(parallel):
            t = threading.Thread(target=worker_loop, args=(i + 1,), daemon=True)
            t.start()
            threads.append(t)
            time.sleep(0.5)

        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print(f"\n\n중단. {stats['total']}회 | 발견:{stats['found']} 미발견:{stats['not_found']} 실패:{stats['failed']}")


def main():
    parser = argparse.ArgumentParser(description='직접 연결 워커 (쿠키/프록시 미사용)')
    parser.add_argument('work_type', choices=['rank', 'dev_rank'], help='작업 타입')
    parser.add_argument('--loop', '-l', action='store_true', help='무한 반복')
    parser.add_argument('--parallel', '-p', type=int, help='병렬 수')
    parser.add_argument('--count', '-n', type=int, help='실행 횟수')
    parser.add_argument('--max-page', type=int, default=15, help='최대 페이지 (기본: 15, 약 300등)')
    parser.add_argument('--task-id', type=int, help='특정 task ID')
    parser.add_argument('--verbose', '-v', action='store_true', default=True)
    parser.add_argument('--debug', '-d', action='store_true', help='디버그 모드')

    args = parser.parse_args()

    if args.parallel:
        run_parallel(args)
    elif args.loop:
        run_loop(args)
    elif args.count:
        run_count(args)
    else:
        run_work(args)


if __name__ == '__main__':
    main()
