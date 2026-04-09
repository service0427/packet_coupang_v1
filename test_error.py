import json
import traceback
import lib.api.rank_checker_direct as rank_checker

keyword = "1인용접이식책상"
product_id = "9999999999"

print(f"[{keyword}] 키워드로 직접 연결 테스트 (에러 상세 확인용)")

try:
    result = rank_checker.check_rank(keyword=keyword, product_id=product_id, max_page=2)
    print("\n--- 결과 ---")
    print(json.dumps(result, indent=2, ensure_ascii=False))
except Exception as e:
    print("\n--- 💥 예상치 못한 치명적 에러 발생! ---")
    traceback.print_exc()
