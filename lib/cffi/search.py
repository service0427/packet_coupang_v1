"""
검색 모듈 - curl-cffi

Coupang 상품 검색 및 순위 확인
"""

import random
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor, as_completed

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from cffi.request import make_request, parse_response_cookies, generate_trace_id, timestamp
from extractor.search_extractor import ProductExtractor


def fetch_page(page_num, query, trace_id, cookies, fingerprint, proxy, save_html=False):
    """단일 페이지 검색

    Args:
        page_num: 페이지 번호
        query: 검색어
        trace_id: 쿠팡 traceId
        cookies: 쿠키 딕셔너리
        fingerprint: 핑거프린트 레코드
        proxy: 프록시 URL
        save_html: HTML 원본 저장 여부

    Returns:
        dict: {page, success, products, size, error, response_cookies, response_cookies_full, html}
    """
    url = f'https://www.coupang.com/np/search?q={quote(query)}&traceId={trace_id}&channel=user&listSize=72&page={page_num}'

    try:
        resp = make_request(url, cookies, fingerprint, proxy)
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
                'is_no_results_page': is_no_results_page
            }
        elif resp.status_code == 403:
            return {
                'page': page_num,
                'success': False,
                'products': [],
                'error': 'BLOCKED_403',
                'response_cookies': response_cookies,
                'response_cookies_full': response_cookies_full,
                'html': None
            }
        elif size <= 5000:
            return {
                'page': page_num,
                'success': False,
                'products': [],
                'error': f'CHALLENGE_{size}B',
                'response_cookies': response_cookies,
                'response_cookies_full': response_cookies_full,
                'html': None
            }
        else:
            return {
                'page': page_num,
                'success': False,
                'products': [],
                'error': f'STATUS_{resp.status_code}',
                'response_cookies': response_cookies,
                'response_cookies_full': response_cookies_full,
                'html': None
            }

    except Exception as e:
        return {
            'page': page_num,
            'success': False,
            'products': [],
            'error': str(e)[:150],
            'response_cookies': {},
            'response_cookies_full': [],
            'html': None
        }


def search_product(query, target_product_id, cookies, fingerprint, proxy,
                   max_page=13, verbose=True, save_html=False):
    """상품 검색 (점진적 배치)

    배치 전략:
    - Tier 1: 1페이지만 (대부분 여기서 발견)
    - Tier 2: 2-3페이지 (미발견 시)
    - Tier 3: 4-13페이지 (미발견 시)

    Args:
        query: 검색어
        target_product_id: 타겟 상품 ID
        cookies: 쿠키 딕셔너리
        fingerprint: 핑거프린트 레코드
        proxy: 프록시 URL
        max_page: 최대 페이지
        verbose: 상세 출력
        save_html: HTML 저장 여부 (스크린샷용)

    Returns:
        dict: {
            found: 발견 상품 정보 또는 None,
            all_products: 모든 상품 리스트,
            blocked: 차단 여부,
            block_error: 차단 에러 메시지,
            total_bytes: 총 트래픽,
            response_cookies: 응답 쿠키,
            response_cookies_full: 응답 쿠키 (전체 속성),
            found_html: 상품 발견 페이지 HTML (save_html=True인 경우)
        }
    """
    trace_id = generate_trace_id()
    if verbose:
        print(f"\n[{timestamp()}] 검색 중... (traceId: {trace_id})")

    found = None
    found_html = None  # 상품 발견 페이지 HTML
    all_products = []
    blocked = False
    block_error = ''
    page_errors = []  # 각 페이지별 에러 수집
    total_bytes = 0
    all_response_cookies = {}
    all_response_cookies_full = []

    # 배치 정의 (빈 배치 제외)
    batches = [
        [1],                    # Tier 1
        [2, 3],                 # Tier 2
        list(range(4, min(max_page + 1, 14)))  # Tier 3
    ]
    batches = [b for b in batches if b]  # 빈 배치 제거

    cookies_ref = cookies.copy()  # 쿠키 업데이트용

    # 검색 결과 없음 플래그 (1페이지 0개면 조기 종료)
    no_results = False

    for batch_idx, pages in enumerate(batches):
        if found or blocked or no_results:
            break

        if verbose:
            tier_name = ['1페이지', '2-3페이지', f'4-{max_page}페이지'][batch_idx]
            print(f"  Tier {batch_idx + 1}: {tier_name}")

        with ThreadPoolExecutor(max_workers=len(pages)) as executor:
            futures = {
                executor.submit(
                    fetch_page, p, query, trace_id, cookies_ref, fingerprint, proxy, save_html
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
                    for product in result['products']:
                        product['_page'] = result['page']
                        all_products.append(product)

                        if product['productId'] == target_product_id and not found:
                            found = product
                            found['page'] = result['page']
                            # 스크린샷용 HTML 저장
                            if save_html and result.get('html'):
                                found_html = result['html']
                            if verbose:
                                print(f"  [{timestamp()}] ✅ 발견! Page {result['page']}, Rank {product['rank']}")

                    if verbose and not found:
                        print(f"    Page {result['page']:2d}: {len(result['products'])}개")
                else:
                    error = result.get('error', '')
                    if error:
                        page_errors.append({'page': result['page'], 'error': error})
                    if verbose:
                        print(f"    Page {result['page']:2d}: ❌ {error}")

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
        for product in all_products:
            if product['productId'] == target_product_id:
                actual_rank = product['actual_rank']
                break

    return {
        'found': found,
        'actual_rank': actual_rank,
        'all_products': all_products,
        'blocked': blocked,
        'block_error': block_error,
        'page_errors': page_errors,
        'total_bytes': total_bytes,
        'trace_id': trace_id,
        'response_cookies': all_response_cookies,
        'response_cookies_full': all_response_cookies_full,
        'found_html': found_html,
        'no_results': no_results  # 쿠팡이 "검색결과 없음" 응답 (정상적인 미발견)
    }


if __name__ == '__main__':
    print("검색 모듈 테스트")
    print("=" * 60)
    print("사용법: search.py는 직접 실행하지 않고 모듈로 import하여 사용")
