import json
import lib.api.rank_checker_direct as rank_checker

original_extract = rank_checker._extract_products

page_counter = 1
def patched_extract(rdata):
    global page_counter
    products = original_extract(rdata)
    print(f"\n=== [Page {page_counter}] 상품 {len(products)}개 로드됨 ===")
    
    page_counter += 1
    return products

# 디버깅을 위해 함수 바꿔치기 (Monkeypatch)
rank_checker._extract_products = patched_extract

keyword = "무선청소기"
product_id = "9999999999"

print(f"[{keyword}] 키워드로 가능한 모든 페이지(최대 50장) 리스트업 테스트 시작...")

# 넉넉하게 50페이지까지 탐색 시도
result = rank_checker.check_rank(keyword=keyword, product_id=product_id, max_page=50)

print("\n\n--- 최종 검색 결과 (Summary) ---")
print(json.dumps(result, indent=2, ensure_ascii=False))
