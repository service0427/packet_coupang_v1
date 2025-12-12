"""
TLS 핑거프린트 관리 모듈
- JSON 파일에서 TLS 프로파일 로드
- 랜덤 선택 기능

Note: DB 의존성 없음, 로컬 JSON 파일만 사용
"""

import json
import random
from pathlib import Path

# JSON 파일 경로 (lib/work/tls_profiles.json)
_TLS_PROFILES_PATH = Path(__file__).parent.parent / 'work' / 'tls_profiles.json'

# 캐시 (한 번 로드 후 재사용)
_profiles_cache = None


def _load_profiles():
    """TLS 프로필 JSON 로드 (캐시)"""
    global _profiles_cache
    if _profiles_cache is None:
        with open(_TLS_PROFILES_PATH, 'r', encoding='utf-8') as f:
            _profiles_cache = json.load(f)
    return _profiles_cache


def get_tls_profile(platform=None, excluded_builds=None):
    """TLS 프로필 랜덤 선택

    Args:
        platform: 'pc', 'mobile', 또는 None (전체 랜덤)
        excluded_builds: 제외할 chrome_version 목록 (예: ['142.0.0.0'])

    Returns:
        dict: TLS 프로필 레코드 또는 None
    """
    data = _load_profiles()
    excluded_builds = set(excluded_builds or [])

    # 플랫폼별 프로필 수집
    candidates = []

    if platform in ('pc', None):
        for profile_id, profile in data.get('pc', {}).items():
            if profile.get('chrome_version_full') not in excluded_builds:
                candidates.append({'profile_id': profile_id, **profile})

    if platform in ('mobile', None):
        for profile_id, profile in data.get('mobile', {}).items():
            if profile.get('chrome_version_full') not in excluded_builds:
                candidates.append({'profile_id': profile_id, **profile})

    if not candidates:
        return None

    return random.choice(candidates)


def build_tls_extra_fp(profile):
    """extra_fp 딕셔너리 생성

    Args:
        profile: TLS 프로필 레코드

    Returns:
        dict: curl-cffi extra_fp 파라미터
    """
    sig_algs = profile['signature_algorithms']
    # 이미 리스트면 그대로, 문자열이면 파싱
    if isinstance(sig_algs, str):
        sig_algs = json.loads(sig_algs)

    return {
        'tls_signature_algorithms': sig_algs,
        'tls_grease': True,
        'tls_permute_extensions': True,  # Chrome 106+: extension 순서 랜덤화
        'http2_stream_weight': 256,
        'http2_stream_exclusive': 1,
        'tls_cert_compression': 'brotli',
    }


def build_tls_headers(profile, referer=None):
    """HTTP 헤더 생성

    Args:
        profile: TLS 프로필 레코드
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

    # sec-ch-ua 헤더
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
        match_type: 쿠키 매칭 타입 (exact, subnet, random)
        user_platform: 사용자가 명시적으로 지정한 플랫폼

    Returns:
        str: 'pc' 또는 'mobile'
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
    """TLS 프로필 목록 조회

    Args:
        platform: 'pc', 'mobile' 또는 None (전체)

    Returns:
        list: 프로필 목록
    """
    data = _load_profiles()
    result = []

    if platform in ('pc', None):
        for profile_id, profile in data.get('pc', {}).items():
            result.append({
                'profile_id': profile_id,
                'platform': 'pc',
                'browser_version': profile['browser_version'],
            })

    if platform in ('mobile', None):
        for profile_id, profile in data.get('mobile', {}).items():
            result.append({
                'profile_id': profile_id,
                'platform': 'mobile',
                'browser_version': profile['browser_version'],
            })

    return result


if __name__ == '__main__':
    print("TLS 핑거프린트 모듈 테스트 (JSON 기반)")
    print("=" * 60)

    # 프로필 목록
    profiles = list_tls_profiles()
    print(f"\n총 {len(profiles)}개 프로필")

    mobile = [p for p in profiles if p['platform'] == 'mobile']
    pc = [p for p in profiles if p['platform'] == 'pc']
    print(f"  Mobile: {len(mobile)}개")
    print(f"  PC: {len(pc)}개")

    # 랜덤 선택 테스트
    print(f"\n랜덤 Mobile 프로필:")
    p = get_tls_profile(platform='mobile')
    if p:
        print(f"  {p['profile_id']} (Chrome {p['browser_version']})")

    print(f"\n랜덤 PC 프로필:")
    p = get_tls_profile(platform='pc')
    if p:
        print(f"  {p['profile_id']} (Chrome {p['browser_version']})")
