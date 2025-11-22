#!/usr/bin/env python3
"""
TLS Rotator - Chrome TLS 버전 로테이션 시스템

Mobile UA를 사용하면 구버전(127-130)도 사용 가능하여
총 18개 이상의 TLS 프로파일로 로테이션 가능
"""

import json
import random
from pathlib import Path
from typing import Optional, Dict, List, Tuple

# PC UA에서 안정적으로 작동하는 버전 (재검증 완료)
PC_WORKING_VERSIONS = [136, 138, 140, 142]

# Mobile UA에서 작동하는 버전 (재검증 결과 구버전 제외)
MOBILE_WORKING_VERSIONS = [136, 138, 140, 142]

# Mobile UA로만 작동하는 버전 (재검증 결과 없음)
MOBILE_ONLY_VERSIONS = []

# 참고: 초기 테스트에서는 더 많은 버전이 작동했으나,
# 요청 빈도가 높아지면 일시적으로 차단될 수 있음
# 안정적인 운영을 위해 검증된 4개 버전만 사용 권장


class TLSRotator:
    """TLS 프로파일 로테이션 관리자"""

    def __init__(self, base_dir: Path, strategy: str = "round_robin"):
        """
        Args:
            base_dir: 프로젝트 루트 디렉토리
            strategy: 로테이션 전략 (round_robin, random, weighted)
        """
        self.base_dir = base_dir
        self.tls_dir = base_dir / "chrome-versions" / "tls"
        self.strategy = strategy

        # 프로파일 로드
        self.profiles = self._load_profiles()

        # 로테이션 상태
        self.pc_index = 0
        self.mobile_index = 0
        self.blocked_versions = set()

        # 통계
        self.stats = {
            'total_requests': 0,
            'success': 0,
            'blocked': 0,
            'by_version': {}
        }

    def _load_profiles(self) -> Dict[int, Dict]:
        """모든 TLS 프로파일 로드"""
        profiles = {}

        for f in self.tls_dir.glob("*.json"):
            # 메타 파일 제외
            if any(x in f.name for x in ['summary', 'mapping', 'cache']):
                continue

            try:
                with open(f, 'r') as fp:
                    data = json.load(fp)

                version = f.stem
                major = int(version.split('.')[0])

                profiles[major] = {
                    'version': version,
                    'major': major,
                    'ja3_text': data.get('ja3_text', ''),
                    'ja3_hash': data.get('ja3_hash', ''),
                    'akamai_text': data.get('akamai_text', ''),
                    'user_agent': data.get('user_agent', '')
                }
            except Exception as e:
                print(f"프로파일 로드 실패: {f.name} - {e}")

        return profiles

    def get_pc_profile(self) -> Tuple[Dict, Dict]:
        """PC UA용 TLS 프로파일 반환

        Returns:
            (profile, headers) 튜플
        """
        # 차단되지 않은 버전 필터링
        available = [v for v in PC_WORKING_VERSIONS if v not in self.blocked_versions]

        if not available:
            # 모든 버전이 차단되면 리셋
            self.blocked_versions.clear()
            available = PC_WORKING_VERSIONS

        # 전략에 따라 버전 선택
        if self.strategy == "random":
            major = random.choice(available)
        elif self.strategy == "weighted":
            # 최신 버전에 가중치
            weights = [i + 1 for i in range(len(available))]
            major = random.choices(available, weights=weights)[0]
        else:  # round_robin
            major = available[self.pc_index % len(available)]
            self.pc_index += 1

        profile = self.profiles.get(major, self.profiles.get(136))

        headers = self._get_pc_headers(profile['user_agent'])

        return profile, headers

    def get_mobile_profile(self, ua_version: int = 120) -> Tuple[Dict, Dict]:
        """Mobile UA용 TLS 프로파일 반환

        Mobile UA를 사용하면 구버전 TLS도 사용 가능

        Args:
            ua_version: User-Agent의 Chrome 버전 (기본 120)

        Returns:
            (profile, headers) 튜플
        """
        # 차단되지 않은 버전 필터링
        available = [v for v in MOBILE_WORKING_VERSIONS if v not in self.blocked_versions]

        if not available:
            self.blocked_versions.clear()
            available = MOBILE_WORKING_VERSIONS

        # 전략에 따라 버전 선택
        if self.strategy == "random":
            major = random.choice(available)
        elif self.strategy == "weighted":
            weights = [i + 1 for i in range(len(available))]
            major = random.choices(available, weights=weights)[0]
        else:  # round_robin
            major = available[self.mobile_index % len(available)]
            self.mobile_index += 1

        profile = self.profiles.get(major, self.profiles.get(136))

        headers = self._get_mobile_headers(ua_version)

        return profile, headers

    def get_mixed_profile(self) -> Tuple[Dict, Dict]:
        """PC와 Mobile을 섞어서 최대 다양성 확보

        Returns:
            (profile, headers) 튜플
        """
        # 50% 확률로 Mobile UA 사용 (더 많은 버전 사용 가능)
        if random.random() < 0.5:
            return self.get_mobile_profile()
        else:
            return self.get_pc_profile()

    def _get_pc_headers(self, user_agent: str) -> Dict:
        """PC용 헤더 생성"""
        return {
            'User-Agent': user_agent,
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

    def _get_mobile_headers(self, ua_version: int = 120) -> Dict:
        """Mobile용 헤더 생성"""
        mobile_ua = f"Mozilla/5.0 (Linux; Android 14; SM-S928N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{ua_version}.0.6099.144 Mobile Safari/537.36"

        return {
            'User-Agent': mobile_ua,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://www.coupang.com/',
            'sec-ch-ua-mobile': '?1',
            'sec-ch-ua-platform': '"Android"',
            'sec-fetch-dest': 'document',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
        }

    def mark_blocked(self, major: int):
        """특정 버전을 차단 목록에 추가"""
        self.blocked_versions.add(major)
        print(f"TLS 버전 {major} 차단됨. 남은 버전: {len(MOBILE_WORKING_VERSIONS) - len(self.blocked_versions)}")

    def record_result(self, major: int, success: bool):
        """요청 결과 기록"""
        self.stats['total_requests'] += 1

        if success:
            self.stats['success'] += 1
        else:
            self.stats['blocked'] += 1

        if major not in self.stats['by_version']:
            self.stats['by_version'][major] = {'success': 0, 'blocked': 0}

        if success:
            self.stats['by_version'][major]['success'] += 1
        else:
            self.stats['by_version'][major]['blocked'] += 1

    def get_stats(self) -> Dict:
        """통계 반환"""
        return {
            **self.stats,
            'success_rate': self.stats['success'] / max(1, self.stats['total_requests']),
            'blocked_versions': list(self.blocked_versions),
            'available_pc': len([v for v in PC_WORKING_VERSIONS if v not in self.blocked_versions]),
            'available_mobile': len([v for v in MOBILE_WORKING_VERSIONS if v not in self.blocked_versions])
        }

    def reset(self):
        """상태 초기화"""
        self.pc_index = 0
        self.mobile_index = 0
        self.blocked_versions.clear()
        self.stats = {
            'total_requests': 0,
            'success': 0,
            'blocked': 0,
            'by_version': {}
        }


def get_all_available_versions() -> Dict:
    """사용 가능한 모든 버전 정보 반환"""
    return {
        'pc_versions': PC_WORKING_VERSIONS,
        'mobile_versions': MOBILE_WORKING_VERSIONS,
        'mobile_only': MOBILE_ONLY_VERSIONS,
        'total_unique': len(set(PC_WORKING_VERSIONS + MOBILE_WORKING_VERSIONS)),
        'max_tls_profiles': len(MOBILE_WORKING_VERSIONS)  # Mobile이 더 많음
    }


if __name__ == '__main__':
    # 테스트
    base_dir = Path(__file__).parent.parent
    rotator = TLSRotator(base_dir, strategy="round_robin")

    print("=" * 60)
    print("TLS Rotator Test")
    print("=" * 60)

    info = get_all_available_versions()
    print(f"PC 버전: {len(info['pc_versions'])}개")
    print(f"Mobile 버전: {len(info['mobile_versions'])}개")
    print(f"Mobile 전용: {info['mobile_only']}")
    print(f"총 유니크 버전: {info['total_unique']}개")
    print()

    print("PC 프로파일 로테이션 (5회):")
    for i in range(5):
        profile, headers = rotator.get_pc_profile()
        print(f"  {i+1}. Chrome {profile['major']}")

    print()
    print("Mobile 프로파일 로테이션 (5회):")
    for i in range(5):
        profile, headers = rotator.get_mobile_profile()
        print(f"  {i+1}. Chrome {profile['major']} TLS + Mobile UA")

    print()
    print("Mixed 프로파일 로테이션 (5회):")
    for i in range(5):
        profile, headers = rotator.get_mixed_profile()
        ua_type = "Mobile" if "Android" in headers['sec-ch-ua-platform'] else "PC"
        print(f"  {i+1}. Chrome {profile['major']} + {ua_type} UA")
