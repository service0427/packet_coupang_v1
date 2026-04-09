#!/usr/bin/env python3
"""INCOMPLETE 수정 검증: 내셔널지오그래픽바람막이 키워드로 테스트"""

import sys, os, json, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib'))

from api.rank_checker_direct import check_rank

keyword = "내셔널지오그래픽바람막이"
product_id = "8701273297"
item_id = "25268057490"
vendor_item_id = "92263814664"

print(f"키워드: {keyword}")
print(f"P:{product_id} I:{item_id} V:{vendor_item_id}")
print("=" * 60)

start = time.time()
result = check_rank(keyword, product_id, item_id, vendor_item_id, max_page=15)
elapsed = time.time() - start

print(json.dumps(result, ensure_ascii=False, indent=2))
print(f"\n소요: {elapsed:.1f}s")

# 핵심 체크
if result['success'] and not result['found']:
    print("✅ 정상 미발견 (INCOMPLETE 아님!)")
elif result['success'] and result['found']:
    print(f"✅ 발견: {result['rank']}위")
else:
    print(f"❌ 실패: {result.get('error_code')} - {result.get('error_message')}")
