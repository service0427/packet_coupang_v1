"""
검색 모듈 - curl-cffi

Coupang 상품 검색 및 순위 확인
"""

from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor, as_completed

from work.request import make_request, parse_response_cookies, generate_trace_id, timestamp
from extractor.search_extractor import ProductExtractor


def fetch_page(page_num, query, trace_id, cookies, tls_profile, proxy, save_html=False, max_retries=2):
    """단일 페이지 검색 (TLS 에러 시 재시도)

    Args:
        page_num: 페이지 번호
        query: 검색어
        trace_id: 쿠팡 traceId
        cookies: 쿠키 딕셔너리
        tls_profile: TLS 프로필 레코드 (tls_profiles 테이블)
        proxy: 프록시 URL
        save_html: HTML 원본 저장 여부
        max_retries: TLS 에러 시 재시도 횟수 (기본: 2)

    Returns:
        dict: {page, success, products, size, error, response_cookies, response_cookies_full, html, retried}
    """
    import time

    url = f'https://www.coupang.com/np/search?q={quote(query)}&traceId={trace_id}&channel=user&listSize=72&page={page_num}'

    # 재시도 대상 에러 패턴
    # 동일 프록시로 다른 페이지가 성공하면 일시적 네트워크 문제일 수 있음
    RETRYABLE_ERRORS = [
        'curl: (35)',           # TLS connect error
        'TLS connect error',
        'TLSV1_ALERT',
        'SSL routines',
        'curl: (56)',           # Recv failure
        'curl: (28)',           # Timeout
        'timed out',
        'curl: (7)',            # Connection refused
        'Could not connect',
        'curl: (92)',           # HTTP/2 stream error
        'HTTP/2 stream',
    ]

    last_error = None
    retried = 0

    for attempt in range(max_retries + 1):
        try:
            resp = make_request(url, cookies, tls_profile, proxy)
            size = len(resp.content)

            response_cookies, response_cookies_full = parse_response_cookies(resp)

            if resp.status_code == 200 and size > 5000:
                html_text = resp.text
                result = ProductExtractor.extract_products_from_html(html_text)

                # "검색결과 없음" 페이지 감지 (쿠팡 정상 응답이지만 상품 없음)
                is_no_results_page = (
                    '에 대한 검색결과가 없습니다' in html_text or
                    '검색결과가 없습니다' in html_text
                )

                return {
                    'page': page_num,
                    'success': True,
                    'products': result['ranking'],
                    'size': size,
                    'response_cookies': response_cookies,
                    'response_cookies_full': response_cookies_full,
                    'html': html_text if save_html else None,
                    'is_no_results_page': is_no_results_page,
                    'retried': retried
                }
            elif resp.status_code == 403:
                return {
                    'page': page_num,
                    'success': False,
                    'products': [],
                    'error': 'BLOCKED_403',
                    'response_cookies': response_cookies,
                    'response_cookies_full': response_cookies_full,
                    'html': None,
                    'retried': retried
                }
            elif size <= 5000:
                return {
                    'page': page_num,
                    'success': False,
                    'products': [],
                    'error': f'CHALLENGE_{size}B',
                    'response_cookies': response_cookies,
                    'response_cookies_full': response_cookies_full,
                    'html': None,
                    'retried': retried
                }
            else:
                return {
                    'page': page_num,
                    'success': False,
                    'products': [],
                    'error': f'STATUS_{resp.status_code}',
                    'response_cookies': response_cookies,
                    'response_cookies_full': response_cookies_full,
                    'html': None,
                    'retried': retried
                }

        except Exception as e:
            error_msg = str(e)[:150]
            last_error = error_msg

            # 재시도 가능한 에러인지 확인
            is_retryable = any(pattern in error_msg for pattern in RETRYABLE_ERRORS)

            if is_retryable and attempt < max_retries:
                retried += 1
                time.sleep(0.5)  # 짧은 대기 후 재시도
                continue

            # 재시도 불가능하거나 최대 재시도 도달
            return {
                'page': page_num,
                'success': False,
                'products': [],
                'error': error_msg,
                'response_cookies': {},
                'response_cookies_full': [],
                'html': None,
                'retried': retried
            }

    # max_retries 도달 (모든 재시도 실패)
    return {
        'page': page_num,
        'success': False,
        'products': [],
        'error': last_error or 'MAX_RETRIES',
        'response_cookies': {},
        'response_cookies_full': [],
        'html': None,
        'retried': retried
    }


def _match_product(product, target_product_id, target_item_id=None, target_vendor_item_id=None):
    """상품 매칭 우선순위 체크

    우선순위:
    1. product_id + item_id + vendor_item_id (완전 매칭)
    2. product_id + vendor_item_id
    3. product_id + item_id
    4. product_id만
    5. vendor_item_id만
    6. item_id만

    Returns:
        tuple: (매칭 여부, 매칭 타입) 또는 (False, None)
    """
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


def search_product(query, target_product_id, cookies, tls_profile, proxy,
                   target_item_id=None, target_vendor_item_id=None,
                   max_page=13, verbose=True, save_html=False,
                   total_timeout=20):
    """상품 검색 (점진적 배치)

    배치 전략:
    - Tier 1: 1페이지만 (대부분 여기서 발견)
    - Tier 2: 2-5페이지 동시 (미발견 시)
    - Tier 3: 6-13페이지 동시 (미발견 시)

    매칭 우선순위:
    1. product_id + item_id + vendor_item_id (완전 매칭)
    2. product_id + vendor_item_id
    3. product_id + item_id
    4. product_id만
    5. vendor_item_id만
    6. item_id만

    Args:
        query: 검색어
        target_product_id: 타겟 상품 ID
        cookies: 쿠키 딕셔너리
        tls_profile: TLS 프로필 레코드 (tls_profiles 테이블)
        proxy: 프록시 URL
        target_item_id: 타겟 아이템 ID (선택)
        target_vendor_item_id: 타겟 벤더 아이템 ID (선택)
        max_page: 최대 페이지
        verbose: 상세 출력
        save_html: HTML 저장 여부 (스크린샷용)
        total_timeout: 전체 타임아웃 (초, 기본 20초)

    Returns:
        dict: {
            found: 발견 상품 정보 또는 None,
            id_match_type: 매칭 타입 (full_match, product_vendor, product_item, product_only, vendor_only, item_only),
            all_products: 모든 상품 리스트,
            blocked: 차단 여부,
            block_error: 차단 에러 메시지,
            total_bytes: 총 트래픽,
            response_cookies: 응답 쿠키,
            response_cookies_full: 응답 쿠키 (전체 속성),
            found_html: 상품 발견 페이지 HTML (save_html=True인 경우)
        }
    """
    import time
    start_time = time.time()

    trace_id = generate_trace_id()
    if verbose:
        print(f"\n[{timestamp()}] 검색 중... (traceId: {trace_id})")

    found = None
    found_html = None  # 상품 발견 페이지 HTML
    id_match_type = None  # 매칭 타입
    all_products = []
    blocked = False
    block_error = ''
    page_errors = []  # 각 페이지별 에러 수집
    page_counts = {}  # 페이지별 상품 수 {1: 72, 2: 72, ...}
    total_bytes = 0
    all_response_cookies = {}
    all_response_cookies_full = []
    pages_searched = 0  # 성공적으로 검색한 페이지 수

    # 배치 정의 (빈 배치 제외)
    batches = [
        [1],                    # Tier 1: 1페이지 단독
        [2, 3, 4, 5],           # Tier 2: 2-5페이지 동시
        list(range(6, min(max_page + 1, 14)))  # Tier 3: 6-13페이지 동시
    ]
    batches = [b for b in batches if b]  # 빈 배치 제거

    cookies_ref = cookies.copy()  # 쿠키 업데이트용

    # 검색 결과 없음 플래그 (1페이지 0개면 조기 종료)
    no_results = False

    for batch_idx, pages in enumerate(batches):
        if found or blocked or no_results:
            break

        # 전체 타임아웃 체크
        elapsed = time.time() - start_time
        if elapsed >= total_timeout:
            blocked = True
            block_error = f'TOTAL_TIMEOUT_{int(elapsed)}s'
            if verbose:
                print(f"  🛑 전체 타임아웃 ({int(elapsed)}초) → 조기 종료")
            break

        if verbose:
            tier_name = ['1페이지', '2-5페이지', f'6-{max_page}페이지'][batch_idx]
            print(f"  Tier {batch_idx + 1}: {tier_name}")

        with ThreadPoolExecutor(max_workers=len(pages)) as executor:
            futures = {
                executor.submit(
                    fetch_page, p, query, trace_id, cookies_ref, tls_profile, proxy, save_html
                ): p for p in pages
            }

            for future in as_completed(futures):
                result = future.result()

                # 응답 쿠키 수집 (필수)
                all_response_cookies.update(result['response_cookies'])
                cookies_ref.update(result['response_cookies'])  # 다음 요청에 반영
                all_response_cookies_full.extend(result['response_cookies_full'])

                total_bytes += result.get('size', 0)

                if result['success']:
                    pages_searched = max(pages_searched, result['page'])  # 최대 페이지 추적
                    # 페이지별 (상품 수, 재시도 횟수)
                    retried = result.get('retried', 0)
                    page_counts[result['page']] = (len(result['products']), retried)

                    for product in result['products']:
                        product['_page'] = result['page']
                        all_products.append(product)

                        if not found:
                            matched, match_type = _match_product(
                                product, target_product_id, target_item_id, target_vendor_item_id
                            )
                            if matched:
                                found = product
                                found['page'] = result['page']
                                id_match_type = match_type
                                # 스크린샷용 HTML 저장
                                if save_html and result.get('html'):
                                    found_html = result['html']
                                if verbose:
                                    print(f"  [{timestamp()}] ✅ 발견! Page {result['page']}, Rank {product['rank']} ({match_type})")
                                # 상품 발견 시 현재 배치의 나머지 요청 취소 및 루프 종료
                                for f in futures:
                                    f.cancel()
                                break  # for product 루프 종료

                    # 상품 발견 시 for future 루프 종료
                    if found:
                        break

                    if verbose:
                        retry_info = f" (retry:{result['retried']})" if result.get('retried', 0) > 0 else ""
                        print(f"    Page {result['page']:2d}: {len(result['products'])}개{retry_info}")
                else:
                    error = result.get('error', '')
                    retried = result.get('retried', 0)
                    page_counts[result['page']] = (-1, retried)  # 에러 페이지는 -1로 표시
                    if error:
                        page_errors.append({'page': result['page'], 'error': error, 'retried': result.get('retried', 0)})
                    if verbose:
                        retry_info = f" (retry:{result.get('retried', 0)})" if result.get('retried', 0) > 0 else ""
                        print(f"    Page {result['page']:2d}: ❌ {error}{retry_info}")

                    # HTTP/2 스트림 에러도 차단으로 처리 (가장 흔한 차단 방식)
                    if (error == 'BLOCKED_403' or
                        error.startswith('CHALLENGE_') or
                        'HTTP/2 stream' in error or
                        'curl: (92)' in error):
                        blocked = True
                        if 'HTTP/2 stream' in error or 'curl: (92)' in error:
                            block_error = 'HTTP2_PROTOCOL_ERROR'
                        else:
                            block_error = error
                        for f in futures:
                            f.cancel()
                        break

                    # 1페이지 타임아웃 시 조기 종료 (프록시 문제)
                    if (batch_idx == 0 and result['page'] == 1 and
                        ('timed out' in error.lower() or 'curl: (28)' in error or
                         'Could not connect' in error or 'curl: (7)' in error)):
                        blocked = True
                        block_error = 'PROXY_TIMEOUT'
                        if verbose:
                            print(f"  🛑 1페이지 타임아웃 → 조기 종료")
                        for f in futures:
                            f.cancel()
                        break

        # 배치 완료 후 실패한 페이지 재시도 (found/blocked가 아닌 경우만)
        if not found and not blocked:
            # 타임아웃 체크
            elapsed = time.time() - start_time
            if elapsed >= total_timeout:
                blocked = True
                block_error = f'TOTAL_TIMEOUT_{int(elapsed)}s'
                if verbose:
                    print(f"  🛑 전체 타임아웃 ({int(elapsed)}초) → 재시도 생략")
            else:
                # 현재 배치에서 실패한 페이지 찾기 (page_counts에서 -1인 페이지)
                failed_pages = [p for p in pages if page_counts.get(p, (0, 0))[0] == -1]

                if failed_pages and verbose:
                    print(f"  🔄 실패 페이지 재시도: {failed_pages}")

                # 실패 페이지 순차적으로 재시도 (1번씩)
                for retry_page in failed_pages:
                    # 재시도 전 타임아웃 체크
                    elapsed = time.time() - start_time
                    if found or blocked or elapsed >= total_timeout:
                        if elapsed >= total_timeout:
                            blocked = True
                            block_error = f'TOTAL_TIMEOUT_{int(elapsed)}s'
                        break

                    result = fetch_page(retry_page, query, trace_id, cookies_ref, tls_profile, proxy, save_html, max_retries=1)

                    # 응답 쿠키 수집
                    all_response_cookies.update(result['response_cookies'])
                    cookies_ref.update(result['response_cookies'])
                    all_response_cookies_full.extend(result['response_cookies_full'])
                    total_bytes += result.get('size', 0)

                    if result['success']:
                        pages_searched = max(pages_searched, result['page'])
                        retried = result.get('retried', 0) + page_counts.get(retry_page, (0, 0))[1] + 1  # 기존 재시도 + 배치 재시도
                        page_counts[result['page']] = (len(result['products']), retried)

                        for product in result['products']:
                            product['_page'] = result['page']
                            all_products.append(product)

                            if not found:
                                matched, match_type = _match_product(
                                    product, target_product_id, target_item_id, target_vendor_item_id
                                )
                                if matched:
                                    found = product
                                    found['page'] = result['page']
                                    id_match_type = match_type
                                    if save_html and result.get('html'):
                                        found_html = result['html']
                                    if verbose:
                                        print(f"  [{timestamp()}] ✅ 발견! Page {result['page']}, Rank {product['rank']} ({match_type}) [재시도]")
                                    break

                        if verbose and not found:
                            print(f"    Page {result['page']:2d}: {len(result['products'])}개 (재시도 성공)")
                    else:
                        # 재시도도 실패 - 기존 에러 유지, 재시도 횟수만 업데이트
                        prev_retried = page_counts.get(retry_page, (0, 0))[1]
                        page_counts[retry_page] = (-1, prev_retried + 1)
                        if verbose:
                            print(f"    Page {retry_page:2d}: ❌ 재시도 실패")

        # Tier 1 완료 후 검색 결과가 0개면 조기 종료
        # no_results는 쿠팡이 명시적으로 "검색결과 없음"을 반환한 경우에만 True
        # 에러(타임아웃 등)로 인한 0개는 no_results = False
        if batch_idx == 0 and len(all_products) == 0 and not blocked:
            # 에러 없이 성공한 요청 중 "검색결과 없음" 페이지가 있는지 확인
            is_coupang_no_results = any(
                f.result().get('is_no_results_page', False)
                for f in futures if f.done() and not f.cancelled() and f.result().get('success')
            )

            if is_coupang_no_results:
                no_results = True  # 쿠팡이 명시적으로 검색결과 없음 반환
                if verbose:
                    print(f"  ⚠️ 쿠팡 검색결과 없음 - 조기 종료")
            else:
                no_results = False  # 에러로 인한 0개 (타임아웃 등)
                if verbose:
                    print(f"  ⚠️ 검색 결과 없음 - 조기 종료")

    # 실제 순위 계산
    all_products.sort(key=lambda p: (p['_page'], p.get('rank') or 999))
    for i, product in enumerate(all_products):
        product['actual_rank'] = i + 1

    actual_rank = None
    if found:
        # found 상품의 actual_rank 찾기 (uniqueKey로 매칭)
        found_key = found.get('uniqueKey')
        for product in all_products:
            if product.get('uniqueKey') == found_key:
                actual_rank = product['actual_rank']
                break

    # 페이지별 상품 수 정렬 (1페이지부터)
    sorted_page_counts = dict(sorted(page_counts.items()))

    # 에러 페이지(-1)가 1개라도 있으면 blocked 처리 (상품 미발견 시에만)
    # 완성도를 맞추지 못하면 실패 - 에러 페이지에 상품이 있었을 수 있음
    # page_counts 값은 (count, retried) 튜플
    # count: 0 = 정상 응답이지만 상품 없음, -1 = 에러
    if not found and not blocked and page_counts:
        error_pages = sum(1 for v in page_counts.values() if v[0] == -1)
        total_pages = len(page_counts)
        if error_pages > 0:
            blocked = True
            block_error = f'INCOMPLETE_{error_pages}/{total_pages}'

    # 튜플을 문자열로 변환: (63, 0) -> "63", (63, 2) -> "63(r2)", (-1, 1) -> "-1(r1)"
    page_counts_str = {}
    for page, (count, retried) in sorted_page_counts.items():
        if retried > 0:
            page_counts_str[page] = f"{count}(r{retried})"
        else:
            page_counts_str[page] = str(count)

    return {
        'found': found,
        'actual_rank': actual_rank,
        'id_match_type': id_match_type,  # 매칭 타입 추가
        'all_products': all_products,
        'blocked': blocked,
        'block_error': block_error,
        'page_errors': page_errors,
        'page_counts': page_counts_str,  # 페이지별 상품 수 {1: "72", 2: "72(r1)", 13: "-1(r2)"}
        'total_bytes': total_bytes,
        'trace_id': trace_id,
        'response_cookies': all_response_cookies,
        'response_cookies_full': all_response_cookies_full,
        'found_html': found_html,
        'no_results': no_results,  # 쿠팡이 "검색결과 없음" 응답 (정상적인 미발견)
        'pages_searched': pages_searched  # 성공적으로 검색 완료한 최대 페이지
    }


if __name__ == '__main__':
    print("검색 모듈 테스트")
    print("=" * 60)
    print("사용법: search.py는 직접 실행하지 않고 모듈로 import하여 사용")
