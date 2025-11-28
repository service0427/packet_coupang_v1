#!/usr/bin/env python3
"""
HTML 파일에서 self.__next_f.push 데이터 추출

사용법:
  python3 tools/extract_nextf.py                    # 랜덤 파일 선택
  python3 tools/extract_nextf.py 5540725827.html    # 특정 파일 지정
  python3 tools/extract_nextf.py --all              # 모든 항목 표시
"""

import re
import json
import random
import sys
from pathlib import Path

# 프로젝트 루트
PROJECT_ROOT = Path(__file__).parent.parent
HTML_DIR = PROJECT_ROOT / 'html'


def extract_next_f_push(html_content):
    """self.__next_f.push 데이터 추출"""
    # self.__next_f.push([...]) 패턴 찾기
    pattern = r'self\.__next_f\.push\(\s*(\[.*?\])\s*\)'
    matches = re.findall(pattern, html_content, re.DOTALL)

    results = []
    for match in matches:
        try:
            data = json.loads(match)
            results.append(data)
        except json.JSONDecodeError:
            # JSON 파싱 실패 시 원본 저장
            results.append({'raw': match[:500] + '...' if len(match) > 500 else match})

    return results


def parse_next_f_data(data_list):
    """next_f 데이터 파싱 및 분류"""
    parsed = {
        'metadata': [],      # 메타데이터
        'product_info': [],  # 상품 정보
        'json_data': [],     # JSON 데이터
        'other': []          # 기타
    }

    for idx, item in enumerate(data_list):
        if isinstance(item, dict) and 'raw' in item:
            parsed['other'].append({'index': idx, 'data': item['raw']})
            continue

        if not isinstance(item, list):
            parsed['other'].append({'index': idx, 'data': item})
            continue

        # [id, content] 형식
        if len(item) >= 2:
            item_id = item[0]
            content = item[1] if len(item) > 1 else None

            # 문자열 내용 파싱 시도
            if isinstance(content, str):
                # JSON 문자열인 경우
                if content.startswith('{') or content.startswith('['):
                    try:
                        json_content = json.loads(content)
                        parsed['json_data'].append({
                            'index': idx,
                            'id': item_id,
                            'data': json_content
                        })
                        continue
                    except:
                        pass

                # 상품 정보 포함 여부 체크
                if any(keyword in content for keyword in ['productId', 'itemId', 'vendorItemId', 'price', 'title']):
                    parsed['product_info'].append({
                        'index': idx,
                        'id': item_id,
                        'content': content[:2000] if len(content) > 2000 else content
                    })
                else:
                    parsed['metadata'].append({
                        'index': idx,
                        'id': item_id,
                        'content': content[:500] if len(content) > 500 else content
                    })
            else:
                parsed['json_data'].append({
                    'index': idx,
                    'id': item_id,
                    'data': content
                })

    return parsed


def find_product_data(parsed_data):
    """상품 관련 데이터 찾기"""
    product_fields = {}

    # JSON 데이터에서 상품 정보 찾기
    for item in parsed_data['json_data']:
        data = item.get('data', {})
        if isinstance(data, dict):
            # 상품 정보 관련 필드 찾기
            def search_dict(d, path=''):
                if not isinstance(d, dict):
                    return
                for key, value in d.items():
                    current_path = f"{path}.{key}" if path else key
                    if key in ['title', 'productName', 'name'] and isinstance(value, str) and len(value) > 5:
                        product_fields[f'title ({current_path})'] = value[:100]
                    elif key in ['price', 'salePrice', 'originalPrice', 'basePrice']:
                        product_fields[f'price ({current_path})'] = value
                    elif key in ['rating', 'ratingScore', 'averageRating']:
                        product_fields[f'rating ({current_path})'] = value
                    elif key in ['reviewCount', 'ratingCount', 'totalReviewCount']:
                        product_fields[f'reviews ({current_path})'] = value
                    elif key in ['productId', 'itemId', 'vendorItemId']:
                        product_fields[f'id ({current_path})'] = value
                    elif key in ['soldOut', 'isSoldOut']:
                        product_fields[f'soldOut ({current_path})'] = value
                    elif key in ['deliveryType', 'rocketDelivery']:
                        product_fields[f'delivery ({current_path})'] = value
                    elif isinstance(value, dict):
                        search_dict(value, current_path)
                    elif isinstance(value, list) and len(value) > 0 and isinstance(value[0], dict):
                        for i, v in enumerate(value[:3]):  # 처음 3개만
                            search_dict(v, f"{current_path}[{i}]")

            search_dict(data)

    return product_fields


def main():
    show_all = '--all' in sys.argv

    # 파일 선택
    if len(sys.argv) > 1 and not sys.argv[1].startswith('--'):
        filename = sys.argv[1]
        if not filename.endswith('.html'):
            filename += '.html'
        html_path = HTML_DIR / filename
    else:
        # 랜덤 선택
        html_files = list(HTML_DIR.glob('*.html'))
        if not html_files:
            print("❌ HTML 파일이 없습니다.")
            return
        html_path = random.choice(html_files)

    if not html_path.exists():
        print(f"❌ 파일 없음: {html_path}")
        return

    print(f"{'=' * 70}")
    print(f"📄 파일: {html_path.name}")
    print(f"{'=' * 70}")

    # HTML 읽기
    html_content = html_path.read_text(encoding='utf-8')
    print(f"📊 HTML 크기: {len(html_content):,} bytes")

    # next_f.push 추출
    data_list = extract_next_f_push(html_content)
    print(f"📦 self.__next_f.push 항목: {len(data_list)}개")

    if not data_list:
        print("❌ next_f.push 데이터가 없습니다.")
        return

    # 데이터 파싱
    parsed = parse_next_f_data(data_list)

    print(f"\n{'─' * 70}")
    print("📋 데이터 분류:")
    print(f"   - 메타데이터: {len(parsed['metadata'])}개")
    print(f"   - 상품 정보: {len(parsed['product_info'])}개")
    print(f"   - JSON 데이터: {len(parsed['json_data'])}개")
    print(f"   - 기타: {len(parsed['other'])}개")

    # 상품 관련 필드 찾기
    product_fields = find_product_data(parsed)
    if product_fields:
        print(f"\n{'─' * 70}")
        print("🛒 발견된 상품 정보:")
        for field, value in product_fields.items():
            print(f"   {field}: {value}")

    # 상세 출력
    if show_all or len(parsed['json_data']) <= 10:
        print(f"\n{'─' * 70}")
        print("📦 JSON 데이터 상세:")
        for item in parsed['json_data']:
            print(f"\n[{item['index']}] ID: {item['id']}")
            data_str = json.dumps(item['data'], ensure_ascii=False, indent=2)
            if len(data_str) > 3000 and not show_all:
                print(data_str[:3000] + '\n... (truncated)')
            else:
                print(data_str)
    else:
        print(f"\n💡 전체 JSON 데이터 보기: python3 tools/extract_nextf.py {html_path.name} --all")

    # 상품 정보 문자열 출력
    if parsed['product_info']:
        print(f"\n{'─' * 70}")
        print("🔍 상품 정보 포함 문자열:")
        for item in parsed['product_info'][:5]:  # 처음 5개만
            print(f"\n[{item['index']}] ID: {item['id']}")
            print(item['content'][:1000] if not show_all else item['content'])


if __name__ == '__main__':
    main()
