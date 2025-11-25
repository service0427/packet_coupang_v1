"""
상품 검색 명령어 (리팩토링 버전)

핵심 알고리즘:
  랜덤 IP (바인딩) + 랜덤 쿠키 (/24 매칭) + 랜덤 TLS = 성공
"""

import json
import random
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from common.db import execute_query
from common.proxy import get_bound_cookie, get_cookie_by_id, parse_cookie_data, get_subnet, update_cookie_stats, update_cookie_data
from common.fingerprint import get_fingerprint_by_version, get_random_fingerprint, VERIFIED_VERSIONS
from cffi.search import search_product
from cffi.click import click_product, extract_ids_from_url
from cffi.request import timestamp
from screenshot import save_html_with_urls, take_screenshot_from_saved

# 프로젝트 루트 (lib/cffi/ → 상위 2단계)
PROJECT_ROOT = Path(__file__).parent.parent.parent  # /home/tech/packet_coupang_v1

# 기본 테스트 상품
DEFAULT_PRODUCT = {
    'product_id': '9024146312',
    'query': '호박 달빛식혜'
}


def get_random_product(product_list_id=None):
    """DB에서 상품 조회"""
    if product_list_id:
        result = execute_query("""
            SELECT id, keyword, product_id, item_id, vendor_item_id
            FROM product_list WHERE id = %s
        """, (product_list_id,))
    else:
        result = execute_query("""
            SELECT id, keyword, product_id, item_id, vendor_item_id
            FROM product_list ORDER BY RAND() LIMIT 1
        """)
    return result[0] if result else None


def direct_access_product(product_id, item_id, vendor_item_id, cookies, fingerprint, proxy):
    """상품 URL 직접 접속으로 정보 추출

    Args:
        product_id: 상품 ID
        item_id: 아이템 ID (없으면 None)
        vendor_item_id: 벤더 아이템 ID (없으면 None)
        cookies: 쿠키 딕셔너리
        fingerprint: 핑거프린트 레코드
        proxy: 프록시 URL

    Returns:
        dict: {success, productData, response_cookies_full}
    """
    from cffi.request import make_request, parse_response_cookies
    from extractor.detail_extractor import extract_product_detail

    # URL 구성
    if item_id and vendor_item_id:
        url = f'https://www.coupang.com/vp/products/{product_id}?itemId={item_id}&vendorItemId={vendor_item_id}'
    else:
        url = f'https://www.coupang.com/vp/products/{product_id}'

    print(f"\n[{timestamp()}] 직접 접속...")
    print(f"  URL: {url}")

    try:
        resp = make_request(url, cookies, fingerprint, proxy, referer='https://www.coupang.com/')
        size = len(resp.content)

        response_cookies, response_cookies_full = parse_response_cookies(resp)

        print(f"  Status: {resp.status_code} | Size: {size:,} bytes")

        if size > 100000:
            product_data = extract_product_detail(resp.text)

            if product_data:
                print(f"\n{'─' * 70}")
                print("📦 직접 접속 상품 정보")
                print(f"{'─' * 70}")
                for key, value in product_data.items():
                    print(f"   {key}: {value}")
                print(f"{'─' * 70}")

            return {
                'success': True,
                'productData': product_data,
                'response_cookies_full': response_cookies_full,
                'size': size
            }
        else:
            print(f"  ❌ 응답 크기 부족 ({size:,} bytes)")
            return {
                'success': False,
                'error': f'INVALID_RESPONSE_{size}B',
                'response_cookies_full': response_cookies_full,
                'size': size
            }

    except Exception as e:
        print(f"  ❌ 에러: {str(e)[:50]}")
        return {
            'success': False,
            'error': str(e)[:100],
            'response_cookies_full': [],
            'size': 0
        }


def run_search(args):
    """상품 검색 실행"""
    print("=" * 70)
    print("상품 검색")
    print("=" * 70)

    # 상품 정보 (직접 접속용)
    product_info = None

    # --random: DB에서 키워드 선택
    if args.random:
        pl_id = args.pl_id
        product_info = get_random_product(pl_id)
        if not product_info:
            print("❌ product_list 데이터 없음")
            return None
        args.query = product_info['keyword']
        args.product_id = product_info['product_id']
        print(f"🎲 랜덤 선택 [PL#{product_info['id']}]: {args.query}")

    # IP 바인딩 + 쿠키 선택
    if args.cookie_id:
        # 특정 쿠키 ID 지정
        cookie_record = get_cookie_by_id(args.cookie_id)
        if not cookie_record:
            print(f"❌ 쿠키 ID {args.cookie_id} 없음")
            return None
        cookies = parse_cookie_data(cookie_record)
        proxy = args.proxy or (f"socks5://{cookie_record['proxy_url']}" if cookie_record['proxy_url'] else None)
        print(f"📍 쿠키 ID: {cookie_record['id']} (지정)")
    else:
        # IP 바인딩 자동 선택
        print("🔍 IP 바인딩 쿠키 탐색...")
        bound = get_bound_cookie(min_remain=30, max_age_minutes=60)
        if not bound:
            print("❌ IP 바인딩 매칭 실패")
            return None

        cookie_record = bound['cookie_record']
        cookies = bound['cookies']
        proxy = args.proxy or bound['proxy']

        match_icon = "✅" if bound['match_type'] == 'exact' else "🔗"
        print(f"  {match_icon} 쿠키 ID: {cookie_record['id']} ({bound['match_type']})")
        print(f"     IP: {bound['external_ip']} (서브넷: {get_subnet(bound['external_ip'])}.*)")
        print(f"     나이: {cookie_record['age_minutes']:.0f}분")

    # TLS 핑거프린트 선택 (검증된 버전 중 랜덤)
    fingerprint = get_random_fingerprint(verified_only=True)
    if not fingerprint:
        print("❌ 핑거프린트 없음")
        return None

    print(f"\n타겟: {args.product_id}")
    print(f"검색어: {args.query}")
    print(f"TLS: Chrome {fingerprint['chrome_major']} (custom)")
    print(f"프록시: {proxy}")
    print("=" * 70)

    # 검색 실행
    save_html = args.screenshot
    start_time = datetime.now()
    result = search_product(
        args.query,
        args.product_id,
        cookies,
        fingerprint,
        proxy,
        max_page=args.max_page,
        verbose=True,
        save_html=save_html
    )

    search_time = (datetime.now() - start_time).total_seconds()

    # 결과 출력
    print("\n" + "=" * 70)
    print("결과")
    print("=" * 70)

    found = result['found']
    blocked = result['blocked']

    if found:
        print(f"\n✅ 상품 발견")
        print(f"   페이지: {found['page']}")
        print(f"   순위: {result['actual_rank']}등 / {len(result['all_products'])}개")

        # 검색 결과에서 추출된 상품 정보 (전체 표시)
        print(f"\n{'─' * 70}")
        print("📋 검색 결과 상품 정보")
        print(f"{'─' * 70}")
        for key, value in found.items():
            if key not in ['_page']:  # 내부 키 제외
                print(f"   {key}: {value}")
        print(f"{'─' * 70}")

        # 스크린샷 처리
        screenshot_path = None
        if save_html and result.get('found_html'):
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            screenshot_dir = PROJECT_ROOT / 'screenshot'
            screenshot_dir.mkdir(parents=True, exist_ok=True)  # 폴더 없으면 생성
            html_path = screenshot_dir / f'search_{args.product_id}_{ts}.html'

            # 1단계: HTML + URL JSON 저장
            save_result = save_html_with_urls(
                result['found_html'],
                html_path,
                metadata={
                    'query': args.query,
                    'product_id': args.product_id,
                    'rank': result['actual_rank'],
                    'page': found['page'],
                    'timestamp': ts
                }
            )
            print(f"\n📄 HTML 저장: {save_result['html_path']}")

            # 2단계: 스크린샷 생성
            print(f"📸 스크린샷 생성 중...")
            ss_result = take_screenshot_from_saved(html_path)
            if ss_result['success']:
                screenshot_path = ss_result['path']
                print(f"   ✅ {screenshot_path}")
                print(f"   크기: {ss_result['size']:,} bytes")
                print(f"   이미지: {ss_result['images_loaded']}/{ss_result['images_total']} 로드")
            else:
                print(f"   ❌ 스크린샷 실패: {ss_result.get('error')}")

        # 클릭
        if not args.no_click:
            print(f"\n[{timestamp()}] 상품 클릭...")

            ids = extract_ids_from_url(found['url'])
            product_info = {
                'productId': found['productId'],
                'url': found['url'],
                'rank': found['rank'],
                'itemId': ids['itemId'],
                'vendorItemId': ids['vendorItemId']
            }

            search_url = f'https://www.coupang.com/np/search?q={quote(args.query)}'
            click_result = click_product(
                product_info, search_url, cookies, fingerprint, proxy
            )

            if not click_result['success']:
                print(f"  ❌ 클릭 실패: {click_result.get('error')}")

    elif blocked:
        print(f"\n🚫 차단됨: {result['block_error']}")
    else:
        print(f"\n❌ 상품 미발견 ({len(result['all_products'])}개 검색)")

        # 직접 접속으로 상품 정보 추출 (--no-click이 아니면 실행)
        if not args.no_click:
            item_id = product_info.get('item_id') if product_info else None
            vendor_item_id = product_info.get('vendor_item_id') if product_info else None

            direct_result = direct_access_product(
                args.product_id, item_id, vendor_item_id,
                cookies, fingerprint, proxy
            )

            # 직접 접속 응답 쿠키도 업데이트에 포함
            if direct_result.get('response_cookies_full'):
                result['response_cookies_full'].extend(direct_result['response_cookies_full'])

    # 통계 업데이트
    is_success = not blocked
    update_cookie_stats(cookie_record['id'], is_success)

    # 쿠키 데이터 업데이트 (필수)
    updated = update_cookie_data(cookie_record['id'], result.get('response_cookies_full', []))
    if updated > 0:
        print(f"\n💾 쿠키 업데이트: {updated}개")

    # 트래픽 출력
    total_bytes = result.get('total_bytes', 0)
    if total_bytes > 0:
        if total_bytes >= 1024 * 1024:
            traffic_str = f"{total_bytes / (1024 * 1024):.2f} MB"
        else:
            traffic_str = f"{total_bytes / 1024:.2f} KB"
        print(f"📊 트래픽: {traffic_str} | 시간: {search_time:.1f}초")

    print(f"\n✅ 쿠키:{cookie_record['id']} | TLS:{fingerprint['chrome_major']}")

    return {
        'found': bool(found),
        'blocked': blocked,
        'cookie_id': cookie_record['id'],
        'fingerprint': fingerprint['chrome_major'],
        'search_time': search_time
    }


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--product-id', default='9024146312')
    parser.add_argument('--query', default='호박 달빛식혜')
    parser.add_argument('--max-page', type=int, default=13)
    parser.add_argument('--no-click', action='store_true', help='클릭/직접접속 건너뛰기')
    parser.add_argument('--random', action='store_true')
    parser.add_argument('--cookie-id', type=int)
    parser.add_argument('--proxy')
    parser.add_argument('--screenshot', action='store_true', help='상품 발견 시 스크린샷 저장')

    args = parser.parse_args()
    run_search(args)
