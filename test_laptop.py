import sys
import lib.api.rank_checker_direct as rank_checker

original_extract = rank_checker._extract_products

page_counter = 1
samples = {}
target_pages = {3, 5, 7, 14}

def patched_extract(rdata):
    global page_counter
    products = original_extract(rdata)
    
    if page_counter in target_pages and products:
        # Get the first product of the target page
        p = products[0]
        samples[page_counter] = {
            'page': page_counter,
            'productId': p.get('productId'),
            'itemId': p.get('itemId'),
            'vendorItemId': p.get('vendorItemId'),
            'title': p.get('title', '')
        }
    
    page_counter += 1
    return products

rank_checker._extract_products = patched_extract

keyword = "노트북"
product_id = "9999999999"  # Dummy ID to force all pages to be searched

print(f"[{keyword}] 키워드로 페이지 탐색 테스트 시작...")
result = rank_checker.check_rank(keyword=keyword, product_id=product_id, max_page=15)

print("\n--- 샘플 추출 결과 ---")
for page in sorted(target_pages):
    if page in samples:
        s = samples[page]
        title = s['title'][:40] + "..." if len(s['title']) > 40 else s['title']
        print(f"Page {page:2d}: [ProductID: {s['productId']}, ItemID: {s['itemId']}, VendorItemID: {s['vendorItemId']}] -> {title}")
    else:
        print(f"Page {page:2d}: 로드된 상품 없음")
