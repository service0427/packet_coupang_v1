
import sys
import os
import json
sys.path.insert(0, os.path.join(os.getcwd(), 'lib'))

from api.rank_checker_direct import check_rank, _request
from curl_cffi import requests

# Verify that check_rank uses a session by overriding _request globally to check the arg
import api.rank_checker_direct

# We wrap the original _request to add logging
original_request = api.rank_checker_direct._request

def logging_request(url, session):
    print(f"\n[DEBUG] Requesting: {url}")
    print(f"[DEBUG] Session object: {session}")
    # Call original
    resp = original_request(url, session)
    
    print(f"[DEBUG] Status: {resp.status_code}")
    print("[DEBUG] Response Cookies:")
    for name, value in resp.cookies.items():
        print(f"  {name}: {value}")
        if name == '_abck':
            print(f"  -> _abck value analysis: {'~-1~' in value}")

    print("[DEBUG] Session Cookies so far:")
    for name, value in session.cookies.items():
        print(f"  {name}: {value}")
        
    return resp

# Apply the wrapper
api.rank_checker_direct._request = logging_request

# Test with a common keyword
keyword = "블루투스 이어폰"
print(f"Testing keyword: {keyword}")

# Dummy product ID
dummy_product_id = "9999999999" 

result = check_rank(keyword, dummy_product_id, max_page=2)
print("\nFinal Result Summary:")
print(json.dumps(result, ensure_ascii=False, indent=2))
