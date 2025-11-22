"""
Product Extractor (Python)
- Coupang search result page product extraction
- Ranking products vs ads separation
- 3-part unique key (product_id + item_id + vendor_item_id)
"""

import re
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs


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

            if product_card:
                name_el = (product_card.select_one('.name') or
                          product_card.select_one('[class*="name"]') or
                          link)
                price_el = (product_card.select_one('.price-value') or
                           product_card.select_one('[class*="price"]'))

            product_data = {
                'productId': product_id,
                'itemId': item_id,
                'vendorItemId': vendor_item_id,
                'uniqueKey': unique_key,
                'name': name_el.get_text(strip=True) if name_el else '',
                'price': price_el.get_text(strip=True) if price_el else '',
                'url': href,
                'rank': rank
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
