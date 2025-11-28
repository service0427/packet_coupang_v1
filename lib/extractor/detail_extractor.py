"""
상품 상세 정보 추출기
- 상품 페이지 HTML에서 상세 정보 파싱
- 가격, 할인율, 평점, 리뷰, 판매자 등 추출
"""

import re
import json


def _extract_jsonld_product(html_content):
    """HTML에서 JSON-LD (schema.org Product) 추출

    <script type="application/ld+json">에서 @type: Product 데이터 추출
    """
    # Product JSON-LD 찾기
    pattern = r'<script[^>]*type="application/ld\+json"[^>]*>\s*(\{[^<]*"@type"\s*:\s*"Product"[^<]*\})\s*</script>'
    match = re.search(pattern, html_content, re.DOTALL)

    if not match:
        return None

    try:
        jsonld = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None

    result = {}

    # 기본 정보
    result['title'] = jsonld.get('name')

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
                pass

        # 원가 (StrikethroughPrice)
        price_spec = offers.get('priceSpecification', {})
        if price_spec:
            original_str = price_spec.get('price')
            if original_str:
                try:
                    result['original_price'] = int(original_str)
                except (ValueError, TypeError):
                    pass

        # 품절 여부
        availability = offers.get('availability', '')
        result['sold_out'] = 'OutOfStock' in availability

    # 평점/리뷰
    rating = jsonld.get('aggregateRating', {})
    if rating:
        result['rating'] = rating.get('ratingValue')
        review_count = rating.get('ratingCount')
        if review_count:
            try:
                result['review_count'] = int(review_count)
            except (ValueError, TypeError):
                pass

    return result


def _extract_breadcrumb_categories(html_content):
    """HTML에서 BreadcrumbList JSON-LD로 카테고리 추출"""
    categories = []

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


def extract_product_detail(html_content):
    """HTML에서 상품 상세 데이터 추출

    Args:
        html_content: 상품 페이지 HTML

    Returns:
        dict: 상품 상세 정보 (제목, 가격, 원가, 할인율, 배송타입, 평점, 리뷰수, 판매자 등)
    """
    data = {}

    if not html_content:
        return data

    # === JSON-LD (schema.org) 에서 추출 (가장 신뢰도 높음) ===
    jsonld_data = _extract_jsonld_product(html_content)
    if jsonld_data:
        # 가격, 평점, 리뷰 등 JSON-LD에서 우선 추출
        if jsonld_data.get('price'):
            data['price'] = jsonld_data['price']
        if jsonld_data.get('original_price'):
            data['original_price'] = jsonld_data['original_price']
        if jsonld_data.get('rating'):
            data['rating'] = jsonld_data['rating']
        if jsonld_data.get('review_count'):
            data['review_count'] = jsonld_data['review_count']
        if jsonld_data.get('sold_out') is not None:
            data['sold_out'] = jsonld_data['sold_out']
        if jsonld_data.get('thumbnail'):
            data['thumbnail'] = jsonld_data['thumbnail']
        if jsonld_data.get('title'):
            data['title'] = jsonld_data['title']

    # === 제목 ===
    # 우선순위: h1.product-title span > h1.prod-buy-header__title > og:title (쿠팡 제거)
    title_match = re.search(r'<h1[^>]*class="[^"]*product-title[^"]*"[^>]*>\s*<span>([^<]+)</span>', html_content)
    if title_match:
        data['title'] = title_match.group(1).strip()
    else:
        title_match = re.search(r'<h1[^>]*class="[^"]*prod-buy-header__title[^"]*"[^>]*>([^<]+)</h1>', html_content)
        if title_match:
            data['title'] = title_match.group(1).strip()
        else:
            og_title = re.search(r'<meta property="og:title" content="([^"]+)"', html_content)
            if og_title:
                title = og_title.group(1)
                # " | 쿠팡" 또는 " - 카테고리 | 쿠팡" 제거
                title = re.sub(r'\s*[-|]\s*[^|]+\s*\|\s*쿠팡$', '', title)
                data['title'] = title.strip()

    # === 현재 판매가 ===
    # class="price-amount final-price-amount" 패턴
    price_match = re.search(r'class="[^"]*final-price-amount[^"]*"[^>]*>([^<]+)', html_content)
    if price_match:
        price_text = re.sub(r'[^\d]', '', price_match.group(1))
        if price_text:
            data['price'] = int(price_text)

    # 대안: JSON에서 추출
    if 'price' not in data:
        price_pattern = r'"finalPrice"\s*:\s*"?([\d,]+)"?'
        match = re.search(price_pattern, html_content)
        if match:
            data['price'] = int(match.group(1).replace(',', ''))

    if 'price' not in data:
        og_price = re.search(r'<meta property="product:price:amount" content="([^"]+)"', html_content)
        if og_price:
            try:
                data['price'] = int(og_price.group(1))
            except:
                pass

    # === 원가 (할인 전 가격, 취소선) ===
    # class="price-amount original-price-amount" 패턴
    original_price_match = re.search(r'class="[^"]*original-price-amount[^"]*"[^>]*>([^<]+)', html_content)
    if original_price_match:
        orig_text = re.sub(r'[^\d]', '', original_price_match.group(1))
        if orig_text:
            data['original_price'] = int(orig_text)

    # 대안: JSON에서 추출
    if 'original_price' not in data:
        orig_pattern = r'"originPrice"\s*:\s*"?([\d,]+)"?'
        match = re.search(orig_pattern, html_content)
        if match:
            data['original_price'] = int(match.group(1).replace(',', ''))

    # === 쿠팡판매가 (type: "SALES") ===
    # JSON에서 "priceAmount":"금액"..."title":"쿠팡판매가","type":"SALES" 패턴 추출
    # HTML 내 JSON은 이스케이프 형태일 수 있음: \"priceAmount\":\"96,700\"
    # 이스케이프된 형태 먼저 시도
    sales_pattern_escaped = r'\\"priceAmount\\":\\"([\d,]+)\\".*?\\"title\\":\\"쿠팡판매가\\",\\"type\\":\\"SALES\\"'
    sales_match = re.search(sales_pattern_escaped, html_content)
    if sales_match:
        data['sales_price'] = int(sales_match.group(1).replace(',', ''))
    else:
        # 일반 형태 시도
        sales_pattern_normal = r'"priceAmount":"([\d,]+)".*?"title":"쿠팡판매가","type":"SALES"'
        sales_match2 = re.search(sales_pattern_normal, html_content)
        if sales_match2:
            data['sales_price'] = int(sales_match2.group(1).replace(',', ''))

    # === salePrice, couponPrice (next_f.push에서) ===
    # salePrice: 판매가 (쿠폰 적용 전)
    sale_match = re.search(r'salePrice\\?":\\?"([0-9,]+)\\?"', html_content)
    if sale_match:
        try:
            data['sale_price'] = int(sale_match.group(1).replace(',', ''))
        except ValueError:
            pass

    # couponPrice: 쿠폰 적용가 (최종가)
    coupon_match = re.search(r'couponPrice\\?":\\?"([0-9,]+)\\?"', html_content)
    if coupon_match:
        try:
            data['coupon_price'] = int(coupon_match.group(1).replace(',', ''))
        except ValueError:
            pass

    # === 할인율 ===
    # class='discount-rate' 패턴 (JSON 내 유니코드 이스케이프 처리)
    # \u003e = >, \u003c = <
    discount_match = re.search(r"class='discount-rate'(?:\\u003e|>)(\d+)%", html_content)
    if discount_match:
        data['discount_rate'] = int(discount_match.group(1))

    # 대안: JSON에서 추출
    if 'discount_rate' not in data:
        disc_pattern = r'"discountRate"\s*:\s*"?(\d+)"?'
        match = re.search(disc_pattern, html_content)
        if match:
            data['discount_rate'] = int(match.group(1))

    # === 배송 타입 ===
    # 우선순위 1: next_f.push의 deliveryType 필드 (가장 정확)
    delivery_match = re.search(r'deliveryType\\?":\\?"([A-Z_]+)\\?"', html_content)
    if delivery_match:
        data['delivery_type_json'] = delivery_match.group(1)  # 원본 저장 (참고용)
        # ROCKET_MERCHANT, ROCKET, ROCKET_FRESH, COUPANG_GLOBAL 등
        dtype = delivery_match.group(1)
        if dtype == 'ROCKET_FRESH':
            data['delivery_type'] = '로켓프레시'
        elif dtype == 'COUPANG_GLOBAL':
            data['delivery_type'] = '로켓직구'
        elif dtype in ('ROCKET_MERCHANT', 'ROCKET'):
            data['delivery_type'] = '로켓배송'
        else:
            data['delivery_type'] = '판매자배송'
    else:
        # 우선순위 2: 이미지 패턴 기반 추론 (fallback)
        if 'rocket-fresh' in html_content.lower() or 'rocketfresh' in html_content.lower():
            data['delivery_type'] = '로켓프레시'
        elif 'rocket-global' in html_content.lower() or 'rocketglobal' in html_content.lower():
            data['delivery_type'] = '로켓직구'
        elif 'rocket_icon' in html_content or 'RocketDelivery' in html_content or 'rocket_merchant' in html_content.lower():
            data['delivery_type'] = '로켓배송'
        else:
            data['delivery_type'] = '판매자배송'

    # === 평점 ===
    # JSON에서 ratingValue 추출 (실제 패턴)
    rating_pattern = r'"ratingValue"\s*:\s*([\d.]+)'
    rating_match = re.search(rating_pattern, html_content)
    if rating_match:
        data['rating'] = float(rating_match.group(1))

    # 대안: ratingAverage 패턴
    if 'rating' not in data:
        rating_pattern2 = r'"ratingAverage"\s*:\s*([\d.]+)'
        rating_match2 = re.search(rating_pattern2, html_content)
        if rating_match2:
            data['rating'] = float(rating_match2.group(1))

    # === 리뷰 수 ===
    # JSON에서 ratingCount 추출 (문자열 또는 숫자)
    review_pattern = r'"ratingCount"\s*:\s*"?(\d+)"?'
    review_match = re.search(review_pattern, html_content)
    if review_match:
        data['review_count'] = int(review_match.group(1))

    # 대안: ratingTotalCount 패턴
    if 'review_count' not in data:
        review_pattern2 = r'"ratingTotalCount"\s*:\s*(\d+)'
        review_match2 = re.search(review_pattern2, html_content)
        if review_match2:
            data['review_count'] = int(review_match2.group(1))

    # 대안: HTML에서 rating-count-txt 클래스
    if 'review_count' not in data:
        count_match = re.search(r'rating-count-txt[^>]*>(\d+)', html_content)
        if count_match:
            data['review_count'] = int(count_match.group(1))

    # === 판매자 정보 ===
    # 테이블에서 상호/대표자 추출
    seller_match = re.search(r'상호/대표자</div></th><td>([^<]+)</td>', html_content)
    if seller_match:
        seller_info = seller_match.group(1).strip()
        # "달빛기정떡 / 김대중" 형식에서 상호명만 추출
        if ' / ' in seller_info:
            data['seller_name'] = seller_info.split(' / ')[0]
        else:
            data['seller_name'] = seller_info

    # 대안: JSON에서 sellerName
    if 'seller_name' not in data:
        seller_pattern = r'"sellerName"\s*:\s*"([^"]+)"'
        seller_json = re.search(seller_pattern, html_content)
        if seller_json:
            data['seller_name'] = seller_json.group(1)

    # === 품절 여부 ===
    if 'sold-out' in html_content.lower() or 'out-of-stock' in html_content.lower():
        data['sold_out'] = True
        # 품절 타입 (일시품절 vs 완전품절)
        if '일시품절' in html_content:
            data['sold_out_type'] = '일시품절'
        else:
            data['sold_out_type'] = '품절'
    else:
        data['sold_out'] = False

    # === 카테고리 ===
    # 우선순위 1: JSON-LD BreadcrumbList (가장 정확)
    categories = _extract_breadcrumb_categories(html_content)

    # 우선순위 2: HTML ul.breadcrumb 패턴 (fallback)
    if not categories:
        def extract_category_id(href):
            """URL에서 카테고리 ID 추출: /np/categories/416130?... → 416130"""
            match = re.search(r'/categories/(\d+)', href)
            return match.group(1) if match else None

        breadcrumb_ul = re.search(r'<ul[^>]*class="[^"]*breadcrumb[^"]*"[^>]*>(.*?)</ul>', html_content, re.DOTALL)
        if breadcrumb_ul:
            ul_content = breadcrumb_ul.group(1)
            link_pattern = r'<a[^>]*href="([^"]*)"[^>]*>([^<]+)</a>'
            link_matches = re.findall(link_pattern, ul_content)
            for href, name in link_matches:
                name = name.strip()
                cat_id = extract_category_id(href)
                if name and cat_id:
                    categories.append({'id': cat_id, 'name': name})

    if categories:
        data['categories'] = categories

    # === 썸네일 이미지 (첫 번째만) ===
    # prod-image__items 영역의 첫 번째 이미지
    thumbnail_match = re.search(r'<img[^>]*class="[^"]*prod-image__item[^"]*"[^>]*src="([^"]+)"', html_content)
    if thumbnail_match:
        thumbnail = thumbnail_match.group(1)
        # //로 시작하면 https: 추가
        if thumbnail.startswith('//'):
            thumbnail = 'https:' + thumbnail
        data['thumbnail'] = thumbnail
    else:
        # 대안: og:image
        og_image = re.search(r'<meta property="og:image" content="([^"]+)"', html_content)
        if og_image:
            thumbnail = og_image.group(1)
            if thumbnail.startswith('//'):
                thumbnail = 'https:' + thumbnail
            data['thumbnail'] = thumbnail

    # === 배송 뱃지 URL ===
    # 로켓배송 아이콘 이미지
    badge_match = re.search(r'<img[^>]*class="[^"]*delivery-badge[^"]*"[^>]*src="([^"]+)"', html_content)
    if badge_match:
        badge_url = badge_match.group(1)
        if badge_url.startswith('//'):
            badge_url = 'https:' + badge_url
        data['delivery_badge_url'] = badge_url
    else:
        # 대안: rocket-icon 클래스 이미지
        rocket_badge = re.search(r'<img[^>]*class="[^"]*rocket[^"]*"[^>]*src="([^"]+)"', html_content)
        if rocket_badge:
            badge_url = rocket_badge.group(1)
            if badge_url.startswith('//'):
                badge_url = 'https:' + badge_url
            data['delivery_badge_url'] = badge_url

    return data


def convert_to_agent_format(product_data, product_info):
    """추출된 데이터를 coupang_agent_v2 호환 형식으로 변환

    Args:
        product_data: extract_product_detail()에서 추출된 데이터
        product_info: 상품 기본 정보 (productId, itemId, vendorItemId 등)

    Returns:
        dict: coupang_agent_v2 호환 형식의 productData
    """
    # 배송 타입 매핑
    delivery_type_map = {
        '로켓배송': 'ROCKET_DELIVERY',
        '로켓프레시': 'ROCKET_FRESH',
        '로켓직구': 'ROCKET_DIRECT',
        '판매자배송': 'GENERAL'
    }

    # 품절 타입 매핑
    sold_out_type_map = {
        False: 'available',
        '일시품절': 'temporary_out',
        '품절': 'sold_out'
    }

    # 품절 상태 결정
    if product_data.get('sold_out'):
        sold_out_type = sold_out_type_map.get(
            product_data.get('sold_out_type', '품절'),
            'sold_out'
        )
    else:
        sold_out_type = 'available'

    return {
        'title': product_data.get('title'),
        'price': product_data.get('price'),
        'originalPrice': product_data.get('original_price'),
        'discountRate': product_data.get('discount_rate'),
        'deliveryType': delivery_type_map.get(
            product_data.get('delivery_type', '판매자배송'),
            'GENERAL'
        ),
        'deliveryBadgeUrl': product_data.get('delivery_badge_url'),
        'rating': product_data.get('rating'),
        'reviewCount': product_data.get('review_count'),
        'sellerName': product_data.get('seller_name'),
        'soldOut': product_data.get('sold_out', False),
        'soldOutType': sold_out_type,
        'categories': product_data.get('categories', []),
        'thumbnail': product_data.get('thumbnail'),
        # ID 추출 우선순위:
        # 1. product_info (URL에서 파싱된 값) - rank_cmd에서 전달
        # 2. product_data (HTML __NEXT_DATA__에서 추출)
        # 3. None
        'productId': product_info.get('productId') or product_data.get('productId'),
        'itemId': product_info.get('itemId') or product_data.get('itemId'),
        'vendorItemId': product_info.get('vendorItemId') or product_data.get('vendorItemId'),
    }


def to_api_response(product_data):
    """추출된 데이터를 API 응답 형식으로 변환

    Args:
        product_data: extract_product_detail()에서 추출된 데이터

    Returns:
        dict: API 응답용 상품 정보
        {
            "price": 87900,
            "title": "상품명",
            "soldOut": false,
            "categories": [{"href": "...", "name": "..."}],
            "soldOutText": null,
            "soldOutType": "available",
            "deliveryType": "ROCKET_SELLER",
            "discountRate": 20,
            "originalPrice": 109900,
            "thumbnail": "https://...",
            "productNotFound": false,
            "deliveryBadgeUrl": "https://..."
        }
    """
    if not product_data:
        return {'productNotFound': True}

    # 배송 타입 매핑
    delivery_type_map = {
        '로켓배송': 'ROCKET_DELIVERY',
        '로켓프레시': 'ROCKET_FRESH',
        '로켓직구': 'ROCKET_DIRECT',
        '판매자배송': 'ROCKET_SELLER'  # API에서는 ROCKET_SELLER로 표시
    }

    # 품절 상태
    sold_out = product_data.get('sold_out', False)
    if sold_out:
        sold_out_type = 'sold_out' if product_data.get('sold_out_type') == '품절' else 'temporary_out'
        sold_out_text = product_data.get('sold_out_type', '품절')
    else:
        sold_out_type = 'available'
        sold_out_text = None

    return {
        'price': product_data.get('price'),
        'title': product_data.get('title'),
        'soldOut': sold_out,
        'categories': product_data.get('categories', []),
        'soldOutText': sold_out_text,
        'soldOutType': sold_out_type,
        'deliveryType': delivery_type_map.get(
            product_data.get('delivery_type', '판매자배송'),
            'ROCKET_SELLER'
        ),
        'discountRate': product_data.get('discount_rate'),
        'originalPrice': product_data.get('original_price'),
        'salesPrice': product_data.get('sales_price'),  # 쿠팡판매가 (type: SALES)
        'salePrice': product_data.get('sale_price'),  # 판매가 (쿠폰 적용 전)
        'couponPrice': product_data.get('coupon_price'),  # 쿠폰 적용가 (최종가)
        'thumbnail': product_data.get('thumbnail'),
        'productNotFound': False,
        'deliveryBadgeUrl': product_data.get('delivery_badge_url'),
        'rating': product_data.get('rating'),
        'reviewCount': product_data.get('review_count')
    }
