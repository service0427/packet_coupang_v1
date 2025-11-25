"""
TLS 핑거프린트 관리 모듈
- DB에서 custom TLS 프로파일 조회
- 랜덤 선택 기능

Note: impersonate 모드는 사용하지 않음 (CLAUDE.md 참고)
      TLS는 항상 DB의 custom 프로파일만 사용
"""

import json
import random
from .db import execute_query

def get_fingerprint_by_version(chrome_version, platform='u22'):
    """특정 버전 핑거프린트 조회

    Args:
        chrome_version: Chrome 버전 (예: '136.0.7103.113' 또는 136)
        platform: 플랫폼 (u22/win11)

    Returns:
        dict: 핑거프린트 레코드 또는 None
    """
    # 전체 버전 문자열로 조회
    if isinstance(chrome_version, str) and '.' in chrome_version:
        fps = execute_query(
            "SELECT * FROM fingerprints WHERE chrome_version = %s AND platform = %s",
            (chrome_version, platform)
        )
        if fps:
            return fps[0]

    # major 버전으로 조회
    major = int(str(chrome_version).split('.')[0])
    fps = execute_query(
        "SELECT * FROM fingerprints WHERE chrome_major = %s AND platform = %s ORDER BY chrome_version DESC LIMIT 1",
        (major, platform)
    )
    return fps[0] if fps else None


def get_random_fingerprint(platform='u22', verified_only=True):
    """랜덤 핑거프린트 조회

    Args:
        platform: 플랫폼 (u22/win11)
        verified_only: True면 verified=1인 버전만, False면 전체

    Returns:
        dict: 핑거프린트 레코드 또는 None
    """
    if verified_only:
        # DB에서 verified=1인 것 중 랜덤
        fps = execute_query(
            "SELECT * FROM fingerprints WHERE verified = 1 AND platform = %s ORDER BY RAND() LIMIT 1",
            (platform,)
        )
    else:
        # 전체 중 랜덤
        fps = execute_query(
            "SELECT * FROM fingerprints WHERE platform = %s ORDER BY RAND() LIMIT 1",
            (platform,)
        )

    return fps[0] if fps else None


def get_available_versions(platform='u22'):
    """사용 가능한 버전 목록 조회

    Returns:
        list: [{'chrome_major': 136, 'chrome_version': '136.0.7103.113', 'verified': True}, ...]
    """
    fps = execute_query(
        "SELECT DISTINCT chrome_major, chrome_version, verified FROM fingerprints WHERE platform = %s ORDER BY chrome_major",
        (platform,)
    )

    result = []
    for fp in fps:
        result.append({
            'chrome_major': fp['chrome_major'],
            'chrome_version': fp['chrome_version'],
            'verified': bool(fp.get('verified', 0))
        })

    return result


def build_extra_fp(fingerprint):
    """extra_fp 딕셔너리 생성

    Args:
        fingerprint: DB 핑거프린트 레코드

    Returns:
        dict: curl-cffi extra_fp 파라미터
    """
    sig_algs = json.loads(fingerprint['signature_algorithms'])
    return {
        'tls_signature_algorithms': sig_algs,
        'tls_grease': True,
        'tls_permute_extensions': False,
        'tls_cert_compression': 'brotli',
    }


def build_headers(fingerprint, referer=None):
    """HTTP 헤더 생성

    Args:
        fingerprint: DB 핑거프린트 레코드
        referer: Referer 헤더 값

    Returns:
        dict: HTTP 헤더
    """
    major_ver = fingerprint['chrome_major']
    return {
        'User-Agent': fingerprint['user_agent'],
        'sec-ch-ua': f'"Chromium";v="{major_ver}", "Not.A/Brand";v="99"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Linux"',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Referer': referer or 'https://www.coupang.com/',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'same-origin',
    }


if __name__ == '__main__':
    print("TLS 핑거프린트 모듈 테스트")
    print("=" * 60)

    # 사용 가능한 버전 출력
    versions = get_available_versions()
    print(f"\n사용 가능한 버전: {len(versions)}개")
    for v in versions:
        status_str = '✅ verified' if v['verified'] else '⚠️ unverified'
        print(f"  Chrome {v['chrome_major']}: {v['chrome_version']} ({status_str})")

    # 랜덤 핑거프린트
    print(f"\n랜덤 (검증된 버전):")
    fp = get_random_fingerprint(verified_only=True)
    if fp:
        print(f"  Chrome {fp['chrome_major']}: {fp['chrome_version']}")
