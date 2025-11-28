"""
작업 할당 API 기반 검색 실행

API:
  - 할당: GET  http://mkt.techb.kr:29998/api/work/allocate/rank
  - 결과: POST http://mkt.techb.kr:29998/api/work/result/rank

결과 보고 시나리오:
  1. 순위 발견: status='success', rank=N
  2. 순위 미발견: status='success', rank=0
  3. 순위체크 오류 (상품정보만): status='success', rank=None, info={...}
  4. 프록시 오류: status='failed'
"""

import json
import signal
import threading
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor, as_completed

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from common.proxy import get_bound_cookie, get_subnet, update_cookie_stats, update_cookie_data
from common.fingerprint import get_random_fingerprint
from cffi.search import search_product
from cffi.click import click_product, extract_ids_from_url
from extractor.filter_extractor import DEFAULT_FILTER_CATEGORIES, find_searchable_category
from cffi.request import timestamp, make_request, parse_response_cookies
from cffi.work_api import allocate_work, report_result, build_info_data
from extractor.detail_extractor import extract_product_detail, to_api_response
from screenshot import save_html_with_urls, take_screenshot_from_saved

# 프로젝트 루트
PROJECT_ROOT = Path(__file__).parent.parent.parent


def direct_access_product(product_id, item_id, vendor_item_id, cookies, fingerprint, proxy, save_html=False, verbose=True):
    """상품 URL 직접 접속"""
    if item_id and vendor_item_id:
        url = f'https://www.coupang.com/vp/products/{product_id}?itemId={item_id}&vendorItemId={vendor_item_id}'
    else:
        url = f'https://www.coupang.com/vp/products/{product_id}'

    if verbose:
        print(f"\n[{timestamp()}] 직접 접속...")
        print(f"  URL: {url}")

    try:
        resp = make_request(url, cookies, fingerprint, proxy, referer='https://www.coupang.com/')
        size = len(resp.content)
        response_cookies, response_cookies_full = parse_response_cookies(resp)
        html_content = resp.text

        if verbose:
            print(f"  Status: {resp.status_code} | Size: {size:,} bytes")

        # HTML 저장 (사이즈와 관계없이 항상 저장)
        if save_html:
            html_dir = PROJECT_ROOT / 'html'
            html_dir.mkdir(parents=True, exist_ok=True)
            html_path = html_dir / f'{product_id}.html'
            html_path.write_text(html_content, encoding='utf-8')
            if verbose:
                print(f"  📄 HTML 저장: {html_path}")

        if size > 100000:
            product_data = extract_product_detail(html_content)
            return {
                'success': True,
                'productData': product_data,
                'response_cookies_full': response_cookies_full,
                'size': size,
                'html': html_content
            }
        else:
            return {
                'success': False,
                'error': f'INVALID_RESPONSE_{size}B',
                'response_cookies_full': response_cookies_full,
                'size': size,
                'html': html_content
            }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)[:100],
            'response_cookies_full': [],
            'size': 0
        }


def run_work(args):
    """작업 실행"""
    work_type = getattr(args, 'type', 'rank')

    print("=" * 70)
    print(f"작업 할당 검색 [{work_type}]")
    print("=" * 70)

    # 1. 작업 할당 받기
    work_id = getattr(args, 'id', None)
    if work_id:
        print(f"\n📥 작업 조회 (ID: {work_id}, type: {work_type})...")
    else:
        print(f"\n📥 작업 할당 요청 (type: {work_type})...")

    allocation = allocate_work(work_id=work_id, work_type=work_type)
    if not allocation:
        print("❌ 작업 없음" if not work_id else f"❌ ID {work_id} 작업 없음")
        return None

    # 할당 응답 JSON 출력
    print(f"{'─' * 60}")
    print(json.dumps(allocation, ensure_ascii=False, indent=2))
    print(f"{'─' * 60}")

    progress_id = allocation['progress_id']
    keyword = allocation['keyword']
    product_id = str(allocation['product_id'])
    item_id = allocation.get('item_id')
    vendor_item_id = allocation.get('vendor_item_id')
    allocated_proxy = allocation.get('proxy')
    external_ip = allocation.get('external_ip')
    need_screenshot = allocation.get('shot_data', False)

    # 2. 할당된 프록시의 서브넷에 맞는 쿠키 찾기
    if external_ip:
        target_subnet = get_subnet(external_ip)
        print(f"\n🔍 쿠키 탐색 (서브넷: {target_subnet}.*)")

        bound = get_bound_cookie(min_remain=30, max_age_minutes=60, target_subnet=target_subnet)
        if not bound:
            # 서브넷 매칭 실패 시 일반 쿠키 사용
            print(f"  ⚠️ 서브넷 매칭 쿠키 없음 - 일반 쿠키 사용")
            bound = get_bound_cookie(min_remain=30, max_age_minutes=60)

        if not bound:
            print("❌ 사용 가능한 쿠키 없음")
            report_result(progress_id, allocated_proxy, external_ip, 'failed', work_type=work_type)
            return None

        cookie_record = bound['cookie_record']
        cookies = bound['cookies']

        # 할당된 프록시 사용 (API에서 지정)
        proxy = f"socks5://{allocated_proxy}"

        match_type = 'exact' if get_subnet(cookie_record['proxy_ip']) == target_subnet else 'fallback'
        print(f"  ✅ 쿠키 ID: {cookie_record['id']} ({match_type})")
        print(f"     쿠키 IP: {cookie_record['proxy_ip']}")
    else:
        # external_ip 없으면 자동 바인딩
        bound = get_bound_cookie(min_remain=30, max_age_minutes=60)
        if not bound:
            print("❌ IP 바인딩 매칭 실패")
            report_result(progress_id, allocated_proxy or '', external_ip or '', 'failed', work_type=work_type)
            return None

        cookie_record = bound['cookie_record']
        cookies = bound['cookies']
        proxy = bound['proxy']
        print(f"  ✅ 쿠키 ID: {cookie_record['id']} (auto)")

    # 3. 핑거프린트
    fingerprint = get_random_fingerprint(verified_only=True)
    if not fingerprint:
        print("❌ 핑거프린트 없음")
        report_result(progress_id, allocated_proxy or '', external_ip or '', 'failed', work_type=work_type)
        return None

    print(f"\n타겟: {product_id}")
    print(f"검색어: {keyword}")
    print(f"TLS: Chrome {fingerprint['chrome_major']}")
    print(f"프록시: {proxy}")
    print("=" * 70)

    # 4. 검색 실행
    start_time = datetime.now()
    max_page = args.max_page if hasattr(args, 'max_page') else 13

    result = search_product(
        keyword,
        product_id,
        cookies,
        fingerprint,
        proxy,
        max_page=max_page,
        verbose=True,
        save_html=need_screenshot
    )

    search_time = (datetime.now() - start_time).total_seconds()

    # 5. 결과 처리
    print("\n" + "=" * 70)
    print("결과")
    print("=" * 70)

    found = result['found']
    blocked = result['blocked']

    # 결과 보고 변수
    report_rank = None
    report_info = None

    if found:
        print(f"\n✅ 상품 발견")
        print(f"   페이지: {found['page']}")
        print(f"   순위: {result['actual_rank']}등 / {len(result['all_products'])}개")

        report_rank = result['actual_rank']

        # 스크린샷 처리
        if need_screenshot and result.get('found_html'):
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            screenshot_dir = PROJECT_ROOT / 'screenshot'
            screenshot_dir.mkdir(parents=True, exist_ok=True)
            html_path = screenshot_dir / f'work_{progress_id}_{ts}.html'

            save_result = save_html_with_urls(
                result['found_html'],
                html_path,
                metadata={
                    'progress_id': progress_id,
                    'keyword': keyword,
                    'product_id': product_id,
                    'rank': result['actual_rank'],
                    'page': found['page'],
                    'timestamp': ts
                }
            )
            print(f"\n📄 HTML 저장: {save_result['html_path']}")

            print(f"📸 스크린샷 생성 중...")
            ss_result = take_screenshot_from_saved(html_path)
            if ss_result['success']:
                print(f"   ✅ {ss_result['path']}")

        # 클릭
        if not getattr(args, 'no_click', False):
            print(f"\n[{timestamp()}] 상품 클릭...")

            ids = extract_ids_from_url(found['url'])
            product_info = {
                'productId': found['productId'],
                'url': found['url'],
                'rank': found['rank'],
                'itemId': ids['itemId'],
                'vendorItemId': ids['vendorItemId']
            }

            search_url = f'https://www.coupang.com/np/search?q={quote(keyword)}'
            click_result = click_product(
                product_info, search_url, cookies, fingerprint, proxy,
                save_html=True  # HTML 저장
            )

            if click_result['success']:
                # 클릭 성공 시 상품 정보 추출
                if click_result.get('productData'):
                    report_info = build_info_data(to_api_response(click_result['productData']))
            else:
                print(f"  ❌ 클릭 실패: {click_result.get('error')}")

    elif blocked:
        # 프록시 차단 = failed
        print(f"\n🚫 차단됨: {result['block_error']}")

    else:
        # 미발견 vs 검색오류 구분
        search_count = len(result['all_products'])
        page_errors = result.get('page_errors', [])
        no_results = result.get('no_results', False)  # 쿠팡 "검색결과 없음" 응답

        if no_results:
            # 쿠팡이 "검색결과 없음" 응답 = 정상적인 미발견
            print(f"\n❌ 상품 미발견 (쿠팡 검색결과 없음)")
            report_rank = 0
        elif search_count == 0 and page_errors:
            # 검색된 상품 0개 + 에러 있음 = 프록시 오류 (직접 접속 시도 안함)
            print(f"\n⚠️ 검색 오류 → 프록시 실패 처리 (에러: {len(page_errors)}건)")
            for err in page_errors[:3]:  # 처음 3개만 출력
                print(f"   - P{err['page']}: {err['error'][:50]}")
            blocked = True  # 바로 failed 처리
        else:
            # 검색했지만 타겟 상품 없음 = rank 0
            print(f"\n❌ 상품 미발견 ({search_count}개 검색)")
            report_rank = 0

        # 직접 접속으로 상품 정보 수집 (검색 오류가 아닐 때만)
        if not blocked and not getattr(args, 'no_click', False):
            direct_result = direct_access_product(
                product_id, item_id, vendor_item_id,
                cookies, fingerprint, proxy,
                save_html=True  # HTML 저장
            )

            if direct_result['success']:
                product_data = direct_result.get('productData', {})
                if product_data:
                    print(f"\n📦 직접 접속 성공")
                    api_data = to_api_response(product_data)
                    report_info = build_info_data(api_data)

            if direct_result.get('response_cookies_full'):
                result['response_cookies_full'].extend(direct_result['response_cookies_full'])

    # 6. 쿠키 통계 업데이트
    is_success = not blocked
    update_cookie_stats(cookie_record['id'], is_success)

    updated = update_cookie_data(cookie_record['id'], result.get('response_cookies_full', []))
    if updated > 0:
        print(f"\n💾 쿠키 업데이트: {updated}개")

    # 카테고리 필터 지원 여부 로그
    if report_info and report_info.get('categories'):
        cats = report_info['categories']
        searchable = find_searchable_category(cats, DEFAULT_FILTER_CATEGORIES)
        if searchable:
            print(f"\n🏷️ 카테고리: {searchable['name']} ({searchable['id']}) - 검색필터 지원 ✅")
        else:
            cat_names = ' > '.join([c['name'] for c in cats[:3]])
            print(f"\n🏷️ 카테고리: {cat_names} - 검색필터 미지원 ❌")

    # 7. 결과 보고 (work_api 모듈 사용)
    print(f"\n📤 결과 보고...")

    # status 결정: blocked면 failed, 아니면 success
    report_status = 'failed' if blocked else 'success'

    # 보고할 payload 구성
    report_payload = {
        'progress_id': progress_id,
        'proxy': allocated_proxy or '',
        'external_ip': external_ip or '',
        'status': report_status
    }
    if report_rank is not None:
        report_payload['rank'] = report_rank
    if report_info:
        report_payload['info'] = report_info

    # 요청 payload 출력
    print(f"{'─' * 60}")
    print(json.dumps(report_payload, ensure_ascii=False, indent=2))
    print(f"{'─' * 60}")

    report_resp = report_result(
        progress_id=progress_id,
        proxy=allocated_proxy or '',
        external_ip=external_ip or '',
        status=report_status,
        rank=report_rank,
        info=report_info,
        work_type=work_type
    )

    if report_resp:
        print(f"   ✅ 응답:")
        print(f"{'─' * 60}")
        print(json.dumps(report_resp, ensure_ascii=False, indent=2))
        print(f"{'─' * 60}")
    else:
        print(f"   ⚠️ 보고 실패")

    # 트래픽
    total_bytes = result.get('total_bytes', 0)
    if total_bytes > 0:
        traffic_str = f"{total_bytes / 1024:.2f} KB" if total_bytes < 1024 * 1024 else f"{total_bytes / (1024 * 1024):.2f} MB"
        print(f"\n📊 트래픽: {traffic_str} | 시간: {search_time:.1f}초")

    print(f"\n✅ Progress:{progress_id} | 쿠키:{cookie_record['id']} | TLS:{fingerprint['chrome_major']}")

    return {
        'progress_id': progress_id,
        'found': bool(found),
        'blocked': blocked,
        'rank': result.get('actual_rank'),
        'cookie_id': cookie_record['id']
    }




# ============================================================================
# 필터 URL 탐색 모드
# ============================================================================

def search_with_filter(keyword, target_product_id, min_price, max_price, cookies, fingerprint, proxy, page=1, component=None):
    """필터 적용 검색

    Args:
        keyword: 검색어
        target_product_id: 찾을 상품 ID
        min_price: 최소 가격
        max_price: 최대 가격
        cookies: 쿠키 딕셔너리
        fingerprint: 핑거프린트 레코드
        proxy: 프록시 URL
        page: 페이지 번호
        component: 카테고리 ID (component 파라미터)

    Returns:
        dict: {found, rank, page, total_products, url, error}
    """
    from extractor.search_extractor import ProductExtractor

    component_str = component if component else ''
    url = (
        f"https://www.coupang.com/np/search?"
        f"listSize=36&filterType=&rating=0&isPriceRange=false"
        f"&minPrice={min_price}&maxPrice={max_price}"
        f"&component={component_str}&sorter=scoreDesc&brand=&offerCondition="
        f"&filter=&fromComponent=N&channel=user"
        f"&selectedPlpKeepFilter=&page={page}"
        f"&q={quote(keyword)}"
    )

    try:
        resp = make_request(url, cookies, fingerprint, proxy)
        size = len(resp.content)

        if resp.status_code == 200 and size > 5000:
            html_text = resp.text
            result = ProductExtractor.extract_products_from_html(html_text)
            products = result['ranking']

            # 타겟 상품 찾기
            for product in products:
                if product['productId'] == target_product_id:
                    return {
                        'found': True,
                        'rank': product.get('rank'),
                        'page': page,
                        'total_products': len(products),
                        'url': url
                    }

            return {
                'found': False,
                'page': page,
                'total_products': len(products),
                'url': url
            }
        else:
            # 차단 여부 판단 (200이지만 크기가 작으면 Challenge 페이지)
            is_blocked = (resp.status_code == 200 and size < 5000) or resp.status_code == 403
            return {
                'found': False,
                'error': f'STATUS_{resp.status_code}_{size}B',
                'blocked': is_blocked
            }

    except Exception as e:
        return {'found': False, 'error': str(e)[:100]}


def find_filter_url(keyword, product_id, price, cookies, fingerprint, proxy, categories=None, original_price=None, verbose=True):
    """필터 URL 탐색

    Args:
        keyword: 검색어
        product_id: 상품 ID
        price: 할인가 (최종 가격)
        cookies: 쿠키 딕셔너리
        fingerprint: 핑거프린트 레코드
        proxy: 프록시 URL
        categories: 카테고리 목록 [{'id': '123', 'name': '...'}, ...]
        original_price: 원가 (쿠팡판매가) - 필터에서 우선 사용
        verbose: 상세 출력

    Returns:
        str: 성공한 필터 URL (실패 시 None)
    """
    # 카테고리 목록 (대분류 → 소분류 순서로 시도)
    # 대분류에서 결과가 없으면 소분류는 시도할 필요 없음
    category_list = []
    if categories and len(categories) > 0:
        category_list = [{'id': c.get('id'), 'name': c.get('name', '?')} for c in categories if c.get('id')]

    # 시도할 가격 목록 결정 (원가 우선, 할인가 다음)
    prices_to_try = []
    if original_price and original_price != price:
        prices_to_try.append(('쿠팡판매가', original_price))
        prices_to_try.append(('할인가', price))
    else:
        prices_to_try.append(('판매가', price))

    if verbose:
        print(f"\n{'=' * 70}")
        print(f"필터 URL 탐색")
        print(f"{'=' * 70}")
        print(f"검색어: {keyword}")
        print(f"상품ID: {product_id}")
        if original_price and original_price != price:
            print(f"쿠팡판매가: {original_price:,}원 (우선)")
            print(f"할인가: {price:,}원")
        else:
            print(f"기준가격: {price:,}원")
        if category_list:
            cat_names = ' > '.join([c['name'] for c in category_list])
            print(f"카테고리: {cat_names}")
            print(f"  (대분류부터 시도: {' → '.join([c['id'] for c in category_list])})")
        print(f"{'=' * 70}")

    timeout_count = 0  # 타임아웃 연속 카운터
    block_count = 0    # 차단 누적 카운터 (한 번 차단되면 쿠키 문제이므로 누적으로 판단)

    # 각 가격(원가 우선, 할인가 다음)에 대해 시도
    for price_idx, (price_name, base_price) in enumerate(prices_to_try):
        if verbose:
            print(f"\n{'━' * 70}")
            print(f"💵 {price_name} 기준 탐색: {base_price:,}원")
            print(f"{'━' * 70}")

        # 가격 범위 전략들 (해당 가격 기준으로 생성)
        # 할인이 있으면 가격이 내려가는 경우만 있음 → maxPrice는 고정, minPrice만 낮춤
        price_strategies = [
            # 1. 정확한 가격
            (base_price, base_price),
            # 2. -5% ~ 판매가
            (int(base_price * 0.95), base_price),
            # 3. -10% ~ 판매가
            (int(base_price * 0.90), base_price),
            # 4. -20% ~ 판매가
            (int(base_price * 0.80), base_price),
            # 5. -30% ~ 판매가
            (int(base_price * 0.70), base_price),
            # 6. -50% ~ 판매가
            (int(base_price * 0.50), base_price),
            # 7. 필터 없음
            (0, 0),
        ]

        # Phase 1: 카테고리 + 가격 (대분류부터 소분류 순서로)
        # 대분류에서 결과가 없으면 하위 카테고리는 시도하지 않음
        if category_list:
            if verbose:
                print(f"\n📂 Phase 1: 카테고리 + 가격 필터 (대분류→소분류)")

            for cat_idx, cat_info in enumerate(category_list):
                category_id = cat_info['id']
                category_name = cat_info['name']
                category_has_results = False  # 이 카테고리에서 상품이 있었는지

                if verbose:
                    print(f"\n{'─' * 50}")
                    print(f"📁 카테고리 [{cat_idx + 1}/{len(category_list)}]: {category_name} ({category_id})")

                for strategy_idx, (min_p, max_p) in enumerate(price_strategies):
                    # 가격 필터 설정
                    if min_p == 0 and max_p == 0:
                        price_label = "가격필터 없음"
                        min_price, max_price = 0, 0
                    else:
                        price_label = f"{min_p:,}원 ~ {max_p:,}원"
                        min_price, max_price = min_p, max_p

                    # URL 미리 생성 (출력용)
                    preview_url = (
                        f"https://www.coupang.com/np/search?"
                        f"listSize=36&minPrice={min_price}&maxPrice={max_price}"
                        f"&component={category_id}&sorter=scoreDesc&page=1"
                        f"&q={quote(keyword)}"
                    )

                    if verbose:
                        print(f"\n[1-{cat_idx + 1}-{strategy_idx + 1}] {price_label}")
                        print(f"  URL: {preview_url}")

                    # 1~3페이지 검색
                    for page in range(1, 4):
                        result = search_with_filter(
                            keyword, product_id, min_price, max_price,
                            cookies, fingerprint, proxy, page,
                            component=category_id
                        )

                        if result.get('error'):
                            error = result['error']
                            is_blocked = result.get('blocked', False)

                            if is_blocked:
                                block_count += 1
                                if verbose:
                                    print(f"  Page {page}: 🚫 차단 ({error[:40]}) [{block_count}/2]")
                                if block_count >= 2:
                                    if verbose:
                                        print(f"  ⚠️ 차단 {block_count}회 → 쿠키 만료로 중단")
                                    return None
                            elif 'timed out' in error.lower() or 'curl: (28)' in error or 'curl: (7)' in error:
                                timeout_count += 1
                                if verbose:
                                    print(f"  Page {page}: ❌ {error[:60]}")
                                if timeout_count >= 3:
                                    if verbose:
                                        print(f"  ⚠️ 타임아웃 {timeout_count}회 → 프록시 문제로 중단")
                                    return None
                            else:
                                if verbose:
                                    print(f"  Page {page}: ❌ {error[:60]}")
                            break
                        elif result['found']:
                            if verbose:
                                print(f"  Page {page}: ✅ 발견! Rank #{result['rank']}")
                                print(f"\n{'─' * 70}")
                                print(f"✅ 성공! ({price_name} {base_price:,}원 + {category_name})")
                                print(f"{'─' * 70}")
                                print(result['url'])
                                print(f"{'─' * 70}")
                            return result['url']
                        else:
                            timeout_count = 0
                            # 정상 응답 (상품 있음) 시에만 차단 카운터 리셋
                            if result['total_products'] > 0:
                                block_count = 0
                                category_has_results = True
                            if verbose:
                                print(f"  Page {page}: {result['total_products']}개 상품 (미발견)")

                            if result['total_products'] == 0:
                                if verbose:
                                    print(f"  → 상품 없음, 다음 전략으로")
                                break

                # 이 카테고리에서 상품이 한 번도 없었으면 하위 카테고리도 스킵
                if not category_has_results:
                    if verbose:
                        print(f"\n  ⚠️ '{category_name}' 카테고리에 결과 없음 → 하위 카테고리 스킵")
                    break

        # Phase 2: 가격만 (카테고리 없이)
        if verbose:
            print(f"\n💰 Phase 2: 가격 필터만")

        for strategy_idx, (min_p, max_p) in enumerate(price_strategies):
            if min_p == 0 and max_p == 0:
                continue  # 필터 없음은 Phase 2에서 스킵

            # URL 미리 생성 (출력용)
            preview_url = (
                f"https://www.coupang.com/np/search?"
                f"listSize=36&minPrice={min_p}&maxPrice={max_p}"
                f"&component=&sorter=scoreDesc&page=1"
                f"&q={quote(keyword)}"
            )

            if verbose:
                print(f"\n[2-{strategy_idx + 1}] {min_p:,}원 ~ {max_p:,}원")
                print(f"  URL: {preview_url}")

            for page in range(1, 4):
                result = search_with_filter(
                    keyword, product_id, min_p, max_p,
                    cookies, fingerprint, proxy, page,
                    component=None
                )

                if result.get('error'):
                    error = result['error']
                    is_blocked = result.get('blocked', False)

                    if is_blocked:
                        block_count += 1
                        if verbose:
                            print(f"  Page {page}: 🚫 차단 ({error[:40]}) [{block_count}/2]")
                        if block_count >= 2:
                            if verbose:
                                print(f"  ⚠️ 차단 {block_count}회 → 쿠키 만료로 중단")
                            return None
                    elif 'timed out' in error.lower() or 'curl: (28)' in error or 'curl: (7)' in error:
                        timeout_count += 1
                        if verbose:
                            print(f"  Page {page}: ❌ {error[:60]}")
                        if timeout_count >= 3:
                            if verbose:
                                print(f"  ⚠️ 타임아웃 {timeout_count}회 → 프록시 문제로 중단")
                            return None
                    else:
                        if verbose:
                            print(f"  Page {page}: ❌ {error[:60]}")
                    break
                elif result['found']:
                    if verbose:
                        print(f"  Page {page}: ✅ 발견! Rank #{result['rank']}")
                        print(f"\n{'─' * 70}")
                        print(f"✅ 성공! ({price_name} {base_price:,}원 기준)")
                        print(f"{'─' * 70}")
                        print(result['url'])
                        print(f"{'─' * 70}")
                    return result['url']
                else:
                    timeout_count = 0
                    # 정상 응답 (상품 있음) 시에만 차단 카운터 리셋
                    if result['total_products'] > 0:
                        block_count = 0
                    if verbose:
                        print(f"  Page {page}: {result['total_products']}개 상품 (미발견)")

                    if result['total_products'] == 0:
                        if verbose:
                            print(f"  → 상품 없음, 다음 전략으로")
                        break

    if verbose:
        print(f"\n❌ 모든 전략 실패")
    return None


def run_filter(args):
    """필터 URL 탐색 실행

    work API에서 할당받은 상품에 대해 필터 URL을 찾는다.
    """
    print("=" * 70)
    print("필터 URL 탐색 [filter]")
    print("=" * 70)

    # 1. 작업 할당 받기 (rank 타입 사용)
    work_id = getattr(args, 'id', None)
    if work_id:
        print(f"\n📥 작업 조회 (ID: {work_id})...")
    else:
        print(f"\n📥 작업 할당 요청...")

    allocation = allocate_work(work_id=work_id, work_type='rank')
    if not allocation:
        print("❌ 작업 없음" if not work_id else f"❌ ID {work_id} 작업 없음")
        return None

    # 할당 응답 JSON 출력
    print(f"{'─' * 60}")
    print(json.dumps(allocation, ensure_ascii=False, indent=2))
    print(f"{'─' * 60}")

    progress_id = allocation['progress_id']
    keyword = allocation['keyword']
    product_id = str(allocation['product_id'])
    item_id = allocation.get('item_id')
    vendor_item_id = allocation.get('vendor_item_id')
    allocated_proxy = allocation.get('proxy')
    external_ip = allocation.get('external_ip')

    # 2. 쿠키 찾기
    if external_ip:
        target_subnet = get_subnet(external_ip)
        print(f"\n🔍 쿠키 탐색 (서브넷: {target_subnet}.*)")

        bound = get_bound_cookie(min_remain=30, max_age_minutes=60, target_subnet=target_subnet)
        if not bound:
            print(f"  ⚠️ 서브넷 매칭 쿠키 없음 - 일반 쿠키 사용")
            bound = get_bound_cookie(min_remain=30, max_age_minutes=60)

        if not bound:
            print("❌ 사용 가능한 쿠키 없음")
            return None

        cookie_record = bound['cookie_record']
        cookies = bound['cookies']
        proxy = f"socks5://{allocated_proxy}"

        match_type = 'exact' if get_subnet(cookie_record['proxy_ip']) == target_subnet else 'fallback'
        print(f"  ✅ 쿠키 ID: {cookie_record['id']} ({match_type})")
        print(f"     쿠키 IP: {cookie_record['proxy_ip']}")
    else:
        bound = get_bound_cookie(min_remain=30, max_age_minutes=60)
        if not bound:
            print("❌ IP 바인딩 매칭 실패")
            return None

        cookie_record = bound['cookie_record']
        cookies = bound['cookies']
        proxy = bound['proxy']
        print(f"  ✅ 쿠키 ID: {cookie_record['id']} (auto)")

    # 3. 핑거프린트
    fingerprint = get_random_fingerprint(verified_only=True)
    if not fingerprint:
        print("❌ 핑거프린트 없음")
        return None

    print(f"\n타겟: {product_id}")
    print(f"검색어: {keyword}")
    print(f"TLS: Chrome {fingerprint['chrome_major']}")
    print(f"프록시: {proxy}")

    # 4. 상품 가격 조회 (직접 접속)
    print(f"\n[{timestamp()}] 상품 정보 조회...")

    direct_result = direct_access_product(
        product_id, item_id, vendor_item_id,
        cookies, fingerprint, proxy,
        save_html=False, verbose=True
    )

    if not direct_result['success']:
        print(f"❌ 상품 조회 실패: {direct_result.get('error')}")
        return None

    product_data = direct_result.get('productData', {})
    if not product_data:
        print("❌ 상품 데이터 없음")
        return None

    api_data = to_api_response(product_data)
    price = api_data.get('price')  # 할인가 (시간대 특가 등)
    sales_price = api_data.get('salesPrice')  # 쿠팡판매가 (type: SALES) - 필터 기준!
    original_price = api_data.get('originalPrice')  # 원가 (취소선 가격)
    categories = api_data.get('categories', [])

    # 필터에 사용할 가격: 쿠팡판매가 우선 (할인가는 필터 조건에 안 맞는 경우가 많음)
    filter_price = sales_price or price or original_price

    if not filter_price:
        print("❌ 가격 정보 없음")
        return None

    print(f"  상품명: {api_data.get('title', '?')[:40]}...")
    if original_price and original_price != sales_price:
        print(f"  원가: {original_price:,}원 (취소선)")
    if sales_price:
        print(f"  쿠팡판매가: {sales_price:,}원 ← 필터 기준")
    if price and price != sales_price:
        print(f"  할인가: {price:,}원 (시간대 특가)")
    if categories:
        cat_names = ' > '.join([c.get('name', '?') for c in categories])
        print(f"  카테고리: {cat_names}")

    # 5. 쿠키 통계 업데이트 (직접 접속 성공)
    update_cookie_stats(cookie_record['id'], True)

    # 6. 필터 URL 탐색 (쿠팡판매가만 사용 - 할인가는 필터에 안 맞음)
    filter_url = find_filter_url(
        keyword, product_id, filter_price,  # 쿠팡판매가를 메인 가격으로
        cookies, fingerprint, proxy,
        categories=categories,
        original_price=None,  # 할인가/원가는 시도하지 않음
        verbose=True
    )

    # 7. 결과 출력
    print("\n" + "=" * 70)
    print("결과")
    print("=" * 70)

    if filter_url:
        print(f"\n✅ 필터 URL 발견!")
        print(f"Progress ID: {progress_id}")
        print(f"상품: {product_id}")
        if sales_price:
            print(f"쿠팡판매가: {sales_price:,}원")
        else:
            print(f"가격: {filter_price:,}원")
        print(f"\nURL:\n{filter_url}")
    else:
        print(f"\n❌ 필터 URL을 찾지 못함")
        print(f"Progress ID: {progress_id}")
        print(f"상품: {product_id}")

    return {
        'progress_id': progress_id,
        'product_id': product_id,
        'keyword': keyword,
        'price': price,
        'filter_url': filter_url,
        'cookie_id': cookie_record['id']
    }


# ============================================================================
# 병렬 무한 실행 모드
# ============================================================================

# 전역 취소 플래그
_cancelled = False
_stats_lock = threading.Lock()


def get_display_width(text):
    """문자열의 실제 표시 폭 계산 (한글=2, 영문=1)"""
    width = 0
    for char in text:
        if unicodedata.east_asian_width(char) in ('F', 'W'):
            width += 2
        else:
            width += 1
    return width


def pad_to_width(text, width):
    """지정된 폭에 맞게 패딩 추가"""
    current_width = get_display_width(text)
    if current_width >= width:
        return text
    return text + ' ' * (width - current_width)


def run_single_work(task_id, args):
    """단일 작업 실행 (ThreadPoolExecutor용)"""
    global _cancelled
    work_type = getattr(args, 'type', 'rank')

    if _cancelled:
        return {
            'task_id': task_id,
            'status': 'cancelled',
            'found': False,
            'blocked': False,
            'progress_id': None,
            'rank': None,
            'keyword': None,
            'cookie_id': None,
            'proxy_ip': None
        }

    try:
        # 작업 할당
        allocation = allocate_work(work_type=work_type)
        if not allocation:
            return {
                'task_id': task_id,
                'status': 'no_work',
                'found': False,
                'blocked': False,
                'progress_id': None,
                'rank': None,
                'keyword': None,
                'cookie_id': None,
                'proxy_ip': None
            }

        progress_id = allocation['progress_id']
        keyword = allocation['keyword']
        product_id = str(allocation['product_id'])
        item_id = allocation.get('item_id')
        vendor_item_id = allocation.get('vendor_item_id')
        allocated_proxy = allocation.get('proxy')
        external_ip = allocation.get('external_ip')

        # 쿠키 찾기
        bound = None
        if external_ip:
            target_subnet = get_subnet(external_ip)
            bound = get_bound_cookie(min_remain=30, max_age_minutes=60, target_subnet=target_subnet)
            if not bound:
                bound = get_bound_cookie(min_remain=30, max_age_minutes=60)

        if not bound:
            report_result(progress_id, allocated_proxy or '', external_ip or '', 'failed', work_type=work_type)
            return {
                'task_id': task_id,
                'status': 'no_cookie',
                'found': False,
                'blocked': False,
                'progress_id': progress_id,
                'rank': None,
                'keyword': keyword,
                'cookie_id': None,
                'proxy_ip': external_ip
            }

        cookie_record = bound['cookie_record']
        cookies = bound['cookies']
        proxy = f"socks5://{allocated_proxy}" if allocated_proxy else bound['proxy']

        # 쿠키 상세 정보 추출 (DB 쿼리 필드명: created_age_seconds, last_success_age_seconds)
        cookie_info = {
            'id': cookie_record['id'],
            'init_status': cookie_record.get('init_status', '?'),
            'source': cookie_record.get('source', '?'),
            'chrome_version': cookie_record.get('chrome_version', '?'),
            'proxy_ip': cookie_record.get('proxy_ip', ''),
            'created_age': cookie_record.get('created_age_seconds', 0),  # 초 단위
            'last_success_age': cookie_record.get('last_success_age_seconds'),  # 초 단위 (None 가능)
            'success_count': cookie_record.get('success_count', 0),
            'fail_count': cookie_record.get('fail_count', 0),
        }

        # 핑거프린트
        fingerprint = get_random_fingerprint(verified_only=True)
        if not fingerprint:
            report_result(progress_id, allocated_proxy or '', external_ip or '', 'failed', work_type=work_type)
            return {
                'task_id': task_id,
                'status': 'no_fingerprint',
                'found': False,
                'blocked': False,
                'progress_id': progress_id,
                'rank': None,
                'keyword': keyword,
                'cookie_id': cookie_record['id'],
                'proxy_ip': external_ip
            }

        # 검색 실행
        max_page = getattr(args, 'max_page', 13)
        result = search_product(
            keyword,
            product_id,
            cookies,
            fingerprint,
            proxy,
            max_page=max_page,
            verbose=False,  # 병렬 모드에서는 상세 출력 끔
            save_html=False
        )

        found = result['found']
        blocked = result['blocked']

        # 결과 보고
        report_rank = None
        report_info = None

        if found:
            report_rank = result['actual_rank']

            # 클릭
            if not getattr(args, 'no_click', False):
                ids = extract_ids_from_url(found['url'])
                product_info = {
                    'productId': found['productId'],
                    'url': found['url'],
                    'rank': found['rank'],
                    'itemId': ids['itemId'],
                    'vendorItemId': ids['vendorItemId']
                }
                search_url = f'https://www.coupang.com/np/search?q={quote(keyword)}'
                click_result = click_product(
                    product_info, search_url, cookies, fingerprint, proxy,
                    verbose=False,  # 병렬 모드에서 상세 출력 끔
                    save_html=False
                )
                if click_result['success'] and click_result.get('productData'):
                    report_info = build_info_data(to_api_response(click_result['productData']))

        elif not blocked:
            # 미발견 vs 검색오류 구분
            search_count = len(result.get('all_products', []))
            page_errors = result.get('page_errors', [])
            no_results = result.get('no_results', False)  # 쿠팡 "검색결과 없음" 응답

            if no_results:
                # 쿠팡이 "검색결과 없음" 응답 = 정상적인 미발견
                report_rank = 0
            elif search_count == 0 and page_errors:
                # 검색된 상품 0개 + 에러 있음 = 프록시 오류 (직접 접속 시도 안함)
                blocked = True  # 바로 failed 처리
            else:
                # 검색했지만 타겟 상품 없음 = rank 0
                report_rank = 0

            # 직접 접속 (검색 오류가 아닐 때만)
            if not blocked and not getattr(args, 'no_click', False):
                direct_result = direct_access_product(
                    product_id, item_id, vendor_item_id,
                    cookies, fingerprint, proxy,
                    save_html=False,
                    verbose=False  # 병렬 모드에서 상세 출력 끔
                )
                if direct_result['success'] and direct_result.get('productData'):
                    report_info = build_info_data(to_api_response(direct_result['productData']))

        # 쿠키 통계 업데이트
        is_success = not blocked
        update_cookie_stats(cookie_record['id'], is_success)
        update_cookie_data(cookie_record['id'], result.get('response_cookies_full', []))

        # 결과 보고
        report_status = 'failed' if blocked else 'success'
        report_result(
            progress_id=progress_id,
            proxy=allocated_proxy or '',
            external_ip=external_ip or '',
            status=report_status,
            rank=report_rank,
            info=report_info,
            work_type=work_type
        )

        # 페이지 에러 요약 (차단 원인 분석용)
        page_errors = result.get('page_errors', [])
        error_summary = ''
        if page_errors:
            # P1:CHALLENGE_1234B, P2:STATUS_403 형식
            error_parts = [f"P{e['page']}:{e['error'][:20]}" for e in page_errors[:3]]
            error_summary = ', '.join(error_parts)

        return {
            'task_id': task_id,
            'status': 'success',
            'found': bool(found),
            'blocked': blocked,
            'progress_id': progress_id,
            'rank': result.get('actual_rank'),
            'keyword': keyword,
            'cookie_id': cookie_record['id'],
            'proxy_ip': external_ip or cookie_record.get('proxy_ip', ''),
            # 상세 정보 추가
            'tls_version': fingerprint.get('chrome_major', '?'),
            'cookie_info': cookie_info,
            'search_count': len(result.get('all_products', [])),
            'error_summary': error_summary,
            'block_error': result.get('block_error', ''),
        }

    except Exception as e:
        return {
            'task_id': task_id,
            'status': 'error',
            'error': str(e)[:100],
            'found': False,
            'blocked': False,
            'progress_id': None,
            'rank': None,
            'keyword': None,
            'cookie_id': None,
            'proxy_ip': None,
            'tls_version': None,
            'cookie_info': None,
            'search_count': 0,
            'error_summary': '',
            'block_error': '',
        }


def run_work_loop(args):
    """병렬 작업 실행 (횟수 제한 또는 무한)

    Args:
        args.count (-n): 실행 횟수 (0=무한, 기본: 무한)
        args.parallel (-p): 동시 실행 수 (기본: 2)
        args.delay: 실행 간격 초 (기본: 0)
    """
    global _cancelled
    _cancelled = False

    import time

    work_type = getattr(args, 'type', 'rank')
    count = getattr(args, 'count', 0)  # 0=무한
    parallel = getattr(args, 'parallel', 2)
    delay = getattr(args, 'delay', 0)

    start_time = datetime.now()
    print("=" * 70)
    if count == 0:
        print(f"병렬 작업 실행 [{work_type}] - 무한 루프")
    else:
        print(f"병렬 작업 실행 [{work_type}] - {count}회")
    print("=" * 70)
    print(f"시작: {start_time.strftime('%H:%M:%S.%f')[:12]}")
    count_str = "무한" if count == 0 else f"{count}회"
    print(f"타입: {work_type} | 횟수: {count_str} | 병렬: {parallel} | 딜레이: {delay}초")
    print(f"💡 Ctrl+C로 종료")
    print("=" * 70)

    # 통계
    stats = {
        'total': 0,
        'found': 0,
        'not_found': 0,
        'blocked': 0,
        'error': 0,
        'no_work': 0,
        'cancelled': 0
    }

    # Ctrl+C 핸들러
    def signal_handler(sig, frame):
        global _cancelled
        if not _cancelled:
            _cancelled = True
            print("\n\n🛑 중단 요청... 실행 중인 작업 완료 대기...")

    signal.signal(signal.SIGINT, signal_handler)

    task_id = 0
    submitted_count = 0  # 제출된 작업 수 (횟수 제한용)

    try:
        with ThreadPoolExecutor(max_workers=parallel) as executor:
            futures = {}

            # 초기 작업 제출 (횟수 제한 고려)
            initial_submit = parallel if count == 0 else min(parallel, count)
            for i in range(initial_submit):
                task_id += 1
                submitted_count += 1
                futures[executor.submit(run_single_work, task_id, args)] = task_id

            while futures and not _cancelled:
                # 완료된 작업 처리
                done_futures = [f for f in futures if f.done()]

                for future in done_futures:
                    tid = futures.pop(future)
                    result = future.result()

                    # 취소된 작업
                    if result['status'] == 'cancelled':
                        stats['cancelled'] += 1
                        continue

                    stats['total'] += 1

                    # 상태별 통계 및 출력
                    now = datetime.now().strftime('%H:%M:%S.%f')[:12]
                    progress_str = f"[{stats['total']}/{count}]" if count > 0 else f"[{stats['total']}]"

                    if result['status'] == 'no_work':
                        stats['no_work'] += 1
                        print(f"[{now}] {progress_str} ⏸️  작업 없음")
                    elif result['status'] == 'error':
                        stats['error'] += 1
                        print(f"[{now}] {progress_str} ❌ 에러: {result.get('error', '?')}")
                    else:
                        # 공통 정보 추출
                        keyword = result.get('keyword', '?')
                        proxy_ip = result.get('proxy_ip', '?')
                        subnet = '.'.join(proxy_ip.split('.')[:3]) if proxy_ip else '?'
                        progress_id = result.get('progress_id', '?')
                        tls_ver = result.get('tls_version', '?')

                        # 쿠키 정보
                        cookie_info = result.get('cookie_info') or {}
                        cookie_id = cookie_info.get('id', '?')
                        init_status = cookie_info.get('init_status', '?')
                        source = cookie_info.get('source', '?')
                        cookie_ver = cookie_info.get('chrome_version', '?')
                        created_age = cookie_info.get('created_age', 0)
                        last_success_age = cookie_info.get('last_success_age')

                        # source 약어 (local→L, pg_sync→P)
                        source_map = {'local': 'L', 'pg_sync': 'P'}
                        source_short = source_map.get(source, '?')

                        # 쿠키 버전 메이저 (131.0.6778.264 → 131)
                        cookie_major = str(cookie_ver).split('.')[0] if cookie_ver != '?' else '?'

                        # 경과 시간 (C=생성, S=최종성공)
                        age_str = f"C{created_age//60}m"
                        if last_success_age is not None:
                            age_str += f"/S{last_success_age//60}m"

                        # 상태별 처리
                        if result['blocked']:
                            stats['blocked'] += 1
                            status = "🚫차단"
                            rank_str = ""
                            # 차단 원인 표시
                            block_error = result.get('block_error', '')[:25]
                            extra_info = f"[{block_error}]" if block_error else ""
                        elif result['found']:
                            stats['found'] += 1
                            rank = result.get('rank', 0)
                            status = "✅발견"
                            rank_str = f"#{rank}"
                            extra_info = ""
                        else:
                            stats['not_found'] += 1
                            status = "❌미발견"
                            rank_str = ""
                            # 검색 수 및 에러 표시
                            search_count = result.get('search_count', 0)
                            error_summary = result.get('error_summary', '')
                            if error_summary:
                                extra_info = f"({search_count}개) [{error_summary}]"
                            else:
                                extra_info = f"({search_count}개)"

                        # init_status가 비정상일 때만 표시 (success, default는 정상)
                        normal_statuses = {'success', 'default', None}
                        init_info = f"({init_status})" if init_status not in normal_statuses else ""

                        # 고정 너비 정렬
                        keyword_pad = pad_to_width(keyword[:12], 12)
                        age_pad = age_str.rjust(12)
                        print(f"[{now}] {progress_str:<8} {status} {rank_str:>4} | {keyword_pad} | P#{progress_id:<6} | {cookie_id:>6} | [{source_short}]v{cookie_major:>3}/{tls_ver:<3} | {age_pad} | {subnet:<12} {extra_info}{init_info}")

                    # 새 작업 제출 (횟수 제한 또는 무한)
                    can_submit = count == 0 or submitted_count < count
                    if not _cancelled and can_submit:
                        if delay > 0:
                            time.sleep(delay)
                        task_id += 1
                        submitted_count += 1
                        futures[executor.submit(run_single_work, task_id, args)] = task_id

                # 잠시 대기 (CPU 사용량 절감)
                if not done_futures:
                    time.sleep(0.1)

    except KeyboardInterrupt:
        pass

    # 결과 요약
    end_time = datetime.now()
    elapsed = (end_time - start_time).total_seconds()

    print("\n" + "=" * 70)
    print("결과 요약")
    print("=" * 70)
    print(f"총 실행: {stats['total']}회 | 소요: {elapsed:.1f}초")
    if stats['total'] > 0:
        found_rate = stats['found'] * 100 // stats['total']
        print(f"✅ 발견: {stats['found']}회 ({found_rate}%)")
        print(f"❌ 미발견: {stats['not_found']}회")
        print(f"🚫 차단: {stats['blocked']}회")
        print(f"⚠️ 에러: {stats['error']}회")
        if stats['no_work'] > 0:
            print(f"⏸️ 작업없음: {stats['no_work']}회")
        if stats['cancelled'] > 0:
            print(f"🛑 취소: {stats['cancelled']}회")

    print(f"\n완료: {end_time.strftime('%H:%M:%S.%f')[:12]}")

    return stats


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='작업 할당 기반 검색')
    parser.add_argument('--max-page', type=int, default=13, help='최대 검색 페이지')
    parser.add_argument('--no-click', action='store_true', help='클릭 건너뛰기')
    parser.add_argument('-n', '--count', type=int, default=0, help='실행 횟수 (0=무한, 기본: 무한)')
    parser.add_argument('-p', '--parallel', type=int, default=2, help='병렬 수 (기본: 2)')
    parser.add_argument('--delay', type=float, default=0, help='실행 간격 초 (기본: 0)')
    parser.add_argument('--id', type=int, help='특정 작업 ID (1회 실행)')

    args = parser.parse_args()

    if args.id:
        run_work(args)
    else:
        run_work_loop(args)
