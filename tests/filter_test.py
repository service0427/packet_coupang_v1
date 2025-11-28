#!/usr/bin/env python3
"""
필터 조건 탐색 테스트

상품 가격 기반 minPrice/maxPrice 필터를 적용하여
상품이 1~3페이지 내에 나타나는 URL을 찾는다.
"""

import sys
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).parent.parent / 'lib'))

from common.proxy import get_bound_cookie
from common.fingerprint import get_random_fingerprint
from cffi.request import make_request, timestamp
from cffi.work_cmd import direct_access_product
from extractor.search_extractor import ProductExtractor
from extractor.detail_extractor import to_api_response


def get_product_info(product_id, item_id, vendor_item_id, max_retries=3):
    """상품 정보 조회 (가격 포함)"""
    print(f"\n[{timestamp()}] 상품 정보 조회: {product_id}")

    fingerprint = get_random_fingerprint(verified_only=True)
    if not fingerprint:
        print("❌ 핑거프린트 없음")
        return None

    for retry in range(max_retries):
        # 쿠키/핑거프린트 준비
        bound = get_bound_cookie(min_remain=30, max_age_minutes=60)
        if not bound:
            print("❌ 쿠키 없음")
            return None

        cookies = bound['cookies']
        proxy = bound['proxy']
        cookie_id = bound['cookie_record']['id']

        if retry > 0:
            print(f"  [재시도 {retry + 1}/{max_retries}] 쿠키 ID: {cookie_id}")

        # 상품 정보 조회
        result = direct_access_product(
            product_id, item_id, vendor_item_id,
            cookies, fingerprint, proxy,
            save_html=False, verbose=False
        )

        if result['success']:
            product_data = result.get('productData', {})
            if product_data:
                api_data = to_api_response(product_data)
                print(f"  상품명: {api_data.get('title', '?')[:40]}...")
                print(f"  가격: {api_data.get('price', 0):,}원")
                print(f"  원가: {api_data.get('originalPrice', 0):,}원")
                return api_data

        error = result.get('error', '')
        if 'timed out' in error.lower() or 'curl: (28)' in error or 'curl: (7)' in error:
            print(f"  ⚠️ 타임아웃, 다른 쿠키 시도...")
            continue
        else:
            print(f"❌ 상품 조회 실패: {error}")
            return None

    print(f"❌ {max_retries}번 재시도 후 실패")
    return None


def search_with_filter(keyword, target_product_id, min_price, max_price, cookies, fingerprint, proxy, page=1):
    """필터 적용 검색"""
    url = (
        f"https://www.coupang.com/np/search?"
        f"listSize=36&filterType=&rating=0&isPriceRange=false"
        f"&minPrice={min_price}&maxPrice={max_price}"
        f"&component=&sorter=scoreDesc&brand=&offerCondition="
        f"&filter=&fromComponent=N&channel=user"
        f"&selectedPlpKeepFilter=&page={page}"
        f"&q={quote(keyword)}"
    )

    try:
        resp = make_request(url, cookies, fingerprint, proxy)
        size = len(resp.content)

        if resp.status_code == 200 and size > 5000:
            html_text = resp.text
            result = ProductExtractor.extract_products_from_html(html_text)
            products = result['ranking']

            # 타겟 상품 찾기
            for product in products:
                if product['productId'] == target_product_id:
                    return {
                        'found': True,
                        'rank': product.get('rank'),
                        'page': page,
                        'total_products': len(products),
                        'url': url
                    }

            return {
                'found': False,
                'page': page,
                'total_products': len(products),
                'url': url
            }
        else:
            return {'found': False, 'error': f'STATUS_{resp.status_code}_{size}B'}

    except Exception as e:
        return {'found': False, 'error': str(e)[:100]}


def get_new_cookie_and_proxy():
    """새 쿠키/프록시 가져오기"""
    bound = get_bound_cookie(min_remain=30, max_age_minutes=60)
    if not bound:
        return None, None, None
    return bound['cookies'], bound['proxy'], bound['cookie_record']['id']


def find_filter_url(keyword, product_id, item_id, vendor_item_id, price):
    """필터 URL 탐색"""
    print(f"\n{'=' * 70}")
    print(f"필터 URL 탐색")
    print(f"{'=' * 70}")
    print(f"검색어: {keyword}")
    print(f"상품ID: {product_id}")
    print(f"기준가격: {price:,}원")

    fingerprint = get_random_fingerprint(verified_only=True)
    if not fingerprint:
        print("❌ 핑거프린트 없음")
        return None

    # 초기 쿠키/프록시
    cookies, proxy, cookie_id = get_new_cookie_and_proxy()
    if not cookies:
        print("❌ 쿠키 없음")
        return None

    print(f"프록시: {proxy} (쿠키 #{cookie_id})")
    print(f"{'=' * 70}")

    # 가격 범위 전략들 (좁은 범위부터 넓은 범위로)
    price_strategies = [
        # 1. 정확한 가격
        (price, price),
        # 2. ±5% 범위
        (int(price * 0.95), int(price * 1.05)),
        # 3. ±10% 범위
        (int(price * 0.90), int(price * 1.10)),
        # 4. ±20% 범위
        (int(price * 0.80), int(price * 1.20)),
        # 5. ±30% 범위
        (int(price * 0.70), int(price * 1.30)),
        # 6. ±50% 범위
        (int(price * 0.50), int(price * 1.50)),
        # 7. 하한만 (price 이상)
        (price, 0),
        # 8. 상한만 (price 이하)
        (0, price),
        # 9. 절반~2배
        (int(price * 0.5), int(price * 2.0)),
    ]

    timeout_count = 0  # 타임아웃 연속 카운터

    for strategy_idx, (min_p, max_p) in enumerate(price_strategies):
        # max_price가 0이면 상한 없음
        if max_p == 0:
            max_p = 99999999
        if min_p == 0:
            min_p = 0

        print(f"\n[전략 {strategy_idx + 1}] {min_p:,}원 ~ {max_p:,}원")

        # 1~3페이지 검색
        for page in range(1, 4):
            result = search_with_filter(
                keyword, product_id, min_p, max_p,
                cookies, fingerprint, proxy, page
            )

            if result.get('error'):
                error = result['error']
                print(f"  Page {page}: ❌ {error[:60]}")

                # 타임아웃/연결오류 시 쿠키 교체
                if 'timed out' in error.lower() or 'curl: (28)' in error or 'curl: (7)' in error:
                    timeout_count += 1
                    if timeout_count >= 3:
                        print(f"  ⚠️ 타임아웃 {timeout_count}회, 쿠키 교체...")
                        new_cookies, new_proxy, new_cookie_id = get_new_cookie_and_proxy()
                        if new_cookies:
                            cookies, proxy = new_cookies, new_proxy
                            print(f"  → 새 프록시: {proxy} (쿠키 #{new_cookie_id})")
                            timeout_count = 0
                        else:
                            print("  ❌ 사용 가능한 쿠키 없음")
                            return None
                break
            elif result['found']:
                print(f"  Page {page}: ✅ 발견! Rank #{result['rank']}")
                print(f"\n{'─' * 70}")
                print(f"✅ 성공! 최종 URL:")
                print(f"{'─' * 70}")
                print(result['url'])
                print(f"{'─' * 70}")
                return result['url']
            else:
                timeout_count = 0  # 성공 시 리셋
                print(f"  Page {page}: {result['total_products']}개 상품 (미발견)")

                # 상품이 0개면 다음 전략으로
                if result['total_products'] == 0:
                    print(f"  → 상품 없음, 다음 전략으로")
                    break

    print(f"\n❌ 모든 전략 실패")
    return None


def main():
    """메인"""
    import argparse

    parser = argparse.ArgumentParser(description='필터 URL 탐색')
    parser.add_argument('--keyword', '-k', required=True, help='검색어')
    parser.add_argument('--product-id', '-p', required=True, help='상품 ID')
    parser.add_argument('--item-id', '-i', help='아이템 ID')
    parser.add_argument('--vendor-item-id', '-v', help='벤더 아이템 ID')
    parser.add_argument('--price', type=int, help='가격 (없으면 자동 조회)')

    args = parser.parse_args()

    # 가격이 없으면 상품 정보에서 조회
    price = args.price
    if not price:
        product_info = get_product_info(
            args.product_id,
            args.item_id,
            args.vendor_item_id
        )
        if product_info:
            price = product_info.get('price') or product_info.get('originalPrice')

    if not price:
        print("❌ 가격 정보를 가져올 수 없습니다")
        return

    # 필터 URL 탐색
    result_url = find_filter_url(
        args.keyword,
        args.product_id,
        args.item_id,
        args.vendor_item_id,
        price
    )

    if result_url:
        print(f"\n✅ 완료")
    else:
        print(f"\n❌ 필터 URL을 찾지 못했습니다")


if __name__ == '__main__':
    main()
