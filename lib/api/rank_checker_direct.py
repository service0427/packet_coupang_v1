"""
순위 체크 - 직접 연결 방식

쿠키/프록시 없이 커스텀 TLS 핑거프린트로 직접 연결
"""

import time
import random
from urllib.parse import quote
from curl_cffi import requests

# Chrome 143 Mobile TLS 핑거프린트
TLS_CONFIG = {
    "ja3": "771,4865-4866-4867-49195-49199-49196-49200-52393-52392-49171-49172-156-157-47-53,16-10-43-51-17613-5-65281-35-11-0-65037-18-23-45-13-27,4588-29-23-24,0",
    "akamai": "1:65536;2:0;4:6291456;6:262144|15663105|0|m,a,s,p",
    "extra_fp": {
        "tls_signature_algorithms": [
            "ecdsa_secp256r1_sha256",
            "rsa_pss_rsae_sha256",
            "rsa_pkcs1_sha256",
            "ecdsa_secp384r1_sha384",
            "rsa_pss_rsae_sha384",
            "rsa_pkcs1_sha384",
            "rsa_pss_rsae_sha512",
            "rsa_pkcs1_sha512",
        ],
        "tls_grease": True,
        "tls_permute_extensions": True,
    }
}

HEADERS = {
    'coupang-app': 'COUPANG|Android|14|9.0.4',
    'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Mobile Safari/537.36',
}

BASE_URL = "https://cmapi.coupang.com"
CHROME_VERSION = "143.0.0.0"


def _request(url):
    """커스텀 TLS로 요청"""
    return requests.get(
        url,
        headers=HEADERS,
        ja3=TLS_CONFIG["ja3"],
        akamai=TLS_CONFIG["akamai"],
        extra_fp=TLS_CONFIG["extra_fp"],
        timeout=15,
    )


def _extract_products(rdata):
    """entityList에서 상품 추출"""
    products = []
    for ent in rdata.get('entityList', []):
        widget = ent.get('entity', {}).get('widget', {})
        metadata = widget.get('metadata', {})
        mandatory = metadata.get('commonBypassLogParams', {}).get('mandatory', {})
        display = metadata.get('displayItem', {})

        product_id = mandatory.get('productId')
        if not product_id:
            continue

        products.append({
            'productId': str(product_id),
            'itemId': str(mandatory.get('itemId', '')),
            'vendorItemId': str(mandatory.get('vendorItemId', '')),
            'title': display.get('title', ''),
            'price': display.get('price', ''),
            'discountRate': display.get('discountRate', ''),
            'rating': display.get('rating', ''),
            'ratingCount': display.get('ratingCount', ''),
            'rocket': display.get('rocket', False),
            'rocketWow': display.get('rocketWow', False),
            'isAd': mandatory.get('isAds', False),
        })
    return products


def _match_product(product, target_product_id, target_item_id=None, target_vendor_item_id=None):
    """상품 매칭 우선순위 체크"""
    p_id = str(product.get('productId', ''))
    i_id = str(product.get('itemId', ''))
    v_id = str(product.get('vendorItemId', ''))

    t_p_id = str(target_product_id) if target_product_id else ''
    t_i_id = str(target_item_id) if target_item_id else ''
    t_v_id = str(target_vendor_item_id) if target_vendor_item_id else ''

    # 1순위: 3개 모두 매칭
    if t_p_id and t_i_id and t_v_id:
        if p_id == t_p_id and i_id == t_i_id and v_id == t_v_id:
            return (True, 'full_match')

    # 2순위: product_id + vendor_item_id
    if t_p_id and t_v_id:
        if p_id == t_p_id and v_id == t_v_id:
            return (True, 'product_vendor')

    # 3순위: product_id + item_id
    if t_p_id and t_i_id:
        if p_id == t_p_id and i_id == t_i_id:
            return (True, 'product_item')

    # 4순위: product_id만
    if t_p_id and p_id == t_p_id:
        return (True, 'product_only')

    # 5순위: vendor_item_id만
    if t_v_id and v_id == t_v_id:
        return (True, 'vendor_only')

    # 6순위: item_id만
    if t_i_id and i_id == t_i_id:
        return (True, 'item_only')

    return (False, None)


def _error_result(start_time, code, message, detail=None, pages_searched=0):
    """에러 결과"""
    return {
        'success': False,
        'found': False,
        'rank': None,
        'page': None,
        'pages_searched': pages_searched,
        'elapsed_ms': int((time.time() - start_time) * 1000),
        'chrome_version': CHROME_VERSION,
        'error_code': code,
        'error_message': message,
        'error_detail': detail
    }


def _success_result(start_time, found, rank, page, pages_searched,
                    rating=None, review_count=None, id_match_type=None):
    """성공 결과"""
    return {
        'success': True,
        'found': found,
        'rank': rank,
        'page': page,
        'rating': rating,
        'review_count': review_count,
        'id_match_type': id_match_type,
        'pages_searched': pages_searched,
        'elapsed_ms': int((time.time() - start_time) * 1000),
        'chrome_version': CHROME_VERSION,
        'error_code': None,
        'error_message': None
    }


def check_rank(keyword: str, product_id: str, item_id: str = None,
               vendor_item_id: str = None, max_page: int = 13) -> dict:
    """순위 체크 (직접 연결)

    Args:
        keyword: 검색어
        product_id: 상품 ID
        item_id: 아이템 ID (선택)
        vendor_item_id: 벤더 아이템 ID (선택)
        max_page: 최대 검색 페이지

    Returns:
        dict: 순위 체크 결과
    """
    start_time = time.time()

    # 입력값 검증
    if not keyword or not str(keyword).strip():
        return _error_result(start_time, 'INVALID_INPUT', 'keyword is required')
    if not product_id or not str(product_id).strip():
        return _error_result(start_time, 'INVALID_INPUT', 'product_id is required')

    keyword = str(keyword).strip()
    product_id = str(product_id).strip()

    try:
        # 검색 실행
        params = f"filter=KEYWORD:{quote(keyword)}|CCID:ALL|EXTRAS:channel/user|GET_FILTER:NONE|SINGLE_ENTITY:TRUE@SEARCH&preventingRedirection=false&resultType=default&ccidActivated=false"
        url = f"{BASE_URL}/v3/products?{params}"

        resp = _request(url)
        if resp.status_code != 200:
            return _error_result(start_time, 'API_ERROR', f'Status {resp.status_code}')

        data = resp.json()
        if data.get('rCode') != 'RET0000':
            return _error_result(start_time, 'API_ERROR', data.get('rCode'))

        rdata = data.get('rData', {})
        all_products = {}
        found_product = None
        id_match_type = None

        # 첫 페이지
        for p in _extract_products(rdata):
            key = f"{p['productId']}_{p['itemId']}"
            if key not in all_products:
                p['rank'] = len(all_products) + 1
                all_products[key] = p

                if not found_product:
                    matched, match_type = _match_product(p, product_id, item_id, vendor_item_id)
                    if matched:
                        found_product = p
                        id_match_type = match_type

        next_key = rdata.get('nextPageKey')
        next_params = rdata.get('nextPageParams', '')
        pages = 1

        # 다음 페이지들
        while next_key and pages < max_page and not found_product:
            pages += 1
            url = f"{BASE_URL}/v3/products?{params}&nextPageKey={quote(next_key)}&nextPageParams={quote(next_params)}&resultType=search"

            try:
                resp = _request(url)
                data = resp.json()
            except Exception:
                break

            if data.get('rCode') != 'RET0000':
                break

            rdata = data.get('rData', {})
            before_count = len(all_products)

            for p in _extract_products(rdata):
                key = f"{p['productId']}_{p['itemId']}"
                if key not in all_products:
                    p['rank'] = len(all_products) + 1
                    all_products[key] = p

                    if not found_product:
                        matched, match_type = _match_product(p, product_id, item_id, vendor_item_id)
                        if matched:
                            found_product = p
                            id_match_type = match_type
                            break

            if len(all_products) == before_count:
                break

            next_key = rdata.get('nextPageKey')
            next_params = rdata.get('nextPageParams', '')

        # 결과 반환
        if found_product:
            rank = found_product['rank']
            page = (rank - 1) // 72 + 1

            # rating 파싱
            rating = None
            rating_str = found_product.get('rating', '')
            if rating_str:
                try:
                    rating = float(rating_str)
                except:
                    pass

            # review_count 파싱
            review_count = None
            rc_str = found_product.get('ratingCount', '')
            if rc_str:
                try:
                    review_count = int(rc_str.replace(',', '').replace('개', '').replace('(', '').replace(')', ''))
                except:
                    pass

            return _success_result(
                start_time, True, rank, page, pages,
                rating=rating, review_count=review_count, id_match_type=id_match_type
            )
        else:
            return _success_result(start_time, False, None, None, pages)

    except Exception as e:
        return _error_result(start_time, 'INTERNAL_ERROR', 'Unexpected error', str(e)[:100])


def get_public_ip():
    """공인 IP 조회"""
    try:
        resp = requests.get('https://api.ipify.org?format=json', timeout=5)
        return resp.json().get('ip', '')
    except:
        return ''
