#!/usr/bin/env python3
"""
마지막 페이지 응답 분석 테스트

키워드: 내셔널지오그래픽바람막이
목적: 검색 결과가 끝났을 때 API가 어떤 응답을 주는지 확인
     → INCOMPLETE 에러 대신 정상 미발견으로 처리하기 위한 구분자 탐색
"""

import sys, os, json, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib'))

from urllib.parse import quote
from curl_cffi import requests
from api.rank_checker_direct import (
    _build_headers, _session_push_token, _session_pcid,
    _session_identity, _session_cmg_dco, TLS_CONFIG
)

BASE_URL = "https://cmapi.coupang.com"

def do_request(url, session):
    query_params = ""
    if '?' in url:
        query_params = url.split('?', 1)[1]
    headers = _build_headers(_session_push_token, _session_pcid, _session_identity, _session_cmg_dco, query_params)
    return session.get(
        url, headers=headers,
        ja3=TLS_CONFIG["ja3"], akamai=TLS_CONFIG["akamai"],
        extra_fp=TLS_CONFIG["extra_fp"], timeout=15,
    )

def main():
    keyword = "내셔널지오그래픽바람막이"
    session = requests.Session()

    params = f"filter=KEYWORD:{quote(keyword)}|CCID:ALL|EXTRAS:channel/user|GET_FILTER:NONE|SINGLE_ENTITY:TRUE@SEARCH&preventingRedirection=false&resultType=default&ccidActivated=false"
    url = f"{BASE_URL}/v3/products?{params}"

    print(f"{'='*70}")
    print(f"키워드: {keyword}")
    print(f"{'='*70}")

    pages = 0
    total_products = 0

    while pages < 20:  # 최대 20페이지까지 시도
        pages += 1
        print(f"\n{'─'*70}")
        print(f"📄 PAGE {pages}")
        print(f"{'─'*70}")

        try:
            resp = do_request(url, session)
            print(f"  HTTP Status: {resp.status_code}")

            if resp.status_code != 200:
                print(f"  ❌ HTTP 에러 → 여기가 끝인가?")
                print(f"  Response headers: {dict(resp.headers)}")
                try:
                    print(f"  Response body (처음 500자): {resp.text[:500]}")
                except:
                    pass
                break

            data = resp.json()
            rCode = data.get('rCode')
            rMessage = data.get('rMessage', '')
            print(f"  rCode: {rCode}")
            print(f"  rMessage: {rMessage}")

            if rCode != 'RET0000':
                print(f"  ❌ rCode 에러 → 여기가 끝인가?")
                # 전체 응답 키 출력
                print(f"  응답 최상위 키: {list(data.keys())}")
                if 'rData' in data:
                    print(f"  rData 키: {list(data['rData'].keys())}")
                break

            rdata = data.get('rData', {})

            # 핵심 필드들 출력
            total_count = rdata.get('totalCount', 'N/A')
            next_key = rdata.get('nextPageKey')
            next_params = rdata.get('nextPageParams', '')
            entity_list = rdata.get('entityList', [])

            # 상품 수 카운트
            product_count = 0
            for ent in entity_list:
                widget = ent.get('entity', {}).get('widget', {})
                metadata = widget.get('metadata', {})
                mandatory = metadata.get('commonBypassLogParams', {}).get('mandatory', {})
                if mandatory.get('productId'):
                    product_count += 1

            total_products += product_count

            print(f"  totalCount: {total_count}")
            print(f"  entityList 길이: {len(entity_list)}")
            print(f"  상품 수 (productId 있는 것): {product_count}")
            print(f"  누적 상품: {total_products}")
            print(f"  nextPageKey: {repr(next_key)[:80]}")
            print(f"  nextPageParams: {repr(next_params)[:80]}")

            # rData의 모든 키 출력 (구분자 후보 탐색)
            rdata_keys = list(rdata.keys())
            print(f"  rData 키 목록: {rdata_keys}")

            # 추가 필드 탐색 (끝 표시 관련 후보)
            for k in ['hasMore', 'hasNext', 'isLastPage', 'lastPage', 'endOfList',
                       'noMoreResults', 'totalPage', 'totalPages', 'maxPage',
                       'currentPage', 'pageNumber', 'resultEnd']:
                if k in rdata:
                    print(f"  ⭐ {k}: {rdata[k]}")

            # entityList가 비었거나 nextPageKey가 없으면 끝
            if not next_key:
                print(f"\n  ✅ nextPageKey 없음 → 여기가 마지막 페이지!")
                break

            if product_count == 0:
                print(f"\n  ⚠️ 상품 0개이지만 nextPageKey는 있음")
                # 한번 더 시도해봄

            # 다음 페이지 URL 구성
            url = f"{BASE_URL}/v3/products?{params}&nextPageKey={quote(next_key)}&nextPageParams={quote(next_params)}&resultType=search"

        except Exception as e:
            print(f"  ❌ 예외 발생: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            break

    print(f"\n{'='*70}")
    print(f"📊 요약")
    print(f"  총 페이지: {pages}")
    print(f"  총 상품: {total_products}")
    print(f"{'='*70}")


if __name__ == '__main__':
    main()
