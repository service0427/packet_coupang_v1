"""
프록시 관리 모듈
- 프록시 API 조회 (3001)
- 쿠키 API 조회 (5151)
- IP 바인딩된 프록시 + 쿠키 조합
"""

import json
import random
import time
import urllib.request
from .cookie import get_subnet, parse_cookie_data

# API 설정
PROXY_API_URL = 'http://mkt.techb.kr:3001/api/proxy/status'
COOKIE_API_URL = 'http://mkt.techb.kr:5151/api/cookies'

# API 타임아웃 설정
API_TIMEOUT = 15  # 타임아웃 15초


def get_proxy_list(min_remain=30):
    """프록시 API에서 사용 가능한 프록시 목록 조회

    Args:
        min_remain: 최소 남은 시간 (초)

    Returns:
        list: [{'proxy': 'host:port', 'external_ip': '...', 'remaining_work_seconds': '...'}, ...]
    """
    try:
        # urllib 사용 (curl_cffi는 TLS 핑거프린트로 인해 API 서버 거부)
        req = urllib.request.urlopen(PROXY_API_URL, timeout=5)
        data = json.loads(req.read())
        if data.get('success'):
            proxies = data.get('proxies', [])
            # 클라이언트에서 min_remain 필터링
            return [
                p for p in proxies
                if int(p.get('remaining_work_seconds', 0)) >= min_remain
            ]
    except Exception as e:
        print(f"프록시 API 오류: {e}")
    return []


def get_proxy_external_ip(proxy_host):
    """프록시 호스트의 현재 외부 IP 조회

    Args:
        proxy_host: 'host:port' 형식 (socks5:// 제외)

    Returns:
        str: 외부 IP 또는 None
    """
    try:
        req = urllib.request.urlopen(PROXY_API_URL, timeout=5)
        data = json.loads(req.read())
        if data.get('success'):
            for p in data.get('proxies', []):
                if p.get('proxy') == proxy_host:
                    return p.get('external_ip')
    except Exception as e:
        pass
    return None


def check_external_ip(proxy_url):
    """프록시를 통한 외부 IP 확인

    Args:
        proxy_url: socks5://host:port 형식

    Returns:
        str: 외부 IP 또는 None
    """
    try:
        resp = requests.get(
            'https://api.ipify.org?format=json',
            proxy=proxy_url,
            timeout=5,
            verify=False
        )
        return resp.json().get('ip')
    except:
        return None


def allocate_cookie(minutes=60, platform_type='mobile', max_fail=5, max_success=10,
                    exclude_product=None, retries=3):
    """쿠키 API에서 쿠키+프록시 할당 (30초 락)

    Args:
        minutes: created_at 기준 N분 이내
        platform_type: 'pc' (exact/subnet만) 또는 'mobile' (random 폴백 가능)
        max_fail: fail_count 최대값
        max_success: success_count 최대값
        exclude_product: 제외할 product_id (해당 상품을 클릭한 쿠키 제외)
        retries: 최대 재시도 횟수

    Returns:
        dict: 쿠키+프록시 레코드 또는 None
        {
            'id': 쿠키 ID,
            'cookies': [...],
            'proxy': {
                'ip': '프록시 IP',
                'port': 포트,
                'external_ip': '외부 IP',
                'match_type': 'exact' | 'subnet' | 'random',
                'original_ip': '쿠키 원본 IP'
            },
            ...
        }
    """
    url = f"{COOKIE_API_URL}/allocate?minutes={minutes}&type={platform_type}&max_fail={max_fail}&max_success={max_success}"
    if exclude_product:
        url += f"&exclude_product={exclude_product}"

    for attempt in range(retries):
        try:
            req = urllib.request.urlopen(url, timeout=API_TIMEOUT)
            resp = json.loads(req.read())
            if resp.get('success'):
                cookie = resp.get('data')
                if cookie:
                    # 기존 코드 호환: proxy_ip 필드 추가
                    proxy_info = cookie.get('proxy', {})
                    cookie['proxy_ip'] = proxy_info.get('original_ip')
                    # age_minutes 계산 (created_at 기준)
                    if cookie.get('created_at'):
                        from datetime import datetime
                        try:
                            created = datetime.fromisoformat(cookie['created_at'].replace('Z', '+00:00'))
                            now = datetime.now(created.tzinfo) if created.tzinfo else datetime.utcnow()
                            cookie['age_minutes'] = int((now - created).total_seconds() / 60)
                        except:
                            cookie['age_minutes'] = 0
                    return cookie
            return None  # success=false, 재시도 없이 종료
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(0.5 * (attempt + 1))  # 백오프: 0.5, 1, 1.5초
                continue
            # 최종 실패 - 조용히 처리
            return None
    return None


def report_cookie_result(cookie_id, success, retries=2):
    """쿠키 사용 결과 보고

    Args:
        cookie_id: 쿠키 ID
        success: 성공 여부
        retries: 최대 재시도 횟수
    """
    url = f"{COOKIE_API_URL}/result"
    payload = json.dumps({'id': cookie_id, 'success': success}).encode('utf-8')

    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
            urllib.request.urlopen(req, timeout=API_TIMEOUT)
            return  # 성공
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(0.3)
                continue
            # 최종 실패 - 조용히 처리


def get_bound_cookie(max_age_minutes=60, platform_type='mobile', exclude_product=None, verbose=True):
    """쿠키+프록시 조합 반환 (Cookie API가 프록시 매칭까지 처리)

    Args:
        max_age_minutes: 쿠키 최대 나이 (분)
        platform_type: 'pc' (exact/subnet만) 또는 'mobile' (random 폴백 가능)
        exclude_product: 제외할 product_id (해당 상품을 클릭한 쿠키 제외)
        verbose: 디버그 정보 출력

    Returns:
        dict: {
            'proxy': 'socks5://host:port',
            'proxy_host': 'host:port',
            'external_ip': '...',
            'cookie_record': {...},
            'cookies': {name: value},
            'match_type': 'exact' | 'subnet' | 'random'
        } 또는 None
    """
    # Cookie API에서 쿠키+프록시 할당 (매칭까지 API가 처리)
    cookie_record = allocate_cookie(minutes=max_age_minutes, platform_type=platform_type,
                                    exclude_product=exclude_product)
    if not cookie_record:
        if verbose:
            print(f"  ⚠️ 쿠키 할당 실패 (max_age: {max_age_minutes}분, type: {platform_type})")
        return None

    proxy_info = cookie_record.get('proxy', {})
    if not proxy_info:
        if verbose:
            print(f"  ⚠️ 프록시 매칭 실패 (쿠키 ID: {cookie_record.get('id')})")
        return None

    cookie_ip = cookie_record.get('proxy_ip')
    cookie_subnet = get_subnet(cookie_ip)

    # 프록시 정보 추출
    proxy_host = f"{proxy_info['ip']}:{proxy_info['port']}"
    external_ip = proxy_info.get('external_ip')
    match_type = proxy_info.get('match_type', 'unknown')

    # 쿠키+프록시 정보 출력
    if verbose:
        match_label = {'exact': '✅ 완전', 'subnet': '🔸 서브넷', 'random': '⚠️ 랜덤'}.get(match_type, match_type)
        print(f"  🍪 쿠키+프록시 할당됨 ({match_label} 매칭):")
        print(f"     쿠키 ID: {cookie_record.get('id')} (age: {cookie_record.get('age_minutes', '?')}분)")
        print(f"     쿠키 IP: {cookie_ip} (subnet: {cookie_subnet})")
        print(f"     프록시: {proxy_host} → 외부IP: {external_ip}")
        print(f"     success/fail: {cookie_record.get('success_count', 0)}/{cookie_record.get('fail_count', 0)}")

    return {
        'proxy': f"socks5://{proxy_host}",
        'proxy_host': proxy_host,
        'external_ip': external_ip,
        'cookie_record': cookie_record,
        'cookies': parse_cookie_data(cookie_record),
        'match_type': match_type
    }


if __name__ == '__main__':
    print("프록시+쿠키 모듈 테스트 (API 5151)")
    print("=" * 60)

    # PC 모드 테스트
    print(f"\n🔗 PC 모드 테스트 (exact/subnet 매칭만)...")
    bound = get_bound_cookie(max_age_minutes=60, platform_type='pc')
    if bound:
        print(f"  ✅ 매칭 성공")
    else:
        print("  ❌ 매칭 실패")

    # Mobile 모드 테스트
    print(f"\n🔗 Mobile 모드 테스트 (random 폴백 가능)...")
    bound = get_bound_cookie(max_age_minutes=120, platform_type='mobile')
    if bound:
        print(f"  ✅ 매칭 성공")
    else:
        print("  ❌ 매칭 실패")
