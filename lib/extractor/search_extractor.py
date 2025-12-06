"""
Product Extractor (Python)
- Coupang search result page product extraction
- Ranking products vs ads separation
- 3-part unique key (product_id + item_id + vendor_item_id)
- LJC 이벤트용 메타 정보 추출 (searchId, buildId 등)
"""

import re
import json
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs


# ============================================================================
# LJC 이벤트용 추출 함수
# ============================================================================

def extract_search_meta(html):
    """검색 HTML에서 메타 정보 추출

    모바일(m.coupang.com)과 PC(www.coupang.com) HTML 구조가 다름:
    - 모바일: URL 파라미터에서 searchId 추출, __NEXT_DATA__ 없음
    - PC: JSON 형식으로 searchId, __NEXT_DATA__에서 buildId 추출

    Args:
        html: 검색 페이지 HTML

    Returns:
        dict: {searchId, totalProductCount, buildId, listSize}
    """
    result = {
        'searchId': '',
        'totalProductCount': 0,
        'buildId': '',
        'listSize': 36
    }

    # searchId 추출 (URL 파라미터 형식 우선 - 모바일)
    match = re.search(r'searchId=([^&"\s<>]+)', html)
    if match:
        result['searchId'] = match.group(1)
    else:
        # PC 형식 (JSON)
        match = re.search(r'"searchId"\s*:\s*"([^"]+)"', html)
        if match:
            result['searchId'] = match.group(1)

    # itemsCount 추출 (listSize 용도)
    match = re.search(r'itemsCount[":=]+(\d+)', html)
    if match:
        result['listSize'] = int(match.group(1))

    # totalProductCount 추출 (PC)
    match = re.search(r'"totalProductCount"\s*:\s*(\d+)', html)
    if match:
        result['totalProductCount'] = int(match.group(1))
    else:
        # 모바일: totalProductCount 없음 - 상품 링크 개수로 추정
        product_links = re.findall(r'/vp/products/\d+', html)
        if product_links:
            unique_products = len(set(product_links))
            result['totalProductCount'] = unique_products

    # __NEXT_DATA__에서 buildId 추출 (PC)
    match = re.search(r'<script id="__NEXT_DATA__"[^>]*>([^<]+)</script>', html)
    if match:
        try:
            next_data = json.loads(match.group(1))
            result['buildId'] = next_data.get('buildId', '')

            props = next_data.get('props', {})
            page_props = props.get('pageProps', {})
            if 'listSize' in page_props:
                result['listSize'] = page_props['listSize']
        except (json.JSONDecodeError, KeyError):
            pass

    return result


def extract_products_from_html(html):
    """HTML에서 상품 목록 추출 (ProductExtractor.extract_products_from_html과 동일)

    Args:
        html: 검색 페이지 HTML

    Returns:
        dict: {ranking: [...], ads: [...], total: int}
    """
    return ProductExtractor.extract_products_from_html(html)


def find_product_by_id(products, target_product_id):
    """상품 목록에서 타겟 상품 찾기

    Args:
        products: 상품 목록 (ranking 리스트)
        target_product_id: 찾을 상품 ID

    Returns:
        dict or None: 찾은 상품 정보
    """
    target_id = str(target_product_id)

    for product in products:
        if str(product['productId']) == target_id:
            return product

    return None


def extract_filter_key(url):
    """URL에서 filterKey 추출

    Args:
        url: 검색 URL

    Returns:
        str: 쿼리스트링 (filterKey)
    """
    parsed = urlparse(url)
    return parsed.query


# ============================================================================
# 기존 ProductExtractor 클래스
# ============================================================================


class ProductExtractor:
    """Extract product information from Coupang HTML"""

    @staticmethod
    def extract_products_from_html(html):
        """
        Extract products from HTML content

        Args:
            html: HTML string from Coupang search page

        Returns:
            dict with ranking, ads, total counts
        """
        soup = BeautifulSoup(html, 'html.parser')

        # Find product list container
        product_list = soup.select_one('#productList, #product-list')
        if not product_list:
            return {'ranking': [], 'ads': [], 'total': 0}

        # Find all product links
        links = product_list.select('a[href*="/products/"]')

        ranking_products = {}
        ad_products = {}

        for link in links:
            href = link.get('href', '')

            # Only /vp/products/ format
            if '/vp/products/' not in href:
                continue

            # Extract product_id
            product_id_match = re.search(r'/vp/products/(\d+)', href)
            if not product_id_match:
                continue

            product_id = product_id_match.group(1)

            # Parse URL parameters
            parsed = urlparse(href)
            params = parse_qs(parsed.query)

            item_id = params.get('itemId', [''])[0]
            vendor_item_id = params.get('vendorItemId', [''])[0]

            # Unique key: product_id + item_id + vendor_item_id
            unique_key = f"{product_id}_{item_id}_{vendor_item_id}"

            # Check rank parameter
            has_rank = 'rank' in params
            rank = None

            if has_rank:
                try:
                    rank = int(params['rank'][0])
                except (ValueError, IndexError):
                    pass

            # Check AdMark class
            product_card = link.find_parent('li') or link.find_parent('div')
            has_ad_mark = False

            if product_card:
                ad_mark = product_card.select('[class*="AdMark"]')
                has_ad_mark = len(ad_mark) > 0

            # Extract name and price
            name_el = None
            price_el = None
            rating = None
            review_count = None

            if product_card:
                name_el = (product_card.select_one('.name') or
                          product_card.select_one('[class*="name"]') or
                          link)
                price_el = (product_card.select_one('.price-value') or
                           product_card.select_one('[class*="price"]'))

                # Extract rating (평점)
                rating_el = product_card.select_one('.rating, [class*="rating"]')
                if rating_el:
                    rating_text = rating_el.get_text(strip=True)
                    rating_match = re.search(r'(\d+\.?\d*)', rating_text)
                    if rating_match:
                        rating = float(rating_match.group(1))

                # Extract review count (리뷰 수)
                review_el = product_card.select_one('.rating-total-count, [class*="count"]')
                if review_el:
                    review_text = review_el.get_text(strip=True)
                    # (1,234) 또는 1234 형식
                    review_match = re.search(r'\(?([\d,]+)\)?', review_text)
                    if review_match:
                        review_count = int(review_match.group(1).replace(',', ''))

            product_data = {
                'productId': product_id,
                'itemId': item_id,
                'vendorItemId': vendor_item_id,
                'uniqueKey': unique_key,
                'name': name_el.get_text(strip=True) if name_el else '',
                'price': price_el.get_text(strip=True) if price_el else '',
                'url': href,
                'rank': rank,
                'rating': rating,
                'review_count': review_count
            }

            # Pure ranking products (has rank, no ad mark)
            if has_rank and rank is not None and not has_ad_mark:
                if unique_key not in ranking_products:
                    ranking_products[unique_key] = product_data
            else:
                if unique_key not in ad_products:
                    ad_products[unique_key] = product_data

        return {
            'ranking': list(ranking_products.values()),
            'ads': list(ad_products.values()),
            'total': len(ranking_products) + len(ad_products)
        }

    @staticmethod
    def check_duplicates(results):
        """
        Check for duplicate products across multiple pages

        Args:
            results: List of result dicts with rankingProducts

        Returns:
            dict with duplicate statistics
        """
        all_product_keys = []
        page_products = {}
        product_details = {}

        for result in results:
            if result.get('success') and result.get('rankingProducts'):
                page_num = result['page']
                product_keys = [p['uniqueKey'] for p in result['rankingProducts']]
                all_product_keys.extend(product_keys)
                page_products[page_num] = set(product_keys)

                for p in result['rankingProducts']:
                    key = p['uniqueKey']
                    if key not in product_details:
                        product_details[key] = []

                    product_details[key].append({
                        'page': page_num,
                        'url': p['url'],
                        'name': p['name'],
                        'rank': p['rank']
                    })

        total_products = len(all_product_keys)
        unique_products = len(set(all_product_keys))
        duplicate_count = total_products - unique_products

        return {
            'total': total_products,
            'unique': unique_products,
            'duplicates': duplicate_count,
            'duplicate_rate': (duplicate_count / total_products * 100) if total_products > 0 else 0,
            'pageProducts': page_products,
            'productDetails': product_details
        }

    @staticmethod
    def print_duplicates(duplicate_stats):
        """Print duplicate statistics"""
        print("\n" + "="*80)
        print("[DUPLICATE CHECK - RANKING PRODUCTS (product_id + item_id + vendor_item_id)]")
        print("="*80)

        print(f"Total Ranking Products: {duplicate_stats['total']}")
        print(f"Unique Products: {duplicate_stats['unique']}")
        print(f"Duplicates: {duplicate_stats['duplicates']}")

        if duplicate_stats['duplicates'] > 0:
            print(f"\n[WARNING] {duplicate_stats['duplicates']}개 중복 상품 발견!")

            # Count occurrences
            product_counter = {}
            for page_products in duplicate_stats['pageProducts'].values():
                for key in page_products:
                    product_counter[key] = product_counter.get(key, 0) + 1

            # Find duplicates
            duplicates = [(key, count) for key, count in product_counter.items() if count > 1]

            print("\n[DUPLICATE PRODUCTS WITH FULL URLS]:")
            for key, count in duplicates:
                print(f"\n  Key {key}: {count}번 등장")

                # Find pages with this duplicate
                pages_with_duplicate = []
                for page_num, product_set in duplicate_stats['pageProducts'].items():
                    if key in product_set:
                        pages_with_duplicate.append(page_num)

                print(f"    Pages: {', '.join(map(str, pages_with_duplicate))}")

                # Print details
                details = duplicate_stats['productDetails'].get(key, [])
                for detail in details:
                    print(f"    Page {detail['page']}:")
                    print(f"      URL: {detail['url']}")
                    print(f"      Name: {detail['name'][:50]}...")
                    print(f"      Rank: {detail['rank']}")
        else:
            print("\n[OK] 중복 없음! 모든 상품이 고유합니다.")

        return duplicate_stats
