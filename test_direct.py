#!/usr/bin/env python3
"""
직접 연결 테스트 - 상세 로그 저장
"""

import sys
import os
import json
import time
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib'))

from api.rank_checker_direct import check_rank, get_public_ip

# 로그 파일
LOG_FILE = f"logs/test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"


def test_search(keyword, product_id, item_id=None, vendor_item_id=None):
    """검색 테스트 및 상세 로그"""
    print(f"\n{'='*60}")
    print(f"키워드: {keyword}")
    print(f"상품ID: {product_id} / {item_id} / {vendor_item_id}")
    print('='*60)

    result = check_rank(keyword, product_id, item_id, vendor_item_id, max_page=13)

    # 핵심 정보 출력
    print(f"\n[결과]")
    print(f"  success: {result['success']}")
    print(f"  found: {result['found']}")
    print(f"  rank: {result.get('rank')}")
    print(f"  pages_searched: {result['pages_searched']}")
    print(f"  elapsed_ms: {result['elapsed_ms']}")

    if result.get('error_code'):
        print(f"\n[에러]")
        print(f"  code: {result['error_code']}")
        print(f"  message: {result['error_message']}")
        print(f"  detail: {result.get('error_detail')}")

    print(f"\n[페이지별 상품 수]")
    for page, count in sorted(result.get('page_counts', {}).items()):
        status = "✓" if count >= 20 else "⚠" if count > 0 else "✗"
        print(f"  P{page}: {count} {status}")

    # 로그 저장
    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'keyword': keyword,
        'product_id': product_id,
        'item_id': item_id,
        'vendor_item_id': vendor_item_id,
        **result
    }

    os.makedirs('logs', exist_ok=True)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')

    print(f"\n→ 로그 저장: {LOG_FILE}")
    return result


def test_from_api():
    """API에서 작업 받아서 테스트"""
    import requests

    print("\n작업 할당 요청...")
    try:
        resp = requests.get(
            'http://mkt.techb.kr:3302/api/work/allocate?work_type=rank&proxy=false&user_folder=test_d',
            timeout=15
        )
        data = resp.json()
    except Exception as e:
        print(f"할당 실패: {e}")
        return None

    if not data.get('success'):
        print(f"작업 없음: {data.get('reason', data.get('message', 'unknown'))}")
        return None

    print(f"할당됨: {data['keyword']} (P:{data['product_id']})")

    result = test_search(
        data['keyword'],
        data['product_id'],
        data.get('item_id'),
        data.get('vendor_item_id')
    )

    # 결과 보고
    if result:
        payload = {
            'allocation_key': data['allocation_key'],
            'success': result['success'],
            'actual_ip': get_public_ip(),
            'rank_data': {
                'rank': result.get('rank') or 0,
                'page': result.get('page') or result['pages_searched'],
                'listSize': 72
            },
            'chrome_version': '143.0.0.0'
        }
        if result.get('error_code'):
            payload['success'] = False
            payload['error_type'] = result['error_code']
            payload['error_message'] = result.get('error_message', '')

        try:
            resp = requests.post(
                'http://mkt.techb.kr:3302/api/work/result',
                json=payload,
                timeout=15
            )
            print(f"\n결과 보고: {resp.json()}")
        except Exception as e:
            print(f"\n결과 보고 실패: {e}")

    return result


def main():
    import argparse
    parser = argparse.ArgumentParser(description='직접 연결 테스트')
    parser.add_argument('--keyword', '-k', help='검색 키워드')
    parser.add_argument('--product-id', '-p', help='상품 ID')
    parser.add_argument('--count', '-n', type=int, default=1, help='API 테스트 횟수')
    parser.add_argument('--api', '-a', action='store_true', help='API에서 작업 받기')

    args = parser.parse_args()

    print(f"공인 IP: {get_public_ip()}")
    print(f"로그 파일: {LOG_FILE}")

    if args.api or (not args.keyword and not args.product_id):
        # API 테스트
        for i in range(args.count):
            if args.count > 1:
                print(f"\n[{i+1}/{args.count}]")
            test_from_api()
            if i < args.count - 1:
                time.sleep(1)
    else:
        # 수동 테스트
        if not args.keyword or not args.product_id:
            print("--keyword와 --product-id 필요")
            return
        test_search(args.keyword, args.product_id)


if __name__ == '__main__':
    main()
