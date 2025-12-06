#!/usr/bin/env python3
"""
API 스트레스 테스트

Usage:
    python3 tests/api_stress_test.py                    # 기본: 5스레드, 200회, 단일 모드
    python3 tests/api_stress_test.py -t 10 -n 500       # 10스레드, 500회
    python3 tests/api_stress_test.py --multi            # 멀티-트라이 모드
    python3 tests/api_stress_test.py --url http://...   # URL 지정
"""

import argparse
import requests
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed


def run_test(url, total, workers, mode='single'):
    results = []
    lock = threading.Lock()
    start_time = time.time()

    def check_rank(idx):
        try:
            st = time.time()
            resp = requests.get(url, timeout=60)
            elapsed = int((time.time() - st) * 1000)
            data = resp.json()

            success = data.get('success', False)
            error_code = data.get('error', {}).get('code') if not success else None
            found = data.get('data', {}).get('found') if success else None
            meta = data.get('meta', {}) or {}
            match_type = meta.get('match_type')
            tries_count = meta.get('tries_count')
            tries_total = meta.get('tries_total')
            round_num = meta.get('round')
            round_detail = meta.get('round_detail')

            with lock:
                results.append({
                    'idx': idx,
                    'success': success,
                    'found': found,
                    'error': error_code,
                    'match_type': match_type,
                    'tries_count': tries_count,
                    'tries_total': tries_total,
                    'round': round_num,
                    'round_detail': round_detail,
                    'elapsed': elapsed
                })

                # 진행 상황 (20개마다)
                if len(results) % 20 == 0:
                    elapsed_total = time.time() - start_time
                    rate = len(results) / elapsed_total
                    success_so_far = sum(1 for r in results if r['success'])
                    print(f'[{len(results):3d}/{total}] {rate:.1f}/sec | 성공: {success_so_far} | elapsed: {elapsed_total:.0f}s')

            return True
        except Exception as e:
            with lock:
                results.append({
                    'idx': idx,
                    'success': False,
                    'found': None,
                    'error': str(e)[:30],
                    'match_type': None,
                    'tries_count': None,
                    'tries_total': None,
                    'elapsed': 0
                })
            return False

    mode_label = 'Progressive Retry (1→2→3→4)' if mode == 'multi' else '단일'
    print(f'🚀 테스트 시작: {total}회, {workers} 스레드, {mode_label}')
    print(f'   URL: {url}')
    print('=' * 60)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(check_rank, i) for i in range(total)]
        for f in as_completed(futures):
            pass

    total_time = time.time() - start_time

    # 결과 분석
    print()
    print('=' * 60)
    print(f'📊 결과 요약 ({total_time:.1f}초) - {mode_label}')
    print('=' * 60)

    success_count = sum(1 for r in results if r['success'])
    found_count = sum(1 for r in results if r['success'] and r['found'])
    not_found_count = sum(1 for r in results if r['success'] and not r['found'])
    fail_count = sum(1 for r in results if not r['success'])

    print(f'✅ 성공: {success_count}/{total} ({success_count/total*100:.1f}%)')
    print(f'   - 발견: {found_count}')
    print(f'   - 미발견: {not_found_count}')
    print(f'❌ 실패: {fail_count}/{total} ({fail_count/total*100:.1f}%)')

    # 에러 분류
    errors = Counter(r['error'] for r in results if not r['success'])
    if errors:
        print(f'\n에러 유형:')
        for err, cnt in errors.most_common(5):
            print(f'   {err}: {cnt}')

    # 매칭 타입 분류
    match_types = Counter(r['match_type'] for r in results if r['success'])
    if match_types:
        print(f'\n매칭 타입:')
        for mt, cnt in match_types.most_common():
            print(f'   {mt}: {cnt}')

    # Progressive Retry 라운드 분석
    if mode == 'multi':
        # 라운드별 분포
        round_dist = Counter(r.get('round') for r in results if r.get('round') is not None)
        if round_dist:
            print(f'\n🎯 라운드별 성공 분포:')
            for rnd, cnt in sorted(round_dist.items()):
                pct = cnt / len(results) * 100
                label = {1: 'R1(1회)', 2: 'R2(2회)', 3: 'R3(3회)', 4: 'R4(4회)'}.get(rnd, f'R{rnd}')
                print(f'   {label}: {cnt} ({pct:.1f}%)')

        # 시도 횟수 분석
        tries_list = [r.get('tries_count') for r in results if r.get('tries_count') is not None]
        if tries_list:
            avg_tries = sum(tries_list) / len(tries_list)
            print(f'\n🔄 시도 횟수:')
            print(f'   평균: {avg_tries:.1f}회 (최대 10회)')
            tries_dist = Counter(tries_list)
            for t, cnt in sorted(tries_dist.items()):
                print(f'   {t}회: {cnt}')

    # 응답 시간 분석
    elapsed_list = [r['elapsed'] for r in results if r['elapsed'] > 0]
    if elapsed_list:
        avg = sum(elapsed_list) / len(elapsed_list)
        min_e = min(elapsed_list)
        max_e = max(elapsed_list)
        print(f'\n⏱️ 응답 시간:')
        print(f'   평균: {avg:.0f}ms')
        print(f'   최소: {min_e}ms / 최대: {max_e}ms')

        # 분포
        under_2s = sum(1 for e in elapsed_list if e < 2000)
        under_5s = sum(1 for e in elapsed_list if e < 5000)
        under_10s = sum(1 for e in elapsed_list if e < 10000)
        over_10s = sum(1 for e in elapsed_list if e >= 10000)
        print(f'   <2초: {under_2s} | <5초: {under_5s} | <10초: {under_10s} | ≥10초: {over_10s}')

    print(f'\n🔥 처리량: {total/total_time:.2f} req/sec')


def main():
    parser = argparse.ArgumentParser(description='API 스트레스 테스트')
    parser.add_argument('-t', '--threads', type=int, default=5, help='스레드 수 (기본: 5)')
    parser.add_argument('-n', '--count', type=int, default=200, help='요청 횟수 (기본: 200)')
    parser.add_argument('--multi', action='store_true', help='멀티-트라이 모드 (5회 동시 시도)')
    parser.add_argument('--url', default=None, help='API URL (기본: localhost:8088)')
    args = parser.parse_args()

    if args.url:
        url = args.url
        mode = 'multi' if 'multi' in url else 'single'
    elif args.multi:
        url = 'http://localhost:8088/api/rank/sample-multi'
        mode = 'multi'
    else:
        url = 'http://localhost:8088/api/rank/sample'
        mode = 'single'

    run_test(url, args.count, args.threads, mode)


if __name__ == '__main__':
    main()
