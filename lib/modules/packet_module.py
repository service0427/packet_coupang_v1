"""
Packet Module - Chrome 버전별 TLS 커스텀 패킷 요청 모듈

기능:
- Chrome 버전별 TLS 설정 자동 로드
- curl-cffi manual TLS (ja3 + akamai 파라미터)
- 쿠키 재사용으로 고속 요청
- 차단 감지 및 에러 처리
"""

import sys
import json
import os
from pathlib import Path
from curl_cffi import requests


class PacketModule:
    def __init__(self, base_path=None):
        """
        Args:
            base_path: 프로젝트 루트 경로 (기본: 현재 파일 기준 2단계 상위)
        """
        if base_path is None:
            base_path = Path(__file__).parent.parent.parent
        else:
            base_path = Path(base_path)

        self.base_path = base_path
        self.cookies_path = base_path / 'cookies'
        self.tls_configs_path = base_path / 'tls_configs'
        self.block_threshold = 50000

        # 디렉토리 생성
        self.cookies_path.mkdir(exist_ok=True)
        self.tls_configs_path.mkdir(exist_ok=True)

    def load_tls_config(self, version):
        """
        Chrome 버전별 TLS 설정 로드

        Args:
            version: Chrome 버전 (예: 130, 123)

        Returns:
            dict: {
                'ja3_string': str,
                'akamai_string': str,
                'user_agent': str
            }
        """
        config_file = self.tls_configs_path / f'chrome{version}_profile.json'

        if not config_file.exists():
            raise FileNotFoundError(
                f"TLS 설정 파일을 찾을 수 없습니다: {config_file}\n"
                f"먼저 Browser Module로 TLS 추출을 실행하세요."
            )

        with open(config_file, 'r', encoding='utf-8') as f:
            tls_data = json.load(f)

        # JA3 추출
        browserleaks = tls_data.get('raw_fingerprints', {}).get('https://tls.browserleaks.com/json', {})
        peet = tls_data.get('raw_fingerprints', {}).get('https://tls.peet.ws/api/all', {})

        ja3_string = browserleaks.get('ja3_text')
        if not ja3_string:
            # Fallback: manual_tls_config에서 시도
            ja3_string = tls_data.get('manual_tls_config', {}).get('ja3_string')

        # Akamai 추출
        akamai_string = browserleaks.get('akamai_text')
        if not akamai_string:
            # Fallback: peet.ws에서 시도
            akamai_string = peet.get('http2', {}).get('akamai_fingerprint')

        # User-Agent 추출
        user_agent = browserleaks.get('user_agent') or peet.get('user_agent')

        if not ja3_string or not akamai_string:
            raise ValueError(
                f"Chrome {version} TLS 설정이 불완전합니다\n"
                f"JA3: {ja3_string}\n"
                f"Akamai: {akamai_string}"
            )

        return {
            'ja3_string': ja3_string,
            'akamai_string': akamai_string,
            'user_agent': user_agent,
            'config_file': str(config_file)
        }

    def load_cookies(self, version):
        """
        Chrome 버전별 쿠키 로드

        Args:
            version: Chrome 버전

        Returns:
            dict: {cookie_name: cookie_value}
        """
        cookie_file = self.cookies_path / f'chrome{version}_cookies.json'

        if not cookie_file.exists():
            raise FileNotFoundError(
                f"쿠키 파일을 찾을 수 없습니다: {cookie_file}\n"
                f"먼저 Browser Module로 쿠키 생성을 실행하세요."
            )

        with open(cookie_file, 'r', encoding='utf-8') as f:
            cookies = json.load(f)

        # Playwright 쿠키 포맷 → curl-cffi 포맷
        cookie_dict = {}
        for cookie in cookies:
            cookie_dict[cookie['name']] = cookie['value']

        return cookie_dict

    def build_headers(self, user_agent):
        """
        Chrome 헤더 생성

        Args:
            user_agent: User-Agent 문자열

        Returns:
            dict: HTTP 헤더
        """
        # Chrome 버전 추출 (예: "Chrome/123.0.0.0" → "123")
        import re
        match = re.search(r'Chrome/(\d+)\.', user_agent)
        chrome_version = match.group(1) if match else '123'

        return {
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "ko-KR,ko;q=0.9",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "sec-ch-ua": f'"Chromium";v="{chrome_version}", "Not:A-Brand";v="8"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "none",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1",
        }

    def request(self, version, url, timeout=30):
        """
        Packet 모드로 요청 실행

        Args:
            version: Chrome 버전
            url: 요청 URL
            timeout: 타임아웃 (초)

        Returns:
            dict: {
                'success': bool,
                'size': int,
                'content': str,
                'ja3_string': str,
                'akamai_string': str
            }
        """
        print(f"\n[Packet Module] Chrome {version} Manual TLS 요청")
        print(f"  URL: {url}")

        try:
            # TLS 설정 로드
            tls_config = self.load_tls_config(version)
            print(f"  JA3: {tls_config['ja3_string'][:50]}...")
            print(f"  Akamai: {tls_config['akamai_string']}")

            # 쿠키 로드
            cookies = self.load_cookies(version)
            print(f"  쿠키: {len(cookies)}개 로드됨")

            # 헤더 생성
            headers = self.build_headers(tls_config['user_agent'])

            # 요청 실행
            print("  [요청 중...]")
            response = requests.get(
                url,
                cookies=cookies,
                headers=headers,
                ja3=tls_config['ja3_string'],        # Manual TLS
                akamai=tls_config['akamai_string'],  # Manual HTTP/2
                timeout=timeout
            )

            content = response.text
            size = len(content)

            print(f"  응답 크기: {size} bytes")

            success = size > self.block_threshold

            if success:
                print("  [SUCCESS] 정상 응답")
            else:
                print("  [BLOCKED] 차단 감지")

            return {
                'success': success,
                'size': size,
                'content': content,
                'ja3_string': tls_config['ja3_string'],
                'akamai_string': tls_config['akamai_string'],
                'status_code': response.status_code
            }

        except FileNotFoundError as e:
            print(f"  [ERROR] {e}")
            raise
        except Exception as e:
            print(f"  [ERROR] {e}")
            raise

    def request_multiple_pages(self, version, keyword, max_pages=10, delay=2):
        """
        여러 페이지 요청 (페이지네이션)

        Args:
            version: Chrome 버전
            keyword: 검색 키워드
            max_pages: 최대 페이지 수
            delay: 요청 간 대기 시간 (초)

        Returns:
            dict: {
                'success': bool,
                'results': list,
                'success_rate': float
            }
        """
        import time
        from urllib.parse import quote

        print(f"\n[Packet Module] Chrome {version} - {max_pages}페이지 크롤링")

        results = []

        for page in range(1, max_pages + 1):
            url = f"https://www.coupang.com/np/search?q={quote(keyword)}&page={page}"

            try:
                result = self.request(version, url)
                results.append({
                    'page': page,
                    'success': result['success'],
                    'size': result['size']
                })

                status = '✅' if result['success'] else '❌'
                print(f"  페이지 {page}: {result['size']} bytes {status}")

                if not result['success']:
                    print(f"  [STOP] 페이지 {page}에서 차단 감지")
                    break

                if page < max_pages:
                    time.sleep(delay)

            except Exception as e:
                print(f"  페이지 {page}: ERROR - {e}")
                results.append({
                    'page': page,
                    'success': False,
                    'error': str(e)
                })
                break

        success_count = sum(1 for r in results if r['success'])
        print(f"\n  [결과] {success_count}/{len(results)} 페이지 성공")

        return {
            'success': success_count > 0,
            'results': results,
            'success_rate': success_count / len(results) if results else 0
        }


def main():
    """
    CLI 인터페이스

    Usage:
        python packet_module.py <version> <url>
        python packet_module.py 130 "https://www.coupang.com/np/search?q=물티슈"
    """
    if len(sys.argv) < 3:
        print("Usage: python packet_module.py <version> <url>")
        print("Example: python packet_module.py 130 \"https://www.coupang.com/np/search?q=물티슈\"")
        sys.exit(1)

    version = int(sys.argv[1])
    url = sys.argv[2]

    module = PacketModule()

    try:
        result = module.request(version, url)

        print("\n" + "="*80)
        print("결과 요약")
        print("="*80)
        print(f"성공: {result['success']}")
        print(f"응답 크기: {result['size']} bytes")
        print(f"상태 코드: {result['status_code']}")
        print(f"JA3: {result['ja3_string'][:50]}...")
        print(f"Akamai: {result['akamai_string']}")

    except Exception as e:
        print(f"\n[FATAL ERROR] {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
