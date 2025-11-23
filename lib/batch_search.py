"""
점진적 배치 검색 모듈
- 1페이지 단독 → 2-3 → 4-13 순서로 검색
- 발견 시 즉시 중단
- 실패 페이지 재시도
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# 기본 배치 설정
DEFAULT_BATCHES = [
    [1],           # 1단계: 1페이지만
    [2, 3],        # 2단계: 2-3페이지
    [4, 5, 6, 7, 8, 9, 10, 11, 12, 13]  # 3단계: 나머지
]

def timestamp():
    """타임스탬프 생성"""
    return datetime.now().strftime('%H:%M:%S.%f')[:-3]


class BatchSearcher:
    """점진적 배치 검색 클래스"""

    def __init__(self, fetch_func, max_page=13, max_retries=3, batches=None, cookies_ref=None):
        """
        Args:
            fetch_func: 페이지 검색 함수 (page_num) -> result dict
            max_page: 최대 페이지 수
            max_retries: 재시도 횟수
            batches: 커스텀 배치 설정 [[1], [2,3], [4,5,...]]
            cookies_ref: 원본 쿠키 딕셔너리 참조 (Cookie Jar 방식)
        """
        self.fetch_func = fetch_func
        self.max_page = max_page
        self.max_retries = max_retries
        self.cookies_ref = cookies_ref  # Cookie Jar: 원본 쿠키 참조

        # 배치 설정 (max_page에 맞게 필터링)
        if batches:
            self.batches = self._filter_batches(batches, max_page)
        else:
            self.batches = self._filter_batches(DEFAULT_BATCHES, max_page)

    @staticmethod
    def match_product(product, target_product_id, target_item_id=None, target_vendor_item_id=None):
        """
        상품 매칭 우선순위 체크

        Returns:
            tuple: (match_level, match_type_str) or (0, None) if no match
            - 1: 완전 매칭 (ProductId + ItemId + VendorItemId)
            - 2: ProductId + VendorItemId
            - 3: ProductId + ItemId
            - 4: ProductId만
            - 5: VendorItemId만
            - 6: ItemId만
        """
        p_id = product.get('productId')
        i_id = product.get('itemId')
        v_id = product.get('vendorItemId')

        # 1순위: 완전 매칭
        if target_product_id and target_item_id and target_vendor_item_id:
            if p_id == target_product_id and i_id == target_item_id and v_id == target_vendor_item_id:
                return (1, '완전매칭')

        # 2순위: ProductId + VendorItemId
        if target_product_id and target_vendor_item_id:
            if p_id == target_product_id and v_id == target_vendor_item_id:
                return (2, 'P+V')

        # 3순위: ProductId + ItemId
        if target_product_id and target_item_id:
            if p_id == target_product_id and i_id == target_item_id:
                return (3, 'P+I')

        # 4순위: ProductId만
        if target_product_id and p_id == target_product_id:
            return (4, 'P')

        # 5순위: VendorItemId만
        if target_vendor_item_id and v_id == target_vendor_item_id:
            return (5, 'V')

        # 6순위: ItemId만
        if target_item_id and i_id == target_item_id:
            return (6, 'I')

        return (0, None)

    def _filter_batches(self, batches, max_page):
        """max_page에 맞게 배치 필터링"""
        filtered = []
        for batch in batches:
            filtered_batch = [p for p in batch if p <= max_page]
            if filtered_batch:
                filtered.append(filtered_batch)
        return filtered

    def search(self, target_product_id, target_item_id=None, target_vendor_item_id=None, on_result=None):
        """
        점진적 배치 검색 실행

        Args:
            target_product_id: 찾을 상품 ID
            target_item_id: 찾을 아이템 ID (옵션)
            target_vendor_item_id: 찾을 벤더아이템 ID (옵션)
            on_result: 결과 콜백 함수 (result) -> None

        Returns:
            dict: {
                'found': product or None,
                'match_type': str (매칭 타입),
                'all_products': list,
                'all_response_cookies': dict,
                'all_response_cookies_full': list,
                'blocked': bool,
                'block_error': str,
                'failed_pages': list
            }
        """
        found = None
        match_type = None
        all_products = []
        all_response_cookies = {}
        all_response_cookies_full = []
        blocked = False
        block_error = ''
        final_failed_pages = []
        total_bytes = 0  # 총 트래픽

        for batch_idx, batch in enumerate(self.batches):
            if found or blocked:
                break

            batch_name = f"배치 {batch_idx + 1}/{len(self.batches)}"
            if len(batch) == 1:
                print(f"\n[{timestamp()}] {batch_name}: 페이지 {batch[0]}")
            else:
                print(f"\n[{timestamp()}] {batch_name}: 페이지 {batch[0]}-{batch[-1]} ({len(batch)}개)")

            # 배치 검색 실행
            batch_result = self._search_batch(
                batch,
                target_product_id,
                target_item_id,
                target_vendor_item_id,
                on_result
            )

            # 결과 병합
            all_products.extend(batch_result['products'])
            all_response_cookies.update(batch_result['response_cookies'])
            all_response_cookies_full.extend(batch_result['response_cookies_full'])
            total_bytes += batch_result.get('total_bytes', 0)

            if batch_result['found']:
                found = batch_result['found']
                match_type = batch_result.get('match_type', 'P')
                print(f"[{timestamp()}] ✅ 발견! Page {found['page']}, Rank {found['rank']} [{match_type}]")
                break

            if batch_result['blocked']:
                blocked = True
                block_error = batch_result['block_error']
                break

            # 실패 페이지 재시도
            failed_pages = batch_result['failed_pages']
            batch_total_products = batch_result['total_products']

            if failed_pages:
                retry_result = self._retry_failed(
                    failed_pages,
                    target_product_id,
                    target_item_id,
                    target_vendor_item_id,
                    on_result
                )

                all_products.extend(retry_result['products'])
                all_response_cookies.update(retry_result['response_cookies'])
                all_response_cookies_full.extend(retry_result['response_cookies_full'])
                total_bytes += retry_result.get('total_bytes', 0)

                # 재시도 결과 반영
                batch_total_products += retry_result['total_products']

                if retry_result['found']:
                    found = retry_result['found']
                    match_type = retry_result.get('match_type', 'P')
                    print(f"[{timestamp()}] ✅ 재시도 발견! Page {found['page']}, Rank {found['rank']} [{match_type}]")
                    break

                if retry_result['blocked']:
                    blocked = True
                    block_error = retry_result['block_error']
                    break

                final_failed_pages.extend(retry_result['failed_pages'])

            # 배치 내 모든 성공한 페이지가 0개면 조기 종료 (첫 배치 제외)
            # 조건: 첫 배치가 아니고, 재시도 포함 총 상품 0개이고, 최종 실패 페이지도 없음
            if batch_idx > 0 and batch_total_products == 0 and not failed_pages:
                print(f"  [{timestamp()}] ⏹️ 검색 결과 없음, 검색 종료")
                break

        return {
            'found': found,
            'match_type': match_type,
            'all_products': all_products,
            'all_response_cookies': all_response_cookies,
            'all_response_cookies_full': all_response_cookies_full,
            'blocked': blocked,
            'block_error': block_error,
            'failed_pages': final_failed_pages,
            'total_bytes': total_bytes
        }

    def _search_batch(self, pages, target_product_id, target_item_id=None, target_vendor_item_id=None, on_result=None):
        """
        단일 배치 검색

        Args:
            pages: 검색할 페이지 리스트
            target_product_id: 찾을 상품 ID
            target_item_id: 찾을 아이템 ID (옵션)
            target_vendor_item_id: 찾을 벤더아이템 ID (옵션)
            on_result: 결과 콜백

        Returns:
            dict: 배치 검색 결과
        """
        found = None
        match_type = None
        products = []
        response_cookies = {}
        response_cookies_full = []
        blocked = False
        block_error = ''
        failed_pages = []
        total_bytes = 0  # 총 트래픽

        with ThreadPoolExecutor(max_workers=len(pages)) as executor:
            futures = {
                executor.submit(self.fetch_func, page): page
                for page in pages
            }

            for future in as_completed(futures, timeout=60):
                try:
                    result = future.result(timeout=30)

                    # 트래픽 수집
                    if result.get('size'):
                        total_bytes += result['size']

                    # 응답 쿠키 수집
                    if result.get('response_cookies'):
                        response_cookies.update(result['response_cookies'])
                        # Cookie Jar: 원본 쿠키에도 업데이트 (다음 요청에 반영)
                        if self.cookies_ref is not None:
                            self.cookies_ref.update(result['response_cookies'])
                    if result.get('response_cookies_full'):
                        response_cookies_full.extend(result['response_cookies_full'])

                    # 콜백 호출
                    if on_result:
                        on_result(result)

                    if result['success']:
                        for product in result['products']:
                            product['_page'] = result['page']
                            products.append(product)

                            # 매칭 우선순위 체크
                            if not found:
                                level, m_type = self.match_product(
                                    product, target_product_id, target_item_id, target_vendor_item_id
                                )
                                if level > 0:
                                    found = product
                                    found['page'] = result['page']
                                    match_type = m_type

                        if found:
                            # 발견 시 나머지 취소
                            for f in futures:
                                f.cancel()
                            break
                        else:
                            print(f"  [{timestamp()}] Page {result['page']:2d}: {len(result['products'])}개")
                    else:
                        error = result.get('error', '')
                        print(f"  [{timestamp()}] Page {result['page']:2d}: ❌ {error}")

                        # 차단 확인
                        if error == 'BLOCKED_403' or error.startswith('CHALLENGE_'):
                            blocked = True
                            block_error = error
                            for f in futures:
                                f.cancel()
                            break
                        else:
                            failed_pages.append(result['page'])

                except Exception as e:
                    pass

        return {
            'found': found,
            'match_type': match_type,
            'products': products,
            'total_products': len(products),
            'response_cookies': response_cookies,
            'response_cookies_full': response_cookies_full,
            'blocked': blocked,
            'block_error': block_error,
            'failed_pages': failed_pages,
            'total_bytes': total_bytes
        }

    def _retry_failed(self, failed_pages, target_product_id, target_item_id=None, target_vendor_item_id=None, on_result=None):
        """
        실패한 페이지 재시도

        Args:
            failed_pages: 실패한 페이지 리스트
            target_product_id: 찾을 상품 ID
            on_result: 결과 콜백

        Returns:
            dict: 재시도 결과
        """
        found = None
        match_type = None
        products = []
        response_cookies = {}
        response_cookies_full = []
        blocked = False
        block_error = ''
        total_bytes = 0

        current_failed = failed_pages[:]

        for retry_num in range(1, self.max_retries + 1):
            if not current_failed or found or blocked:
                break

            print(f"\n  [{timestamp()}] 재시도 #{retry_num}: {current_failed}")

            retry_result = self._search_batch(
                current_failed,
                target_product_id,
                target_item_id,
                target_vendor_item_id,
                on_result
            )

            products.extend(retry_result['products'])
            response_cookies.update(retry_result['response_cookies'])
            response_cookies_full.extend(retry_result['response_cookies_full'])
            total_bytes += retry_result.get('total_bytes', 0)

            if retry_result['found']:
                found = retry_result['found']
                match_type = retry_result.get('match_type')
                break

            if retry_result['blocked']:
                blocked = True
                block_error = retry_result['block_error']
                break

            current_failed = retry_result['failed_pages']

            if current_failed and retry_num < self.max_retries:
                print(f"  [{timestamp()}] 남은 실패: {len(current_failed)}개")

        return {
            'found': found,
            'match_type': match_type,
            'products': products,
            'total_products': len(products),
            'response_cookies': response_cookies,
            'response_cookies_full': response_cookies_full,
            'blocked': blocked,
            'block_error': block_error,
            'failed_pages': current_failed,
            'total_bytes': total_bytes
        }


def create_batch_searcher(fetch_page_func, query, trace_id, cookies, fingerprint, proxy,
                          max_page=13, max_retries=3, batches=None):
    """
    배치 검색기 생성 헬퍼 함수

    Args:
        fetch_page_func: fetch_page 함수 참조
        query, trace_id, cookies, fingerprint, proxy: fetch_page 파라미터
        max_page: 최대 페이지
        max_retries: 재시도 횟수
        batches: 커스텀 배치 설정

    Returns:
        BatchSearcher 인스턴스
    """
    def fetch_wrapper(page_num):
        return fetch_page_func(page_num, query, trace_id, cookies, fingerprint, proxy)

    return BatchSearcher(
        fetch_func=fetch_wrapper,
        max_page=max_page,
        max_retries=max_retries,
        batches=batches,
        cookies_ref=cookies  # 원본 쿠키 참조 전달 (Cookie Jar)
    )
