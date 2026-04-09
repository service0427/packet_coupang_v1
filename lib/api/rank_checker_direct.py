"""
순위 체크 - 직접 연결 방식

쿠키/프록시 없이 커스텀 TLS 핑거프린트로 직접 연결
"""

import time
import random
import string
import hashlib
import uuid
import struct
from urllib.parse import quote
from curl_cffi import requests

from api.cp_signature import generate_x_cp_s

# Chrome 143 Mobile TLS 핑거프린트
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

# ─── 디바이스 프로필 (고정 하드웨어 정보) ───
DEVICE_HW = {
    "model": "SM-A165N",
    "os_ver": "15",
    "app_ver": "9.1.5",
    "dpi": "XXHDPI",
}


def _generate_device_identity():
    """세션당 고유 디바이스 식별자 생성"""
    dev_uuid = str(uuid.uuid4())                          # UUID v4
    dev_uuid_raw = dev_uuid.replace('-', '')               # 대시 제거
    ad_track_id = str(uuid.uuid4())                        # 광고 추적 ID
    sid_raw = str(uuid.uuid4())                            # SID 원본
    sid_hash = hashlib.sha1(sid_raw.encode()).hexdigest()   # SHA-1 해시 (40자)
    return {
        "uuid": dev_uuid,
        "uuid_raw": dev_uuid_raw,
        "ad_track_id": ad_track_id,
        "sid_hash": sid_hash,
    }


def _generate_trace_ix_id():
    """x-trace-ix-id 생성 (UUID v4 형태, 첫 세그먼트에 카운터/타임스탬프 기반 값)"""
    ts_counter = int(time.time()) & 0xFFFF
    seg1 = f"{ts_counter:08x}"
    rand_bytes = random.getrandbits(80)
    seg2 = f"{(rand_bytes >> 64) & 0xFFFF:04x}"
    seg3 = f"{(rand_bytes >> 48) & 0xFFFF:04x}"
    seg4 = f"{(rand_bytes >> 32) & 0xFFFF:04x}"
    seg5 = f"{rand_bytes & 0xFFFFFFFFFFFF:012x}"
    return f"{seg1}-{seg2}-{seg3}-{seg4}-{seg5}"


def _generate_cmg_dco():
    """x-cmg-dco 생성"""
    now_ms = int(time.time() * 1000)
    offset_ms = random.randint(3600_000, 172800_000)
    return str(now_ms - offset_ms)


BASE_URL = "https://cmapi.coupang.com"
CHROME_VERSION = "146.0.0.0"

# 검증 기준
MIN_PRODUCTS_PER_PAGE = 10
MIN_PAGES_FOR_NOT_FOUND = 6


def _generate_push_token():
    """랜덤 FCM Push Token 생성"""
    part1 = ''.join(random.choices(string.ascii_letters + string.digits + '_', k=22))
    part2 = ''.join(random.choices(string.ascii_letters + string.digits + '_-', k=120))
    return f"{part1}:APA91b{part2}"


def _generate_pcid():
    """PCID 생성"""
    ts = str(int(time.time() * 1000))
    rand_suffix = ''.join([str(random.randint(0, 9)) for _ in range(10)])
    return ts + rand_suffix


def _generate_signature(timestamp_ms, pcid):
    """x-signature 생성"""
    n = int(pcid[-1])
    suffix = pcid[-n:] if n > 0 else ""
    raw = str(timestamp_ms) + suffix
    return hashlib.sha256(raw.encode()).hexdigest()


def _build_coupang_app_header(push_token, pcid, identity):
    """coupang-app 헤더 조립 (v9.1.5 캡처 기준)"""
    hw = DEVICE_HW
    fields = [
        "COUPANG",           # 0
        "Android",           # 1
        hw["os_ver"],        # 2
        hw["app_ver"],       # 3
        "",                  # 4
        push_token,          # 5
        identity["uuid"],    # 6
        "Y",                 # 7
        hw["model"],         # 8
        identity["uuid_raw"],    # 9
        identity["ad_track_id"], # 10
        hw["dpi"],           # 11
        pcid,                # 12
        "",                  # 13
        "0",                 # 14
        "",                  # 15
        "4g",                # 16
        "-1",                # 17
        "",                  # 18
        "",                  # 19
        "Asia/Seoul",        # 20
        identity["sid_hash"],    # 21
        "",                  # 22
        "1080",              # 23
        "450",               # 24
        "-1",                # 25: 고정 (v9.1.5 캡처 기준)
        "1.0",               # 26
        "true",              # 27
    ]
    return "|".join(fields)


def _build_headers(push_token, pcid, identity, cmg_dco, query_params=""):
    """매 요청마다 동적 헤더 생성"""
    now_ms = int(time.time() * 1000)
    signature = _generate_signature(now_ms, pcid)
    hw = DEVICE_HW
    coupang_app = _build_coupang_app_header(push_token, pcid, identity)

    # x-cp-s 서명 생성
    x_cp_s = generate_x_cp_s(
        headers_payload=coupang_app,
        query_params=query_params,
        timestamp_ms=now_ms,
        app_version=hw["app_ver"],
        uuid_raw=identity["uuid_raw"]
    )

    return {
        "x-timestamp": str(now_ms),
        "coupang-app": coupang_app,
        "x-coupang-font-scale": "1.0",
        "run-mode": "production",
        "x-coupang-app-request": "true",
        "baggage": "enable-upstream-tti-info=true",
        "x-cp-app-req-time": str(now_ms + random.randint(500, 1500)),
        "x-view-name": "/search",
        "x-coupang-target-market": "KR",
        "x-coupang-app-name": "coupang",
        "x-cp-app-id": "com.coupang.mobile",
        "x-cmg-dco": cmg_dco,
        "x-coupang-origin-region": "KR",
        "x-signature": signature,
        "x-coupang-accept-language": "ko-KR",
        "x-trace-ix-id": _generate_trace_ix_id(),
        "user-agent": f"Dalvik/2.1.0 (Linux; U; Android {hw['os_ver']}; {hw['model']} Build/AP3A.240905.015.A2)",
        "accept-encoding": "gzip",
        "x-cp-s": x_cp_s,
    }


_session_push_token = _generate_push_token()
_session_pcid = _generate_pcid()
_session_identity = _generate_device_identity()
_session_cmg_dco = _generate_cmg_dco()


def _request(url, session):
    """커스텀 TLS로 요청"""
    query_params = url.split('?', 1)[1] if '?' in url else ""
    headers = _build_headers(_session_push_token, _session_pcid, _session_identity, _session_cmg_dco, query_params)
    return session.get(
        url,
        headers=headers,
        ja3=TLS_CONFIG["ja3"],
        akamai=TLS_CONFIG["akamai"],
        extra_fp=TLS_CONFIG["extra_fp"],
        timeout=15,
    )


def _extract_products(rdata):
    """entityList에서 상품 추출"""
    products = []
    for ent in rdata.get('entityList', []):
        entity = ent.get('entity', {})
        widget = entity.get('widget', {})
        metadata = widget.get('metadata', {})
        
        # v9.1.5 구조에 맞춰 추출 경로 수정
        common_log = metadata.get('commonBypassLogParams', {})
        mandatory = common_log.get('mandatory', {})
        display = metadata.get('displayItem', {})

        product_id = mandatory.get('productId')
        if not product_id:
            continue

        products.append({
            'productId': str(product_id),
            'itemId': str(mandatory.get('itemId', '')),
            'vendorItemId': str(mandatory.get('vendorItemId', '')),
            'title': display.get('title', ''),
            'price': display.get('price', ''),
            'discountRate': display.get('discountRate', ''),
            'rating': display.get('rating', ''),
            'ratingCount': display.get('ratingCount', ''),
            'rocket': display.get('rocket', False),
            'rocketWow': display.get('rocketWow', False),
            'isAd': mandatory.get('isAds', False),
        })
    return products


def _match_product(product, target_product_id, target_item_id=None, target_vendor_item_id=None):
    """상품 매칭"""
    p_id = str(product.get('productId', ''))
    i_id = str(product.get('itemId', ''))
    v_id = str(product.get('vendorItemId', ''))

    t_p_id = str(target_product_id) if target_product_id else ''
    t_i_id = str(target_item_id) if target_item_id else ''
    t_v_id = str(target_vendor_item_id) if target_vendor_item_id else ''

    if t_p_id and t_i_id and t_v_id:
        if p_id == t_p_id and i_id == t_i_id and v_id == t_v_id:
            return (True, 'full_match')
    if t_p_id and t_v_id:
        if p_id == t_p_id and v_id == t_v_id:
            return (True, 'product_vendor')
    if t_p_id and p_id == t_p_id:
        return (True, 'product_only')
    return (False, None)


def _error_result(start_time, code, message, detail=None, pages_searched=0, page_counts=None):
    return {
        'success': False,
        'found': False,
        'rank': None,
        'page': None,
        'pages_searched': pages_searched,
        'page_counts': page_counts or {},
        'elapsed_ms': int((time.time() - start_time) * 1000),
        'error_code': code,
        'error_message': message,
        'error_detail': detail
    }


def _success_result(start_time, found, rank, page, pages_searched,
                    rating=None, review_count=None, id_match_type=None, page_counts=None):
    return {
        'success': True,
        'found': found,
        'rank': rank,
        'page': page,
        'rating': rating,
        'review_count': review_count,
        'id_match_type': id_match_type,
        'pages_searched': pages_searched,
        'page_counts': page_counts or {},
        'elapsed_ms': int((time.time() - start_time) * 1000),
        'error_code': None,
        'error_message': None
    }


def check_rank(keyword: str, product_id: str, item_id: str = None,
               vendor_item_id: str = None, max_page: int = 15) -> dict:
    """순위 체크 실행"""
    start_time = time.time()
    keyword = str(keyword).strip()
    product_id = str(product_id).strip()

    page_counts = {}
    page_errors = []
    session = requests.Session()

    try:
        # 검색 실행 (referrerPage=HOME 추가)
        params = f"filter=KEYWORD:{quote(keyword)}|CCID:ALL|EXTRAS:channel/user|GET_FILTER:NONE|SINGLE_ENTITY:TRUE@SEARCH&preventingRedirection=false&resultType=default&ccidActivated=false&referrerPage=HOME"
        url = f"{BASE_URL}/v3/products?{params}"

        resp = _request(url, session)
        if resp.status_code != 200:
            return _error_result(start_time, 'API_ERROR', f'Status {resp.status_code}')

        data = resp.json()
        if data.get('rCode') != 'RET0000':
            return _error_result(start_time, 'API_ERROR', data.get('rCode'))

        rdata = data.get('rData', {})
        total_count = rdata.get('totalCount', 0)
        all_products = {}
        found_product = None
        id_match_type = None

        # 페이지 처리 루프
        pages = 0
        next_key = "START" # Dummy start
        next_params = ""

        while next_key and pages < max_page and not found_product:
            pages += 1
            if pages > 1:
                url = f"{BASE_URL}/v3/products?{params}&nextPageKey={quote(next_key)}&nextPageParams={quote(next_params)}&resultType=search"
                resp = _request(url, session)
                if resp.status_code != 200: break
                data = resp.json()
                if data.get('rCode') != 'RET0000': break
                rdata = data.get('rData', {})

            page_products = _extract_products(rdata)
            page_counts[pages] = len(page_products)

            for p in page_products:
                key = f"{p['productId']}_{p['itemId']}"
                if key not in all_products:
                    p['rank'] = len(all_products) + 1
                    all_products[key] = p
                    if not found_product:
                        matched, m_type = _match_product(p, product_id, item_id, vendor_item_id)
                        if matched:
                            found_product = p
                            id_match_type = m_type

            next_key = rdata.get('nextPageKey')
            next_params = rdata.get('nextPageParams', '')
            if not next_key: break

        if found_product:
            return _success_result(
                start_time, True, found_product['rank'], pages, pages,
                id_match_type=id_match_type, page_counts=page_counts
            )

        return _success_result(start_time, False, None, None, pages, page_counts=page_counts)

    except Exception as e:
        return _error_result(start_time, 'INTERNAL_ERROR', str(e))


def get_public_ip():
    try:
        resp = requests.get('https://api.ipify.org?format=json', timeout=5)
        return resp.json().get('ip', '')
    except:
        return ''
