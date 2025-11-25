"""
스크린샷 모듈 (2단계 구조)

1단계: save_html_with_urls() - HTML + 이미지 URL JSON 저장 (rank 실행 시)
2단계: take_screenshot_from_saved() - 저장된 데이터로 스크린샷 생성 (후처리)

사용 예:
    # 1단계: rank 실행 시 저장
    save_html_with_urls(html, 'reports/search_12345.html')

    # 2단계: 최고 순위 결과만 스크린샷
    take_screenshot_from_saved('reports/search_12345.html')
"""

import os
import re
import json
import hashlib
import requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# 설정 - 프로젝트 루트 기준
PROJECT_ROOT = Path(__file__).parent.parent  # /home/tech/packet_coupang_v1
SCREENSHOT_DIR = PROJECT_ROOT / 'screenshot'
IMAGE_CACHE_DIR = SCREENSHOT_DIR / 'cache'
CHROME_PATH = PROJECT_ROOT / 'chrome-versions/files/chrome-136.0.7103.113/chrome-linux64/chrome'


def extract_image_urls(html):
    """HTML에서 이미지 URL 추출 (이미지 파일만)

    Args:
        html: HTML 문자열

    Returns:
        set: 이미지 URL 집합 (https:// 형태로 정규화)
    """
    patterns = [
        # https:// 프로토콜
        r'src="(https?://[^"]*coupangcdn\.com[^"]*)"',
        r'src="(https?://[^"]*thumbnail[^"]*)"',
        r'data-src="(https?://[^"]*coupangcdn\.com[^"]*)"',
        r'srcset="(https?://[^"\s,]*coupangcdn\.com[^"\s,]*)',
        # // 프로토콜 상대 URL (예: //image7.coupangcdn.com)
        r'src="(//[^"]*coupangcdn\.com[^"]*)"',
        r'data-src="(//[^"]*coupangcdn\.com[^"]*)"',
    ]

    urls = set()
    for pattern in patterns:
        matches = re.findall(pattern, html)
        for url in matches:
            # // 로 시작하면 https:// 추가
            if url.startswith('//'):
                url = 'https:' + url
            urls.add(url)

    # 이미지 파일만 필터링 (js, css 제외)
    image_extensions = ('.jpg', '.jpeg', '.png', '.webp', '.gif', '.svg')
    filtered = set()
    for url in urls:
        url_lower = url.split('?')[0].lower()
        if any(url_lower.endswith(ext) for ext in image_extensions):
            filtered.add(url)

    return filtered


def download_image(url, cache_dir):
    """이미지 다운로드 (캐시 사용)

    Args:
        url: 이미지 URL
        cache_dir: 캐시 디렉토리

    Returns:
        (url, local_path) 또는 (url, None)
    """
    try:
        # URL 해시로 파일명 생성
        url_hash = hashlib.md5(url.encode()).hexdigest()[:16]
        ext = url.split('?')[0].split('.')[-1][:4]
        if ext not in ['jpg', 'jpeg', 'png', 'webp', 'gif']:
            ext = 'jpg'
        local_path = cache_dir / f"{url_hash}.{ext}"

        # 캐시 확인
        if local_path.exists():
            return (url, str(local_path))

        # 다운로드 (프록시 없이)
        resp = requests.get(url, timeout=10, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

        if resp.status_code == 200 and len(resp.content) > 100:
            local_path.write_bytes(resp.content)
            return (url, str(local_path))

    except Exception:
        pass

    return (url, None)


def download_images(urls, cache_dir, max_workers=10):
    """이미지 병렬 다운로드

    Args:
        urls: 이미지 URL 리스트
        cache_dir: 캐시 디렉토리
        max_workers: 병렬 워커 수

    Returns:
        dict: {url: local_path}
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    url_map = {}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = executor.map(lambda u: download_image(u, cache_dir), urls)
        for url, local_path in results:
            if local_path:
                url_map[url] = local_path

    return url_map


def replace_urls_with_local(html, url_map):
    """HTML에서 URL을 로컬 경로로 교체

    Args:
        html: HTML 문자열
        url_map: {url: local_path} 매핑 (https:// 형태)

    Returns:
        str: 수정된 HTML
    """
    for url, local_path in url_map.items():
        # file:// URL로 변환
        file_url = f"file://{local_path}"
        html = html.replace(f'"{url}"', f'"{file_url}"')
        html = html.replace(f"'{url}'", f"'{file_url}'")

        # // 프로토콜 상대 URL도 교체 (예: //image7.coupangcdn.com)
        if url.startswith('https:'):
            relative_url = url[6:]  # https: 제거 → //image7.coupangcdn.com/...
            html = html.replace(f'"{relative_url}"', f'"{file_url}"')
            html = html.replace(f"'{relative_url}'", f"'{file_url}'")

    return html


def take_screenshot(html, output_path, viewport=(1920, 1080), full_page=False):
    """HTML을 Playwright로 렌더링하여 스크린샷

    Args:
        html: HTML 문자열
        output_path: 출력 파일 경로
        viewport: 뷰포트 크기 (width, height)
        full_page: 전체 페이지 스크린샷 여부

    Returns:
        dict: {'success': bool, 'path': str, 'size': int, ...}
    """
    os.environ['DISPLAY'] = ':99'

    try:
        from playwright.sync_api import sync_playwright

        # 디렉토리 생성
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)

        # 1. 이미지 URL 추출
        img_urls = extract_image_urls(html)

        # 2. 이미지 다운로드 (프록시 없이)
        url_map = download_images(img_urls, IMAGE_CACHE_DIR)

        # 3. HTML에서 URL을 로컬 경로로 교체
        html_local = replace_urls_with_local(html, url_map)

        # 4. base 태그 추가 (남은 리소스용)
        html_local = html_local.replace(
            '<head>',
            '<head><base href="https://www.coupang.com/">'
        )

        # 5. Playwright로 렌더링
        with sync_playwright() as p:
            browser = p.chromium.launch(
                executable_path=CHROME_PATH,
                headless=False,
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )

            page = browser.new_page(viewport={
                'width': viewport[0],
                'height': viewport[1]
            })

            page.set_content(html_local, wait_until='domcontentloaded')

            # 스크롤로 lazy loading 트리거
            for i in range(5):
                page.evaluate(f"window.scrollTo(0, {(i+1) * 400})")
                page.wait_for_timeout(300)

            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(1000)

            # 스크린샷
            page.screenshot(path=str(output_path), full_page=full_page)

            # 이미지 로드 통계
            img_count = page.evaluate("document.querySelectorAll('img').length")
            loaded_count = page.evaluate("""
                Array.from(document.querySelectorAll('img'))
                    .filter(img => img.complete && img.naturalHeight > 0).length
            """)

            browser.close()

        file_size = Path(output_path).stat().st_size

        return {
            'success': True,
            'path': str(output_path),
            'size': file_size,
            'images_total': img_count,
            'images_loaded': loaded_count,
            'images_downloaded': len(url_map)
        }

    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def screenshot_from_html_file(html_path, output_path=None):
    """HTML 파일에서 스크린샷 생성 (기존 방식)

    Args:
        html_path: HTML 파일 경로
        output_path: 출력 경로 (None이면 자동 생성)

    Returns:
        dict: 결과
    """
    html_path = Path(html_path)

    if not html_path.exists():
        return {'success': False, 'error': f'파일 없음: {html_path}'}

    with open(html_path, 'r', encoding='utf-8') as f:
        html = f.read()

    if output_path is None:
        output_path = html_path.with_suffix('.png')

    return take_screenshot(html, output_path)


# =============================================================================
# 2단계 구조 함수들
# =============================================================================

def save_html_with_urls(html, output_path, metadata=None):
    """1단계: HTML + 이미지 URL JSON 저장 (rank 실행 시 호출)

    Args:
        html: HTML 문자열
        output_path: HTML 저장 경로 (예: reports/search_12345.html)
        metadata: 추가 메타데이터 (query, rank, product_id 등)

    Returns:
        dict: {'html_path': '...', 'urls_path': '...', 'url_count': N}
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # HTML 저장
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    # 이미지 URL 추출 및 JSON 저장
    img_urls = list(extract_image_urls(html))
    urls_path = output_path.with_suffix('.urls.json')

    urls_data = {
        'image_urls': img_urls,
        'count': len(img_urls),
        'metadata': metadata or {}
    }

    with open(urls_path, 'w', encoding='utf-8') as f:
        json.dump(urls_data, f, ensure_ascii=False, indent=2)

    return {
        'html_path': str(output_path),
        'urls_path': str(urls_path),
        'url_count': len(img_urls)
    }


def take_screenshot_from_saved(html_path, output_path=None, viewport=(1920, 1080), full_page=False):
    """2단계: 저장된 HTML에서 스크린샷 생성 (후처리 시 호출)

    1. HTML 파일 읽기
    2. .urls.json에서 이미지 URL 로드
    3. 이미지 다운로드 (캐시 사용)
    4. HTML 수정 후 렌더링

    Args:
        html_path: HTML 파일 경로
        output_path: 스크린샷 출력 경로 (None이면 .png로 자동 생성)
        viewport: 뷰포트 크기
        full_page: 전체 페이지 스크린샷 여부

    Returns:
        dict: {'success': bool, 'path': str, ...}
    """
    html_path = Path(html_path)
    urls_path = html_path.with_suffix('.urls.json')

    if not html_path.exists():
        return {'success': False, 'error': f'HTML 파일 없음: {html_path}'}

    # HTML 읽기
    with open(html_path, 'r', encoding='utf-8') as f:
        html = f.read()

    # URL JSON 읽기 (있으면 사용, 없으면 HTML에서 추출)
    if urls_path.exists():
        with open(urls_path, 'r', encoding='utf-8') as f:
            urls_data = json.load(f)
        img_urls = urls_data.get('image_urls', [])
    else:
        img_urls = list(extract_image_urls(html))

    # 출력 경로
    if output_path is None:
        output_path = html_path.with_suffix('.png')

    # 스크린샷 생성 (이미지 다운로드 포함)
    return _render_screenshot(html, img_urls, output_path, viewport, full_page)


def _render_screenshot(html, img_urls, output_path, viewport=(1920, 1080), full_page=False):
    """내부 함수: Playwright 렌더링

    Playwright는 file:// 프로토콜 접근이 제한되므로,
    이미지는 원본 URL 그대로 두고 네트워크에서 로드합니다.

    Args:
        html: HTML 문자열
        img_urls: 이미지 URL 리스트 (현재 통계용)
        output_path: 출력 경로
        viewport: 뷰포트 크기
        full_page: 전체 페이지 여부

    Returns:
        dict: 결과
    """
    os.environ['DISPLAY'] = ':99'

    try:
        from playwright.sync_api import sync_playwright

        # 출력 디렉토리 생성
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # base 태그 추가 (상대 URL 처리용)
        html_with_base = html.replace(
            '<head>',
            '<head><base href="https://www.coupang.com/">'
        )

        # Playwright로 렌더링 (이미지는 원본 URL에서 직접 로드)
        with sync_playwright() as p:
            browser = p.chromium.launch(
                executable_path=CHROME_PATH,
                headless=False,
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )

            page = browser.new_page(viewport={
                'width': viewport[0],
                'height': viewport[1]
            })

            page.set_content(html_with_base, wait_until='domcontentloaded')

            # 스크롤로 lazy loading 트리거
            for i in range(5):
                page.evaluate(f"window.scrollTo(0, {(i+1) * 400})")
                page.wait_for_timeout(300)

            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(1500)  # 이미지 로드 대기 시간 증가

            # 스크린샷
            page.screenshot(path=str(output_path), full_page=full_page)

            # 이미지 로드 통계
            img_count = page.evaluate("document.querySelectorAll('img').length")
            loaded_count = page.evaluate("""
                Array.from(document.querySelectorAll('img'))
                    .filter(img => img.complete && img.naturalHeight > 0).length
            """)

            browser.close()

        file_size = Path(output_path).stat().st_size

        return {
            'success': True,
            'path': str(output_path),
            'size': file_size,
            'images_total': img_count,
            'images_loaded': loaded_count,
            'images_extracted': len(img_urls)
        }

    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1:
        html_file = sys.argv[1]
        output_file = sys.argv[2] if len(sys.argv) > 2 else None

        # 2단계 함수 사용
        result = take_screenshot_from_saved(html_file, output_file)
    else:
        # 기본 테스트
        test_html = SCREENSHOT_DIR / 'coupang_search.html'
        if test_html.exists():
            result = take_screenshot_from_saved(test_html)
        else:
            print(f"테스트 파일 없음: {test_html}")
            sys.exit(1)

    if result['success']:
        print(f"✅ 스크린샷 생성 완료")
        print(f"   경로: {result['path']}")
        print(f"   크기: {result['size']:,} bytes")
        print(f"   이미지: {result['images_loaded']}/{result['images_total']} 로드")
        print(f"   다운로드: {result['images_downloaded']}개")
    else:
        print(f"❌ 실패: {result.get('error')}")
