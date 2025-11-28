"""
JSON-LD (schema.org) 기반 상품 정보 추출기

HTML의 self.__next_f.push 데이터에서 @type: Product 형식의
구조화된 데이터를 추출합니다.

사용법:
  from extractor.jsonld_extractor import extract_jsonld_product

  product = extract_jsonld_product(html_content)
  print(product)
  # {
  #   'title': '상품명',
  #   'price': 13890,
  #   'original_price': 35000,
  #   'rating': 4.9,
  #   'review_count': 1382,
  #   'sold_out': False,
  #   'thumbnail': 'https://...',
  #   'sku': '8726581090-25351888746',
  #   'url': 'https://www.coupang.com/vp/products/...'
  # }
"""

import re
import json


def extract_next_f_push(html_content):
    """HTML에서 self.__next_f.push 데이터 추출"""
    pattern = r'self\.__next_f\.push\(\s*(\[.*?\])\s*\)'
    matches = re.findall(pattern, html_content, re.DOTALL)

    results = []
    for match in matches:
        try:
            data = json.loads(match)
            results.append(data)
        except json.JSONDecodeError:
            continue

    return results


def find_jsonld_product(next_f_data):
    """next_f.push 데이터에서 JSON-LD Product 찾기"""
    for item in next_f_data:
        if not isinstance(item, list) or len(item) < 2:
            continue

        content = item[1]
        if not isinstance(content, str):
            # 이미 dict인 경우
            if isinstance(content, dict) and content.get('@type') == 'Product':
                return content
            continue

        # JSON 문자열 파싱 시도
        if content.startswith('{'):
            try:
                data = json.loads(content)
                if data.get('@type') == 'Product':
                    return data
            except json.JSONDecodeError:
                continue

    return None


def extract_categories(html_content):
    """HTML에서 카테고리(BreadcrumbList JSON-LD) 추출

    <script type="application/ld+json">에서 BreadcrumbList 추출
    예: {"id": "305798", "name": "헬스/건강식품", "href": "/np/categories/305798"}
    """
    categories = []

    # BreadcrumbList JSON-LD 찾기
    pattern = r'<script[^>]*type="application/ld\+json"[^>]*>\s*(\{[^<]*"@type"\s*:\s*"BreadcrumbList"[^<]*\})\s*</script>'
    match = re.search(pattern, html_content, re.DOTALL)

    if not match:
        return categories

    try:
        breadcrumb_data = json.loads(match.group(1))
        items = breadcrumb_data.get('itemListElement', [])

        for item in items:
            # 중첩 리스트 처리 (쿠팡 특이 구조)
            if isinstance(item, list):
                for sub_item in item:
                    if isinstance(sub_item, dict) and sub_item.get('@type') == 'ListItem':
                        name = sub_item.get('name', '')
                        url = sub_item.get('item', '')
                        if name and name != '쿠팡 홈' and '/np/categories/' in url:
                            cat_id = re.search(r'/categories/(\d+)', url)
                            categories.append({
                                'id': cat_id.group(1) if cat_id else None,
                                'name': name
                            })
            elif isinstance(item, dict) and item.get('@type') == 'ListItem':
                name = item.get('name', '')
                url = item.get('item', '')
                if name and name != '쿠팡 홈' and '/np/categories/' in url:
                    cat_id = re.search(r'/categories/(\d+)', url)
                    categories.append({
                        'id': cat_id.group(1) if cat_id else None,
                        'name': name
                    })
    except (json.JSONDecodeError, KeyError):
        pass

    return categories


def extract_price_info(html_content):
    """HTML에서 salePrice, couponPrice 추출 (next_f.push 데이터에서)

    Returns:
        dict: {'sale_price': 51600, 'coupon_price': 47590}
    """
    result = {
        'sale_price': None,
        'coupon_price': None
    }

    # salePrice 패턴: salePrice\":\"51,600\" (콤마 포함 문자열)
    sale_match = re.search(r'salePrice\\?":\\?"([0-9,]+)\\?"', html_content)
    if sale_match:
        try:
            result['sale_price'] = int(sale_match.group(1).replace(',', ''))
        except ValueError:
            pass

    # couponPrice 패턴: couponPrice\":\"47,590\" (콤마 포함 문자열)
    coupon_match = re.search(r'couponPrice\\?":\\?"([0-9,]+)\\?"', html_content)
    if coupon_match:
        try:
            result['coupon_price'] = int(coupon_match.group(1).replace(',', ''))
        except ValueError:
            pass

    return result


def extract_delivery_info(html_content):
    """HTML에서 배송 정보 추출 (next_f.push 데이터에서)

    Returns:
        dict: {'delivery_type': 'ROCKET_MERCHANT', 'badge_url': 'https://...'}
    """
    result = {
        'delivery_type': None,
        'badge_url': None
    }

    # deliveryType 패턴 (이스케이프된 따옴표 포함)
    # 패턴: deliveryType\":\"ROCKET_MERCHANT\" 또는 deliveryType":"ROCKET_MERCHANT"
    delivery_match = re.search(r'deliveryType\\?":\\?"([A-Z_]+)\\?"', html_content)
    if delivery_match:
        result['delivery_type'] = delivery_match.group(1)

    # badgeUrl 패턴 (이스케이프된 따옴표 포함)
    badge_match = re.search(r'badgeUrl\\?":\\?"(https?://[^"\\]+)\\?"', html_content)
    if badge_match:
        result['badge_url'] = badge_match.group(1)

    return result


def extract_jsonld_product(html_content):
    """HTML에서 JSON-LD 상품 정보 추출

    Args:
        html_content: HTML 문자열

    Returns:
        dict: 상품 정보 또는 None
        {
            'title': str,
            'price': int,
            'original_price': int,
            'discount_rate': int,
            'rating': float,
            'review_count': int,
            'sold_out': bool,
            'thumbnail': str,
            'sku': str,
            'url': str,
            'description': str
        }
    """
    # next_f.push 데이터 추출
    next_f_data = extract_next_f_push(html_content)
    if not next_f_data:
        return None

    # JSON-LD Product 찾기
    jsonld = find_jsonld_product(next_f_data)
    if not jsonld:
        return None

    # 데이터 변환
    result = {}

    # 기본 정보
    result['title'] = jsonld.get('name')
    result['description'] = jsonld.get('description')
    result['sku'] = jsonld.get('sku')

    # 이미지 (첫 번째)
    images = jsonld.get('image', [])
    if images:
        result['thumbnail'] = images[0] if isinstance(images, list) else images

    # 가격 정보
    offers = jsonld.get('offers', {})
    if offers:
        # 현재가
        price_str = offers.get('price')
        if price_str:
            try:
                result['price'] = int(price_str)
            except (ValueError, TypeError):
                result['price'] = None

        # 원가 (StrikethroughPrice)
        price_spec = offers.get('priceSpecification', {})
        if price_spec:
            original_str = price_spec.get('price')
            if original_str:
                try:
                    result['original_price'] = int(original_str)
                except (ValueError, TypeError):
                    result['original_price'] = None

        # 할인율 계산
        if result.get('price') and result.get('original_price'):
            discount = result['original_price'] - result['price']
            result['discount_rate'] = int(discount / result['original_price'] * 100)

        # 품절 여부
        availability = offers.get('availability', '')
        result['sold_out'] = 'OutOfStock' in availability

        # 상품 URL
        result['url'] = offers.get('url')

    # 평점/리뷰
    rating = jsonld.get('aggregateRating', {})
    if rating:
        result['rating'] = rating.get('ratingValue')
        review_count = rating.get('ratingCount')
        if review_count:
            try:
                result['review_count'] = int(review_count)
            except (ValueError, TypeError):
                result['review_count'] = None

    # 카테고리 추출 (BreadcrumbList JSON-LD에서)
    categories = extract_categories(html_content)
    if categories:
        result['categories'] = categories

    # salePrice, couponPrice 추출 (next_f.push에서)
    price_info = extract_price_info(html_content)
    if price_info['sale_price']:
        result['sale_price'] = price_info['sale_price']
    if price_info['coupon_price']:
        result['coupon_price'] = price_info['coupon_price']

    # 배송 정보 추출 (next_f.push에서)
    delivery_info = extract_delivery_info(html_content)
    if delivery_info['delivery_type']:
        result['delivery_type'] = delivery_info['delivery_type']
    else:
        # Fallback: 이미지 패턴으로 배송 타입 추론
        result['delivery_type'] = _extract_delivery_type_fallback(html_content)

    if delivery_info['badge_url']:
        result['badge_url'] = delivery_info['badge_url']

    return result


def _extract_delivery_type_fallback(html_content):
    """이미지 패턴으로 배송 타입 추론 (JSON-LD에 deliveryType이 없을 때)

    Returns:
        str: ROCKET_MERCHANT, ROCKET, ROCKET_FRESH, COUPANG_GLOBAL 또는 None
    """
    # 로켓프레시 우선 체크
    if 'rocket-fresh' in html_content.lower() or 'rocketfresh' in html_content.lower():
        return 'ROCKET_FRESH'

    # 로켓직구
    if 'rocket-global' in html_content.lower() or 'rocketglobal' in html_content.lower() or 'coupang_global' in html_content.lower():
        return 'COUPANG_GLOBAL'

    # 로켓배송 판매자 (rocket_merchant 이미지)
    if 'rocket_merchant' in html_content.lower() or 'logoRocketMerchant' in html_content:
        return 'ROCKET_MERCHANT'

    # 일반 로켓배송
    if 'rocket_icon' in html_content or 'RocketDelivery' in html_content or 'logo_rocket' in html_content.lower():
        return 'ROCKET'

    return None


def normalize_delivery_type(delivery_type):
    """JSON-LD deliveryType을 기존 시스템 명명 규칙으로 변환

    JSON-LD 값 → 기존 시스템 값:
        ROCKET_MERCHANT → ROCKET_SELLER (로켓배송 판매자)
        ROCKET → ROCKET_DELIVERY (로켓배송)
        ROCKET_FRESH → ROCKET_FRESH (로켓프레시)
        COUPANG_GLOBAL → COUPANG_GLOBAL (로켓직구)
    """
    if not delivery_type:
        return None

    mapping = {
        'ROCKET_MERCHANT': 'ROCKET_SELLER',
        'ROCKET': 'ROCKET_DELIVERY',
        'ROCKET_FRESH': 'ROCKET_FRESH',
        'COUPANG_GLOBAL': 'ROCKET_DIRECT',
    }
    return mapping.get(delivery_type, delivery_type)


def to_api_format(product_data):
    """API 응답 형식으로 변환 (기존 detail_extractor 호환)

    Args:
        product_data: extract_jsonld_product() 결과

    Returns:
        dict: API 응답 형식
        - deliveryType: 기존 시스템 명명규칙 (ROCKET_SELLER, ROCKET_DELIVERY 등)
        - deliveryType_json: JSON-LD 원본 값 (참고용, ROCKET_MERCHANT, ROCKET 등)
    """
    if not product_data:
        return {'productNotFound': True}

    delivery_type_json = product_data.get('delivery_type')  # JSON-LD 원본
    delivery_type = normalize_delivery_type(delivery_type_json)  # 기존 시스템용

    return {
        'price': product_data.get('price'),
        'title': product_data.get('title'),
        'soldOut': product_data.get('sold_out', False),
        'soldOutText': None,
        'soldOutType': 'sold_out' if product_data.get('sold_out') else 'available',
        'discountRate': product_data.get('discount_rate'),
        'originalPrice': product_data.get('original_price'),
        # 추가 가격 정보 (next_f.push에서 추출, 있을 때만)
        'salePrice': product_data.get('sale_price'),
        'couponPrice': product_data.get('coupon_price'),
        'thumbnail': product_data.get('thumbnail'),
        'productNotFound': False,
        'rating': product_data.get('rating'),
        'reviewCount': product_data.get('review_count'),
        # 배송 정보
        'deliveryType': delivery_type,  # 기존 시스템 명명규칙
        'deliveryType_json': delivery_type_json,  # JSON-LD 원본 (참고용)
        'deliveryBadgeUrl': product_data.get('badge_url'),
        # 카테고리 (BreadcrumbList JSON-LD에서 추출)
        'categories': product_data.get('categories', [])
    }


# CLI 테스트
if __name__ == '__main__':
    import sys
    from pathlib import Path

    if len(sys.argv) < 2:
        # html 폴더에서 랜덤 선택
        import random
        html_dir = Path(__file__).parent.parent.parent / 'html'
        html_files = list(html_dir.glob('*.html'))
        if not html_files:
            print("❌ HTML 파일 없음")
            sys.exit(1)
        html_path = random.choice(html_files)
    else:
        html_path = Path(sys.argv[1])
        if not html_path.exists():
            # html 폴더에서 찾기
            html_dir = Path(__file__).parent.parent.parent / 'html'
            html_path = html_dir / (sys.argv[1] if sys.argv[1].endswith('.html') else sys.argv[1] + '.html')

    if not html_path.exists():
        print(f"❌ 파일 없음: {html_path}")
        sys.exit(1)

    print(f"📄 파일: {html_path.name}")
    print("=" * 60)

    html_content = html_path.read_text(encoding='utf-8')
    product = extract_jsonld_product(html_content)

    if product:
        print("✅ JSON-LD 추출 성공\n")
        for key, value in product.items():
            if value is not None:
                # url, thumbnail은 전체 표시, 나머지는 60자 제한
                if key in ('url', 'thumbnail'):
                    print(f"  {key}: {value}")
                else:
                    display_value = str(value)[:60] + '...' if len(str(value)) > 60 else value
                    print(f"  {key}: {display_value}")

        print("\n" + "─" * 60)
        print("📦 API 형식:")
        api_data = to_api_format(product)
        print(json.dumps(api_data, ensure_ascii=False, indent=2))
    else:
        print("❌ JSON-LD 데이터 없음")
