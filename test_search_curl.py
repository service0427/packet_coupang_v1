
from curl_cffi import requests
from urllib.parse import quote

# Target: Coupang Search "notebook"
KEYWORD = "notebook"
ENCODED_KEYWORD = quote(KEYWORD)
URL = f"https://www.coupang.com/np/search?component=&q={ENCODED_KEYWORD}&channel=user"

# Headers from HAR (Minimal but necessary)
HEADERS = {
    'authority': 'www.coupang.com',
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'accept-language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
    'cache-control': 'max-age=0',
    'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'document',
    'sec-fetch-mode': 'navigate',
    'sec-fetch-site': 'none',
    'sec-fetch-user': '?1',
    'upgrade-insecure-requests': '1',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

print(f"Testing Search URL: {URL}")

try:
    # Use impersonate to mimic Chrome browser TLS fingerprint
    response = requests.get(
        URL,
        headers=HEADERS,
        impersonate="chrome120",
        allow_redirects=True,
        timeout=15
    )

    print(f"Status Code: {response.status_code}")
    print(f"Response URL: {response.url}")
    
    # Check for Akamai block or valid content
    if response.status_code == 200:
        if "Access Denied" in response.text or "Akamai" in response.text:
             print("FAILURE: Blocked by Akamai (Access Denied/Challenge).")
        elif "product-list" in response.text or "search-product" in response.text:
             print("SUCCESS: Search results found!")
             # Extract some product titles to be sure
             import re
             titles = re.findall(r'class="name">([^<]+)', response.text)
             if titles:
                 print(f"Found {len(titles)} products. First 3:")
                 for t in titles[:3]:
                     print(f" - {t.strip()}")
        else:
             print("WARNING: 200 OK but unknown content structure.")
             print(response.text[:500])
    
    elif response.status_code == 403:
        print("FAILURE: 403 Forbidden (Likely Akamai Block)")
    else:
        print(f"FAILURE: Unexpected status {response.status_code}")

except Exception as e:
    print(f"Error: {e}")
