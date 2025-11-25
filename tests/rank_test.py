#!/usr/bin/env python3
"""
Rank 테스트 - 병렬 실행
python3 rank_test.py -n 100 -w 20

Ctrl+C로 중단 시 현재까지 결과 출력
"""

import sys
import signal
import subprocess
import argparse
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# 전역 취소 플래그
cancelled = False


def get_display_width(text):
    """문자열의 실제 표시 폭 계산 (한글=2, 영문=1)"""
    width = 0
    for char in text:
        if unicodedata.east_asian_width(char) in ('F', 'W'):
            width += 2
        else:
            width += 1
    return width


def pad_to_width(text, width):
    """지정된 폭에 맞게 패딩 추가"""
    current_width = get_display_width(text)
    if current_width >= width:
        return text
    return text + ' ' * (width - current_width)

sys.path.insert(0, str(Path(__file__).parent.parent / 'lib'))
from common.db import insert_one, execute_query


def parse_result(output):
    """출력에서 결과 파싱"""
    result = {}

    # 키워드 파싱: "🎲 랜덤 선택 [PL#2362]: 검색어"
    match = re.search(r'\[PL#(\d+)\]: (.+)', output)
    if match:
        result['pl_id'] = match.group(1)
        result['keyword'] = match.group(2).strip()

    # 타겟 파싱: "타겟: 8805482155"
    match = re.search(r'타겟: (\d+)', output)
    if match:
        result['product_id'] = match.group(1)

    # 순위 파싱: "순위: 7등" (미발견 시 0)
    match = re.search(r'순위: (\d+)등', output)
    if match:
        result['rank'] = int(match.group(1))
    else:
        result['rank'] = 0

    # 쿠키 ID 파싱: "쿠키 ID: 3381" 또는 "✅ 쿠키:3381"
    match = re.search(r'쿠키[^:]*:\s*(\d+)', output)
    if match:
        result['cookie_id'] = int(match.group(1))

    # IP 파싱: "IP: 175.223.38.238"
    match = re.search(r'IP: ([\d.]+)', output)
    if match:
        result['proxy_ip'] = match.group(1)

    # 상품 발견 여부
    result['found'] = '✅ 상품 발견' in output

    # 차단 여부
    result['blocked'] = '차단됨' in output or 'BLOCKED' in output or 'CHALLENGE' in output

    return result


def run_single_search(task_id):
    """단일 검색 실행"""
    global cancelled
    if cancelled:
        return {
            'task_id': task_id,
            'stdout': '',
            'stderr': 'CANCELLED',
            'returncode': -2
        }

    try:
        result = subprocess.run(
            ['python3', 'coupang.py', 'search', '--random'],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(Path(__file__).parent.parent)
        )
        return {
            'task_id': task_id,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'returncode': result.returncode
        }
    except subprocess.TimeoutExpired:
        return {
            'task_id': task_id,
            'stdout': '',
            'stderr': 'TIMEOUT',
            'returncode': -1
        }
    except Exception as e:
        return {
            'task_id': task_id,
            'stdout': '',
            'stderr': str(e),
            'returncode': -1
        }


def save_to_db(parsed):
    """결과 DB 저장"""
    try:
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
        return True
    except Exception as e:
        print(f"DB 저장 실패: {e}")
        return False


def print_summary(stats, start_time, subnet_stats, interrupted=False):
    """결과 요약 출력"""
    end_time = datetime.now()
    elapsed = (end_time - start_time).total_seconds()

    print("\n" + "=" * 70)
    if interrupted:
        print("결과 요약 (중단됨)")
    else:
        print("결과 요약")
    print("=" * 70)
    print(f"총 실행: {stats['total']}회 | 소요: {elapsed:.1f}초")
    if stats['total'] > 0:
        print(f"✅ 발견: {stats['found']}회 ({stats['found']*100//stats['total']}%)")
        print(f"❌ 미발견: {stats['not_found']}회")
        print(f"🚫 차단: {stats['blocked']}회")
        print(f"⚠️ 에러: {stats['error']}회")
        if stats.get('cancelled', 0) > 0:
            print(f"🛑 취소: {stats['cancelled']}회")
    print(f"💾 DB 저장: {stats['saved']}건")

    # 서브넷별 통계 (사용량 많은 순)
    if subnet_stats:
        print(f"\n--- 서브넷별 통계 ---")
        sorted_subnets = sorted(subnet_stats.items(), key=lambda x: x[1]['total'], reverse=True)
        for subnet, s in sorted_subnets[:10]:  # 상위 10개만
            block_rate = s['blocked'] * 100 // s['total'] if s['total'] > 0 else 0
            print(f"  {subnet}.* : {s['total']:2d}회 (차단:{s['blocked']} 발견:{s['found']}) {block_rate}%차단")

    print(f"\n완료: {end_time.strftime('%H:%M:%S')}")


def main():
    global cancelled

    parser = argparse.ArgumentParser(description='Rank 테스트 - 병렬 실행')
    parser.add_argument('-n', '--count', type=int, default=10, help='총 실행 횟수 (기본: 10)')
    parser.add_argument('-w', '--workers', type=int, default=10, help='동시 실행 수 (기본: 10)')
    parser.add_argument('--no-save', action='store_true', help='DB 저장 안함')
    parser.add_argument('-v', '--verbose', action='store_true', help='상세 출력')
    args = parser.parse_args()

    start_time = datetime.now()
    print("=" * 70)
    print(f"Rank 테스트 - 병렬 실행")
    print("=" * 70)
    print(f"시작: {start_time.strftime('%H:%M:%S')}")
    print(f"총 실행: {args.count}회 | 동시 실행: {args.workers}개")
    print(f"💡 Ctrl+C로 중단 가능 (현재까지 결과 출력)")
    print("=" * 70)

    # 통계
    stats = {
        'total': 0,
        'found': 0,
        'not_found': 0,
        'blocked': 0,
        'error': 0,
        'saved': 0,
        'cancelled': 0
    }
    # 서브넷별 통계: {subnet: {'total': 0, 'blocked': 0}}
    subnet_stats = {}

    # Ctrl+C 핸들러
    def signal_handler(sig, frame):
        global cancelled
        if not cancelled:
            cancelled = True
            print("\n\n🛑 중단 요청... 실행 중인 작업 완료 대기...")

    signal.signal(signal.SIGINT, signal_handler)

    try:
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            # 모든 작업 제출
            futures = {executor.submit(run_single_search, i): i for i in range(1, args.count + 1)}

            for future in as_completed(futures):
                task_id = futures[future]
                result = future.result()

                # 취소된 작업은 스킵
                if result['stderr'] == 'CANCELLED':
                    stats['cancelled'] += 1
                    continue

                stats['total'] += 1

                if result['returncode'] != 0 or result['stderr'] == 'TIMEOUT':
                    stats['error'] += 1
                    print(f"[{task_id:3d}] ❌ 에러")
                    continue

                parsed = parse_result(result['stdout'])

                # 상태 판단
                if parsed['blocked']:
                    stats['blocked'] += 1
                    status = "🚫 차단  "
                    rank_str = "    "
                elif parsed['found']:
                    stats['found'] += 1
                    rank = parsed.get('rank', 0)
                    status = "✅ 발견  "
                    rank_str = f"#{rank:<3d}"
                else:
                    stats['not_found'] += 1
                    status = "❌ 미발견"
                    rank_str = "    "

                # 키워드 자르기 (표시폭 12 기준)
                keyword = parsed.get('keyword', '?')
                if get_display_width(keyword) > 12:
                    # 12폭에 맞게 자르기
                    cut_keyword = ''
                    for char in keyword:
                        if get_display_width(cut_keyword + char) > 12:
                            break
                        cut_keyword += char
                    keyword = cut_keyword

                # IP 서브넷 추출 (마지막 옥텟 제외)
                proxy_ip = parsed.get('proxy_ip', '')
                subnet = '.'.join(proxy_ip.split('.')[:3]) if proxy_ip else '?'

                # 서브넷별 통계 수집
                if subnet != '?':
                    if subnet not in subnet_stats:
                        subnet_stats[subnet] = {'total': 0, 'blocked': 0, 'found': 0}
                    subnet_stats[subnet]['total'] += 1
                    if parsed['blocked']:
                        subnet_stats[subnet]['blocked'] += 1
                    elif parsed['found']:
                        subnet_stats[subnet]['found'] += 1

                # 요약 출력 (고정폭 정렬)
                keyword_padded = pad_to_width(keyword, 12)
                cookie_id = parsed.get('cookie_id', '?')
                print(f"[{task_id:3d}] {status} {rank_str} | {keyword_padded} | {cookie_id} | {subnet}")

                # 상세 출력
                if args.verbose:
                    print(result['stdout'])
                    print("-" * 70)

                # DB 저장 (차단 아닌 경우만)
                if not args.no_save and not parsed['blocked'] and parsed.get('keyword'):
                    if save_to_db(parsed):
                        stats['saved'] += 1

    except KeyboardInterrupt:
        # 이미 signal_handler에서 처리됨
        pass

    # 결과 요약
    print_summary(stats, start_time, subnet_stats, interrupted=cancelled)


if __name__ == '__main__':
    main()
