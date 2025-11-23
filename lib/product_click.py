#!/usr/bin/env python3
"""
상품 클릭 모듈 - 상품 페이지 요청 및 정보 수집

용도: 상품 정보 수집, 페이지 접근 가능 여부 확인
"""

from pathlib import Path
from curl_cffi import requests
from common import build_extra_fp
from extractor.detail_extractor import extract_product_detail, convert_to_agent_format


def get_sec_ch_ua(chrome_major):
    """Chrome 버전별 sec-ch-ua 헤더 생성"""
    sec_ch_ua_map = {
        136: '"Not/A)Brand";v="8", "Chromium";v="136"',
        137: '"Not/A)Brand";v="8", "Chromium";v="137"',
        138: '"Not)A;Brand";v="8", "Chromium";v="138"',
        139: '"Not)A;Brand";v="8", "Chromium";v="139"',
        140: '"Not/A)Brand";v="8", "Chromium";v="140"',
        141: '"Not/A)Brand";v="8", "Chromium";v="141"',
        142: '"Not/A)Brand";v="8", "Chromium";v="142"',
    }
    return sec_ch_ua_map.get(chrome_major, f'"Not)A;Brand";v="8", "Chromium";v="{chrome_major}"')


def build_document_headers(fingerprint, referer=None):
    """Document 요청용 헤더 생성"""
    major_version = fingerprint['chrome_major']

    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'ko-KR,ko;q=0.9',
        'Cache-Control': 'max-age=0',
        'Connection': 'keep-alive',
        'Sec-Ch-Ua': get_sec_ch_ua(major_version),
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Linux"',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-User': '?1',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': fingerprint['user_agent'],
    }

    if referer:
        headers['Referer'] = referer

    return headers


def product_click(product_info, search_url, cookies, fingerprint, proxy=None, verbose=True):
    """상품 클릭 - 상품 페이지 요청 및 정보 수집

    Args:
        product_info: 상품 정보 (url 필수)
        search_url: 검색 결과 페이지 URL (Referer용)
        cookies: 쿠키 딕셔너리
        fingerprint: TLS 핑거프린트
        proxy: 프록시 URL
        verbose: 상세 출력

    Returns:
        dict: success, status, size, product_data (추출된 상품 정보)
    """
    product_url = f"https://www.coupang.com{product_info['url']}"

    if verbose:
        print(f"\n  🔗 상품 페이지 요청...")
        print(f"    URL: {product_url[:80]}...")

    headers = build_document_headers(fingerprint, search_url)

    ja3 = fingerprint['ja3_text']
    akamai = fingerprint['akamai_text']
    extra_fp = build_extra_fp(fingerprint)

    try:
        response = requests.get(
            product_url,
            headers=headers,
            cookies=cookies,
            ja3=ja3,
            akamai=akamai,
            extra_fp=extra_fp,
            proxy=proxy,
            timeout=30,
            allow_redirects=True,
            verify=False
        )

        size = len(response.content)

        # 응답 쿠키 수집 (cookie jar 방식)
        response_cookies = {}
        if response.cookies:
            for name, value in response.cookies.items():
                response_cookies[name] = value

        if size > 100000:
            # 성공 - 상품 정보 추출
            product_data = extract_product_detail(response.text)

            # coupang_agent_v2 호환 형식으로 변환
            agent_format_data = convert_to_agent_format(product_data, product_info)

            # 디버그: HTML 저장 (분석용)
            debug_path = Path(__file__).parent.parent / 'reports' / 'debug_product_page.html'
            with open(debug_path, 'w', encoding='utf-8') as f:
                f.write(response.text)

            result = {
                'success': True,
                'status': response.status_code,
                'size': size,
                'product_data': product_data,
                # coupang_agent_v2 호환 형식
                'productData': agent_format_data,
                # 응답 쿠키 (cookie jar 방식)
                'response_cookies': response_cookies
            }

            if verbose:
                print(f"  ✅ {response.status_code} - {size:,} bytes")
                print(f"\n  {'─' * 50}")
                print(f"  📦 상품 정보")
                print(f"  {'─' * 50}")

                if product_data.get('title'):
                    title = product_data['title']
                    if len(title) > 60:
                        title = title[:60] + '...'
                    print(f"    제목: {title}")

                # 가격 정보
                if product_data.get('price'):
                    price_str = f"{product_data['price']:,}원"
                    if product_data.get('original_price'):
                        orig_str = f"{product_data['original_price']:,}원"
                        discount = product_data.get('discount_rate', 0)
                        print(f"    가격: {price_str} (원가: {orig_str}, {discount}% 할인)")
                    else:
                        print(f"    가격: {price_str}")

                # 배송 타입
                if product_data.get('delivery_type'):
                    print(f"    배송: {product_data['delivery_type']}")

                # 평점/리뷰
                if product_data.get('rating'):
                    review_count = product_data.get('review_count', 0)
                    print(f"    평점: ⭐ {product_data['rating']} ({review_count:,}개 리뷰)")

                # 판매자
                if product_data.get('seller_name'):
                    print(f"    판매자: {product_data['seller_name']}")

                # 품절 여부
                if product_data.get('sold_out'):
                    sold_type = product_data.get('sold_out_type', '품절')
                    print(f"    상태: ❌ {sold_type}")
                else:
                    print(f"    상태: ✅ 판매중")

                # 카테고리
                if product_data.get('categories'):
                    cats = ' > '.join(product_data['categories'][:4])
                    print(f"    카테고리: {cats}")

                print(f"  {'─' * 50}")

            return result

        elif response.status_code == 403:
            result = {
                'success': False,
                'status': 403,
                'size': size,
                'error': 'BLOCKED_403',
                'product_data': {},
                'response_cookies': response_cookies
            }
            if verbose:
                print(f"  ❌ 403 BLOCKED ({size} bytes)")
            return result

        else:
            result = {
                'success': False,
                'status': response.status_code,
                'size': size,
                'error': f'INVALID_{size}B',
                'product_data': {},
                'response_cookies': response_cookies
            }
            if verbose:
                print(f"  ❌ {response.status_code} - {size} bytes")
            return result

    except Exception as e:
        result = {
            'success': False,
            'error': str(e)[:100],
            'product_data': {},
            'response_cookies': {}
        }
        if verbose:
            print(f"  ❌ Error: {str(e)[:100]}")
        return result
