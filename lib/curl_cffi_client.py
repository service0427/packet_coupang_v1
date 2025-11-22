#!/usr/bin/env python3
"""
curl-cffi 클라이언트 - 커스텀 TLS 핑거프린트 지원

브라우저에서 추출한 TLS 프로파일(JA3/Akamai)을 사용하여
쿠팡 Akamai Bot Manager를 우회합니다.
"""

import json
import time
import random
from pathlib import Path
from typing import Optional
from curl_cffi import requests


class CoupangClient:
    """쿠팡 API 클라이언트 (커스텀 TLS 핑거프린트)"""

    def __init__(self, chrome_version: str, base_dir: Optional[Path] = None):
        """
        Args:
            chrome_version: Chrome 버전 (예: '136.0.7103.113')
            base_dir: 프로젝트 루트 디렉토리
        """
        self.chrome_version = chrome_version
        self.base_dir = base_dir or Path(__file__).parent.parent

        # TLS 프로파일 로드
        self.tls_profile = self._load_tls_profile()

        # 쿠키 로드
        self.cookies = self._load_cookies()

        # JA3/Akamai 문자열
        self.ja3_text = self.tls_profile.get('ja3_text', '')
        self.akamai_text = self.tls_profile.get('akamai_text', '')
        self.user_agent = self.tls_profile.get('user_agent', '')

        # extra_fp 설정 (signature_algorithms, tls_grease, tls_cert_compression)
        self.extra_fp = self._build_extra_fp()

        # sec-ch-ua 헤더 생성
        self.sec_ch_ua = self._build_sec_ch_ua()

        # 기본 헤더
        self.headers = {
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://www.coupang.com/',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
        }

        # 요청 간 딜레이 (초)
        self.delay = 5.0

    def _load_tls_profile(self) -> dict:
        """TLS 프로파일 로드"""
        tls_file = self.base_dir / 'chrome-versions' / 'tls' / f'{self.chrome_version}.json'

        if not tls_file.exists():
            raise FileNotFoundError(f'TLS 프로파일을 찾을 수 없습니다: {tls_file}')

        with open(tls_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _load_cookies(self) -> dict:
        """쿠키 로드"""
        cookie_file = self.base_dir / 'cookies' / f'chrome{self.chrome_version}_cookies.json'

        if not cookie_file.exists():
            raise FileNotFoundError(f'쿠키 파일을 찾을 수 없습니다: {cookie_file}')

        with open(cookie_file, 'r', encoding='utf-8') as f:
            cookies_list = json.load(f)

        # Playwright 쿠키 형식을 dict로 변환
        return {c['name']: c['value'] for c in cookies_list}

    def _build_extra_fp(self) -> dict:
        """extra_fp 설정 빌드 (signature_algorithms, tls_grease, tls_cert_compression)"""
        # TLS 프로파일에서 signature_algorithms 추출
        sig_algs = self._extract_signature_algorithms()

        return {
            'tls_signature_algorithms': sig_algs if sig_algs else None,
            'tls_grease': True,
            'tls_permute_extensions': False,
            'tls_cert_compression': 'brotli',
        }

    def _extract_signature_algorithms(self) -> list:
        """TLS 프로파일에서 signature_algorithms 이름 목록 추출"""
        tls = self.tls_profile.get('tls', {})
        extensions = tls.get('extensions', [])

        for ext in extensions:
            if ext.get('name') == 'signature_algorithms':
                data = ext.get('data', {})
                algs = data.get('supported_signature_algorithms', [])
                return [a['name'] for a in algs if 'name' in a]

        return []

    def _build_sec_ch_ua(self) -> str:
        """sec-ch-ua 헤더 생성"""
        major = self.chrome_version.split('.')[0]
        return f'"Chromium";v="{major}", "Google Chrome";v="{major}", "Not-A.Brand";v="99"'

    def get(self, url: str, proxy: str = None, **kwargs) -> requests.Response:
        """GET 요청 (커스텀 TLS 적용)"""
        # sec-ch-ua 헤더 동적 추가
        headers = self.headers.copy()
        headers['sec-ch-ua'] = self.sec_ch_ua

        request_kwargs = {
            'headers': headers,
            'cookies': self.cookies,
            'ja3': self.ja3_text,
            'akamai': self.akamai_text,
            'extra_fp': self.extra_fp,
            'timeout': kwargs.get('timeout', 30),
        }

        if proxy:
            request_kwargs['proxy'] = proxy

        return requests.get(
            url,
            **request_kwargs,
            **{k: v for k, v in kwargs.items() if k != 'timeout'}
        )

    def search(self, query: str, page: int = 1, proxy: str = None) -> requests.Response:
        """쿠팡 검색"""
        url = f'https://www.coupang.com/np/search?q={query}&channel=user&page={page}'
        return self.get(url, proxy=proxy)

    def search_pages(self, query: str, pages: int = 5, verbose: bool = True) -> list:
        """여러 페이지 검색

        Returns:
            list: 각 페이지 결과 [{'page': 1, 'status_code': 200, 'size': 1234, 'result': 'SUCCESS'}, ...]
        """
        results = []

        import sys

        consecutive_blocks = 0

        for page in range(1, pages + 1):
            # 첫 요청 제외하고 랜덤 딜레이 적용
            if page > 1:
                # 연속 차단 시 더 긴 대기
                if consecutive_blocks > 0:
                    delay = self.delay * 2 + random.uniform(1, 3)
                else:
                    delay = self.delay + random.uniform(0, 2.0)
                time.sleep(delay)

            try:
                response = self.search(query, page)
                size = len(response.content)
                status = 'SUCCESS' if size > 50000 else 'BLOCKED'

                result = {
                    'page': page,
                    'status_code': response.status_code,
                    'size': size,
                    'result': status
                }
                results.append(result)

                if verbose:
                    print(f'Page {page}: {response.status_code} | {size:,} bytes | {status}')
                    sys.stdout.flush()

                # 차단 카운터 업데이트
                if status == 'BLOCKED':
                    consecutive_blocks += 1
                else:
                    consecutive_blocks = 0

            except Exception as e:
                result = {
                    'page': page,
                    'error': str(e),
                    'result': 'ERROR'
                }
                results.append(result)
                consecutive_blocks += 1

                if verbose:
                    print(f'Page {page}: ERROR - {e}')
                    sys.stdout.flush()

        return results

    def get_info(self) -> dict:
        """클라이언트 정보"""
        sig_algs = self.extra_fp.get('tls_signature_algorithms', [])
        return {
            'chrome_version': self.chrome_version,
            'ja3_hash': self.tls_profile.get('ja3_hash', 'N/A'),
            'akamai_hash': self.tls_profile.get('akamai_hash', 'N/A'),
            'cookie_count': len(self.cookies),
            'user_agent': self.user_agent[:80] + '...' if len(self.user_agent) > 80 else self.user_agent,
            'extra_fp': {
                'signature_algorithms_count': len(sig_algs) if sig_algs else 0,
                'tls_grease': self.extra_fp.get('tls_grease'),
                'tls_cert_compression': self.extra_fp.get('tls_cert_compression'),
            }
        }


def get_available_versions(base_dir: Optional[Path] = None) -> list:
    """사용 가능한 Chrome 버전 목록 (쿠키와 TLS 프로파일 모두 있는 버전)"""
    base_dir = base_dir or Path(__file__).parent.parent

    tls_dir = base_dir / 'chrome-versions' / 'tls'
    cookies_dir = base_dir / 'cookies'

    versions = []

    for tls_file in tls_dir.glob('*.json'):
        version = tls_file.stem
        # 숫자로 시작하는 버전만 (버전 형식 확인)
        if version[0].isdigit():
            cookie_file = cookies_dir / f'chrome{version}_cookies.json'
            if cookie_file.exists():
                versions.append(version)

    return sorted(versions, key=lambda x: [int(p) for p in x.split('.')])


# CLI 실행
if __name__ == '__main__':
    import sys
    import io

    # Windows stdout 인코딩 설정
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    base_dir = Path(__file__).parent.parent

    # 사용 가능한 버전 확인
    versions = get_available_versions(base_dir)

    if not versions:
        print('No available versions.')
        print('Run: npm run coupang browser <version>')
        sys.exit(1)

    # 버전 선택
    if len(sys.argv) > 1:
        version = sys.argv[1]
        # 부분 매칭
        matched = [v for v in versions if v.startswith(version)]
        if matched:
            version = matched[0]
        else:
            print(f'Version not found: {version}')
            print(f'\nAvailable versions:')
            for v in versions:
                print(f'  - {v}')
            sys.exit(1)
    else:
        version = versions[-1]  # 최신 버전

    # 검색어
    query = sys.argv[2] if len(sys.argv) > 2 else 'notebook'

    # 클라이언트 생성
    client = CoupangClient(version, base_dir)

    # 정보 출력
    info = client.get_info()
    print('=' * 60)
    print(f"Chrome Version: {info['chrome_version']}")
    print(f"JA3 Hash: {info['ja3_hash']}")
    print(f"Akamai Hash: {info['akamai_hash']}")
    print(f"Cookie Count: {info['cookie_count']}")
    print('=' * 60)
    print()

    # 검색 테스트
    results = client.search_pages(query, pages=3)

    # 결과 요약
    success_count = sum(1 for r in results if r.get('result') == 'SUCCESS')
    print(f'\nResult: {success_count}/3 pages success')
