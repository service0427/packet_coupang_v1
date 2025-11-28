"""
상품 클릭 모듈 - curl-cffi

상품 상세 페이지 요청 및 정보 추출
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from cffi.request import make_request, parse_response_cookies, timestamp
from extractor.detail_extractor import extract_product_detail


def click_product(product_info, search_url, cookies, fingerprint, proxy, verbose=True, save_html=False):
    """상품 클릭 (상세 페이지 요청)

    Args:
        product_info: {productId, url, rank, itemId, vendorItemId}
        search_url: Referer로 사용할 검색 URL
        cookies: 쿠키 딕셔너리
        fingerprint: 핑거프린트 레코드
        proxy: 프록시 URL
        verbose: 상세 출력
        save_html: HTML 저장 여부

    Returns:
        dict: {
            success: bool,
            status: HTTP 상태 코드,
            size: 응답 크기,
            productData: 추출된 상품 정보,
            response_cookies: 응답 쿠키,
            error: 에러 메시지
        }
    """
    full_url = f'https://www.coupang.com{product_info["url"]}'
    product_id = product_info.get('productId')

    try:
        resp = make_request(
            full_url, cookies, fingerprint, proxy,
            referer=search_url
        )
        size = len(resp.content)
        html_content = resp.text

        response_cookies, response_cookies_full = parse_response_cookies(resp)

        # HTML 저장 (사이즈와 관계없이 항상 저장)
        if save_html and product_id:
            html_dir = Path(__file__).parent.parent.parent / 'html'
            html_dir.mkdir(parents=True, exist_ok=True)
            html_path = html_dir / f'{product_id}.html'
            html_path.write_text(html_content, encoding='utf-8')
            if verbose:
                print(f"  📄 HTML 저장: {html_path}")

        # 상세 정보 출력
        if verbose:
            print(f"\n{'─' * 60}")
            print("📤 Request")
            print(f"{'─' * 60}")
            print(f"  URL: {full_url[:80]}...")
            print(f"  Referer: {search_url[:60]}..." if search_url else "  Referer: None")

            print(f"\n{'─' * 60}")
            print("📥 Response")
            print(f"{'─' * 60}")
            print(f"  Status: {resp.status_code}")
            print(f"  Size: {size:,} bytes")

            if response_cookies:
                print(f"  Set-Cookie: {len(response_cookies)}개")

            print(f"{'─' * 60}\n")

        # 결과 판정 (100KB 이상 = 성공)
        if size > 100000:
            # 상품 정보 추출
            product_data = extract_product_detail(html_content)

            if verbose:
                print(f"  ✅ 클릭 성공")

            return {
                'success': True,
                'status': resp.status_code,
                'size': size,
                'url': full_url,
                'productData': product_data,
                'response_cookies': response_cookies,
                'response_cookies_full': response_cookies_full
            }
        elif resp.status_code == 403:
            return {
                'success': False,
                'status': 403,
                'size': size,
                'error': 'BLOCKED_403',
                'response_cookies': response_cookies,
                'response_cookies_full': response_cookies_full
            }
        else:
            return {
                'success': False,
                'status': resp.status_code,
                'size': size,
                'error': f'INVALID_RESPONSE_{size}B',
                'response_cookies': response_cookies,
                'response_cookies_full': response_cookies_full
            }

    except Exception as e:
        return {
            'success': False,
            'status': None,
            'size': 0,
            'error': str(e)[:100],
            'response_cookies': {},
            'response_cookies_full': []
        }


def extract_ids_from_url(url):
    """URL에서 itemId, vendorItemId 추출

    Args:
        url: 상품 URL

    Returns:
        dict: {itemId, vendorItemId}
    """
    item_id_match = re.search(r'itemId=(\d+)', url)
    vendor_item_id_match = re.search(r'vendorItemId=(\d+)', url)

    return {
        'itemId': item_id_match.group(1) if item_id_match else None,
        'vendorItemId': vendor_item_id_match.group(1) if vendor_item_id_match else None
    }


if __name__ == '__main__':
    print("상품 클릭 모듈 테스트")
    print("=" * 60)
    print("사용법: click.py는 직접 실행하지 않고 모듈로 import하여 사용")
