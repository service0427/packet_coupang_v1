"""
상품 검색 명령어 (리팩토링 버전)

핵심 알고리즘:
  랜덤 IP (바인딩) + 랜덤 쿠키 (/24 매칭) + 랜덤 TLS = 성공
"""

import json
import random
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from common.db import execute_query
from common.proxy import get_bound_cookie, get_cookie_by_id, parse_cookie_data, get_subnet, update_cookie_stats, update_cookie_data, get_proxy_list
from common.fingerprint import get_fingerprint_by_version, get_random_fingerprint
from cffi.search import search_product
from cffi.click import click_product, extract_ids_from_url
from cffi.request import timestamp
from screenshot import save_html_with_urls, take_screenshot_from_saved

# 프로젝트 루트 (lib/cffi/ → 상위 2단계)
PROJECT_ROOT = Path(__file__).parent.parent.parent  # /home/tech/packet_coupang_v1

# 기본 테스트 상품
DEFAULT_PRODUCT = {
    'product_id': '9024146312',
    'query': '호박 달빛식혜'
}


def direct_access_product(product_id, item_id, vendor_item_id, cookies, fingerprint, proxy):
    """상품 URL 직접 접속으로 정보 추출

    Args:
        product_id: 상품 ID
        item_id: 아이템 ID (없으면 None)
        vendor_item_id: 벤더 아이템 ID (없으면 None)
        cookies: 쿠키 딕셔너리
        fingerprint: 핑거프린트 레코드
        proxy: 프록시 URL

    Returns:
        dict: {success, productData, response_cookies_full}
    """
    from cffi.request import make_request, parse_response_cookies
    from extractor.detail_extractor import extract_product_detail

    # URL 구성
    if item_id and vendor_item_id:
        url = f'https://www.coupang.com/vp/products/{product_id}?itemId={item_id}&vendorItemId={vendor_item_id}'
    else:
        url = f'https://www.coupang.com/vp/products/{product_id}'

    print(f"\n[{timestamp()}] 직접 접속...")
    print(f"  URL: {url}")

    try:
        resp = make_request(url, cookies, fingerprint, proxy, referer='https://www.coupang.com/')
        size = len(resp.content)

        response_cookies, response_cookies_full = parse_response_cookies(resp)

        print(f"  Status: {resp.status_code} | Size: {size:,} bytes")

        if size > 100000:
            product_data = extract_product_detail(resp.text)

            if product_data:
                print(f"\n{'─' * 70}")
                print("📦 직접 접속 상품 정보")
                print(f"{'─' * 70}")
                for key, value in product_data.items():
                    print(f"   {key}: {value}")
                print(f"{'─' * 70}")

            return {
                'success': True,
                'productData': product_data,
                'response_cookies_full': response_cookies_full,
                'size': size
            }
        else:
            print(f"  ❌ 응답 크기 부족 ({size:,} bytes)")
            return {
                'success': False,
                'error': f'INVALID_RESPONSE_{size}B',
                'response_cookies_full': response_cookies_full,
                'size': size
            }

    except Exception as e:
        print(f"  ❌ 에러: {str(e)[:50]}")
        return {
            'success': False,
            'error': str(e)[:100],
            'response_cookies_full': [],
            'size': 0
        }


def run_search(args):
    """상품 검색 실행"""
    print("=" * 70)
    print("상품 검색")
    print("=" * 70)

    # IP 바인딩 + 쿠키 선택
    if args.cookie_id:
        # 특정 쿠키 ID 지정
        cookie_record = get_cookie_by_id(args.cookie_id)
        if not cookie_record:
            print(f"❌ 쿠키 ID {args.cookie_id} 없음")
            return None
        cookies = parse_cookie_data(cookie_record)

        # 쿠키의 IP 서브넷과 매칭되는 현재 사용 가능한 프록시 찾기
        if args.proxy:
            proxy = args.proxy
        else:
            cookie_subnet = get_subnet(cookie_record['proxy_ip'])
            proxies = get_proxy_list(min_remain=30)
            matching_proxy = None
            for p in proxies:
                if get_subnet(p.get('external_ip')) == cookie_subnet:
                    matching_proxy = f"socks5://{p['proxy']}"
                    break
            if matching_proxy:
                proxy = matching_proxy
                print(f"📍 쿠키 ID: {cookie_record['id']} (지정) - 서브넷 매칭 프록시 사용")
                print(f"   쿠키 IP: {cookie_record['proxy_ip']} → 프록시 서브넷: {cookie_subnet}.*")
            else:
                # 매칭 프록시 없으면 원래 proxy_url 사용 (경고 출력)
                proxy = f"socks5://{cookie_record['proxy_url']}" if cookie_record['proxy_url'] else None
                print(f"⚠️ 쿠키 ID: {cookie_record['id']} (지정) - 서브넷 매칭 프록시 없음!")
                print(f"   쿠키 IP: {cookie_record['proxy_ip']} - 원래 프록시 사용 (차단 가능성 높음)")
    else:
        # IP 바인딩 자동 선택
        print("🔍 IP 바인딩 쿠키 탐색...")

        # 제외할 서브넷 파싱
        exclude_subnets = []
        if hasattr(args, 'exclude_subnets') and args.exclude_subnets:
            exclude_subnets = [s.strip() for s in args.exclude_subnets.split(',') if s.strip()]
            if exclude_subnets:
                print(f"  ⛔ 제외 서브넷: {len(exclude_subnets)}개")

        bound = get_bound_cookie(min_remain=30, max_age_minutes=60, exclude_subnets=exclude_subnets)
        if not bound:
            print("❌ IP 바인딩 매칭 실패")
            return None

        cookie_record = bound['cookie_record']
        cookies = bound['cookies']
        proxy = args.proxy or bound['proxy']

        match_icon = "✅" if bound['match_type'] == 'exact' else "🔗"
        print(f"  {match_icon} 쿠키 ID: {cookie_record['id']} ({bound['match_type']})")
        print(f"     IP: {bound['external_ip']} (서브넷: {get_subnet(bound['external_ip'])}.*)")
        # 경과 시간 표시
        created_age = cookie_record.get('created_age_seconds', 0) or 0
        last_success_age = cookie_record.get('last_success_age_seconds')
        last_success_str = f"{last_success_age}초" if last_success_age else "없음"
        print(f"     경과: 생성 {created_age}초 | 최종성공 {last_success_str}")
        print(f"     상태: {cookie_record.get('init_status', '?')} | 소스: {cookie_record.get('source', '?')} | 쿠키버전: {cookie_record.get('chrome_version', '?')}")

    # TLS 핑거프린트 선택 (검증된 버전 중 랜덤)
    fingerprint = get_random_fingerprint(verified_only=True)
    if not fingerprint:
        print("❌ 핑거프린트 없음")
        return None

    print(f"\n타겟: {args.product_id}")
    print(f"검색어: {args.query}")
    print(f"TLS: Chrome {fingerprint['chrome_major']} (custom)")
    print(f"프록시: {proxy}")
    print("=" * 70)

    # 검색 실행
    save_html = args.screenshot
    start_time = datetime.now()
    result = search_product(
        args.query,
        args.product_id,
        cookies,
        fingerprint,
        proxy,
        max_page=args.max_page,
        verbose=True,
        save_html=save_html
    )

    search_time = (datetime.now() - start_time).total_seconds()

    # 페이지 에러가 있고 상품 미발견 시 재시도 (curl 타임아웃, TLS 에러 등)
    page_errors = result.get('page_errors', [])
    retry_errors = ['curl: (28)', 'curl: (35)', 'TLS connect error', 'Operation timed out']
    has_retry_error = any(
        any(err in e.get('error', '') for err in retry_errors)
        for e in page_errors
    )

    if not result['found'] and not result['blocked'] and has_retry_error and not args.cookie_id:
        print(f"\n🔄 네트워크 에러 발생 - 다른 프록시로 재시도...")

        # 현재 서브넷 제외하고 새 쿠키 탐색
        current_subnet = get_subnet(cookie_record['proxy_ip'])
        retry_exclude = [current_subnet] if current_subnet else []
        if hasattr(args, 'exclude_subnets') and args.exclude_subnets:
            retry_exclude.extend([s.strip() for s in args.exclude_subnets.split(',') if s.strip()])

        retry_bound = get_bound_cookie(min_remain=30, max_age_minutes=60, exclude_subnets=retry_exclude)
        if retry_bound:
            retry_cookie_record = retry_bound['cookie_record']
            retry_cookies = retry_bound['cookies']
            retry_proxy = retry_bound['proxy']
            retry_fingerprint = get_random_fingerprint(verified_only=True)

            print(f"  ✅ 새 쿠키 ID: {retry_cookie_record['id']}")
            print(f"     IP: {retry_bound['external_ip']} (서브넷: {get_subnet(retry_bound['external_ip'])}.*)")

            # 재시도 검색
            retry_result = search_product(
                args.query,
                args.product_id,
                retry_cookies,
                retry_fingerprint,
                retry_proxy,
                max_page=args.max_page,
                verbose=True,
                save_html=save_html
            )

            # 재시도 쿠키 통계 업데이트
            retry_success = not retry_result['blocked']
            update_cookie_stats(retry_cookie_record['id'], retry_success)

            if retry_result.get('response_cookies_full'):
                update_cookie_data(retry_cookie_record['id'], retry_result['response_cookies_full'])

            # 재시도 결과가 더 좋으면 교체
            if retry_result['found'] or (not retry_result['blocked'] and not result['found']):
                result = retry_result
                cookie_record = retry_cookie_record
                cookies = retry_cookies
                fingerprint = retry_fingerprint
                proxy = retry_proxy
                search_time += (datetime.now() - start_time).total_seconds() - search_time
        else:
            print(f"  ⚠️ 재시도용 프록시 없음 - 건너뜀")

    # 결과 출력
    print("\n" + "=" * 70)
    print("결과")
    print("=" * 70)

    found = result['found']
    blocked = result['blocked']

    if found:
        print(f"\n✅ 상품 발견")
        print(f"   페이지: {found['page']}")
        print(f"   순위: {result['actual_rank']}등 / {len(result['all_products'])}개")

        # 검색 결과에서 추출된 상품 정보 (전체 표시)
        print(f"\n{'─' * 70}")
        print("📋 검색 결과 상품 정보")
        print(f"{'─' * 70}")
        for key, value in found.items():
            if key not in ['_page']:  # 내부 키 제외
                print(f"   {key}: {value}")
        print(f"{'─' * 70}")

        # 스크린샷 처리
        screenshot_path = None
        if save_html and result.get('found_html'):
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            screenshot_dir = PROJECT_ROOT / 'screenshot'
            screenshot_dir.mkdir(parents=True, exist_ok=True)  # 폴더 없으면 생성
            html_path = screenshot_dir / f'search_{args.product_id}_{ts}.html'

            # 1단계: HTML + URL JSON 저장
            save_result = save_html_with_urls(
                result['found_html'],
                html_path,
                metadata={
                    'query': args.query,
                    'product_id': args.product_id,
                    'rank': result['actual_rank'],
                    'page': found['page'],
                    'timestamp': ts
                }
            )
            print(f"\n📄 HTML 저장: {save_result['html_path']}")

            # 2단계: 스크린샷 생성
            print(f"📸 스크린샷 생성 중...")
            ss_result = take_screenshot_from_saved(html_path)
            if ss_result['success']:
                screenshot_path = ss_result['path']
                print(f"   ✅ {screenshot_path}")
                print(f"   크기: {ss_result['size']:,} bytes")
                print(f"   이미지: {ss_result['images_loaded']}/{ss_result['images_total']} 로드")
            else:
                print(f"   ❌ 스크린샷 실패: {ss_result.get('error')}")

        # 클릭
        if not args.no_click:
            print(f"\n[{timestamp()}] 상품 클릭...")

            ids = extract_ids_from_url(found['url'])
            product_info = {
                'productId': found['productId'],
                'url': found['url'],
                'rank': found['rank'],
                'itemId': ids['itemId'],
                'vendorItemId': ids['vendorItemId']
            }

            search_url = f'https://www.coupang.com/np/search?q={quote(args.query)}'
            click_result = click_product(
                product_info, search_url, cookies, fingerprint, proxy
            )

            if not click_result['success']:
                print(f"  ❌ 클릭 실패: {click_result.get('error')}")

    elif blocked:
        print(f"\n🚫 차단됨: {result['block_error']}")
    else:
        # 페이지 에러가 있으면 표시
        page_errors = result.get('page_errors', [])
        if page_errors:
            error_str = ', '.join([f"P{e['page']}:{e['error']}" for e in page_errors])
            print(f"\n❌ 상품 미발견 ({len(result['all_products'])}개 검색) | 에러: {error_str}")
        else:
            print(f"\n❌ 상품 미발견 ({len(result['all_products'])}개 검색)")

        # 직접 접속으로 상품 정보 추출 (--no-click이 아니면 실행)
        if not args.no_click:
            item_id = product_info.get('item_id') if product_info else None
            vendor_item_id = product_info.get('vendor_item_id') if product_info else None

            direct_result = direct_access_product(
                args.product_id, item_id, vendor_item_id,
                cookies, fingerprint, proxy
            )

            # 직접 접속 응답 쿠키도 업데이트에 포함
            if direct_result.get('response_cookies_full'):
                result['response_cookies_full'].extend(direct_result['response_cookies_full'])

            # 직접 접속 실패 시 재시도 (새 쿠키/프록시로)
            if not direct_result.get('success') and not args.cookie_id:
                print(f"\n🔄 직접접속 차단 - 새 쿠키로 재시도...")

                # 현재 서브넷 제외하고 새 쿠키 탐색
                current_subnet = get_subnet(cookie_record['proxy_ip'])
                retry_exclude = [current_subnet] if current_subnet else []
                if hasattr(args, 'exclude_subnets') and args.exclude_subnets:
                    retry_exclude.extend([s.strip() for s in args.exclude_subnets.split(',') if s.strip()])

                retry_bound = get_bound_cookie(min_remain=30, max_age_minutes=60, exclude_subnets=retry_exclude)
                if retry_bound:
                    retry_cookie_record = retry_bound['cookie_record']
                    retry_cookies = retry_bound['cookies']
                    retry_proxy = retry_bound['proxy']
                    retry_fingerprint = get_random_fingerprint(verified_only=True)

                    print(f"  ✅ 새 쿠키 ID: {retry_cookie_record['id']}")
                    print(f"     IP: {retry_bound['external_ip']} (서브넷: {get_subnet(retry_bound['external_ip'])}.*)")

                    direct_result = direct_access_product(
                        args.product_id, item_id, vendor_item_id,
                        retry_cookies, retry_fingerprint, retry_proxy
                    )

                    # 재시도 쿠키 통계 업데이트
                    retry_success = direct_result.get('success', False)
                    update_cookie_stats(retry_cookie_record['id'], retry_success)

                    if direct_result.get('response_cookies_full'):
                        update_cookie_data(retry_cookie_record['id'], direct_result['response_cookies_full'])
                else:
                    print(f"  ❌ 재시도용 쿠키 없음")

    # 통계 업데이트
    is_success = not blocked
    update_cookie_stats(cookie_record['id'], is_success)

    # 쿠키 데이터 업데이트 (필수)
    updated = update_cookie_data(cookie_record['id'], result.get('response_cookies_full', []))
    if updated > 0:
        print(f"\n💾 쿠키 업데이트: {updated}개")

    # 트래픽 출력
    total_bytes = result.get('total_bytes', 0)
    if total_bytes > 0:
        if total_bytes >= 1024 * 1024:
            traffic_str = f"{total_bytes / (1024 * 1024):.2f} MB"
        else:
            traffic_str = f"{total_bytes / 1024:.2f} KB"
        print(f"📊 트래픽: {traffic_str} | 시간: {search_time:.1f}초")

    print(f"\n✅ 쿠키:{cookie_record['id']} | TLS:{fingerprint['chrome_major']}")

    return {
        'found': bool(found),
        'blocked': blocked,
        'cookie_id': cookie_record['id'],
        'fingerprint': fingerprint['chrome_major'],
        'search_time': search_time
    }


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--product-id', default='9024146312')
    parser.add_argument('--query', default='호박 달빛식혜')
    parser.add_argument('--max-page', type=int, default=13)
    parser.add_argument('--no-click', action='store_true', help='클릭/직접접속 건너뛰기')
    parser.add_argument('--cookie-id', type=int)
    parser.add_argument('--proxy')
    parser.add_argument('--screenshot', action='store_true', help='상품 발견 시 스크린샷 저장')

    args = parser.parse_args()
    run_search(args)
