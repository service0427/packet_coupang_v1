#!/usr/bin/env python3
"""
작업 실행 - API 기반 (3302 + localhost:8088)

Flow:
1. 할당: GET http://mkt.techb.kr:3302/api/work/allocate?work_type=rank
2. 체크: POST http://localhost:8088/api/rank/check-multi
3. 결과: POST http://mkt.techb.kr:3302/api/work/result

사용법:
  python3 work.py rank              # rank 작업 (단일)
  python3 work.py rank --loop       # 무한 반복
  python3 work.py rank -p 5         # 5개 병렬 실행

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️  3302 API 결과 포맷 (수정 금지)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
POST /api/work/result

성공 (찾음):
  {allocation_key, success:true, actual_ip, rank_data:{rank,page,listSize},
   rating, review_count, proxy_id?, chrome_version}

성공 (못찾음):
  {allocation_key, success:true, actual_ip, rank_data:{rank:0,page,listSize},
   chrome_version}

실패 (차단):
  {allocation_key, success:false, actual_ip, error_type, error_message}

❌ work_type, work_data 래퍼 사용 안함!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import warnings
warnings.filterwarnings('ignore')

import time
import argparse
import requests
import threading
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# API 설정
WORK_API = 'http://mkt.techb.kr:3302'
RANK_API = 'http://localhost:8088'

# 쓰레드별 세션 (ThreadLocal)
_thread_local = threading.local()


def get_session():
    """쓰레드별 재사용 가능한 requests 세션"""
    if not hasattr(_thread_local, 'session'):
        _thread_local.session = requests.Session()
        retry = Retry(total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry, pool_connections=50, pool_maxsize=50)
        _thread_local.session.mount('http://', adapter)
    return _thread_local.session


def allocate_work(work_type='rank', task_id=None, user_folder=None, verbose=True, show_url=True, debug=False):
    """작업 할당 (3302)"""
    try:
        url = f"{WORK_API}/api/work/allocate?work_type={work_type}"
        if task_id:
            url += f"&task_id={task_id}"
        if user_folder:
            url += f"&user_folder={user_folder}"
        if verbose and show_url:
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
    """순위 체크 (localhost:8088)"""
    try:
        url = f"{RANK_API}/api/rank/check"
        payload = {"keyword": keyword, "product_id": str(product_id), "max_page": max_page}
        if item_id:
            payload["item_id"] = str(item_id)
        if vendor_item_id:
            payload["vendor_item_id"] = str(vendor_item_id)
        if verbose:
            print(f"POST {url}")
        resp = get_session().post(url, json=payload, timeout=60)
        return resp.json()
    except Exception as e:
        return {"success": False, "error": {"code": "API_ERROR", "message": str(e)[:100]}}


def report_result(allocation_key, success, actual_ip, rank_data, chrome_version=None,
                  proxy_id=None, rating=None, review_count=None,
                  error_type=None, error_message=None, verbose=True, debug=False):
    """결과 보고 (3302)

    ⚠️ API 스펙 (수정 금지) ⚠️
    ─────────────────────────────────────────────────────────────
    성공 시 (상품 찾음):
    {
      "allocation_key": "abc123-task-id",
      "success": true,
      "actual_ip": "123.456.78.90",
      "rank_data": {"page": 3, "listSize": 36, "rank": 15},
      "rating": 4.8,              # 찾았을 때만
      "review_count": 1523,       # 찾았을 때만
      "proxy_id": 12345,          # 옵션
      "chrome_version": "138.0.7204.49"
    }

    성공 시 (상품 못찾음):
    {
      "allocation_key": "abc123-task-id",
      "success": true,
      "actual_ip": "123.456.78.90",
      "rank_data": {"page": 13, "listSize": 36, "rank": 0},
      "chrome_version": "138.0.7204.49"
    }

    실패 시 (차단/에러):
    {
      "allocation_key": "abc123-task-id",
      "success": false,
      "actual_ip": "123.456.78.90",
      "error_type": "blocked",
      "error_message": "Request blocked by Akamai"
    }

    ❌ 사용하지 않는 필드: work_type, work_data (래퍼 없음!)
    ─────────────────────────────────────────────────────────────
    """
    import json as _json
    url = f"{WORK_API}/api/work/result"

    if success:
        # 성공: 찾음 또는 못찾음
        payload = {
            'allocation_key': allocation_key,
            'success': True,
            'actual_ip': actual_ip,
            'rank_data': rank_data
        }
        # 옵션 필드
        if proxy_id:
            payload['proxy_id'] = proxy_id
        if rating is not None:
            payload['rating'] = rating
        if review_count is not None:
            payload['review_count'] = review_count
    else:
        # 실패: 차단/에러
        payload = {
            'allocation_key': allocation_key,
            'success': False,
            'actual_ip': actual_ip,
            'error_type': error_type or 'blocked',
            'error_message': error_message or 'Request blocked'
        }
        if proxy_id:
            payload['proxy_id'] = proxy_id

    if chrome_version:
        payload['chrome_version'] = chrome_version

    if debug:
        print(f"[DEBUG] report_result POST: {_json.dumps(payload, ensure_ascii=False)}")

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
    start_time = time.time()  # 전체 소요 시간 측정

    if verbose:
        print("=" * 60)
        print(f"API 작업 실행 [{args.work_type}]")
        print("=" * 60)

    # 1. 할당
    if verbose:
        print(f"\n📥 작업 할당 (3302)...")

    user_folder = getattr(args, 'user_folder', None) or 'worker_00'
    alloc = allocate_work(args.work_type, getattr(args, 'task_id', None), user_folder, verbose, debug=debug)
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
        print(f"\n🔍 순위 체크 (localhost:8088)...")

    result = check_rank(keyword, product_id, item_id, vendor_item_id, args.max_page, verbose)

    # result가 None이면 빈 dict로 처리
    if result is None:
        result = {"success": False, "error": {"code": "NULL_RESPONSE", "message": "API returned null"}}

    # 디버그: API 응답 전체 출력
    if debug:
        import json
        print(f"[DEBUG] check_rank response: {json.dumps(result, ensure_ascii=False)}")

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
    id_match_type = data.get('id_match_type', '')  # full_match, product_vendor, product_item, product_only, vendor_only, item_only
    proxy_ip = meta.get('proxy_ip', '')
    proxy_id = meta.get('proxy_id')  # 프록시 ID
    chrome = meta.get('cookie_chrome', '')
    cookie_match_type = meta.get('match_type', '')  # new_exact, new_subnet, old_exact, old_subnet
    cookie_age = meta.get('cookie_age_seconds', 0) or 0
    cookie_id = meta.get('cookie_id')  # 쿠키 추적용
    rating = data.get('rating')  # 상품 평점
    review_count = data.get('review_count')  # 리뷰 수

    # 에러 정보 추출
    error_info = result.get('error') or {}
    error_code = error_info.get('code', '')
    error_message = error_info.get('message', '')

    # API elapsed_ms 먼저 계산 (결과 보고에 사용)
    api_elapsed = meta.get('elapsed_ms', 0)
    total_elapsed_ms = int((time.time() - start_time) * 1000)
    elapsed_ms = api_elapsed if api_elapsed > 0 else total_elapsed_ms

    # 3. 결과 보고
    # rank_data 구성:
    # - 찾음: rank=실제순위, page=발견페이지
    # - 못찾음: rank=0, page=검색한마지막페이지 (pages_searched)
    # - 차단: success=false로 처리
    if success:
        if found:
            rank_data = {'rank': rank, 'page': page, 'listSize': 72}
        else:
            # 못 찾음: page는 검색한 마지막 페이지 (page >= 6이어야 인정)
            rank_data = {'rank': 0, 'page': pages_searched, 'listSize': 72}
    else:
        rank_data = {'rank': 0, 'page': 0, 'listSize': 72}

    if verbose:
        import json
        print(f"\n📤 결과 보고 (3302)...")
        payload_preview = {
            'allocation_key': key,
            'success': success,
            'actual_ip': proxy_ip,
            'rank_data': rank_data if success else None,
            'rating': rating if success and found else None,
            'review_count': review_count if success and found else None,
            'error_type': error_code if not success else None,
            'chrome_version': chrome
        }
        print(json.dumps({k: v for k, v in payload_preview.items() if v is not None}, ensure_ascii=False, indent=2))

    resp = report_result(
        key, success, proxy_ip, rank_data, chrome,
        proxy_id=proxy_id,
        rating=rating if found else None,
        review_count=review_count if found else None,
        error_type=error_code if not success else None,
        error_message=error_message if not success else None,
        verbose=verbose,
        debug=debug
    )
    if verbose:
        if resp:
            print(f"→ {json.dumps(resp, ensure_ascii=False)}")
        else:
            print(f"→ ⚠️ 실패")

    # 결과 보고 성공 여부 확인
    if debug and resp:
        import json
        print(f"[DEBUG] report resp: {json.dumps(resp, ensure_ascii=False)}")
    report_success = resp.get('success', False) if resp else False
    # message가 없으면 error 필드 사용
    report_msg = resp.get('message', '') or resp.get('error', '') if resp else 'no response'

    return {
        'success': success, 'found': found, 'rank': rank, 'page': page,
        'keyword': keyword, 'product_id': product_id,
        'item_id': item_id, 'vendor_item_id': vendor_item_id,
        'id_match_type': id_match_type,
        'cookie_match_type': cookie_match_type,  # new_exact, new_subnet, old_exact, old_subnet
        'cookie_age': cookie_age,  # 쿠키 나이 (초)
        'cookie_id': cookie_id,  # 쿠키 ID (추적용)
        'proxy_ip': proxy_ip, 'elapsed_ms': elapsed_ms,
        'report_success': report_success,  # 결과 보고 성공 여부
        'report_msg': report_msg  # 결과 보고 메시지
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
                print("   작업 없음 - 5초 대기...")
                time.sleep(5)
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


def run_parallel(args):
    """병렬 실행 (연속 방식 - 각 워커가 독립적으로 무한 루프)"""
    parallel = args.parallel
    stats = {'total': 0, 'found': 0, 'not_found': 0, 'failed': 0, 'no_task': 0}
    stats_lock = threading.Lock()

    print(f"\n🚀 병렬 모드 ({parallel}개)", flush=True)
    print("=" * 60, flush=True)

    def worker_loop(wid):
        """각 워커가 독립적으로 무한 루프"""
        a = argparse.Namespace(**vars(args))
        a.verbose = False
        a.user_folder = f"worker_{wid:02d}"  # 워커별 고유 폴더

        while True:
            r = run_work(a)

            should_sleep = False
            with stats_lock:
                stats['total'] += 1
                now = time.time()
                ts = time.strftime('%H:%M:%S', time.localtime(now)) + f".{int((now % 1) * 1000):03d}"

                if r is None:
                    stats['no_task'] += 1
                    print(f"[{ts}][{wid:2d}] ⏸️ 없음", flush=True)
                    should_sleep = True

            # 락 밖에서 sleep (다른 쓰레드 블록 방지)
            if should_sleep:
                time.sleep(30)
                continue

            # 공통 정보 추출 (락 밖에서)
            kw = r.get('keyword', '')
            pid = str(r.get('product_id', '') or '')
            iid = str(r.get('item_id', '') or '')
            vid = str(r.get('vendor_item_id', '') or '')
            ip = r.get('proxy_ip', '') or '-'
            elapsed = r.get('elapsed_ms', 0) / 1000
            id_match = r.get('id_match_type', '') or ''
            cookie_match = r.get('cookie_match_type', '') or ''
            cookie_age = r.get('cookie_age', 0) or 0
            cid = r.get('cookie_id') or 0  # 쿠키 ID

            # ID 매칭 타입 축약 (4자리)
            id_short = {
                'full_match': 'FULL',
                'product_vendor': 'P+V ',
                'product_item': 'P+I ',
                'product_only': 'P   ',
                'vendor_only': 'V   ',
                'item_only': 'I   '
            }.get(id_match, '    ')

            # 쿠키 매칭 타입 축약 (2자리)
            cookie_short = {
                'new_exact': 'NE',
                'new_subnet': 'NS',
                'old_exact': 'OE',
                'old_subnet': 'OS'
            }.get(cookie_match, '--')

            # 결과 보고 상태
            report_ok = r.get('report_success', False)
            if not report_ok and 'successfully' in r.get('report_msg', ''):
                report_ok = True
            rs = 'R:OK' if report_ok else 'R:NG'

            # 통계 업데이트 및 출력 (락 안에서)
            with stats_lock:
                now = time.time()
                ts = time.strftime('%H:%M:%S', time.localtime(now)) + f".{int((now % 1) * 1000):03d}"

                if not r['success']:
                    stats['failed'] += 1
                    print(f"[{ts}][{wid:2d}] 🚫 P 0 #  0 | {ip:15s} | {elapsed:5.2f}s | C:{cid:<6} {cookie_short} {cookie_age:4d}s [    ] {rs} | P:{pid:>10s} I:{iid:>11s} V:{vid:>11s} | {kw}\n", flush=True)
                elif r['found']:
                    stats['found'] += 1
                    print(f"[{ts}][{wid:2d}] ✅ P{r['page']:2d} #{r['rank']:3d} | {ip:15s} | {elapsed:5.2f}s | C:{cid:<6} {cookie_short} {cookie_age:4d}s [{id_short}] {rs} | P:{pid:>10s} I:{iid:>11s} V:{vid:>11s} | {kw}\n", flush=True)
                else:
                    stats['not_found'] += 1
                    print(f"[{ts}][{wid:2d}] ❌ P 0 #  0 | {ip:15s} | {elapsed:5.2f}s | C:{cid:<6} {cookie_short} {cookie_age:4d}s [    ] {rs} | P:{pid:>10s} I:{iid:>11s} V:{vid:>11s} | {kw}\n", flush=True)

    # 워커 쓰레드 시작 (0.5초 간격으로 순차 시작 - 초기 동시 요청 방지)
    threads = []
    try:
        for i in range(parallel):
            t = threading.Thread(target=worker_loop, args=(i + 1,), daemon=True)
            t.start()
            threads.append(t)
            if i < parallel - 1:  # 마지막 워커 제외
                time.sleep(0.5)

        # 메인 쓰레드는 대기 (Ctrl+C 받을 때까지)
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print(f"\n\n중단. {stats['total']}회 | 발견:{stats['found']} 미발견:{stats['not_found']} 실패:{stats['failed']}")


def main():
    parser = argparse.ArgumentParser(description='Work Executor (3302 + localhost:8088)')
    parser.add_argument('work_type', choices=['rank', 'dev_rank'], help='작업 타입')
    parser.add_argument('--loop', '-l', action='store_true', help='무한 반복')
    parser.add_argument('--parallel', '-p', type=int, help='병렬 수')
    parser.add_argument('--max-page', type=int, default=13, help='최대 페이지')
    parser.add_argument('--task-id', type=int, help='특정 task ID')
    parser.add_argument('--verbose', '-v', action='store_true', default=True)
    parser.add_argument('--debug', '-d', action='store_true', help='디버그 모드 (할당 응답 출력)')

    args = parser.parse_args()

    if args.parallel:
        run_parallel(args)
    elif args.loop:
        run_loop(args)
    else:
        run_work(args)


if __name__ == '__main__':
    main()
