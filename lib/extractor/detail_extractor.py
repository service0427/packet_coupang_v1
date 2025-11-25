"""
상품 상세 정보 추출기
- 상품 페이지 HTML에서 상세 정보 파싱
- 가격, 할인율, 평점, 리뷰, 판매자 등 추출
"""

import re
import json


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

    # __NEXT_DATA__에서 추출 시도
    next_data_match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.+?)</script>', html_content, re.DOTALL)
    if next_data_match:
        try:
            next_data = json.loads(next_data_match.group(1))
            props = next_data.get('props', {}).get('pageProps', {})

            # productId, itemId, vendorItemId
            if 'productId' in props:
                data['productId'] = str(props['productId'])
            if 'itemId' in props:
                data['itemId'] = str(props['itemId'])
            if 'vendorItemId' in props:
                data['vendorItemId'] = str(props['vendorItemId'])

            # 가격 정보
            if 'price' in props:
                data['price'] = props['price']

        except json.JSONDecodeError:
            pass

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

    # === 원가 (할인 전 가격) ===
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
    # 로켓배송, 로켓프레시, 로켓직구, 판매자배송 등
    if 'rocket_icon' in html_content or 'RocketDelivery' in html_content:
        if 'rocket-fresh' in html_content.lower() or 'rocketfresh' in html_content.lower():
            data['delivery_type'] = '로켓프레시'
        elif 'rocket-global' in html_content.lower() or 'rocketglobal' in html_content.lower():
            data['delivery_type'] = '로켓직구'
        else:
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
    categories = []
    breadcrumb_matches = re.findall(r'<a[^>]*class="[^"]*breadcrumb[^"]*"[^>]*>([^<]+)</a>', html_content)
    if breadcrumb_matches:
        categories = [c.strip() for c in breadcrumb_matches if c.strip()]
        data['categories'] = categories

    # === 썸네일 이미지 ===
    # prod-image__items 영역의 이미지들
    thumbnail_matches = re.findall(r'<img[^>]*class="[^"]*prod-image__item[^"]*"[^>]*src="([^"]+)"', html_content)
    if thumbnail_matches:
        data['thumbnail_images'] = thumbnail_matches
    else:
        # 대안: og:image
        og_image = re.search(r'<meta property="og:image" content="([^"]+)"', html_content)
        if og_image:
            data['thumbnail_images'] = [og_image.group(1)]

    # === 배송 뱃지 URL ===
    # 로켓배송 아이콘 이미지
    badge_match = re.search(r'<img[^>]*class="[^"]*delivery-badge[^"]*"[^>]*src="([^"]+)"', html_content)
    if badge_match:
        data['delivery_badge_url'] = badge_match.group(1)
    else:
        # 대안: rocket-icon 클래스 이미지
        rocket_badge = re.search(r'<img[^>]*class="[^"]*rocket[^"]*"[^>]*src="([^"]+)"', html_content)
        if rocket_badge:
            data['delivery_badge_url'] = rocket_badge.group(1)

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
        'thumbnailImages': product_data.get('thumbnail_images', []),
        # ID 추출 우선순위:
        # 1. product_info (URL에서 파싱된 값) - rank_cmd에서 전달
        # 2. product_data (HTML __NEXT_DATA__에서 추출)
        # 3. None
        'productId': product_info.get('productId') or product_data.get('productId'),
        'itemId': product_info.get('itemId') or product_data.get('itemId'),
        'vendorItemId': product_info.get('vendorItemId') or product_data.get('vendorItemId'),
    }
