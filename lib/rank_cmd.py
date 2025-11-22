"""
상품 등수 체크 명령어
"""

import sys
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from urllib.parse import quote

# Add lib directory to path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / 'click-tracker'))

from common import (
    timestamp, get_cookie_by_id, get_latest_cookie, get_fingerprint,
    check_proxy_ip, parse_cookies, make_request, verify_ip_binding
)
from extractor.product_extractor import ProductExtractor
from traceid import generate_traceid
from realistic_click import realistic_click

BASE_DIR = Path(__file__).parent.parent

# 기본 테스트 상품 (호박 달빛식혜)
DEFAULT_PRODUCT = {
    'product_id': '9024146312',
    'item_id': '26462223016',
    'vendor_item_id': '93437504341',
    'query': '호박 달빛식혜'
}

def fetch_page(page_num, query, trace_id, cookies, fingerprint, proxy):
    """페이지 검색"""
    url = f'https://www.coupang.com/np/search?q={quote(query)}&traceId={trace_id}&channel=user&listSize=72&page={page_num}'

    try:
        resp = make_request(url, cookies, fingerprint, proxy)
        size = len(resp.content)

        if resp.status_code == 200 and size > 5000:
            result = ProductExtractor.extract_products_from_html(resp.text)
            return {'page': page_num, 'success': True, 'products': result['ranking'], 'size': size}
        elif resp.status_code == 403:
            return {'page': page_num, 'success': False, 'products': [], 'error': 'BLOCKED_403'}
        elif size <= 5000:
            return {'page': page_num, 'success': False, 'products': [], 'error': f'CHALLENGE_{size}B'}
        else:
            return {'page': page_num, 'success': False, 'products': [], 'error': f'STATUS_{resp.status_code}'}

    except Exception as e:
        return {'page': page_num, 'success': False, 'products': [], 'error': str(e)[:50]}

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

def run_rank(args):
    """상품 등수 체크 실행"""
    print("=" * 70)
    print("상품 등수 체커")
    print("=" * 70)

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

    # IP 검증
    if proxy:
        print("\nIP 검증 중...")
        success, current_ip, message = verify_ip_binding(proxy, cookie_record['proxy_ip'])

        if current_ip:
            print(f"  현재 IP: {current_ip}")
            print(f"  쿠키 IP: {cookie_record['proxy_ip']}")

        if not success:
            print(f"\n❌ {message}")
            return

        print("  ✅ IP 일치")

    print("=" * 70)

    trace_id = generate_traceid()
    print(f"\n[{timestamp()}] 검색 중... (traceId: {trace_id})")

    found = None
    start_time = datetime.now()
    all_products = []
    failed_pages = []

    with ThreadPoolExecutor(max_workers=args.max_page) as executor:
        futures = {
            executor.submit(fetch_page, i, args.query, trace_id, cookies, fingerprint, proxy): i
            for i in range(1, args.max_page + 1)
        }

        for future in as_completed(futures, timeout=60):
            try:
                result = future.result(timeout=30)

                if result['success']:
                    for product in result['products']:
                        product['_page'] = result['page']
                        all_products.append(product)

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
                    print(f"  [{timestamp()}] Page {result['page']:2d}: ❌ {result.get('error')}")
                    failed_pages.append(result['page'])

            except:
                pass

        # 재시도 (발견 안 된 경우만)
        if not found and failed_pages:
            print(f"\n[{timestamp()}] 재시도: {failed_pages}")
            retry_futures = {
                executor.submit(fetch_page, p, args.query, trace_id, cookies, fingerprint, proxy): p
                for p in failed_pages
            }

            for future in as_completed(retry_futures, timeout=60):
                try:
                    result = future.result(timeout=30)
                    if result['success']:
                        for product in result['products']:
                            product['_page'] = result['page']
                            all_products.append(product)
                            if product['productId'] == args.product_id:
                                found = product
                                found['page'] = result['page']
                                print(f"[{timestamp()}] ✅ 재시도 발견! Page {result['page']}")
                        if found:
                            # 조기 종료
                            for f in retry_futures:
                                f.cancel()
                            break
                except:
                    pass

    search_time = (datetime.now() - start_time).total_seconds()

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
        'list_size': 72,
    }

    if found:
        print(f"\n✅ 상품 발견")
        print(f"   페이지: {found['page']}")
        print(f"   URL rank: {found['rank']}")
        print(f"   실제 순위: {actual_rank}등 / {len(all_products)}개")
        print(f"   상품명: {found['name'][:50]}...")
        print(f"\n   URL: https://www.coupang.com{found['url']}")

        report['found'] = True
        report['page'] = found['page']
        report['url_rank'] = found['rank']
        report['actual_rank'] = actual_rank
        report['product'] = {
            'productId': found['productId'],
            'name': found['name'],
            'url': found['url']
        }

        # 상품 클릭 (기본 동작) - 실제 브라우저 트래픽 재현
        if not getattr(args, 'no_click', False):
            print(f"\n[{timestamp()}] 상품 클릭...")

            # URL에서 itemId, vendorItemId 파싱
            from urllib.parse import urlparse, parse_qs
            parsed_url = urlparse(found['url'])
            params = parse_qs(parsed_url.query)

            product_info = {
                'productId': found['productId'],
                'itemId': params.get('itemId', [''])[0],
                'vendorItemId': params.get('vendorItemId', [''])[0],
                'url': found['url'],
                'rank': found['rank']
            }

            search_url = f'https://www.coupang.com/np/search?q={quote(args.query)}'
            click_result = realistic_click(product_info, search_url, cookies, fingerprint, proxy)

            if click_result['success']:
                page_result = click_result.get('product_page', {})
                print(f"✅ 클릭 성공 ({page_result.get('size', 0):,} bytes)")
            else:
                page_result = click_result.get('product_page', {})
                print(f"❌ 클릭 실패: {page_result.get('error', 'Unknown')}")

            report['click'] = click_result
    else:
        print(f"\n❌ 상품 미발견 ({args.max_page}페이지)")
        report['found'] = False

    report['all_products'] = all_products

    # 리포트 저장
    reports_dir = BASE_DIR / 'reports'
    reports_dir.mkdir(exist_ok=True)
    filename = f"rank_{args.product_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report_path = reports_dir / filename

    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n📁 리포트: {report_path}")

    return report
