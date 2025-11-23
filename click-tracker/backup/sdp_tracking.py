#!/usr/bin/env python3
"""
상품 상세 페이지(SDP) 트래킹 모듈
- webBuildNo 동적 추출
- sdpVisitKey 생성
- SDP 진입 후 트래킹 이벤트
"""

import sys
import json
import uuid
import time
import re
import random
import string
from pathlib import Path
from datetime import datetime, timezone

# Add lib directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'lib'))

from curl_cffi import requests
from common import build_extra_fp

# 상수
LIBRARY_VERSION = '0.13.16'
DEFAULT_RESOLUTION = '1280x720'


def generate_sdp_visit_key():
    """sdpVisitKey 생성

    형식: 랜덤 영숫자 18자리 (예: 39m9vx97tjjhzwci4t)
    실제 브라우저에서 생성하는 패턴 기반
    """
    chars = string.ascii_lowercase + string.digits
    return ''.join(random.choice(chars) for _ in range(18))


def extract_web_build_no(html_content):
    """HTML에서 webBuildNo 추출

    쿠팡 페이지에서 webBuildNo는 여러 곳에 포함:
    1. window.__NEXT_DATA__ JSON
    2. 인라인 스크립트
    3. ljc 로깅 코드
    """
    if not html_content:
        return None

    # 패턴 1: __NEXT_DATA__에서 추출
    pattern1 = r'"webBuildNo"\s*:\s*"([a-f0-9]{40})"'
    match = re.search(pattern1, html_content)
    if match:
        return match.group(1)

    # 패턴 2: 인라인 스크립트에서 추출
    pattern2 = r'webBuildNo["\']?\s*[:=]\s*["\']([a-f0-9]{40})["\']'
    match = re.search(pattern2, html_content)
    if match:
        return match.group(1)

    # 패턴 3: Git commit hash 형식으로 검색
    pattern3 = r'["\']([a-f0-9]{40})["\']'
    matches = re.findall(pattern3, html_content)
    # 여러 개 있으면 가장 먼저 나온 것 사용
    if matches:
        return matches[0]

    return None


def extract_product_data(html_content):
    """HTML에서 상품 데이터 추출

    Returns:
        dict: productId, itemId, vendorItemId, price, title 등
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

    # 메타 태그에서 추출
    og_title = re.search(r'<meta property="og:title" content="([^"]+)"', html_content)
    if og_title:
        data['title'] = og_title.group(1)

    # 가격 추출 (다양한 패턴)
    price_pattern = r'"price"\s*:\s*(\d+)'
    price_match = re.search(price_pattern, html_content)
    if price_match and 'price' not in data:
        data['price'] = int(price_match.group(1))

    return data


def build_api_headers(fingerprint, referer=None, content_type=None):
    """API 요청용 헤더 생성"""
    major_version = fingerprint['chrome_major']

    # Chrome 버전별 sec-ch-ua
    sec_ch_ua_map = {
        136: '"Not/A)Brand";v="8", "Chromium";v="136"',
        137: '"Not/A)Brand";v="8", "Chromium";v="137"',
        138: '"Not)A;Brand";v="8", "Chromium";v="138"',
        139: '"Not)A;Brand";v="8", "Chromium";v="139"',
        140: '"Not/A)Brand";v="8", "Chromium";v="140"',
        141: '"Not/A)Brand";v="8", "Chromium";v="141"',
        142: '"Not/A)Brand";v="8", "Chromium";v="142"',
    }
    sec_ch_ua = sec_ch_ua_map.get(major_version, f'"Not)A;Brand";v="8", "Chromium";v="{major_version}"')

    headers = {
        'Accept': '*/*',
        'Accept-Encoding': 'gzip, deflate, br, zstd',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        'Connection': 'keep-alive',
        'Sec-Ch-Ua': sec_ch_ua,
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Linux"',
        'User-Agent': fingerprint['user_agent'],
    }

    if referer:
        headers['Referer'] = referer

    if content_type:
        headers['Content-Type'] = content_type

    return headers


def make_api_request(url, headers, cookies, fingerprint, proxy=None, method='GET', data=None):
    """curl-cffi API 요청"""
    ja3 = fingerprint['ja3_text']
    akamai = fingerprint['akamai_text']
    extra_fp = build_extra_fp(fingerprint)

    try:
        if method == 'POST':
            response = requests.post(
                url,
                headers=headers,
                cookies=cookies,
                data=data,
                ja3=ja3,
                akamai=akamai,
                extra_fp=extra_fp,
                proxy=proxy,
                timeout=30,
                allow_redirects=True,
                verify=False
            )
        else:
            response = requests.get(
                url,
                headers=headers,
                cookies=cookies,
                ja3=ja3,
                akamai=akamai,
                extra_fp=extra_fp,
                proxy=proxy,
                timeout=30,
                allow_redirects=True,
                verify=False
            )
        return response
    except Exception as e:
        print(f"    [ERROR] {str(e)[:100]}")
        return None


# ==================== SDP 트래킹 함수들 ====================

def send_sdp_pageview(cookies, fingerprint, proxy, page_url, product_info, pcid, pvid, web_build_no, sdp_visit_key, verbose=True):
    """SDP 페이지뷰 로그 (schemaId: 12734)

    상품 페이지 진입 시 전송
    """
    url = 'https://ljc.coupang.com/api/v2/submit?appCode=coupang&market=KR'

    headers = build_api_headers(fingerprint, 'https://www.coupang.com/', 'text/plain')
    headers['Sec-Fetch-Dest'] = 'empty'
    headers['Sec-Fetch-Mode'] = 'cors'
    headers['Sec-Fetch-Site'] = 'same-site'

    now = datetime.now(timezone.utc)
    event_time = now.strftime('%Y-%m-%dT%H:%M:%S.') + f'{now.microsecond // 1000:03d}Z'

    log_data = {
        "common": {
            "platform": "web",
            "pcid": pcid,
            "memberSrl": "",
            "libraryVersion": LIBRARY_VERSION,
            "lang": "ko-KR",
            "resolution": DEFAULT_RESOLUTION,
            "eventTime": event_time,
            "webBuildNo": web_build_no,
            "web": {
                "pvid": pvid,
                "rvid": "",
                "url": page_url,
                "referrer": ""
            }
        },
        "meta": {
            "schemaId": 12734,
            "schemaVersion": 1
        },
        "data": {
            "logCategory": "pageview",
            "logType": "pageview",
            "pageName": "sdp",
            "pageType": "sdp",
            "sdpVisitKey": sdp_visit_key,
            "productId": product_info.get('productId', ''),
            "itemId": product_info.get('itemId', ''),
            "vendorItemId": product_info.get('vendorItemId', '')
        }
    }

    data = json.dumps(log_data)

    if verbose:
        print(f"    📤 schemaId=12734, sdpVisitKey={sdp_visit_key[:10]}...")

    response = make_api_request(url, headers, cookies, fingerprint, proxy, 'POST', data)

    if response:
        result = {
            'success': response.status_code in [200, 204],
            'status': response.status_code,
            'response': response.text[:100]
        }
        if verbose:
            print(f"    📥 {result['status']}: {result['response']}")
        return result
    return {'success': False, 'error': 'Request failed'}


def send_sdp_impression(cookies, fingerprint, proxy, page_url, product_info, pcid, pvid, web_build_no, verbose=True):
    """SDP impression 로그 (schemaId: 238)

    상품 페이지에서 상품 노출
    """
    url = 'https://ljc.coupang.com/api/v2/submit?appCode=coupang&market=KR'

    headers = build_api_headers(fingerprint, 'https://www.coupang.com/', 'text/plain')
    headers['Sec-Fetch-Dest'] = 'empty'
    headers['Sec-Fetch-Mode'] = 'cors'
    headers['Sec-Fetch-Site'] = 'same-site'

    now = datetime.now(timezone.utc)
    event_time = now.strftime('%Y-%m-%dT%H:%M:%S.') + f'{now.microsecond // 1000:03d}Z'

    log_data = {
        "common": {
            "platform": "web",
            "pcid": pcid,
            "memberSrl": "",
            "libraryVersion": LIBRARY_VERSION,
            "lang": "ko-KR",
            "resolution": DEFAULT_RESOLUTION,
            "eventTime": event_time,
            "webBuildNo": web_build_no,
            "web": {
                "pvid": pvid,
                "rvid": "",
                "url": page_url,
                "referrer": ""
            }
        },
        "meta": {
            "schemaId": 238,
            "schemaVersion": 41
        },
        "data": {
            "domain": "sdp",
            "logCategory": "impression",
            "logType": "product",
            "productId": product_info.get('productId', ''),
            "itemId": product_info.get('itemId', ''),
            "vendorItemId": product_info.get('vendorItemId', ''),
            "price": product_info.get('price', 0)
        }
    }

    data = json.dumps(log_data)

    if verbose:
        print(f"    📤 schemaId=238, domain=sdp")

    response = make_api_request(url, headers, cookies, fingerprint, proxy, 'POST', data)

    if response:
        result = {
            'success': response.status_code in [200, 204],
            'status': response.status_code,
            'response': response.text[:100]
        }
        if verbose:
            print(f"    📥 {result['status']}: {result['response']}")
        return result
    return {'success': False, 'error': 'Request failed'}


def send_sdp_view_event(cookies, fingerprint, proxy, page_url, product_info, pcid, pvid, web_build_no, sdp_visit_key, verbose=True):
    """SDP view 이벤트 (schemaId: 124)

    상품 페이지 조회 이벤트
    """
    url = 'https://ljc.coupang.com/api/v2/submit?appCode=coupang&market=KR'

    headers = build_api_headers(fingerprint, 'https://www.coupang.com/', 'text/plain')
    headers['Sec-Fetch-Dest'] = 'empty'
    headers['Sec-Fetch-Mode'] = 'cors'
    headers['Sec-Fetch-Site'] = 'same-site'

    now = datetime.now(timezone.utc)
    event_time = now.strftime('%Y-%m-%dT%H:%M:%S.') + f'{now.microsecond // 1000:03d}Z'

    log_data = {
        "common": {
            "platform": "web",
            "pcid": pcid,
            "memberSrl": "",
            "libraryVersion": LIBRARY_VERSION,
            "lang": "ko-KR",
            "resolution": DEFAULT_RESOLUTION,
            "eventTime": event_time,
            "webBuildNo": web_build_no,
            "web": {
                "pvid": pvid,
                "rvid": "",
                "url": page_url,
                "referrer": ""
            }
        },
        "meta": {
            "schemaId": 124,
            "schemaVersion": 47
        },
        "data": {
            "logCategory": "event",
            "logType": "view",
            "targetType": "product",
            "productId": product_info.get('productId', ''),
            "itemId": product_info.get('itemId', ''),
            "vendorItemId": product_info.get('vendorItemId', ''),
            "sdpVisitKey": sdp_visit_key
        }
    }

    data = json.dumps(log_data)

    if verbose:
        print(f"    📤 schemaId=124, logType=view")

    response = make_api_request(url, headers, cookies, fingerprint, proxy, 'POST', data)

    if response:
        result = {
            'success': response.status_code in [200, 204],
            'status': response.status_code,
            'response': response.text[:100]
        }
        if verbose:
            print(f"    📥 {result['status']}: {result['response']}")
        return result
    return {'success': False, 'error': 'Request failed'}


def send_sdp_scroll_event(cookies, fingerprint, proxy, page_url, product_info, pcid, pvid, web_build_no, scroll_depth=50, verbose=True):
    """SDP 스크롤 이벤트 (schemaId: 116)

    상품 페이지 스크롤 (사용자 행동)
    """
    url = 'https://ljc.coupang.com/api/v2/submit?appCode=coupang&market=KR'

    headers = build_api_headers(fingerprint, 'https://www.coupang.com/', 'text/plain')
    headers['Sec-Fetch-Dest'] = 'empty'
    headers['Sec-Fetch-Mode'] = 'cors'
    headers['Sec-Fetch-Site'] = 'same-site'

    now = datetime.now(timezone.utc)
    event_time = now.strftime('%Y-%m-%dT%H:%M:%S.') + f'{now.microsecond // 1000:03d}Z'

    log_data = {
        "common": {
            "platform": "web",
            "pcid": pcid,
            "memberSrl": "",
            "libraryVersion": LIBRARY_VERSION,
            "lang": "ko-KR",
            "resolution": DEFAULT_RESOLUTION,
            "eventTime": event_time,
            "webBuildNo": web_build_no,
            "web": {
                "pvid": pvid,
                "rvid": "",
                "url": page_url,
                "referrer": ""
            }
        },
        "meta": {
            "schemaId": 116,
            "schemaVersion": 22
        },
        "data": {
            "domain": "sdp",
            "logCategory": "view",
            "logType": "scroll",
            "scrollDepth": scroll_depth,
            "productId": product_info.get('productId', '')
        }
    }

    data = json.dumps(log_data)

    if verbose:
        print(f"    📤 schemaId=116, scrollDepth={scroll_depth}")

    response = make_api_request(url, headers, cookies, fingerprint, proxy, 'POST', data)

    if response:
        result = {
            'success': response.status_code in [200, 204],
            'status': response.status_code,
            'response': response.text[:100]
        }
        if verbose:
            print(f"    📥 {result['status']}: {result['response']}")
        return result
    return {'success': False, 'error': 'Request failed'}


# ==================== 메인 함수 ====================

def sdp_tracking(page_url, html_content, cookies, fingerprint, product_info, pcid, pvid, proxy=None, verbose=True):
    """SDP(상품 상세 페이지) 트래킹 실행

    Args:
        page_url: 상품 페이지 URL
        html_content: 상품 페이지 HTML (webBuildNo 추출용)
        cookies: 쿠키 딕셔너리
        fingerprint: TLS 핑거프린트
        product_info: 상품 정보 (productId, itemId, vendorItemId)
        pcid: PC 식별자
        pvid: 페이지뷰 ID
        proxy: 프록시 URL
        verbose: 상세 출력

    Returns:
        dict: 각 트래킹 결과
    """
    results = {
        'sdp_pageview': None,
        'sdp_impression': None,
        'sdp_view_event': None,
        'sdp_scroll': None,
        'success': False
    }

    # webBuildNo 추출
    web_build_no = extract_web_build_no(html_content)
    if not web_build_no:
        # 기본값 사용 (최신 캡처에서 추출한 값)
        web_build_no = '71ac3d6293e865b896f120df45ac0233a502aac5'
        if verbose:
            print(f"  ⚠️ webBuildNo 추출 실패, 기본값 사용")
    else:
        if verbose:
            print(f"  📦 webBuildNo: {web_build_no[:16]}...")

    # sdpVisitKey 생성
    sdp_visit_key = generate_sdp_visit_key()
    if verbose:
        print(f"  🔑 sdpVisitKey: {sdp_visit_key}")

    # HTML에서 추가 상품 정보 추출
    extracted_data = extract_product_data(html_content)
    for key, value in extracted_data.items():
        if key not in product_info:
            product_info[key] = value

    # 1. 페이지뷰 로그
    if verbose:
        print("\n  [SDP 1/4] pageview...")
    result = send_sdp_pageview(cookies, fingerprint, proxy, page_url, product_info, pcid, pvid, web_build_no, sdp_visit_key, verbose)
    results['sdp_pageview'] = result

    time.sleep(0.05)

    # 2. impression 로그
    if verbose:
        print("\n  [SDP 2/4] impression...")
    result = send_sdp_impression(cookies, fingerprint, proxy, page_url, product_info, pcid, pvid, web_build_no, verbose)
    results['sdp_impression'] = result

    time.sleep(0.1)

    # 3. view 이벤트
    if verbose:
        print("\n  [SDP 3/4] view event...")
    result = send_sdp_view_event(cookies, fingerprint, proxy, page_url, product_info, pcid, pvid, web_build_no, sdp_visit_key, verbose)
    results['sdp_view_event'] = result

    time.sleep(0.3)

    # 4. 스크롤 이벤트 (50%, 75%)
    if verbose:
        print("\n  [SDP 4/4] scroll events...")
    result = send_sdp_scroll_event(cookies, fingerprint, proxy, page_url, product_info, pcid, pvid, web_build_no, 50, verbose)
    results['sdp_scroll'] = result

    time.sleep(0.2)
    send_sdp_scroll_event(cookies, fingerprint, proxy, page_url, product_info, pcid, pvid, web_build_no, 75, False)

    # 결과 요약
    success_count = sum(1 for k, v in results.items() if k != 'success' and v and v.get('success'))
    results['success'] = success_count >= 3

    if verbose:
        print(f"\n  📊 SDP 트래킹: {success_count}/4 성공")

    return results


if __name__ == '__main__':
    # 테스트
    print("SDP Tracking Module")
    print("=" * 50)

    # sdpVisitKey 생성 테스트
    key = generate_sdp_visit_key()
    print(f"Generated sdpVisitKey: {key}")

    # webBuildNo 추출 테스트
    test_html = '''
    <script id="__NEXT_DATA__">{"props":{"webBuildNo":"abc123def456789012345678901234567890abcd"}}</script>
    '''
    build_no = extract_web_build_no(test_html)
    print(f"Extracted webBuildNo: {build_no}")
