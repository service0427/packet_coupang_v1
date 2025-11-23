"""
상품 등수 체크 명령어
"""

import sys
import json
import re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from urllib.parse import quote
from http.cookies import SimpleCookie

# Add lib directory to path
sys.path.insert(0, str(Path(__file__).parent))

from common import (
    timestamp, get_cookie_by_id, get_latest_cookie, get_fingerprint,
    check_proxy_ip, parse_cookies, make_request, verify_ip_binding,
    generate_traceid, update_cookie_stats, update_cookie_data
)
from extractor.search_extractor import ProductExtractor
from product_click import product_click
from usage_log import log_cookie_usage
from batch_search import create_batch_searcher

BASE_DIR = Path(__file__).parent.parent

# 기본 테스트 상품 (호박 달빛식혜)
DEFAULT_PRODUCT = {
    'product_id': '9024146312',
    'item_id': '26462223016',
    'vendor_item_id': '93437504341',
    'query': '호박 달빛식혜'
}

def parse_set_cookie_header(set_cookie_str):
    """Set-Cookie 헤더 파싱하여 쿠키 속성 추출

    Args:
        set_cookie_str: Set-Cookie 헤더 값

    Returns:
        dict: {name, value, domain, path, expires, max_age, ...}
    """
    cookie = SimpleCookie()
    try:
        cookie.load(set_cookie_str)
        for name, morsel in cookie.items():
            result = {
                'name': name,
                'value': morsel.value,
                'domain': morsel.get('domain', '.coupang.com'),
                'path': morsel.get('path', '/'),
            }
            # expires 처리
            if morsel.get('expires'):
                result['expires'] = morsel.get('expires')
            # max-age 처리 (초 단위)
            if morsel.get('max-age'):
                try:
                    max_age = int(morsel.get('max-age'))
                    # max-age를 expires timestamp로 변환 (float 유지 - Playwright와 동일)
                    from time import time
                    result['expires'] = time() + max_age
                except:
                    pass
            return result
    except:
        pass
    return None


def parse_response_cookies(resp):
    """응답에서 전체 쿠키 속성 파싱

    Args:
        resp: curl_cffi 응답 객체

    Returns:
        list: 쿠키 딕셔너리 리스트 [{name, value, domain, path, expires, ...}]
    """
    cookies_list = []

    # Set-Cookie 헤더에서 전체 속성 파싱
    if hasattr(resp, 'headers'):
        # 여러 Set-Cookie 헤더 처리
        set_cookies = resp.headers.get_list('set-cookie') if hasattr(resp.headers, 'get_list') else []

        # get_list가 없으면 단일 헤더로 시도
        if not set_cookies:
            set_cookie = resp.headers.get('set-cookie', '')
            if set_cookie:
                # 여러 쿠키가 쉼표로 구분된 경우 분리 (주의: expires 안의 쉼표 처리)
                # 간단히 각각의 Set-Cookie를 처리
                set_cookies = [set_cookie]

        for sc in set_cookies:
            parsed = parse_set_cookie_header(sc)
            if parsed:
                cookies_list.append(parsed)

    return cookies_list


def fetch_page(page_num, query, trace_id, cookies, fingerprint, proxy):
    """페이지 검색"""
    url = f'https://www.coupang.com/np/search?q={quote(query)}&traceId={trace_id}&channel=user&listSize=72&page={page_num}'

    try:
        resp = make_request(url, cookies, fingerprint, proxy)
        size = len(resp.content)

        # 응답 쿠키 수집 (전체 속성 포함)
        response_cookies_list = parse_response_cookies(resp)
        # 간단한 {name: value} 딕셔너리도 유지 (호환성)
        response_cookies = {c['name']: c['value'] for c in response_cookies_list}

        if resp.status_code == 200 and size > 5000:
            result = ProductExtractor.extract_products_from_html(resp.text)
            return {
                'page': page_num, 'success': True, 'products': result['ranking'], 'size': size,
                'response_cookies': response_cookies,
                'response_cookies_full': response_cookies_list
            }
        elif resp.status_code == 403:
            return {'page': page_num, 'success': False, 'products': [], 'error': 'BLOCKED_403', 'response_cookies': response_cookies, 'response_cookies_full': response_cookies_list}
        elif size <= 5000:
            return {'page': page_num, 'success': False, 'products': [], 'error': f'CHALLENGE_{size}B', 'response_cookies': response_cookies, 'response_cookies_full': response_cookies_list}
        else:
            return {'page': page_num, 'success': False, 'products': [], 'error': f'STATUS_{resp.status_code}', 'response_cookies': response_cookies, 'response_cookies_full': response_cookies_list}

    except Exception as e:
        return {'page': page_num, 'success': False, 'products': [], 'error': str(e)[:150], 'response_cookies': {}, 'response_cookies_full': []}


def compare_cookies(original_cookies, response_cookies):
    """쿠키 변경사항 비교

    Args:
        original_cookies: 원본 쿠키 딕셔너리
        response_cookies: 응답에서 받은 쿠키 딕셔너리

    Returns:
        dict: {'new': [], 'changed': [], 'unchanged': []}
    """
    result = {'new': [], 'changed': [], 'unchanged': []}

    for name, value in response_cookies.items():
        if name not in original_cookies:
            result['new'].append(name)
        elif original_cookies[name] != value:
            result['changed'].append(name)
        else:
            result['unchanged'].append(name)

    return result


def print_cookie_changes(original_cookies, all_response_cookies):
    """쿠키 변경사항 출력

    Args:
        original_cookies: 원본 쿠키 딕셔너리
        all_response_cookies: 모든 응답에서 수집된 쿠키 딕셔너리
    """
    if not all_response_cookies:
        return

    changes = compare_cookies(original_cookies, all_response_cookies)

    if changes['new'] or changes['changed']:
        print(f"\n{'─' * 60}")
        print("🍪 쿠키 변경사항")
        print(f"{'─' * 60}")

        if changes['new']:
            print(f"  신규: {', '.join(changes['new'])}")

        if changes['changed']:
            print(f"  변경: {', '.join(changes['changed'])}")
            # 변경된 쿠키의 이전/이후 값 비교 (일부만 표시)
            for name in changes['changed'][:3]:
                old_val = original_cookies.get(name, '')[:30]
                new_val = all_response_cookies.get(name, '')[:30]
                print(f"    {name}:")
                print(f"      이전: {old_val}...")
                print(f"      이후: {new_val}...")

        print(f"{'─' * 60}")

def click_product(product_url, cookies, fingerprint, proxy, referer, verbose=True):
    """상품 클릭 (상세 정보 출력)"""
    full_url = f'https://www.coupang.com{product_url}'

    try:
        resp = make_request(full_url, cookies, fingerprint, proxy, referer)
        size = len(resp.content)

        # 상세 정보 출력
        if verbose:
            print(f"\n{'─' * 60}")
            print("📤 Request")
            print(f"{'─' * 60}")
            print(f"  URL: {full_url[:80]}...")
            print(f"  Method: GET")
            print(f"  Referer: {referer[:60]}..." if referer else "  Referer: None")

            # Request Headers (주요 항목)
            req_headers = resp.request.headers if hasattr(resp, 'request') and hasattr(resp.request, 'headers') else {}
            if req_headers:
                print(f"  Headers:")
                for key in ['User-Agent', 'Accept', 'Sec-Ch-Ua', 'Sec-Fetch-Site']:
                    if key in req_headers:
                        val = req_headers[key]
                        if len(val) > 50:
                            val = val[:50] + '...'
                        print(f"    {key}: {val}")

            print(f"\n{'─' * 60}")
            print("📥 Response")
            print(f"{'─' * 60}")
            print(f"  Status: {resp.status_code}")
            print(f"  Size: {size:,} bytes")

            # Response Headers (주요 항목)
            resp_headers = dict(resp.headers) if hasattr(resp, 'headers') else {}
            if resp_headers:
                print(f"  Headers:")
                for key in ['Content-Type', 'Content-Encoding', 'Server', 'X-Cache']:
                    if key.lower() in [k.lower() for k in resp_headers]:
                        actual_key = next(k for k in resp_headers if k.lower() == key.lower())
                        print(f"    {actual_key}: {resp_headers[actual_key]}")

            # 쿠키 정보
            if resp.cookies:
                print(f"  Set-Cookie: {len(resp.cookies)}개")

            print(f"{'─' * 60}\n")

        # 결과 판정
        if size > 100000:
            return {
                'success': True,
                'status': resp.status_code,
                'size': size,
                'url': full_url,
                'response_headers': dict(resp.headers) if hasattr(resp, 'headers') else {}
            }
        elif resp.status_code == 403:
            return {'success': False, 'status': 403, 'size': size, 'error': 'BLOCKED_403'}
        else:
            return {'success': False, 'status': resp.status_code, 'size': size, 'error': f'INVALID_RESPONSE_{size}B'}

    except Exception as e:
        return {'success': False, 'status': None, 'size': 0, 'error': str(e)[:100]}

def get_random_product(product_list_id=None):
    """DB에서 상품 조회

    Args:
        product_list_id: 특정 ID 지정 시 해당 상품, None이면 랜덤
    """
    from db import execute_query

    if product_list_id:
        result = execute_query("""
            SELECT id, keyword, product_id, item_id, vendor_item_id
            FROM product_list
            WHERE id = %s
        """, (product_list_id,))
    else:
        result = execute_query("""
            SELECT id, keyword, product_id, item_id, vendor_item_id
            FROM product_list
            ORDER BY RAND()
            LIMIT 1
        """)
    return result[0] if result else None


def run_rank(args):
    """상품 등수 체크 실행"""
    print("=" * 70)
    print("상품 등수 체커")
    print("=" * 70)

    # --random: DB에서 키워드 선택 (--pl-id로 특정 ID 지정 가능)
    if getattr(args, 'random', False):
        pl_id = getattr(args, 'pl_id', None)
        product = get_random_product(pl_id)
        if not product:
            if pl_id:
                print(f"❌ product_list ID {pl_id} 없음")
            else:
                print("❌ product_list 테이블에 데이터 없음")
            return
        args.query = product['keyword']
        args.product_id = product['product_id']
        args.pl_id_used = product['id']  # 사용된 product_list ID 저장
        # item_id, vendor_item_id도 설정 (완전 매칭용)
        if product.get('item_id'):
            args.item_id = product['item_id']
        if product.get('vendor_item_id'):
            args.vendor_item_id = product['vendor_item_id']

        if pl_id:
            print(f"📋 선택 [PL {product['id']}]: {args.query} (상품 ID: {args.product_id})")
        else:
            print(f"🎲 랜덤 선택 [PL#{product['id']}]: {args.query} (상품 ID: {args.product_id})")

    # Get cookie
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
        print(f"쿠키 ID: {cookie_record['id']} (최신)")

    fingerprint = get_fingerprint(cookie_record['chrome_version'], args.platform)
    if not fingerprint:
        print("❌ 핑거프린트 없음")
        return

    cookies = parse_cookies(cookie_record)
    # DB에는 host:port만 저장, 사용시 socks5:// 추가
    db_proxy = cookie_record['proxy_url']
    proxy = args.proxy or (f'socks5://{db_proxy}' if db_proxy else None)

    print(f"타겟: {args.product_id}")
    print(f"검색어: {args.query}")
    print(f"Chrome: {cookie_record['chrome_version']}")
    print(f"프록시: {proxy}")

    # IP 검증 (기본: 건너뜀, --ip-check로 활성화)
    current_ip = None
    do_ip_check = getattr(args, 'ip_check', False)

    if proxy:
        current_ip = check_proxy_ip(proxy)
        if current_ip:
            print(f"\n  현재 IP: {current_ip}")
            print(f"  쿠키 IP: {cookie_record['proxy_ip']}")

            if current_ip == cookie_record['proxy_ip']:
                print("  ✅ IP 일치")
            else:
                print("  ⚠️  IP 불일치")
                if do_ip_check:
                    print("\n❌ IP 바인딩 검증 실패 (--ip-check)")
                    return

    print("=" * 70)

    # --previsit: 상품 페이지 사전 방문 (검색 전)
    if getattr(args, 'previsit', False):
        if not getattr(args, 'random', False):
            print("\n❌ --previsit은 --random과 함께 사용해야 합니다")
            return

        # item_id, vendor_item_id 필수
        item_id = getattr(args, 'item_id', None)
        vendor_item_id = getattr(args, 'vendor_item_id', None)

        if not item_id or not vendor_item_id:
            print("\n❌ 사전 방문에는 item_id, vendor_item_id가 필요합니다")
            return

        # 상품 URL 생성
        previsit_url = f"/vp/products/{args.product_id}?itemId={item_id}&vendorItemId={vendor_item_id}"

        print(f"\n[{timestamp()}] 🔍 사전 방문 중...")
        print(f"  URL: https://www.coupang.com{previsit_url}")

        # product_click 재활용
        previsit_info = {
            'productId': args.product_id,
            'url': previsit_url,
            'itemId': item_id,
            'vendorItemId': vendor_item_id
        }

        # 메인 페이지를 Referer로 사용
        previsit_result = product_click(
            previsit_info,
            'https://www.coupang.com/',
            cookies,
            fingerprint,
            proxy,
            verbose=False
        )

        if previsit_result['success']:
            print(f"  ✅ 사전 방문 성공 ({previsit_result['size']:,} bytes)")
        else:
            print(f"  ❌ 사전 방문 실패: {previsit_result.get('error', 'Unknown')}")
            # 실패해도 검색은 계속 진행

        # Cookie Jar: 응답 쿠키 병합 (previsit에서 업데이트된 쿠키 반영)
        if previsit_result.get('response_cookies'):
            cookies.update(previsit_result['response_cookies'])
            print(f"  🍪 쿠키 업데이트: {len(previsit_result['response_cookies'])}개")

    trace_id = generate_traceid()
    print(f"\n[{timestamp()}] 검색 중... (traceId: {trace_id})")

    found = None
    start_time = datetime.now()
    all_products = []
    failed_pages = []
    blocked_403 = False  # BLOCKED_403 또는 CHALLENGE 발생 시 즉시 종료
    block_error = ''  # 차단 에러 메시지
    all_response_cookies = {}  # 모든 응답에서 수집된 쿠키 {name: value}
    all_response_cookies_full = []  # 전체 속성 포함 [{name, value, domain, path, expires, ...}]

    # 배치 모드 vs 기존 모드 (--no-batch로 비활성화)
    use_batch_mode = getattr(args, 'batch', True) and not getattr(args, 'no_batch', False)

    if use_batch_mode:
        # 점진적 배치 검색 모드
        print(f"  모드: 점진적 배치 (1 → 2-3 → 4-{args.max_page})")

        batch_searcher = create_batch_searcher(
            fetch_page,
            args.query,
            trace_id,
            cookies,
            fingerprint,
            proxy,
            max_page=args.max_page,
            max_retries=3
        )

        # 3개 ID 전달 (완전 매칭 지원)
        target_item_id = getattr(args, 'item_id', None)
        target_vendor_item_id = getattr(args, 'vendor_item_id', None)

        search_result = batch_searcher.search(
            args.product_id,
            target_item_id,
            target_vendor_item_id
        )

        found = search_result['found']
        match_type = search_result.get('match_type')
        all_products = search_result['all_products']
        all_response_cookies = search_result['all_response_cookies']
        all_response_cookies_full = search_result['all_response_cookies_full']
        blocked_403 = search_result['blocked']
        block_error = search_result['block_error']
        failed_pages = search_result['failed_pages']
        total_bytes = search_result.get('total_bytes', 0)

        if failed_pages:
            print(f"\n[{timestamp()}] ⚠️  최종 실패 페이지: {failed_pages}")

    else:
        # 기존 모드: 모든 페이지 동시 검색
        total_bytes = 0  # 기존 모드에서는 트래픽 추적 안함
        match_type = None
        with ThreadPoolExecutor(max_workers=args.max_page) as executor:
            futures = {
                executor.submit(fetch_page, i, args.query, trace_id, cookies, fingerprint, proxy): i
                for i in range(1, args.max_page + 1)
            }

            for future in as_completed(futures, timeout=60):
                try:
                    result = future.result(timeout=30)

                    # 응답 쿠키 수집
                    if result.get('response_cookies'):
                        all_response_cookies.update(result['response_cookies'])
                    if result.get('response_cookies_full'):
                        all_response_cookies_full.extend(result['response_cookies_full'])

                    if result['success']:
                        for product in result['products']:
                            product['_page'] = result['page']
                            all_products.append(product)

                            # 상품 매칭 우선순위 (coupang_agent_v2 기준):
                            # 1순위: ProductId + VendorItemId + ItemId (완전 매칭)
                            # 2순위: ProductId + VendorItemId
                            # 3순위: ProductId만
                            # 4순위: VendorItemId만
                            # 5순위: ItemId만
                            # 현재 구현: ProductId만 사용 (3순위)
                            if product['productId'] == args.product_id and not found:
                                found = product
                                found['page'] = result['page']
                                print(f"[{timestamp()}] ✅ 발견! Page {result['page']}, Rank {product['rank']}")

                        if found:
                            # 조기 종료: 대기 중인 작업 취소
                            for f in futures:
                                f.cancel()
                            break
                        else:
                            print(f"  [{timestamp()}] Page {result['page']:2d}: {len(result['products'])}개")
                    else:
                        error = result.get('error', '')
                        print(f"  [{timestamp()}] Page {result['page']:2d}: ❌ {error}")

                        # BLOCKED_403 또는 CHALLENGE = Akamai 완전 차단, 즉시 종료
                        if error == 'BLOCKED_403' or error.startswith('CHALLENGE_'):
                            blocked_403 = True
                            block_error = error
                            for f in futures:
                                f.cancel()
                            break
                        else:
                            # TLS 에러 등은 재시도 가능
                            failed_pages.append(result['page'])

                except:
                    pass

            # 재시도 (발견 안 된 경우만, BLOCKED_403이 아닌 경우만, 최대 3회)
            max_retries = 3
            retry_count = 0

            while not found and not blocked_403 and failed_pages and retry_count < max_retries:
                retry_count += 1
                print(f"\n[{timestamp()}] 재시도 #{retry_count}: {failed_pages}")

                retry_futures = {
                    executor.submit(fetch_page, p, args.query, trace_id, cookies, fingerprint, proxy): p
                    for p in failed_pages
                }

                still_failed = []

                for future in as_completed(retry_futures, timeout=60):
                    try:
                        result = future.result(timeout=30)
                        page_num = result['page']

                        # 응답 쿠키 수집
                        if result.get('response_cookies'):
                            all_response_cookies.update(result['response_cookies'])
                        if result.get('response_cookies_full'):
                            all_response_cookies_full.extend(result['response_cookies_full'])

                        if result['success']:
                            print(f"  [{timestamp()}] Page {page_num:2d}: ✅ {len(result['products'])}개")
                            for product in result['products']:
                                product['_page'] = result['page']
                                all_products.append(product)
                                if product['productId'] == args.product_id and not found:
                                    found = product
                                    found['page'] = result['page']
                                    print(f"[{timestamp()}] ✅ 재시도 발견! Page {result['page']}, Rank {product['rank']}")
                            if found:
                                # 조기 종료
                                for f in retry_futures:
                                    f.cancel()
                                break
                        else:
                            print(f"  [{timestamp()}] Page {page_num:2d}: ❌ {result.get('error')}")
                            still_failed.append(page_num)
                    except Exception as e:
                        # 타임아웃 등의 예외
                        pass

                # 다음 재시도를 위해 실패 목록 갱신
                failed_pages = still_failed

                if failed_pages and retry_count < max_retries:
                    print(f"  [{timestamp()}] 남은 실패: {len(failed_pages)}개")

            # 최종 실패 페이지 보고
            if failed_pages:
                print(f"\n[{timestamp()}] ⚠️  최종 실패 페이지: {failed_pages}")

    search_time = (datetime.now() - start_time).total_seconds()

    # 트래픽 통계 출력 (배치 모드에서만)
    if use_batch_mode and total_bytes > 0:
        if total_bytes >= 1024 * 1024:
            traffic_str = f"{total_bytes / (1024 * 1024):.2f} MB"
        elif total_bytes >= 1024:
            traffic_str = f"{total_bytes / 1024:.2f} KB"
        else:
            traffic_str = f"{total_bytes} bytes"
        print(f"\n[{timestamp()}] 📊 총 트래픽: {traffic_str}")

    # 쿠키 변경사항 출력
    print_cookie_changes(cookies, all_response_cookies)

    # 실제 순위 계산 (페이지 + URL rank 기준 정렬)
    all_products.sort(key=lambda p: (p['_page'], p.get('rank') or 999))
    for i, product in enumerate(all_products):
        product['actual_rank'] = i + 1

    # 타겟 상품의 실제 순위 찾기
    actual_rank = None
    if found:
        for product in all_products:
            if product['productId'] == args.product_id:
                actual_rank = product['actual_rank']
                break

    # 결과
    print("\n" + "=" * 70)
    print("결과")
    print("=" * 70)

    # coupang_agent_v2 호환 형식의 allocate 정보 (임의 생성)
    import uuid
    allocate_id = str(uuid.uuid4())[:8]
    allocate_uid = f"packet_{cookie_record['id']}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

    report = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'cookie_id': cookie_record['id'],
        'chrome_version': cookie_record['chrome_version'],
        'proxy_ip': cookie_record['proxy_ip'],
        'query': args.query,
        'trace_id': trace_id,
        'target_product_id': args.product_id,
        'search_time': round(search_time, 2),
        'total_products': len(all_products),
        'total_bytes': total_bytes,
        'list_size': 72,
        # coupang_agent_v2 호환 형식
        'allocate': {
            'allocateId': allocate_id,
            'allocateUid': allocate_uid,
            'keyword': args.query,
            'productId': args.product_id,
            'itemId': getattr(args, 'item_id', None),
            'vendorItemId': getattr(args, 'vendor_item_id', None),
            'proxy': {
                'ip': cookie_record['proxy_ip'],
                'url': proxy
            }
        }
    }

    if found:
        match_str = f" [{match_type}]" if match_type else ""
        print(f"\n✅ 상품 발견{match_str}")
        print(f"   페이지: {found['page']}")
        print(f"   URL rank: {found['rank']}")
        print(f"   실제 순위: {actual_rank}등 / {len(all_products)}개")
        print(f"   상품명: {found['name'][:50]}...")
        print(f"\n   URL: https://www.coupang.com{found['url']}")

        report['found'] = True
        report['page'] = found['page']
        report['url_rank'] = found['rank']
        report['actual_rank'] = actual_rank
        report['match_type'] = match_type
        report['product'] = {
            'productId': found['productId'],
            'name': found['name'],
            'url': found['url']
        }

        # 상품 클릭 - 상품 페이지 요청 및 정보 수집
        if not getattr(args, 'no_click', False):
            print(f"\n[{timestamp()}] 상품 클릭...")

            # URL에서 itemId, vendorItemId 추출
            import re
            url = found['url']
            item_id_match = re.search(r'itemId=(\d+)', url)
            vendor_item_id_match = re.search(r'vendorItemId=(\d+)', url)

            product_info = {
                'productId': found['productId'],
                'url': found['url'],
                'rank': found['rank'],
                'itemId': item_id_match.group(1) if item_id_match else None,
                'vendorItemId': vendor_item_id_match.group(1) if vendor_item_id_match else None
            }

            # allocate에도 추출된 ID 반영
            if product_info['itemId']:
                report['allocate']['itemId'] = product_info['itemId']
            if product_info['vendorItemId']:
                report['allocate']['vendorItemId'] = product_info['vendorItemId']

            search_url = f'https://www.coupang.com/np/search?q={quote(args.query)}'
            click_result = product_click(product_info, search_url, cookies, fingerprint, proxy)

            if not click_result['success']:
                print(f"  ❌ 클릭 실패: {click_result.get('error', 'Unknown')}")

            # Cookie Jar: 클릭 응답 쿠키 병합
            if click_result.get('response_cookies'):
                cookies.update(click_result['response_cookies'])
                all_response_cookies.update(click_result['response_cookies'])

            report['click'] = click_result

            # agent 형식 POST 데이터 출력
            if click_result.get('productData'):
                post_data = {
                    'success': True,
                    'allocate': report['allocate'],
                    'result': {
                        'found': True,
                        'page': found['page'],
                        'rank': actual_rank,
                        'productData': click_result['productData']
                    },
                    'executionTime': int(search_time * 1000)
                }
                # print(f"\n  {'─' * 50}")
                # print(f"  📤 POST Data (agent format)")
                # print(f"  {'─' * 50}")
                # print(json.dumps(post_data, indent=2, ensure_ascii=False))
                # print(f"  {'─' * 50}")
    else:
        # 차단 vs 미발견 구분
        if blocked_403:
            print(f"\n🚫 차단됨: {block_error}")
            report['found'] = False
            report['blocked'] = True
            report['block_error'] = block_error
        else:
            print(f"\n❌ 상품 미발견 (검색 {len(all_products)}개 중 타겟 없음)")
            report['found'] = False
            report['blocked'] = False

    report['all_products'] = all_products

    # 리포트 저장
    reports_dir = BASE_DIR / 'reports'
    reports_dir.mkdir(exist_ok=True)
    filename = f"rank_{args.product_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report_path = reports_dir / filename

    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # 오래된 리포트 정리 (최신 10개만 유지)
    rank_files = sorted(reports_dir.glob('rank_*.json'), key=lambda f: f.stat().st_mtime, reverse=True)
    for old_file in rank_files[10:]:
        old_file.unlink()
        print(f"  🗑️ 삭제: {old_file.name}")

    print(f"\n📁 리포트: {report_path}")

    # 쿠키 사용 통계 업데이트
    # 성공 기준: 차단되지 않음 (쿠키가 정상 작동)
    # 상품 미발견은 쿠키 문제가 아니므로 성공으로 처리
    is_success = not blocked_403
    update_cookie_stats(cookie_record['id'], is_success)

    # 쿠키 데이터 업데이트 (응답 쿠키 반영 - 전체 속성 포함)
    if all_response_cookies_full:
        updated_count = update_cookie_data(cookie_record['id'], all_response_cookies_full)
        if updated_count > 0:
            print(f"\n💾 쿠키 DB 업데이트: {updated_count}개 변경됨")

    # 사용 로그 기록
    click_success = report.get('click', {}).get('success', False)
    log_result = {
        'success': not blocked_403,
        'found': bool(found),
        'rank': actual_rank if found else None,
        'click_success': click_success,
        'error': block_error if blocked_403 else ''
    }
    log_id = log_cookie_usage(cookie_record['id'], cookie_record, fingerprint, log_result, current_ip)
    print(f"📝 로그 ID: {log_id}")

    # 마지막 요약 라인
    pl_id = getattr(args, 'pl_id_used', None) or getattr(args, 'pl_id', '-')
    print(f"\n✅ 쿠키:{cookie_record['id']} | PL:{pl_id} | 로그:{log_id}")

    return report
