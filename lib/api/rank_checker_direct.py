"""
순위 체크 - 직접 연결 방식

쿠키/프록시 없이 커스텀 TLS 핑거프린트로 직접 연결
"""

import time
import random
import string
import hashlib
import uuid
from urllib.parse import quote
from curl_cffi import requests

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
    "app_ver": "9.1.4",
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

BASE_URL = "https://cmapi.coupang.com"
CHROME_VERSION = "146.0.0.0"

# 검증 기준
MIN_PRODUCTS_PER_PAGE = 15  # 페이지당 최소 상품 수 (cmapi는 ~20개 반환)
MIN_PAGES_FOR_NOT_FOUND = 6  # 미발견 인정 최소 페이지 수


def _generate_push_token():
    """랜덤 FCM Push Token 생성 (152자)"""
    # FCM 토큰 형태: 랜덤문자열:APA91b + 랜덤문자열
    part1 = ''.join(random.choices(string.ascii_letters + string.digits + '_', k=22))
    part2 = ''.join(random.choices(string.ascii_letters + string.digits + '_-', k=120))
    return f"{part1}:APA91b{part2}"


def _generate_pcid():
    """PCID 생성: 현재 타임스탬프(ms) + 랜덤 10자리 = 총 23자리"""
    ts = str(int(time.time() * 1000))
    rand_suffix = ''.join([str(random.randint(0, 9)) for _ in range(10)])
    return ts + rand_suffix


def _generate_signature(timestamp_ms, pcid):
    """x-signature 생성: SHA256(timestamp + PCID 끝 N자리)"""
    n = int(pcid[-1])
    suffix = pcid[-n:] if n > 0 else ""
    raw = str(timestamp_ms) + suffix
    return hashlib.sha256(raw.encode()).hexdigest()


def _build_coupang_app_header(push_token, pcid, identity):
    """coupang-app 헤더 조립 (28필드 파이프 구분)"""
    hw = DEVICE_HW
    fields = [
        "COUPANG",           # 0: 고정
        "Android",           # 1: OS
        hw["os_ver"],        # 2: OS 버전
        hw["app_ver"],       # 3: 앱 버전
        "",                  # 4: 빈값
        push_token,          # 5: FCM Push Token (동적)
        identity["uuid"],    # 6: UUID (동적)
        "Y",                 # 7: 고정
        hw["model"],         # 8: 기기명
        identity["uuid_raw"],    # 9: Raw UUID (동적)
        identity["ad_track_id"], # 10: adTrackId (동적)
        hw["dpi"],           # 11: DPI
        pcid,                # 12: PCID (동적)
        "",                  # 13: 빈값
        "0",                 # 14: 고정
        "",                  # 15: memberSrl 빈값
        "4g",                # 16: 네트워크
        "-1",                # 17: 고정
        "",                  # 18: 빈값
        "",                  # 19: 빈값
        "Asia/Seoul",        # 20: 타임존
        identity["sid_hash"],    # 21: SID 해시 (동적)
        "",                  # 22: 빈값
        "1080",              # 23: 화면 너비
        "450",               # 24: 화면 높이
        "4",                 # 25: 고정
        "1.0",               # 26: 폰트 스케일
        "true",              # 27: 앱 요청 플래그
    ]
    return "|".join(fields)


def _build_headers(push_token, pcid, identity):
    """매 요청마다 동적 헤더 생성"""
    now_ms = int(time.time() * 1000)
    signature = _generate_signature(now_ms, pcid)
    hw = DEVICE_HW

    return {
        "coupang-app": _build_coupang_app_header(push_token, pcid, identity),
        "x-coupang-app-request": "true",
        "x-signature": signature,
        "x-coupang-accept-language": "ko-KR",
        "user-agent": f"Dalvik/2.1.0 (Linux; U; Android {hw['os_ver']}; {hw['model']} Build/AP3A.240905.015.A2)",
        "accept-encoding": "gzip",
    }


# ─── 세션당 1회 생성되는 동적 값 ───
_session_push_token = _generate_push_token()
_session_pcid = _generate_pcid()
_session_identity = _generate_device_identity()


def _request(url, session):
    """커스텀 TLS로 요청 (매 요청마다 x-signature 갱신)"""
    headers = _build_headers(_session_push_token, _session_pcid, _session_identity)
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
        widget = ent.get('entity', {}).get('widget', {})
        metadata = widget.get('metadata', {})
        mandatory = metadata.get('commonBypassLogParams', {}).get('mandatory', {})
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
    """상품 매칭 우선순위 체크"""
    p_id = str(product.get('productId', ''))
    i_id = str(product.get('itemId', ''))
    v_id = str(product.get('vendorItemId', ''))

    t_p_id = str(target_product_id) if target_product_id else ''
    t_i_id = str(target_item_id) if target_item_id else ''
    t_v_id = str(target_vendor_item_id) if target_vendor_item_id else ''

    # 1순위: 3개 모두 매칭
    if t_p_id and t_i_id and t_v_id:
        if p_id == t_p_id and i_id == t_i_id and v_id == t_v_id:
            return (True, 'full_match')

    # 2순위: product_id + vendor_item_id
    if t_p_id and t_v_id:
        if p_id == t_p_id and v_id == t_v_id:
            return (True, 'product_vendor')

    # 3순위: product_id + item_id
    if t_p_id and t_i_id:
        if p_id == t_p_id and i_id == t_i_id:
            return (True, 'product_item')

    # 4순위: product_id만
    if t_p_id and p_id == t_p_id:
        return (True, 'product_only')

    # 5순위: vendor_item_id만
    if t_v_id and v_id == t_v_id:
        return (True, 'vendor_only')

    # 6순위: item_id만
    if t_i_id and i_id == t_i_id:
        return (True, 'item_only')

    return (False, None)


def _error_result(start_time, code, message, detail=None, pages_searched=0, page_counts=None):
    """에러 결과"""
    return {
        'success': False,
        'found': False,
        'rank': None,
        'page': None,
        'pages_searched': pages_searched,
        'page_counts': page_counts or {},
        'elapsed_ms': int((time.time() - start_time) * 1000),
        'chrome_version': CHROME_VERSION,
        'error_code': code,
        'error_message': message,
        'error_detail': detail
    }


def _success_result(start_time, found, rank, page, pages_searched,
                    rating=None, review_count=None, id_match_type=None, page_counts=None):
    """성공 결과"""
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
        'chrome_version': CHROME_VERSION,
        'error_code': None,
        'error_message': None
    }


def check_rank(keyword: str, product_id: str, item_id: str = None,
               vendor_item_id: str = None, max_page: int = 15) -> dict:
    """순위 체크 (직접 연결)

    Args:
        keyword: 검색어
        product_id: 상품 ID
        item_id: 아이템 ID (선택)
        vendor_item_id: 벤더 아이템 ID (선택)
        max_page: 최대 검색 페이지

    Returns:
        dict: 순위 체크 결과
    """
    start_time = time.time()

    # 입력값 검증
    if not keyword or not str(keyword).strip():
        return _error_result(start_time, 'INVALID_INPUT', 'keyword is required')
    if not product_id or not str(product_id).strip():
        return _error_result(start_time, 'INVALID_INPUT', 'product_id is required')

    keyword = str(keyword).strip()
    product_id = str(product_id).strip()

    page_counts = {}  # 페이지별 상품 수 {1: 36, 2: 36, ...}
    page_errors = []  # 에러 페이지 목록

    # 세션 생성 (쿠키 유지)
    session = requests.Session()

    try:
        # 검색 실행
        params = f"filter=KEYWORD:{quote(keyword)}|CCID:ALL|EXTRAS:channel/user|GET_FILTER:NONE|SINGLE_ENTITY:TRUE@SEARCH&preventingRedirection=false&resultType=default&ccidActivated=false"
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

        # 첫 페이지
        first_page_products = _extract_products(rdata)
        page_counts[1] = len(first_page_products)

        for p in first_page_products:
            key = f"{p['productId']}_{p['itemId']}"
            if key not in all_products:
                p['rank'] = len(all_products) + 1
                all_products[key] = p

                if not found_product:
                    matched, match_type = _match_product(p, product_id, item_id, vendor_item_id)
                    if matched:
                        found_product = p
                        id_match_type = match_type

        next_key = rdata.get('nextPageKey')
        next_params = rdata.get('nextPageParams', '')
        pages = 1

        # 첫 페이지 검증: 상품이 너무 적으면 차단 의심
        if page_counts[1] < MIN_PRODUCTS_PER_PAGE and total_count > 100:
            return _error_result(
                start_time, 'BLOCKED', 'Insufficient products on page 1',
                detail=f'p1:{page_counts[1]}/total:{total_count}',
                pages_searched=1, page_counts=page_counts
            )

        # 다음 페이지들
        while next_key and pages < max_page and not found_product:
            pages += 1
            url = f"{BASE_URL}/v3/products?{params}&nextPageKey={quote(next_key)}&nextPageParams={quote(next_params)}&resultType=search"

            try:
                resp = _request(url, session)
                if resp.status_code != 200:
                    page_counts[pages] = -1
                    page_errors.append({'page': pages, 'error': f'STATUS_{resp.status_code}'})
                    break

                data = resp.json()
            except Exception as e:
                page_counts[pages] = -1
                page_errors.append({'page': pages, 'error': str(e)[:50]})
                break

            if data.get('rCode') != 'RET0000':
                page_counts[pages] = -1
                page_errors.append({'page': pages, 'error': data.get('rCode', 'UNKNOWN')})
                break

            rdata = data.get('rData', {})
            page_products = _extract_products(rdata)
            page_counts[pages] = len(page_products)

            # 페이지 상품 수 검증
            if len(page_products) < MIN_PRODUCTS_PER_PAGE and pages <= 5:
                # 초반 페이지에서 상품이 너무 적으면 차단 의심
                page_errors.append({'page': pages, 'error': f'LOW_COUNT_{len(page_products)}'})

            before_count = len(all_products)

            for p in page_products:
                key = f"{p['productId']}_{p['itemId']}"
                if key not in all_products:
                    p['rank'] = len(all_products) + 1
                    all_products[key] = p

                    if not found_product:
                        matched, match_type = _match_product(p, product_id, item_id, vendor_item_id)
                        if matched:
                            found_product = p
                            id_match_type = match_type
                            break

            # 새 상품이 없으면 종료 (정상적인 끝 또는 문제)
            if len(all_products) == before_count:
                if len(page_products) == 0:
                    # 빈 페이지 = 정상 종료
                    break
                # 상품은 있지만 모두 중복 = 계속 진행

            next_key = rdata.get('nextPageKey')
            next_params = rdata.get('nextPageParams', '')

            if not next_key:
                break

        # 결과 검증
        total_products = len(all_products)

        # 에러 페이지가 있으면 실패 처리
        if page_errors and not found_product:
            err_summary = ','.join([f"p{e['page']}:{e['error']}" for e in page_errors[:3]])
            return _error_result(
                start_time, 'INCOMPLETE', f'Page errors: {len(page_errors)}',
                detail=err_summary,
                pages_searched=pages, page_counts=page_counts
            )

        # 발견 시
        if found_product:
            rank = found_product['rank']
            page = pages

            # rating 파싱
            rating = None
            rating_str = found_product.get('rating', '')
            if rating_str:
                try:
                    rating = float(rating_str)
                except:
                    pass

            # review_count 파싱
            review_count = None
            rc_str = found_product.get('ratingCount', '')
            if rc_str:
                try:
                    review_count = int(rc_str.replace(',', '').replace('개', '').replace('(', '').replace(')', ''))
                except:
                    pass

            return _success_result(
                start_time, True, rank, page, pages,
                rating=rating, review_count=review_count,
                id_match_type=id_match_type, page_counts=page_counts
            )

        # 미발견 검증
        # 1. 충분한 페이지를 검색했는지 (단, 검색 결과가 원래 적으면 예외)
        #    next_key가 없으면 = API가 모든 결과를 반환한 것 = 정상 종료
        has_more_pages = bool(next_key)
        if pages < MIN_PAGES_FOR_NOT_FOUND and total_count > pages * 20 and has_more_pages:
            # total_count가 충분하고 아직 더 있는데 페이지가 적으면 문제
            return _error_result(
                start_time, 'INCOMPLETE', f'Only {pages} pages searched',
                detail=f'min:{MIN_PAGES_FOR_NOT_FOUND}/total:{total_count}',
                pages_searched=pages, page_counts=page_counts
            )

        # 2. 총 상품 수가 합리적인지
        # - total_count가 1000개 이상인데 추출이 200개 미만이면 문제
        if total_count > 1000 and total_products < 200:
            return _error_result(
                start_time, 'BLOCKED', f'Too few products: {total_products}',
                detail=f'total_count:{total_count}',
                pages_searched=pages, page_counts=page_counts
            )

        # 정상적인 미발견
        return _success_result(
            start_time, False, None, None, pages,
            page_counts=page_counts
        )

    except Exception as e:
        return _error_result(
            start_time, 'INTERNAL_ERROR', 'Unexpected error',
            str(e)[:100], pages_searched=0, page_counts=page_counts
        )


def get_public_ip():
    """공인 IP 조회"""
    try:
        resp = requests.get('https://api.ipify.org?format=json', timeout=5)
        return resp.json().get('ip', '')
    except:
        return ''
