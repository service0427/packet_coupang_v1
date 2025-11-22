#!/usr/bin/env python3
"""
실제 브라우저 트래픽을 100% 재현하는 클릭 시뮬레이터
브라우저 모니터링에서 캡처한 모든 API 호출을 순차적으로 수행
"""

import sys
import json
import uuid
import time
import re
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import quote, urlparse, parse_qs

# Add lib directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'lib'))

# 기존 common 모듈 활용
from common import (
    get_cookie_by_id, get_latest_cookie, get_fingerprint,
    parse_cookies, build_extra_fp, check_proxy_ip, verify_ip_binding
)
from curl_cffi import requests
from sdp_tracking import sdp_tracking, extract_web_build_no, generate_sdp_visit_key

BASE_DIR = Path(__file__).parent.parent

# 상수
WEB_BUILD_NO = '71ac3d6293e865b896f120df45ac0233a502aac5'
LIBRARY_VERSION = '0.13.16'
DEFAULT_RESOLUTION = '1280x720'  # 실제 브라우저 캡처와 동일


def get_sec_ch_ua(chrome_major):
    """Chrome 버전별 sec-ch-ua 헤더 생성

    실제 브라우저 캡처: "Not)A;Brand";v="8", "Chromium";v="138"
    Chrome 버전마다 Brand 이름과 버전이 다름
    """
    # Chrome 버전별 sec-ch-ua 매핑 (실제 브라우저에서 수집)
    sec_ch_ua_map = {
        136: '"Not/A)Brand";v="8", "Chromium";v="136"',
        137: '"Not/A)Brand";v="8", "Chromium";v="137"',
        138: '"Not)A;Brand";v="8", "Chromium";v="138"',
        139: '"Not)A;Brand";v="8", "Chromium";v="139"',
        140: '"Not/A)Brand";v="8", "Chromium";v="140"',
        141: '"Not/A)Brand";v="8", "Chromium";v="141"',
        142: '"Not/A)Brand";v="8", "Chromium";v="142"',
    }
    return sec_ch_ua_map.get(chrome_major, f'"Not)A;Brand";v="8", "Chromium";v="{chrome_major}"')


def get_pcid(cookies):
    """쿠키에서 PCID 추출"""
    return cookies.get('PCID', str(int(time.time() * 1000)) + str(uuid.uuid4().int)[:10])


def generate_pvid():
    """Page View ID 생성"""
    return str(uuid.uuid4())


def get_search_id_from_url(url):
    """URL에서 searchId 추출"""
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    return params.get('searchId', [''])[0]


def build_api_headers(fingerprint, referer=None, content_type=None):
    """API 요청용 헤더 생성"""
    major_version = fingerprint['chrome_major']

    headers = {
        'Accept': '*/*',
        'Accept-Encoding': 'gzip, deflate, br, zstd',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        'Connection': 'keep-alive',
        'Sec-Ch-Ua': get_sec_ch_ua(major_version),
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Linux"',
        'User-Agent': fingerprint['user_agent'],
    }

    if referer:
        headers['Referer'] = referer

    if content_type:
        headers['Content-Type'] = content_type

    return headers


def build_document_headers(fingerprint, referer=None):
    """Document 요청용 헤더 생성"""
    major_version = fingerprint['chrome_major']

    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'ko-KR,ko;q=0.9',
        'Cache-Control': 'max-age=0',
        'Connection': 'keep-alive',
        'Sec-Ch-Ua': get_sec_ch_ua(major_version),
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Linux"',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-User': '?1',
        'Upgrade-Insecure-Requests': '1',
        'User-Agent': fingerprint['user_agent'],
    }

    if referer:
        headers['Referer'] = referer

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


# ==================== API 요청 함수들 ====================

def send_reliability_event(cookies, fingerprint, proxy, referer, verbose=True):
    """n-api/reliability - 검색→상품 전환 이벤트"""
    url = 'https://www.coupang.com/n-api/reliability'

    headers = build_api_headers(fingerprint, referer, 'application/json')
    headers['Accept'] = 'application/json'
    headers['Sec-Fetch-Dest'] = 'empty'
    headers['Sec-Fetch-Mode'] = 'cors'
    headers['Sec-Fetch-Site'] = 'same-origin'

    data = json.dumps({"conversion": {"event": "srp_to_sdp"}})

    if verbose:
        print(f"    📤 Body: {data}")

    response = make_api_request(url, headers, cookies, fingerprint, proxy, 'POST', data)

    if response:
        result = {
            'success': response.status_code in [200, 204],
            'status': response.status_code,
            'size': len(response.content),
            'response': response.text[:200]
        }
        if verbose:
            print(f"    📥 {result['status']}: {result['response']}")
        return result
    return {'success': False, 'error': 'Request failed'}


def send_ljc_event_log(cookies, fingerprint, proxy, search_url, product_info, pcid, pvid, verbose=True):
    """ljc schemaId: 124 - event 로그"""
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
            "webBuildNo": WEB_BUILD_NO,
            "web": {
                "pvid": pvid,
                "rvid": "",
                "url": search_url,
                "referrer": ""
            }
        },
        "meta": {
            "schemaId": 124,
            "schemaVersion": 47
        },
        "data": {
            "logCategory": "event",
            "logType": "click",
            "targetType": "product",
            "productId": product_info.get('productId', ''),
            "itemId": product_info.get('itemId', ''),
            "vendorItemId": product_info.get('vendorItemId', ''),
            "rank": product_info.get('rank', 1)
        }
    }

    data = json.dumps(log_data)

    if verbose:
        print(f"    📤 schemaId=124, logCategory=event, logType=click")

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


def send_ljc_impression_srp(cookies, fingerprint, proxy, search_url, product_info, pcid, pvid, verbose=True):
    """ljc schemaId: 152 - impression (domain:srp)"""
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
            "webBuildNo": WEB_BUILD_NO,
            "web": {
                "pvid": pvid,
                "rvid": "",
                "url": search_url,
                "referrer": ""
            }
        },
        "meta": {
            "schemaId": 152,
            "schemaVersion": 2
        },
        "data": {
            "domain": "srp",
            "logCategory": "impression",
            "logType": "product",
            "productId": product_info.get('productId', ''),
            "rank": product_info.get('rank', 1)
        }
    }

    data = json.dumps(log_data)

    if verbose:
        print(f"    📤 schemaId=152, domain=srp, logCategory=impression")

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


def send_ljc_impression_1335(cookies, fingerprint, proxy, search_url, product_info, pcid, pvid, verbose=True):
    """ljc schemaId: 1335 - impression 로그 (별도 스키마, 2회 전송)

    실제 브라우저에서는 schemaVersion 7과 4를 각각 전송
    """
    url = 'https://ljc.coupang.com/api/v2/submit?appCode=coupang&market=KR'

    headers = build_api_headers(fingerprint, 'https://www.coupang.com/', 'text/plain')
    headers['Sec-Fetch-Dest'] = 'empty'
    headers['Sec-Fetch-Mode'] = 'cors'
    headers['Sec-Fetch-Site'] = 'same-site'

    results = []

    # 첫 번째: schemaVersion 7 (logType: impression)
    now = datetime.now(timezone.utc)
    event_time = now.strftime('%Y-%m-%dT%H:%M:%S.') + f'{now.microsecond // 1000:03d}Z'

    log_data_v7 = {
        "common": {
            "platform": "web",
            "pcid": pcid,
            "memberSrl": "",
            "libraryVersion": LIBRARY_VERSION,
            "lang": "ko-KR",
            "resolution": DEFAULT_RESOLUTION,
            "eventTime": event_time,
            "webBuildNo": WEB_BUILD_NO,
            "web": {
                "pvid": pvid,
                "rvid": "",
                "url": search_url,
                "referrer": ""
            }
        },
        "meta": {
            "schemaId": 1335,
            "schemaVersion": 7
        },
        "data": {
            "logCategory": "impression",
            "logType": "impression",
            "productId": product_info.get('productId', ''),
            "itemId": product_info.get('itemId', ''),
            "vendorItemId": product_info.get('vendorItemId', ''),
            "rank": product_info.get('rank', 1)
        }
    }

    data = json.dumps(log_data_v7)
    response = make_api_request(url, headers, cookies, fingerprint, proxy, 'POST', data)

    if response:
        results.append({
            'success': response.status_code in [200, 204],
            'status': response.status_code,
            'version': 7
        })

    # 두 번째: schemaVersion 4 (domain: srp, logCategory: impression)
    now = datetime.now(timezone.utc)
    event_time = now.strftime('%Y-%m-%dT%H:%M:%S.') + f'{now.microsecond // 1000:03d}Z'

    log_data_v4 = {
        "common": {
            "platform": "web",
            "pcid": pcid,
            "memberSrl": "",
            "libraryVersion": LIBRARY_VERSION,
            "lang": "ko-KR",
            "resolution": DEFAULT_RESOLUTION,
            "eventTime": event_time,
            "webBuildNo": WEB_BUILD_NO,
            "web": {
                "pvid": pvid,
                "rvid": "",
                "url": search_url,
                "referrer": ""
            }
        },
        "meta": {
            "schemaId": 1335,
            "schemaVersion": 4
        },
        "data": {
            "domain": "srp",
            "logCategory": "impression",
            "logType": "product",
            "productId": product_info.get('productId', ''),
            "rank": product_info.get('rank', 1)
        }
    }

    data = json.dumps(log_data_v4)
    response = make_api_request(url, headers, cookies, fingerprint, proxy, 'POST', data)

    if response:
        results.append({
            'success': response.status_code in [200, 204],
            'status': response.status_code,
            'version': 4
        })

    if verbose:
        print(f"    📤 schemaId=1335 (v7, v4)")
        for r in results:
            status = "✅" if r.get('success') else "❌"
            print(f"    📥 v{r['version']}: {status} {r.get('status', 'N/A')}")

    # 둘 다 성공해야 성공
    success = len(results) == 2 and all(r.get('success') for r in results)
    return {
        'success': success,
        'results': results
    }


def send_ljc_pagename(cookies, fingerprint, proxy, page_url, pcid, pvid, verbose=True):
    """ljc schemaId: 12734 - pageName 로그 (상품 페이지 진입 후)"""
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
            "webBuildNo": WEB_BUILD_NO,
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
            "pageName": "www.coupang.com",
            "pageType": "sdp"
        }
    }

    data = json.dumps(log_data)

    if verbose:
        print(f"    📤 schemaId=12734, pageName=sdp")

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


def send_ljc_click_log(cookies, fingerprint, proxy, search_url, product_info, pcid, pvid, verbose=True):
    """ljc schemaId: 14741 - click 로그"""
    url = 'https://ljc.coupang.com/api/v2/submit?appCode=coupang&market=KR'

    headers = build_api_headers(fingerprint, 'https://www.coupang.com/', 'text/plain')
    headers['Sec-Fetch-Dest'] = 'empty'
    headers['Sec-Fetch-Mode'] = 'cors'
    headers['Sec-Fetch-Site'] = 'same-site'

    now = datetime.now(timezone.utc)
    event_time = now.strftime('%Y-%m-%dT%H:%M:%S.') + f'{now.microsecond // 1000:03d}Z'

    search_id = get_search_id_from_url(product_info.get('url', ''))

    log_data = {
        "common": {
            "platform": "web",
            "pcid": pcid,
            "memberSrl": "",
            "libraryVersion": LIBRARY_VERSION,
            "lang": "ko-KR",
            "resolution": DEFAULT_RESOLUTION,
            "eventTime": event_time,
            "webBuildNo": WEB_BUILD_NO,
            "web": {
                "pvid": pvid,
                "rvid": "",
                "url": search_url,
                "referrer": ""
            }
        },
        "meta": {
            "schemaId": 14741,
            "schemaVersion": 32
        },
        "data": {
            "domain": "srp",
            "logCategory": "click",
            "logType": "product",
            "productId": product_info.get('productId', ''),
            "itemId": product_info.get('itemId', ''),
            "vendorItemId": product_info.get('vendorItemId', ''),
            "rank": product_info.get('rank', 1),
            "searchRank": product_info.get('rank', 1),
            "searchId": search_id,
            "listSize": 72
        }
    }

    data = json.dumps(log_data)

    if verbose:
        print(f"    📤 schemaId=14741, domain=srp, logCategory=click")

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


def send_ljc_impression_238(cookies, fingerprint, proxy, search_url, product_info, pcid, pvid, verbose=True):
    """ljc schemaId: 238 - impression 로그"""
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
            "webBuildNo": WEB_BUILD_NO,
            "web": {
                "pvid": pvid,
                "rvid": "",
                "url": search_url,
                "referrer": ""
            }
        },
        "meta": {
            "schemaId": 238,
            "schemaVersion": 41
        },
        "data": {
            "logCategory": "impression",
            "logType": "product",
            "productId": product_info.get('productId', ''),
            "rank": product_info.get('rank', 1)
        }
    }

    data = json.dumps(log_data)

    if verbose:
        print(f"    📤 schemaId=238, logCategory=impression")

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


def send_ljc_performance(cookies, fingerprint, proxy, pcid, verbose=True):
    """ljc extra - 성능 데이터"""
    url = 'https://ljc.coupang.com/api/v2/submit?appCode=coupang&market=KR'

    headers = build_api_headers(fingerprint, 'https://www.coupang.com/', 'text/plain')
    headers['Sec-Fetch-Dest'] = 'empty'
    headers['Sec-Fetch-Mode'] = 'cors'
    headers['Sec-Fetch-Site'] = 'same-site'

    now = datetime.now(timezone.utc)
    event_time = now.strftime('%Y-%m-%dT%H:%M:%S.') + f'{now.microsecond // 1000:03d}Z'
    nav_start = int(time.time() * 1000)

    log_data = {
        "common": {
            "platform": "web",
            "pcid": pcid,
            "memberSrl": "",
            "libraryVersion": LIBRARY_VERSION,
            "lang": "ko-KR",
            "resolution": DEFAULT_RESOLUTION,
            "eventTime": event_time,
            "webBuildNo": WEB_BUILD_NO
        },
        "meta": {
            "schemaId": 100,
            "schemaVersion": 1
        },
        "data": {
            "logCategory": "performance",
            "logType": "performance",
            "navigationStart": nav_start,
            "responseStart": nav_start + 200,
            "responseEnd": nav_start + 500,
            "domInteractive": nav_start + 800,
            "domComplete": nav_start + 1200,
            "loadEventEnd": nav_start + 1250
        },
        "extra": {
            "sentTime": event_time,
            "navigationStart": nav_start,
            "redirectStart": 0,
            "fetchStart": nav_start + 3,
            "domainLookupStart": nav_start + 3,
            "connectStart": nav_start + 3,
            "secureConnectionStart": 0,
            "requestStart": nav_start + 4,
            "responseStart": nav_start + 200,
            "responseEnd": nav_start + 500,
            "domLoading": nav_start + 600,
            "domInteractive": nav_start + 800,
            "domContentLoadedEventStart": nav_start + 850,
            "domContentLoadedEventEnd": nav_start + 900,
            "domComplete": nav_start + 1200,
            "loadEventStart": nav_start + 1200,
            "loadEventEnd": nav_start + 1250
        }
    }

    data = json.dumps(log_data)

    if verbose:
        print(f"    📤 performance data (navigationStart={nav_start})")

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


def build_mercury_protobuf(pcid, event_type='view'):
    """Mercury 트래킹용 protobuf 데이터 생성

    실제 브라우저의 r 파라미터는 protobuf 인코딩된 바이너리 데이터를
    base64로 인코딩한 것. 완벽한 재현은 어렵지만 기본 구조는 구현 가능.
    """
    import base64

    # Protobuf 메시지 수동 구성 (간소화)
    # 실제로는 .proto 정의가 필요하지만, 기본 구조만 재현

    # Field 1: string (request_id) - 16자 랜덤
    request_id = ''.join([chr(ord('a') + (i % 26)) for i in range(16)])

    # Field 2: string (ip)
    ip = "175.223.19.101"  # 예시 IP

    # Field 3: int64 (timestamp)
    timestamp = int(time.time() * 1000)

    # Field 4: int32 (1)
    field4 = 1

    # Field 5: string (session_id)
    session_id = str(uuid.uuid4()).replace('-', '')[:32]

    # Field 6: string (FLAT)
    field6 = "FLAT"

    # Field 7: string (pcid)
    field7 = pcid

    # Field 8: int64 (event_time)
    event_time = int(time.time() * 1000000)

    # Field 9: string (view)
    field9 = event_type

    # Field 10: string (WEB)
    field10 = "WEB"

    # Field 11: string (mars)
    field11 = "mars"

    # 간단한 protobuf-like 구조 (varint + length-delimited)
    def encode_varint(value):
        parts = []
        while value > 127:
            parts.append((value & 0x7f) | 0x80)
            value >>= 7
        parts.append(value)
        return bytes(parts)

    def encode_string(field_num, value):
        tag = (field_num << 3) | 2  # wire type 2 = length-delimited
        encoded = value.encode('utf-8')
        return encode_varint(tag) + encode_varint(len(encoded)) + encoded

    def encode_int64(field_num, value):
        tag = (field_num << 3) | 0  # wire type 0 = varint
        return encode_varint(tag) + encode_varint(value)

    # 메시지 조립
    message = b''
    message += encode_string(1, request_id)
    message += encode_string(2, ip)
    message += encode_int64(3, timestamp)
    message += encode_int64(4, field4)
    message += encode_string(5, session_id)
    message += encode_string(6, field6)
    message += encode_string(7, field7)
    message += encode_int64(8, event_time)
    message += encode_string(9, field9)
    message += encode_string(10, field10)
    message += encode_string(11, field11)

    # URL-safe base64 인코딩
    return base64.urlsafe_b64encode(message).decode('utf-8').rstrip('=')


def send_mercury_tracking(cookies, fingerprint, proxy, pcid, verbose=True):
    """mercury.coupang.com 트래킹 픽셀

    실제 브라우저는 protobuf 인코딩된 r 파라미터를 사용
    """
    base_url = 'https://mercury.coupang.com/e.gif'

    headers = build_api_headers(fingerprint, 'https://www.coupang.com/')
    headers['Accept'] = 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8'

    # protobuf 형식의 r 파라미터 생성
    r_param = build_mercury_protobuf(pcid, 'view')
    t_param = 3  # 실제 브라우저 값

    url = f"{base_url}?r={r_param}&t={t_param}"

    if verbose:
        print(f"    📤 mercury tracking pixel (protobuf)")

    response = make_api_request(url, headers, cookies, fingerprint, proxy)

    if response:
        result = {
            'success': response.status_code in [200, 204],
            'status': response.status_code
        }
        if verbose:
            print(f"    📥 {result['status']}")
        return result
    return {'success': False, 'error': 'Request failed'}


def fetch_product_page(product_url, cookies, fingerprint, proxy, referer):
    """상품 페이지 요청

    Returns:
        dict: success, status, size, html (성공 시 HTML 내용 포함)
    """
    headers = build_document_headers(fingerprint, referer)

    response = make_api_request(product_url, headers, cookies, fingerprint, proxy)

    if response:
        size = len(response.content)
        html_content = response.text if size > 100000 else None

        if size > 100000:
            return {
                'success': True,
                'status': response.status_code,
                'size': size,
                'url': str(response.url),
                'headers': dict(response.headers),
                'cookies': len(response.cookies),
                'html': html_content  # SDP 트래킹용
            }
        elif response.status_code == 403:
            return {'success': False, 'status': 403, 'size': size, 'error': 'BLOCKED_403', 'html': None}
        else:
            return {'success': False, 'status': response.status_code, 'size': size, 'error': f'INVALID_{size}B', 'html': None}

    return {'success': False, 'error': 'Request failed', 'html': None}


# ==================== 메인 함수 ====================

def realistic_click(product_info, search_url, cookies, fingerprint, proxy=None, verbose=True):
    """
    실제 브라우저 100% 재현 클릭 시뮬레이션

    요청 순서:
    1. n-api/reliability - 전환 이벤트
    2. ljc schemaId: 124 - event 로그
    3. ljc schemaId: 152 - impression (srp)
    4. ljc schemaId: 1335 - impression (v7, v4)
    5. 상품 페이지 요청
    6. ljc schemaId: 12734 - pageName
    7. ljc schemaId: 14741 - click 로그 x3
    8. ljc schemaId: 238 - impression
    9. ljc extra - 성능 데이터
    10. mercury 트래킹 픽셀
    """
    results = {
        'reliability': None,
        'ljc_event': None,
        'ljc_impression_srp': None,
        'ljc_impression_1335': None,
        'product_page': None,
        'sdp_tracking': None,
        'ljc_pagename': None,
        'ljc_click': None,
        'ljc_impression_238': None,
        'ljc_performance': None,
        'mercury': None,
        'success': False
    }

    pcid = get_pcid(cookies)
    pvid = generate_pvid()
    product_url = f"https://www.coupang.com{product_info['url']}"

    if verbose:
        print(f"\n{'─' * 60}")
        print("🔄 실제 브라우저 100% 클릭 시뮬레이션")
        print(f"{'─' * 60}")
        print(f"  PCID: {pcid}")
        print(f"  PVID: {pvid}")

    # ===== 클릭 전 요청들 =====

    # 1. n-api/reliability
    if verbose:
        print("\n[1/10] n-api/reliability (srp_to_sdp)...")
    result = send_reliability_event(cookies, fingerprint, proxy, search_url, verbose)
    results['reliability'] = result
    if verbose:
        status = "✅" if result.get('success') else "❌"
        print(f"  {status} {result.get('status', 'N/A')}")

    time.sleep(0.01)

    # 2. ljc schemaId: 124 - event
    if verbose:
        print("\n[2/10] ljc schemaId: 124 (event)...")
    result = send_ljc_event_log(cookies, fingerprint, proxy, search_url, product_info, pcid, pvid, verbose)
    results['ljc_event'] = result
    if verbose:
        status = "✅" if result.get('success') else "❌"
        print(f"  {status} {result.get('status', 'N/A')}")

    time.sleep(0.01)

    # 3. ljc schemaId: 152 - impression (srp)
    if verbose:
        print("\n[3/10] ljc schemaId: 152 (impression srp)...")
    result = send_ljc_impression_srp(cookies, fingerprint, proxy, search_url, product_info, pcid, pvid, verbose)
    results['ljc_impression_srp'] = result
    if verbose:
        status = "✅" if result.get('success') else "❌"
        print(f"  {status} {result.get('status', 'N/A')}")

    time.sleep(0.01)

    # 4. ljc schemaId: 1335 - impression (v7, v4)
    if verbose:
        print("\n[4/10] ljc schemaId: 1335 (impression v7, v4)...")
    result = send_ljc_impression_1335(cookies, fingerprint, proxy, search_url, product_info, pcid, pvid, verbose)
    results['ljc_impression_1335'] = result
    if verbose:
        status = "✅" if result.get('success') else "❌"
        print(f"  {status}")

    time.sleep(0.02)

    # ===== 상품 페이지 요청 =====

    # 5. 상품 페이지
    if verbose:
        print("\n[5/10] 상품 페이지 요청...")
        print(f"    URL: {product_url[:80]}...")
    result = fetch_product_page(product_url, cookies, fingerprint, proxy, search_url)
    results['product_page'] = result

    if verbose:
        if result.get('success'):
            print(f"  ✅ {result['status']} - {result['size']:,} bytes")
        else:
            print(f"  ❌ {result.get('error', 'Failed')}")

    time.sleep(0.05)

    # 5-1. SDP 트래킹 (상품 페이지 성공 시)
    if result.get('success') and result.get('html'):
        if verbose:
            print("\n[5-1] SDP 트래킹...")
        sdp_result = sdp_tracking(
            page_url=product_url,
            html_content=result['html'],
            cookies=cookies,
            fingerprint=fingerprint,
            product_info=product_info,
            pcid=pcid,
            pvid=pvid,
            proxy=proxy,
            verbose=verbose
        )
        results['sdp_tracking'] = sdp_result
    else:
        results['sdp_tracking'] = {'success': False, 'error': 'Product page failed'}

    time.sleep(0.05)

    # ===== 상품 페이지 진입 후 요청들 =====

    # 6. ljc schemaId: 12734 - pageName
    if verbose:
        print("\n[6/10] ljc schemaId: 12734 (pageName)...")
    result = send_ljc_pagename(cookies, fingerprint, proxy, product_url, pcid, pvid, verbose)
    results['ljc_pagename'] = result
    if verbose:
        status = "✅" if result.get('success') else "❌"
        print(f"  {status} {result.get('status', 'N/A')}")

    time.sleep(0.02)

    # 7. ljc schemaId: 14741 - click (3회 호출)
    if verbose:
        print("\n[7/10] ljc schemaId: 14741 (click x3)...")

    for i in range(3):
        result = send_ljc_click_log(cookies, fingerprint, proxy, search_url, product_info, pcid, pvid, verbose and i == 0)
        if i == 0:
            results['ljc_click'] = result
        time.sleep(0.01)

    if verbose:
        status = "✅" if results['ljc_click'].get('success') else "❌"
        print(f"  {status} {results['ljc_click'].get('status', 'N/A')}")

    time.sleep(0.02)

    # 8. ljc schemaId: 238 - impression
    if verbose:
        print("\n[8/10] ljc schemaId: 238 (impression)...")
    result = send_ljc_impression_238(cookies, fingerprint, proxy, search_url, product_info, pcid, pvid, verbose)
    results['ljc_impression_238'] = result
    if verbose:
        status = "✅" if result.get('success') else "❌"
        print(f"  {status} {result.get('status', 'N/A')}")

    time.sleep(0.5)  # 실제 브라우저는 ~1초 후에 성능 데이터 전송

    # 9. ljc extra - 성능 데이터
    if verbose:
        print("\n[9/10] ljc performance data...")
    result = send_ljc_performance(cookies, fingerprint, proxy, pcid, verbose)
    results['ljc_performance'] = result
    if verbose:
        status = "✅" if result.get('success') else "❌"
        print(f"  {status} {result.get('status', 'N/A')}")

    time.sleep(0.1)

    # 10. mercury 트래킹 (3회)
    if verbose:
        print("\n[10/10] mercury tracking x3...")
    for i in range(3):
        result = send_mercury_tracking(cookies, fingerprint, proxy, pcid, verbose and i == 0)
        if i == 0:
            results['mercury'] = result
        time.sleep(0.05)

    if verbose:
        status = "✅" if results['mercury'].get('success') else "❌"
        print(f"  {status} {results['mercury'].get('status', 'N/A')}")

    # ===== 결과 출력 =====

    if verbose:
        print(f"\n{'─' * 60}")
        print("📊 결과 요약")
        print(f"{'─' * 60}")

        success_count = sum(1 for k, v in results.items() if k != 'success' and v and v.get('success'))
        total_count = len([k for k in results.keys() if k != 'success'])

        for key, val in results.items():
            if key == 'success':
                continue
            if val:
                status = "✅" if val.get('success') else "❌"
                extra = f" ({val.get('size', 0):,} bytes)" if 'size' in val else ""
                print(f"  {status} {key}{extra}")
            else:
                print(f"  ⚠️ {key}: 미실행")

        print(f"\n  총 {success_count}/{total_count} 성공")
        print(f"{'─' * 60}\n")

    # 최종 성공 여부 (상품 페이지가 성공하면 전체 성공)
    results['success'] = results['product_page'].get('success', False) if results['product_page'] else False

    return results


def main():
    """테스트 실행"""
    import argparse
    parser = argparse.ArgumentParser(description='실제 브라우저 100% 클릭 시뮬레이터')
    parser.add_argument('--cookie-id', type=int, help='쿠키 ID')
    args = parser.parse_args()

    print("=" * 70)
    print("실제 브라우저 100% 클릭 시뮬레이터")
    print("=" * 70)

    if args.cookie_id:
        cookie_record = get_cookie_by_id(args.cookie_id)
        if not cookie_record:
            print(f"❌ 쿠키 ID {args.cookie_id} 없음")
            return
    else:
        cookie_record = get_latest_cookie()
        if not cookie_record:
            print("❌ 쿠키 없음")
            return

    print(f"쿠키 ID: {cookie_record['id']}")
    print(f"Chrome: {cookie_record['chrome_version']}")
    # DB에는 host:port만 저장
    db_proxy = cookie_record['proxy_url']
    proxy = f'socks5://{db_proxy}' if db_proxy else None
    print(f"프록시: {proxy}")

    fingerprint = get_fingerprint(cookie_record['chrome_version'])
    if not fingerprint:
        print("❌ TLS 프로파일 없음")
        return

    cookies = parse_cookies(cookie_record)

    product_info = {
        'productId': '9024146312',
        'itemId': '26462223016',
        'vendorItemId': '93437504341',
        'url': '/vp/products/9024146312?itemId=26462223016&vendorItemId=93437504341&q=%ED%98%B8%EB%B0%95%20%EB%8B%AC%EB%B9%9B%EC%8B%9D%ED%98%9C&searchId=test123&sourceType=search&searchRank=5&rank=5',
        'rank': 5
    }

    query = '호박 달빛식혜'
    search_url = f"https://www.coupang.com/np/search?q={quote(query)}"

    print("=" * 70)

    result = realistic_click(
        product_info=product_info,
        search_url=search_url,
        cookies=cookies,
        fingerprint=fingerprint,
        proxy=proxy
    )

    if result['success']:
        print("✅ 클릭 시뮬레이션 성공")
    else:
        print("❌ 클릭 시뮬레이션 실패")

    return result


if __name__ == '__main__':
    main()
