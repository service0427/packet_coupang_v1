"""
검색 필터 카테고리 추출기

검색 결과 HTML에서 필터에서 지원하는 카테고리 목록을 추출하고,
상품 카테고리와 매칭하여 검색 가능한 최대 depth 카테고리를 찾습니다.

사용법:
    from extractor.filter_extractor import (
        extract_filter_categories,
        find_searchable_category
    )

    # 검색 결과 HTML에서 필터 카테고리 추출
    filter_cats = extract_filter_categories(search_html)
    # {'177295': '문구/오피스', '317778': '스포츠/레저', ...}

    # 상품 카테고리에서 검색 가능한 카테고리 찾기
    product_cats = [
        {'id': '177295', 'name': '문구/오피스'},
        {'id': '178098', 'name': '학용품/수업준비'},
        {'id': '373322', 'name': '필기용품'},
    ]
    searchable = find_searchable_category(product_cats, filter_cats)
    # {'id': '177295', 'name': '문구/오피스', 'depth': 0}
"""

import re


def extract_filter_categories(html_content):
    """검색 결과 HTML에서 필터 지원 카테고리 추출

    Args:
        html_content: 검색 결과 페이지 HTML

    Returns:
        dict: {카테고리ID: 카테고리명} 형태
        예: {'177295': '문구/오피스', '317778': '스포츠/레저'}
    """
    if not html_content:
        return {}

    filter_cats = {}

    # filter-function-bar-category 클래스에서 카테고리 추출
    matches = re.findall(
        r'filter-function-bar-category[^>]*>.*?'
        r'href="[^"]*?/np/categories/(\d+)[^"]*"[^>]*>([^<]+)</a>',
        html_content, re.DOTALL
    )

    for cat_id, name in matches:
        filter_cats[cat_id] = name.strip()

    return filter_cats


def find_searchable_category(product_categories, filter_categories):
    """상품 카테고리에서 검색 필터에서 지원하는 가장 깊은 카테고리 찾기

    Args:
        product_categories: 상품 카테고리 목록 (depth 순서대로)
            [{'id': '177295', 'name': '문구/오피스'}, ...]
        filter_categories: 필터 지원 카테고리 dict
            {'177295': '문구/오피스', ...}

    Returns:
        dict: 검색 가능한 카테고리 정보
            {'id': '177295', 'name': '문구/오피스', 'depth': 0}
        또는 None (지원하는 카테고리 없음)
    """
    if not product_categories or not filter_categories:
        return None

    # 가장 깊은 depth부터 역순으로 검색
    for depth in range(len(product_categories) - 1, -1, -1):
        cat = product_categories[depth]
        cat_id = cat.get('id')

        if cat_id and cat_id in filter_categories:
            return {
                'id': cat_id,
                'name': cat.get('name') or filter_categories[cat_id],
                'depth': depth
            }

    return None


def get_category_support_info(product_categories, filter_categories):
    """상품 카테고리의 검색 필터 지원 여부 상세 정보

    Args:
        product_categories: 상품 카테고리 목록
        filter_categories: 필터 지원 카테고리 dict

    Returns:
        dict: 카테고리별 지원 여부 정보
        {
            'categories': [
                {'id': '177295', 'name': '문구/오피스', 'supported': True},
                {'id': '178098', 'name': '학용품/수업준비', 'supported': False},
            ],
            'max_searchable': {'id': '177295', 'name': '문구/오피스', 'depth': 0},
            'total_depth': 4,
            'searchable_depth': 1
        }
    """
    result = {
        'categories': [],
        'max_searchable': None,
        'total_depth': len(product_categories),
        'searchable_depth': 0
    }

    for depth, cat in enumerate(product_categories):
        cat_id = cat.get('id')
        supported = cat_id in filter_categories if cat_id else False

        result['categories'].append({
            'id': cat_id,
            'name': cat.get('name'),
            'depth': depth,
            'supported': supported
        })

        if supported:
            result['searchable_depth'] = depth + 1
            result['max_searchable'] = {
                'id': cat_id,
                'name': cat.get('name'),
                'depth': depth
            }

    return result


# 기본 필터 카테고리 (검색 API 실패 시 fallback)
DEFAULT_FILTER_CATEGORIES = {
    '178255': '가전디지털',
    '416130': '결혼준비',
    '396463': '국내여행',
    '317777': '도서/음반/DVD',
    '177295': '문구/오피스',
    '115674': '반려동물용품',
    '176522': '뷰티',
    '115673': '생활용품',
    '317778': '스포츠/레저',
    '194276': '식품',
    '383370': '실버스토어',
    '433784': '싱글라이프',
    '410273': '아트/공예',
    '317779': '완구/취미',
    '184060': '자동차용품',
    '185669': '주방용품',
    '221934': '출산/유아동',
    '510691': '쿠팡수입',
    '564653': '패션의류/잡화',
    '305798': '헬스/건강식품',
    '184555': '홈인테리어',
    '316168': '홈카페',
    '393760': '로켓직구',
}


# CLI 테스트
if __name__ == '__main__':
    import json
    from pathlib import Path

    # 검색 결과 HTML 로드
    search_files = list(Path('screenshot').glob('search_*.html'))
    if search_files:
        html = search_files[0].read_text(encoding='utf-8')
        print(f'📄 파일: {search_files[0].name}')
        print('=' * 60)

        # 필터 카테고리 추출
        filter_cats = extract_filter_categories(html)
        print(f'\n검색 필터 지원 카테고리: {len(filter_cats)}개')
        for cat_id, name in sorted(filter_cats.items(), key=lambda x: x[1]):
            print(f'  {cat_id}: {name}')

        # 테스트: 상품 카테고리 매칭
        test_product_cats = [
            {'id': '177295', 'name': '문구/오피스'},
            {'id': '178098', 'name': '학용품/수업준비'},
            {'id': '373322', 'name': '필기용품'},
            {'id': '373331', 'name': '연필깎이'}
        ]

        print('\n' + '=' * 60)
        print('상품 카테고리 검색 지원 분석')
        print('=' * 60)

        info = get_category_support_info(test_product_cats, filter_cats)
        for cat in info['categories']:
            status = '✅' if cat['supported'] else '❌'
            print(f'{status} [{cat["depth"]}] {cat["id"]}: {cat["name"]}')

        print(f'\n검색 가능 최대 depth: {info["searchable_depth"]}/{info["total_depth"]}')
        if info['max_searchable']:
            print(f'검색 가능 카테고리: {info["max_searchable"]["name"]} ({info["max_searchable"]["id"]})')
    else:
        print('❌ 검색 결과 HTML 파일 없음')
        print('\n기본 필터 카테고리:')
        for cat_id, name in sorted(DEFAULT_FILTER_CATEGORIES.items(), key=lambda x: x[1]):
            print(f'  {cat_id}: {name}')
