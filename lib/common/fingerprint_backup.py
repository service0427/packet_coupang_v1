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
        'tls_permute_extensions': True,  # Chrome 106+: extension 순서 랜덤화
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
    platform = fingerprint.get('platform', 'u22')

    # 플랫폼별 Client Hints 설정
    if platform == 's23':
        # Samsung Galaxy S23 (Android Mobile)
        sec_ch_ua = f'"Chromium";v="{major_ver}", "Google Chrome";v="{major_ver}", "Not_A Brand";v="99"'
        sec_ch_ua_mobile = '?1'
        sec_ch_ua_platform = '"Android"'
    else:
        # Ubuntu 22 (Linux Desktop)
        sec_ch_ua = f'"Chromium";v="{major_ver}", "Not.A/Brand";v="99"'
        sec_ch_ua_mobile = '?0'
        sec_ch_ua_platform = '"Linux"'

    return {
        'User-Agent': fingerprint['user_agent'],
        'sec-ch-ua': sec_ch_ua,
        'sec-ch-ua-mobile': sec_ch_ua_mobile,
        'sec-ch-ua-platform': sec_ch_ua_platform,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Referer': referer or 'https://www.coupang.com/',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'same-origin',
    }


# ============================================================================
# tls_profiles 테이블 함수 (신규)
# ============================================================================

def get_tls_profile(platform=None, excluded_builds=None):
    """tls_profiles 테이블에서 랜덤 프로필 조회

    Args:
        platform: 'pc', 'mobile', 또는 None (전체 랜덤)
        excluded_builds: 제외할 chrome_version 목록 (예: ['131.0.6778.108', '136.0.7103.92'])

    Returns:
        dict: TLS 프로필 레코드 또는 None
    """
    # platform 조건 생성
    platform_condition = "platform = %s" if platform else "1=1"
    base_params = [platform] if platform else []

    if excluded_builds:
        placeholders = ','.join(['%s'] * len(excluded_builds))
        query = f"""
            SELECT * FROM tls_profiles
            WHERE {platform_condition} AND enabled = 1 AND chrome_version_full NOT IN ({placeholders})
            ORDER BY RAND() LIMIT 1
        """
        params = base_params + list(excluded_builds)
        rows = execute_query(query, params)
    else:
        query = f"SELECT * FROM tls_profiles WHERE {platform_condition} AND enabled = 1 ORDER BY RAND() LIMIT 1"
        rows = execute_query(query, tuple(base_params) if base_params else ())
    return rows[0] if rows else None


def build_tls_extra_fp(profile):
    """tls_profiles 레코드에서 extra_fp 생성

    Args:
        profile: tls_profiles 레코드

    Returns:
        dict: curl-cffi extra_fp 파라미터
    """
    sig_algs = json.loads(profile['signature_algorithms'])
    return {
        'tls_signature_algorithms': sig_algs,
        'tls_grease': True,
        'tls_permute_extensions': True,  # Chrome 106+: extension 순서 랜덤화
        'http2_stream_weight': 256,
        'http2_stream_exclusive': 1,
        'tls_cert_compression': 'brotli',
    }


def build_tls_headers(profile, referer=None):
    """tls_profiles 레코드에서 HTTP 헤더 생성

    Args:
        profile: tls_profiles 레코드
        referer: Referer 헤더 값

    Returns:
        dict: HTTP 헤더
    """
    headers = {
        'User-Agent': profile['user_agent'],
        'Accept': profile.get('accept_header') or 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Referer': referer or 'https://www.coupang.com/',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'same-origin',
    }

    # sec-ch-ua 헤더 (DB에 저장된 값 사용)
    if profile.get('sec_ch_ua'):
        headers['sec-ch-ua'] = profile['sec_ch_ua']
    if profile.get('sec_ch_ua_mobile'):
        headers['sec-ch-ua-mobile'] = profile['sec_ch_ua_mobile']
    if profile.get('sec_ch_ua_platform'):
        headers['sec-ch-ua-platform'] = profile['sec_ch_ua_platform']

    return headers


def get_tls_platform_for_match_type(match_type, user_platform=None):
    """match_type에 따라 TLS 플랫폼 결정

    Args:
        match_type: 쿠키 매칭 타입 (new_exact, old_subnet, old_random 등)
        user_platform: 사용자가 명시적으로 지정한 플랫폼 (None이면 자동 결정)

    Returns:
        str: 'pc' 또는 'mobile'

    규칙:
        - exact (new_exact, old_exact): PC (IP 완전 일치 → PC가 더 안정적)
        - subnet (new_subnet, old_subnet): PC/Mobile 랜덤 (서브넷 매칭)
        - random (new_random, old_random): Mobile만 (IP 바인딩 없음)
    """
    if user_platform:
        return user_platform

    if 'exact' in match_type:
        return 'pc'
    elif 'subnet' in match_type:
        return random.choice(['pc', 'mobile'])
    else:  # random
        return 'mobile'


def list_tls_profiles(platform=None):
    """tls_profiles 목록 조회

    Args:
        platform: 'pc', 'mobile' 또는 None (전체)

    Returns:
        list: 프로필 목록
    """
    if platform:
        rows = execute_query(
            "SELECT profile_id, platform, browser_version, enabled FROM tls_profiles WHERE platform = %s ORDER BY profile_id",
            (platform,)
        )
    else:
        rows = execute_query(
            "SELECT profile_id, platform, browser_version, enabled FROM tls_profiles ORDER BY platform, profile_id"
        )
    return rows or []


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
