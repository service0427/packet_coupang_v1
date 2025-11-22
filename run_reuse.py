#!/usr/bin/env python3
"""
쿠키 재사용 테스트
- 현재 프록시 IP로 이전에 생성된 쿠키 찾기
- 동일 IP 쿠키가 있으면 재사용 테스트

Usage: python3 run_reuse.py
       python3 run_reuse.py --remain 60
"""

import sys
import argparse
import requests
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent / 'lib'))

from rank_cmd import run_rank
from db import execute_query, get_cursor

PROXY_API_URL = 'http://mkt.techb.kr:3001/api/proxy/status'

def get_proxies_from_api(remain=60):
    """API에서 프록시 목록 조회 (external_ip 포함)"""
    try:
        resp = requests.get(f'{PROXY_API_URL}?remain={remain}', timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('success') and data.get('proxies'):
                proxies = []
                for p in data['proxies']:
                    proxy_addr = p.get('proxy')
                    external_ip = p.get('external_ip')
                    if proxy_addr and external_ip:
                        proxies.append({
                            'url': f'socks5://{proxy_addr}',
                            'ip': external_ip
                        })
                return proxies
    except Exception as e:
        print(f"⚠️  프록시 API 오류: {e}")
    return []

def find_cookie_by_ip(ip):
    """해당 IP로 생성된 쿠키 찾기 (10분 이상 지난 것 중 가장 최근)"""
    rows = execute_query("""
        SELECT id, chrome_version, created_at, use_count, success_count, fail_count
        FROM cookies
        WHERE proxy_ip = %s
        AND created_at <= NOW() - INTERVAL 10 MINUTE
        ORDER BY id DESC
        LIMIT 1
    """, (ip,))
    return rows[0] if rows else None

def update_cookie_stats(cookie_id, success, click_success=False):
    """쿠키 통계 업데이트"""
    with get_cursor() as cursor:
        if success and click_success:
            cursor.execute("""
                UPDATE cookies SET
                    last_used_at = NOW(),
                    use_count = use_count + 1,
                    success_count = success_count + 1
                WHERE id = %s
            """, (cookie_id,))
        else:
            cursor.execute("""
                UPDATE cookies SET
                    last_used_at = NOW(),
                    use_count = use_count + 1,
                    fail_count = fail_count + 1
                WHERE id = %s
            """, (cookie_id,))

def run_rank_task(cookie_id, product_id, query, max_page, platform):
    """rank 실행 및 통계 업데이트"""
    args = SimpleNamespace(
        cookie_id=cookie_id,
        product_id=product_id,
        query=query,
        max_page=max_page,
        no_click=False,
        proxy=None,
        platform=platform
    )
    try:
        report = run_rank(args)

        if report and report.get('found'):
            click_result = report.get('click', {})
            click_success = click_result.get('success', False)
            update_cookie_stats(cookie_id, success=True, click_success=click_success)

            return {
                'cookie_id': cookie_id,
                'success': True,
                'found': True,
                'rank': report.get('actual_rank'),
                'click_success': click_success
            }
        elif report and not report.get('found'):
            update_cookie_stats(cookie_id, success=False)
            return {
                'cookie_id': cookie_id,
                'success': True,
                'found': False,
                'rank': None
            }
        else:
            update_cookie_stats(cookie_id, success=False)
            return {'cookie_id': cookie_id, 'success': False, 'error': 'No report'}
    except Exception as e:
        try:
            update_cookie_stats(cookie_id, success=False)
        except:
            pass
        return {'cookie_id': cookie_id, 'success': False, 'error': str(e)[:100]}

def main():
    parser = argparse.ArgumentParser(description='쿠키 재사용 테스트')
    parser.add_argument('--remain', type=int, default=60, help='프록시 최소 트래픽')
    parser.add_argument('--product-id', default='9024146312', help='상품 ID')
    parser.add_argument('--query', default='호박 달빛식혜', help='검색어')
    parser.add_argument('--max-page', type=int, default=13, help='최대 페이지')
    parser.add_argument('--platform', default='u22', help='TLS 플랫폼')
    args = parser.parse_args()

    print("=" * 70)
    print("쿠키 재사용 테스트")
    print("=" * 70)
    print(f"시작: {datetime.now().strftime('%H:%M:%S')}")

    # 프록시 목록 가져오기
    print("\n프록시 조회 중...")
    proxies = get_proxies_from_api(args.remain)
    if not proxies:
        print("❌ 사용 가능한 프록시 없음")
        return

    print(f"프록시: {len(proxies)}개 조회됨 (external_ip 포함)")

    # 쿠키 매칭 (API에서 external_ip 사용)
    print("\n쿠키 매칭 중...")
    matched = []

    for p in proxies:
        current_ip = p['ip']
        proxy_url = p['url']

        cookie = find_cookie_by_ip(current_ip)
        if cookie:
            age_seconds = (datetime.now() - cookie['created_at']).total_seconds()
            matched.append({
                'cookie_id': cookie['id'],
                'proxy': proxy_url,
                'ip': current_ip,
                'chrome_version': cookie['chrome_version'],
                'age_seconds': int(age_seconds),
                'use_count': cookie['use_count'],
                'success_count': cookie['success_count'],
                'fail_count': cookie['fail_count']
            })
            print(f"  ✅ {current_ip} -> Cookie {cookie['id']} ({int(age_seconds)}초 전, 사용: {cookie['use_count']}회)")
        else:
            print(f"  ❌ {current_ip} -> 매칭 쿠키 없음")

    if not matched:
        print("\n재사용 가능한 쿠키 없음")
        print("=" * 70)
        return

    print(f"\n매칭: {len(matched)}개")
    print("=" * 70)

    # 상세 정보
    print("\n재사용 테스트 대상:")
    for m in matched:
        age_min = m['age_seconds'] // 60
        print(f"  Cookie {m['cookie_id']}: {m['ip']} | {age_min}분 전 | Chrome {m['chrome_version']} | 사용 {m['use_count']}회")

    print("\n" + "=" * 70)
    print("Rank 실행")
    print("=" * 70)

    # 병렬 실행
    cookie_ids = [m['cookie_id'] for m in matched]
    results = []

    with ProcessPoolExecutor(max_workers=len(matched)) as executor:
        futures = {
            executor.submit(
                run_rank_task,
                m['cookie_id'],
                args.product_id,
                args.query,
                args.max_page,
                args.platform
            ): m
            for m in matched
        }

        for future in as_completed(futures):
            m = futures[future]
            try:
                result = future.result(timeout=120)
                result['age_seconds'] = m['age_seconds']
                result['use_count_before'] = m['use_count']
                results.append(result)
            except Exception as e:
                results.append({
                    'cookie_id': m['cookie_id'],
                    'success': False,
                    'error': str(e)[:100],
                    'age_seconds': m['age_seconds'],
                    'use_count_before': m['use_count']
                })

    # 결과 집계
    success_count = sum(1 for r in results if r.get('success'))
    fail_count = sum(1 for r in results if not r.get('success'))
    found_count = sum(1 for r in results if r.get('found'))
    click_success_count = sum(1 for r in results if r.get('click_success'))

    print("\n" + "=" * 70)
    print("결과")
    print("=" * 70)
    print(f"총: {len(matched)}개")
    print(f"실행 성공: {success_count}, 실패: {fail_count}")
    print(f"상품 발견: {found_count}, 클릭 성공: {click_success_count}")

    # 상세 결과 (나이별 분석)
    print("\n상세 결과 (쿠키 나이별):")
    for r in sorted(results, key=lambda x: x.get('age_seconds', 0)):
        cookie_id = r['cookie_id']
        age_min = r.get('age_seconds', 0) // 60
        use_before = r.get('use_count_before', 0)

        if r.get('success'):
            if r.get('found'):
                rank = r.get('rank', '?')
                click = "✅" if r.get('click_success') else "❌"
                print(f"  Cookie {cookie_id}: {rank}등, 클릭 {click} | {age_min}분 전 | 이전 사용 {use_before}회")
            else:
                print(f"  Cookie {cookie_id}: 미발견 | {age_min}분 전 | 이전 사용 {use_before}회")
        else:
            print(f"  Cookie {cookie_id}: ❌ {r.get('error', 'Unknown')} | {age_min}분 전")

    # 재사용 성공률 계산
    if results:
        reuse_success_rate = (found_count / len(results)) * 100
        click_success_rate = (click_success_count / len(results)) * 100 if found_count > 0 else 0

        print("\n" + "=" * 70)
        print("재사용 분석")
        print("=" * 70)
        print(f"발견 성공률: {reuse_success_rate:.1f}%")
        print(f"클릭 성공률: {click_success_rate:.1f}%")

        # 나이별 성공률
        age_groups = {
            '1분 이내': [r for r in results if r.get('age_seconds', 0) < 60],
            '1-5분': [r for r in results if 60 <= r.get('age_seconds', 0) < 300],
            '5-10분': [r for r in results if 300 <= r.get('age_seconds', 0) < 600],
            '10분+': [r for r in results if r.get('age_seconds', 0) >= 600]
        }

        print("\n나이별 성공률:")
        for name, group in age_groups.items():
            if group:
                found = sum(1 for r in group if r.get('found'))
                rate = (found / len(group)) * 100
                print(f"  {name}: {found}/{len(group)} ({rate:.0f}%)")

    print(f"\n종료: {datetime.now().strftime('%H:%M:%S')}")

if __name__ == '__main__':
    main()
