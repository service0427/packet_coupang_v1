"""
작업 할당 API 모듈

API 엔드포인트:
- 할당: GET  http://mkt.techb.kr:29998/api/work/allocate/{type}
- 결과: POST http://mkt.techb.kr:29998/api/work/result/{type}

지원 타입:
- rank: 순위 체크
- click: 클릭 체크
"""

import requests

# API 설정
BASE_URL = 'http://mkt.techb.kr:29998'

# 지원되는 work 타입
WORK_TYPES = ['rank', 'click']


def get_allocate_url(work_type='rank'):
    """할당 API URL 생성"""
    return f'{BASE_URL}/api/work/allocate/{work_type}'


def get_result_url(work_type='rank'):
    """결과 API URL 생성"""
    return f'{BASE_URL}/api/work/result/{work_type}'


def allocate_work(work_id=None, work_type='rank'):
    """작업 할당 API 호출

    Args:
        work_id: 특정 작업 ID (없으면 자동 할당)

    Returns:
        dict: 할당 정보 또는 None
        {
            "progress_id": 5102,
            "site_code": "topr",
            "keyword": "김",
            "product_id": "9049944835",
            "item_id": "26560784387",
            "vendor_item_id": "93534485960",
            "proxy": "121.142.207.19:10020",
            "external_ip": "175.223.14.53",
            "info_data": false,
            "shot_data": false,
            "is_filter": false
        }
    """
    try:
        base_url = get_allocate_url(work_type)
        url = f"{base_url}?id={work_id}" if work_id else base_url
        resp = requests.get(url, timeout=10)
        data = resp.json()

        if data.get('success') and data.get('allocation'):
            return data['allocation']
        else:
            return None
    except Exception as e:
        print(f"❌ 할당 API 에러: {e}")
        return None


def report_result(progress_id, proxy, external_ip, status, rank=None, info=None, work_type='rank'):
    """결과 보고 API 호출

    Args:
        progress_id: 작업 ID
        proxy: 프록시 (host:port)
        external_ip: 외부 IP
        status: 'success' 또는 'failed'
        rank: 순위 (0=미발견, None=순위체크 오류)
        info: 상품 정보 dict (선택)

    Returns:
        dict: API 응답 또는 None

    Examples:
        # 1. 순위만 저장
        report_result(5652, "14.37.117.98:10027", "39.7.18.253", "success", rank=15)

        # 2. 순위 + 상품정보
        report_result(5652, "14.37.117.98:10027", "39.7.18.253", "success", rank=15, info={...})

        # 3. 순위 미발견
        report_result(5652, "14.37.117.98:10027", "39.7.18.253", "success", rank=0)

        # 4. 순위 체크 오류 (상품정보만)
        report_result(5652, "14.37.117.98:10027", "39.7.18.253", "success", info={...})

        # 5. 프록시 오류
        report_result(5652, "14.37.117.98:10027", "39.7.18.253", "failed")
    """
    payload = {
        'progress_id': progress_id,
        'proxy': proxy,
        'external_ip': external_ip,
        'status': status
    }

    # rank가 있으면 추가 (0도 유효한 값)
    if rank is not None:
        payload['rank'] = rank

    # info가 있으면 추가
    if info:
        payload['info'] = info

    try:
        result_url = get_result_url(work_type)
        resp = requests.post(result_url, json=payload, timeout=10)
        return resp.json()
    except Exception as e:
        print(f"⚠️ 결과 API 에러: {e}")
        return None


def build_info_data(product_data):
    """상품 데이터를 API info 형식으로 변환

    Args:
        product_data: extract_product_detail() 또는 to_api_response() 결과

    Returns:
        dict: API info 형식
        {
            "title": "상품명",
            "price": 299000,
            "originalPrice": 350000,
            "discountRate": 15,
            "rating": 4.8,
            "reviewCount": 5678,
            "soldOut": false,
            "deliveryType": "ROCKET_DELIVERY",
            "thumbnail": "https://..."
        }
    """
    if not product_data:
        return None

    # to_api_response() 결과인 경우 (camelCase)
    if 'soldOut' in product_data:
        return {
            'title': product_data.get('title'),
            'price': product_data.get('price'),
            'originalPrice': product_data.get('originalPrice'),
            'salePrice': product_data.get('salePrice'),  # 판매가 (쿠폰 적용 전)
            'couponPrice': product_data.get('couponPrice'),  # 쿠폰 적용가 (최종가)
            'discountRate': product_data.get('discountRate'),
            'rating': product_data.get('rating'),
            'reviewCount': product_data.get('reviewCount'),
            'soldOut': product_data.get('soldOut'),
            'deliveryType': product_data.get('deliveryType'),
            'thumbnail': product_data.get('thumbnail'),
            'categories': product_data.get('categories', [])
        }

    # extract_product_detail() 결과인 경우 (snake_case)
    return {
        'title': product_data.get('title'),
        'price': product_data.get('price'),
        'originalPrice': product_data.get('original_price'),
        'salePrice': product_data.get('sale_price'),  # 판매가 (쿠폰 적용 전)
        'couponPrice': product_data.get('coupon_price'),  # 쿠폰 적용가 (최종가)
        'discountRate': product_data.get('discount_rate'),
        'rating': product_data.get('rating'),
        'reviewCount': product_data.get('review_count'),
        'soldOut': product_data.get('sold_out', False),
        'deliveryType': product_data.get('delivery_type'),
        'thumbnail': product_data.get('thumbnail'),
        'categories': product_data.get('categories', [])
    }
