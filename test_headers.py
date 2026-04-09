"""
실제 앱 캡쳐 헤더 기반 테스트 스크립트
캡쳐 파일: 최신 캡쳐 (2026-03-27)
기존 TLS 설정은 그대로 유지, 헤더만 캡쳐 기준으로 확장
"""
import json
import time
from urllib.parse import quote
from curl_cffi import requests

# ─── 기존 TLS 핑거프린트 (변경 없음) ───
TLS_CONFIG = {
    "ja3": "771,4865-4866-4867-49195-49199-49196-49200-52393-52392-49171-49172-156-157-47-53,16-10-43-51-17613-5-65281-35-11-0-65037-18-23-45-13-27,4588-29-23-24,0",
    "akamai": "1:65536;2:0;4:6291456;6:262144|15663105|0|m,a,s,p",
    "extra_fp": {
        "tls_signature_algorithms": [
            "ecdsa_secp256r1_sha256",
            "rsa_pss_rsae_sha256",
            "rsa_pkcs1_sha256",
            "ecdsa_secp384r1_sha384",
            "rsa_pss_rsae_sha384",
            "rsa_pkcs1_sha384",
            "rsa_pss_rsae_sha512",
            "rsa_pkcs1_sha512",
        ],
        "tls_grease": True,
        "tls_permute_extensions": True,
    }
}

BASE_URL = "https://cmapi.coupang.com"

# ─── 테스트 1: 기존 최소 헤더 (현재 코드와 동일) ───
HEADERS_MINIMAL = {
    'coupang-app': 'COUPANG|Android|15|9.1.0',
    'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 15; SM-A165N Build/AP3A.240905.015.A2)',
}

# ─── 테스트 2: 캡쳐 기반 확장 헤더 (앱 버전 9.1.4, 2026-03-27 캡쳐) ───
HEADERS_FULL = {
    'x-timestamp': str(int(time.time() * 1000)),
    'coupang-app': 'COUPANG|Android|15|9.1.4||d1UpcX9_ScyKmtWWwfCy8s:APA91bHX0MJug9nUTQ0ubad_fdfTneNrMESXGKzHJiTrb2Aw913w_O_g7tKOo11ARvGAmf-zg02B7REsB46UaQuz9OY5rScV_bz09jT9XP8sdgsQfiNWEuY|f0b740d2-3447-3b2b-b118-d66257275f8f|Y|SM-A165N|f0b740d234472b2bb118d66257275f8f|14ff2a58-b085-4b73-9111-1c3986fe257b|XXHDPI|17721648653230756715148||0||4g|-1|||Asia/Seoul|00e172a610d74badaaa1d044fa4d9d891cca8ca1||1080|450|3|1.0|true',
    'x-coupang-font-scale': '1.0',
    'run-mode': 'production',
    'x-coupang-app-request': 'true',
    'baggage': 'enable-upstream-tti-info=true',
    'x-cp-app-req-time': str(int(time.time() * 1000)),
    'x-view-name': '/search',
    'x-coupang-target-market': 'KR',
    'x-coupang-app-name': 'coupang',
    'x-cp-app-id': 'com.coupang.mobile',
    'x-cmg-dco': '1774420234000',
    'x-coupang-origin-region': 'KR',
    'x-coupang-accept-language': 'ko-KR',
    'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 15; SM-A165N Build/AP3A.240905.015.A2)',
    'accept-encoding': 'gzip',
}

def _request(url, session, headers):
    return session.get(
        url,
        headers=headers,
        ja3=TLS_CONFIG["ja3"],
        akamai=TLS_CONFIG["akamai"],
        extra_fp=TLS_CONFIG["extra_fp"],
        timeout=15,
    )

keyword = "노트북"
params = f"filter=KEYWORD:{quote(keyword)}|CCID:ALL|EXTRAS:channel/user|GET_FILTER:NONE|SINGLE_ENTITY:TRUE@SEARCH&preventingRedirection=false&resultType=default&ccidActivated=false&referrerPage=HOME"
url = f"{BASE_URL}/v3/products?{params}"

session = requests.Session()

# ─── TEST 1: 최소 헤더 (기존 코드) ───
print("=" * 60)
print("TEST 1: 기존 최소 헤더 (coupang-app 9.1.0 + UA만)")
print("=" * 60)
try:
    resp = _request(url, session, HEADERS_MINIMAL)
    print(f"  Status: {resp.status_code}")
    body = resp.json()
    print(f"  rCode: {body.get('rCode')}")
    print(f"  rMessage: {body.get('rMessage')}")
    if body.get('rCode') == 'RET0000':
        rdata = body.get('rData', {})
        print(f"  totalCount: {rdata.get('totalCount')}")
        print(f"  entityList 수: {len(rdata.get('entityList', []))}")
except Exception as e:
    print(f"  ❌ Exception: {e}")

print()

# ─── TEST 2: 캡쳐 기반 확장 헤더 ───
print("=" * 60)
print("TEST 2: 캡쳐 기반 확장 헤더 (coupang-app 9.1.4 + 추가 헤더)")
print("=" * 60)
# 캡쳐 기반 헤더에서 x-signature, x-cp-s 제외 (동적 생성 필요)
try:
    resp = _request(url, session, HEADERS_FULL)
    print(f"  Status: {resp.status_code}")
    body = resp.json()
    print(f"  rCode: {body.get('rCode')}")
    print(f"  rMessage: {body.get('rMessage')}")
    if body.get('rCode') == 'RET0000':
        rdata = body.get('rData', {})
        print(f"  totalCount: {rdata.get('totalCount')}")
        print(f"  entityList 수: {len(rdata.get('entityList', []))}")
except Exception as e:
    print(f"  ❌ Exception: {e}")

print()

# ─── TEST 3: 캡쳐 기반 + x-signature/x-cp-s 포함 (원본 그대로) ───
print("=" * 60)
print("TEST 3: 캡쳐 원본 그대로 (x-signature + x-cp-s 포함)")
print("=" * 60)
HEADERS_RAW = dict(HEADERS_FULL)
HEADERS_RAW['x-signature'] = '3a443e093e66cfd934de2a0992b780388376be469773da07eff1bb47f393bf29'
HEADERS_RAW['x-cp-s'] = 'YzE9MSZjMj0xLjAuMCZjMz0xNzc0NTM2NjEyMjIyJmM0PUNlcEhQZHJOTk9SNisxSXJsUm9SNk92eFA5YnBlSFNGQUd6bStCa3lXdEpUQ0xjWHZvNnpuTEdPbDV4bURwd2doc2g5bzIxR2Y4M2Vwd1ZyQWNvTzhRM0J2ZTFxYVhJMzVvTXR3Y0hmQXhaajQyRnRIYXkrTzN6aEoraTFVZEJLbHRORG1sdlg2YzhpOTZxdy9nYW8vVlFNOGdWZ1NKTVc5eFNqQlpkKzFFdzFqSVc1cFFJMVhUYTBVTXVRVXRXSytYclRzbzIwZEp4Um5PUmpuVVZUcnZMWk4yNzJ0eDA9JmM1PWNvbS5jb3VwYW5nLm1vYmlsZSZjNj05LjEuNCZjNz1NRmt3RXdZSEtvWkl6ajBDQVFZSUtvWkl6ajBEQVFjRFFnQUVtRkdnQTB5bEMzdkJraVB5T2tCSVNiUFJCVmNhRDdzbFRRY0RiemtYMk0zd1NaenduMTNYVnYrbEp1U3QzWmRRSXhYQVJKU2Nua1h0Z1dQL2lBY1p2Zz09JmM4PTc3MGJhOWJiYzgzNDQwMWVhNTA3YWRhYWE5YmMzNDk5JmM5PTYzJnMxPUlEWWE1RzVjanNKSXZ4QVVUaEUxZC8vbGVMd0oyNFJkYkRDVTV1UDYrSkE9JnMyPTEuMC4w'
HEADERS_RAW['x-cmg-dco'] = '1774420234000'
HEADERS_RAW['x-trace-ix-id'] = '0000143d-c2f1-7d83-0bae-0c3eb68d0a07'
try:
    resp = _request(url, session, HEADERS_RAW)
    print(f"  Status: {resp.status_code}")
    body = resp.json()
    print(f"  rCode: {body.get('rCode')}")
    print(f"  rMessage: {body.get('rMessage')}")
    if body.get('rCode') == 'RET0000':
        rdata = body.get('rData', {})
        print(f"  totalCount: {rdata.get('totalCount')}")
        print(f"  entityList 수: {len(rdata.get('entityList', []))}")
except Exception as e:
    print(f"  ❌ Exception: {e}")

print("\n완료!")
