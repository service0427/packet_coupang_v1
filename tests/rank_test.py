#!/usr/bin/env python3
"""
Rank 테스트 - 병렬 실행
python3 rank_test.py -n 100 -w 20

Ctrl+C로 중단 시 현재까지 결과 출력

서브넷 차단 관리:
- 연속 5회 차단 시 해당 서브넷 제외
- 성공 시 연속 차단 카운트 리셋
"""

import sys
import signal
import subprocess
import argparse
import re
import unicodedata
import threading
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# 전역 취소 플래그
cancelled = False

# 서브넷별 연속 차단 카운트 (thread-safe)
subnet_block_counts = {}  # {subnet: consecutive_block_count}
subnet_lock = threading.Lock()
BLOCK_THRESHOLD = 5  # 연속 차단 횟수 임계값


def update_subnet_status(subnet, blocked):
    """서브넷 차단 상태 업데이트

    Args:
        subnet: 서브넷 (예: '110.70.46')
        blocked: 차단 여부

    Returns:
        bool: 해당 서브넷이 임계값 초과로 제외되었는지
    """
    if not subnet or subnet == '?':
        return False

    with subnet_lock:
        if blocked:
            subnet_block_counts[subnet] = subnet_block_counts.get(subnet, 0) + 1
            if subnet_block_counts[subnet] >= BLOCK_THRESHOLD:
                return True  # 임계값 초과
        else:
            # 성공 시 리셋
            subnet_block_counts[subnet] = 0
        return False


def is_subnet_blocked(subnet):
    """서브넷이 차단 임계값 초과인지 확인"""
    if not subnet or subnet == '?':
        return False
    with subnet_lock:
        return subnet_block_counts.get(subnet, 0) >= BLOCK_THRESHOLD


def get_blocked_subnets():
    """차단된 서브넷 목록 반환"""
    with subnet_lock:
        return [s for s, c in subnet_block_counts.items() if c >= BLOCK_THRESHOLD]


def get_display_width(text):
    """문자열의 실제 표시 폭 계산 (한글=2, 영문=1)"""
    width = 0
    for char in text:
        if unicodedata.east_asian_width(char) in ('F', 'W'):
            width += 2
        else:
            width += 1
    return width


def pad_to_width(text, width):
    """지정된 폭에 맞게 패딩 추가"""
    current_width = get_display_width(text)
    if current_width >= width:
        return text
    return text + ' ' * (width - current_width)

sys.path.insert(0, str(Path(__file__).parent.parent / 'lib'))
from common.db import insert_one, execute_query
from common.proxy import get_proxy_list


def cleanup_old_cookies(max_age_minutes=120):
    """오래된 쿠키 만료 처리 (init_status='expired')

    Args:
        max_age_minutes: 만료 기준 시간 (분, 기본: 120분)

    Returns:
        int: 만료 처리된 쿠키 수
    """
    # 만료 대상 쿠키 수 조회
    result = execute_query("""
        SELECT COUNT(*) as cnt FROM cookies
        WHERE created_at < NOW() - INTERVAL %s MINUTE
          AND init_status != 'expired'
    """, (max_age_minutes,))
    count = result[0]['cnt'] if result else 0

    if count > 0:
        # init_status를 expired로 변경 (DELETE 권한 없음)
        execute_query("""
            UPDATE cookies
            SET init_status = 'expired'
            WHERE created_at < NOW() - INTERVAL %s MINUTE
              AND init_status != 'expired'
        """, (max_age_minutes,))

    return count


def get_cookie_count():
    """사용 가능한 쿠키 수 조회 (expired 제외)"""
    result = execute_query("SELECT COUNT(*) as cnt FROM cookies WHERE init_status != 'expired'")
    return result[0]['cnt'] if result else 0


def cleanup_old_logs(log_dir, max_count=30):
    """오래된 로그 파일 정리

    Args:
        log_dir: 로그 디렉토리 경로
        max_count: 유지할 최대 로그 파일 수
    """
    log_files = sorted(log_dir.glob('rank_test_*.log'), key=lambda f: f.stat().st_mtime, reverse=True)

    # max_count 초과분 삭제
    for old_file in log_files[max_count:]:
        try:
            old_file.unlink()
        except Exception:
            pass


def parse_result(output):
    """출력에서 결과 파싱"""
    result = {}

    # 키워드 파싱: "🎲 랜덤 선택 [PL#2362]: 검색어"
    match = re.search(r'\[PL#(\d+)\]: (.+)', output)
    if match:
        result['pl_id'] = match.group(1)
        result['keyword'] = match.group(2).strip()

    # 타겟 파싱: "타겟: 8805482155"
    match = re.search(r'타겟: (\d+)', output)
    if match:
        result['product_id'] = match.group(1)

    # 순위 파싱: "순위: 7등" (미발견 시 0)
    match = re.search(r'순위: (\d+)등', output)
    if match:
        result['rank'] = int(match.group(1))
    else:
        result['rank'] = 0

    # 쿠키 ID 파싱: "쿠키 ID: 3381" 또는 "✅ 쿠키:3381"
    match = re.search(r'쿠키[^:]*:\s*(\d+)', output)
    if match:
        result['cookie_id'] = int(match.group(1))

    # IP 파싱: "IP: 175.223.38.238"
    match = re.search(r'IP: ([\d.]+)', output)
    if match:
        result['proxy_ip'] = match.group(1)

    # TLS 버전 파싱: "TLS: Chrome 136" 또는 "TLS:136"
    match = re.search(r'TLS[:\s]*(?:Chrome\s*)?(\d+)', output)
    if match:
        result['tls_version'] = int(match.group(1))

    # init_status 파싱: "상태: valid | 소스: local | 쿠키버전: 131"
    match = re.search(r'상태:\s*(\w+)', output)
    if match:
        result['init_status'] = match.group(1)

    # source 파싱: "소스: local"
    match = re.search(r'소스:\s*(\w+)', output)
    if match:
        result['source'] = match.group(1)

    # 쿠키 chrome_version 파싱: "쿠키버전: 131"
    match = re.search(r'쿠키버전:\s*(\S+)', output)
    if match:
        result['cookie_version'] = match.group(1)

    # 경과 시간 파싱: "경과: 생성 1234초 | 최종성공 567초"
    match = re.search(r'생성\s*(\d+)초', output)
    if match:
        result['created_age'] = int(match.group(1))

    match = re.search(r'최종성공\s*(\d+)초', output)
    if match:
        result['last_success_age'] = int(match.group(1))

    # 직접 접속 상품 제목 파싱: "title: 상품명"
    match = re.search(r'^\s*title:\s*(.+)$', output, re.MULTILINE)
    if match:
        result['title'] = match.group(1).strip()

    # 직접 접속 실패 여부 (403 차단 등)
    if '응답 크기 부족' in output or '직접 접속' in output and '❌' in output:
        result['direct_blocked'] = True

    # 상품 발견 여부
    result['found'] = '✅ 상품 발견' in output

    # 차단 여부 (HTTP/2 에러 포함 - 가장 흔한 차단 방식)
    result['blocked'] = ('차단됨' in output or 'BLOCKED' in output or
                         'CHALLENGE' in output or 'HTTP/2 stream' in output or
                         'HTTP2_PROTOCOL_ERROR' in output)

    # 검색된 상품 수 파싱: "❌ 상품 미발견 (123개 검색)"
    match = re.search(r'상품 미발견 \((\d+)개 검색\)', output)
    if match:
        result['search_count'] = int(match.group(1))

    # 페이지 에러 파싱: "에러: P1:CHALLENGE_1234B, P2:STATUS_403"
    match = re.search(r'에러:\s*(.+?)(?:\n|$)', output)
    if match:
        result['page_errors'] = match.group(1).strip()

    return result


def run_single_search(task_id):
    """단일 검색 실행"""
    global cancelled
    if cancelled:
        return {
            'task_id': task_id,
            'stdout': '',
            'stderr': 'CANCELLED',
            'returncode': -2
        }

    # 차단된 서브넷 목록
    blocked_subnets = get_blocked_subnets()

    # 명령어 구성
    cmd = ['python3', 'coupang.py', 'search', '--random']
    if blocked_subnets:
        cmd.extend(['--exclude-subnets', ','.join(blocked_subnets)])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(Path(__file__).parent.parent)
        )
        return {
            'task_id': task_id,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'returncode': result.returncode
        }
    except subprocess.TimeoutExpired:
        return {
            'task_id': task_id,
            'stdout': '',
            'stderr': 'TIMEOUT',
            'returncode': -1
        }
    except Exception as e:
        return {
            'task_id': task_id,
            'stdout': '',
            'stderr': str(e),
            'returncode': -1
        }


def save_to_db(parsed):
    """결과 DB 저장"""
    try:
        # use_count, cookie_age 조회
        use_count = 1
        cookie_age = 0
        if parsed.get('cookie_id'):
            cookie_result = execute_query(
                'SELECT success_count, TIMESTAMPDIFF(SECOND, created_at, NOW()) as age FROM cookies WHERE id = %s',
                (parsed.get('cookie_id'),)
            )
            if cookie_result:
                use_count = cookie_result[0]['success_count'] + 1
                cookie_age = cookie_result[0]['age']

        insert_one("""
            INSERT INTO rank_test_logs
            (pl_id, keyword, product_id, rank, cookie_id, use_count, cookie_age, proxy_ip)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            parsed.get('pl_id'),
            parsed.get('keyword'),
            parsed.get('product_id'),
            parsed.get('rank', 0),
            parsed.get('cookie_id'),
            use_count,
            cookie_age,
            parsed.get('proxy_ip')
        ))
        return True
    except Exception as e:
        print(f"DB 저장 실패: {e}")
        return False


def print_summary(stats, start_time, subnet_stats, ip_stats, proxy_count, per_ip, interrupted=False):
    """결과 요약 출력 및 로그 저장"""
    end_time = datetime.now()
    elapsed = (end_time - start_time).total_seconds()

    # 출력 내용 수집
    lines = []
    lines.append("=" * 70)
    if interrupted:
        lines.append("결과 요약 (중단됨)")
    else:
        lines.append("결과 요약")
    lines.append("=" * 70)
    lines.append(f"총 실행: {stats['total']}회 | 소요: {elapsed:.1f}초")
    if stats['total'] > 0:
        found_rate = stats['found']*100//stats['total']
        lines.append(f"✅ 발견: {stats['found']}회 ({found_rate}%)")
        lines.append(f"❌ 미발견: {stats['not_found']}회")
        lines.append(f"🚫 차단: {stats['blocked']}회")
        lines.append(f"⚠️ 에러: {stats['error']}회")
        if stats.get('cancelled', 0) > 0:
            lines.append(f"🛑 취소: {stats['cancelled']}회")
    lines.append(f"💾 DB 저장: {stats['saved']}건")

    # 서브넷별 통계 (사용량 많은 순)
    if subnet_stats:
        lines.append("")
        lines.append("--- 서브넷별 통계 ---")
        sorted_subnets = sorted(subnet_stats.items(), key=lambda x: x[1]['total'], reverse=True)
        for subnet, s in sorted_subnets[:10]:  # 상위 10개만
            block_rate = s['blocked'] * 100 // s['total'] if s['total'] > 0 else 0
            lines.append(f"  {subnet}.* : {s['total']:2d}회 (차단:{s['blocked']} 발견:{s['found']}) {block_rate}%차단")

    # IP별 상세 통계 (서브넷별로 그룹화)
    if ip_stats:
        lines.append("")
        lines.append("--- IP별 상세 통계 ---")

        # 서브넷별로 그룹화
        subnet_ips = {}
        for ip, s in ip_stats.items():
            subnet = '.'.join(ip.split('.')[:3])
            if subnet not in subnet_ips:
                subnet_ips[subnet] = []
            subnet_ips[subnet].append((ip, s))

        # 서브넷별 총 사용량 순으로 정렬
        sorted_subnet_groups = sorted(
            subnet_ips.items(),
            key=lambda x: sum(ip[1]['total'] for ip in x[1]),
            reverse=True
        )

        for subnet, ips in sorted_subnet_groups[:8]:  # 상위 8개 서브넷만
            # 해당 서브넷의 총계
            subnet_total = sum(ip[1]['total'] for ip in ips)
            subnet_blocked = sum(ip[1]['blocked'] for ip in ips)
            block_rate = subnet_blocked * 100 // subnet_total if subnet_total > 0 else 0

            lines.append(f"  {subnet}.* ({subnet_total}회, {block_rate}%차단)")

            # IP별 상세 (사용량 순)
            sorted_ips = sorted(ips, key=lambda x: x[1]['total'], reverse=True)
            for ip, s in sorted_ips:
                last_octet = ip.split('.')[-1]
                ip_block_rate = s['blocked'] * 100 // s['total'] if s['total'] > 0 else 0
                status = "🚫" if ip_block_rate >= 80 else ("⚠️" if ip_block_rate >= 50 else "✅")
                lines.append(f"    .{last_octet:>3}: {s['total']:2d}회 (차단:{s['blocked']} 발견:{s['found']}) {status}")

    lines.append(f"\n완료: {end_time.strftime('%H:%M:%S.%f')[:12]}")

    # 화면 출력
    print("\n" + "\n".join(lines))

    # 로그 파일 저장
    log_dir = Path(__file__).parent.parent / 'logs'
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"rank_test_{start_time.strftime('%Y%m%d_%H%M%S')}.log"

    # 오래된 로그 정리 (최대 30개 유지)
    cleanup_old_logs(log_dir, max_count=30)

    with open(log_file, 'w', encoding='utf-8') as f:
        f.write(f"Rank 테스트 결과\n")
        f.write(f"시작: {start_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:23]}\n")
        f.write(f"종료: {end_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:23]}\n")
        f.write(f"프록시: {proxy_count}개 | IP당: {per_ip}개\n")
        f.write("\n".join(lines))

    print(f"\n📄 로그 저장: {log_file}")


def main():
    global cancelled

    parser = argparse.ArgumentParser(description='Rank 테스트 - 병렬 실행')
    parser.add_argument('-n', '--count', type=int, default=10, help='총 실행 횟수 (기본: 10)')
    parser.add_argument('-w', '--workers', type=int, help='동시 실행 수 (생략: IP수 × 동시요청수)')
    parser.add_argument('-p', '--per-ip', type=int, default=1, help='IP당 동시 요청 수 (기본: 1)')
    parser.add_argument('--min-remain', type=int, default=30, help='프록시 최소 남은 시간 (초, 기본: 30)')
    parser.add_argument('--no-save', action='store_true', help='DB 저장 안함')
    parser.add_argument('-v', '--verbose', action='store_true', help='상세 출력')
    parser.add_argument('--no-cleanup', action='store_true', help='오래된 쿠키 정리 건너뛰기')
    args = parser.parse_args()

    # 오래된 쿠키 만료 처리 (120분 이상)
    if not args.no_cleanup:
        expired_count = cleanup_old_cookies(max_age_minutes=120)
        if expired_count > 0:
            remaining = get_cookie_count()
            print(f"🧹 오래된 쿠키 만료: {expired_count}개 (120분+ 경과)")
            print(f"   사용 가능: {remaining}개")

    # 프록시 수 조회하여 workers 자동 계산
    proxies = get_proxy_list(min_remain=args.min_remain)
    proxy_count = len(proxies)

    if proxy_count == 0:
        print("❌ 사용 가능한 프록시 없음")
        return

    if args.workers:
        workers = args.workers
    else:
        workers = proxy_count * args.per_ip

    # count가 workers보다 작으면 workers 조정
    workers = min(workers, args.count)

    start_time = datetime.now()
    print("=" * 70)
    print(f"Rank 테스트 - 병렬 실행")
    print("=" * 70)
    print(f"시작: {start_time.strftime('%H:%M:%S.%f')[:12]}")
    print(f"프록시: {proxy_count}개 | IP당: {args.per_ip}개 → 동시: {workers}개")
    print(f"총 실행: {args.count}회")
    print(f"💡 Ctrl+C로 중단 가능 (현재까지 결과 출력)")
    print("=" * 70)

    # 통계
    stats = {
        'total': 0,
        'found': 0,
        'not_found': 0,
        'blocked': 0,
        'error': 0,
        'saved': 0,
        'cancelled': 0
    }
    # 서브넷별 통계: {subnet: {'total': 0, 'blocked': 0}}
    subnet_stats = {}
    # IP별 통계: {ip: {'total': 0, 'blocked': 0, 'found': 0}}
    ip_stats = {}

    # Ctrl+C 핸들러
    def signal_handler(sig, frame):
        global cancelled
        if not cancelled:
            cancelled = True
            print("\n\n🛑 중단 요청... 실행 중인 작업 완료 대기...")

    signal.signal(signal.SIGINT, signal_handler)

    try:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            # 모든 작업 제출
            futures = {executor.submit(run_single_search, i): i for i in range(1, args.count + 1)}

            for future in as_completed(futures):
                task_id = futures[future]
                result = future.result()

                # 취소된 작업은 스킵
                if result['stderr'] == 'CANCELLED':
                    stats['cancelled'] += 1
                    continue

                stats['total'] += 1

                if result['returncode'] != 0 or result['stderr'] == 'TIMEOUT':
                    stats['error'] += 1
                    now = datetime.now().strftime('%H:%M:%S.%f')[:12]
                    print(f"[{now}] [{task_id:3d}] ❌ 에러")
                    continue

                parsed = parse_result(result['stdout'])

                # 상태 판단
                if parsed['blocked']:
                    stats['blocked'] += 1
                    status = "🚫 차단  "
                    rank_str = "    "
                elif parsed['found']:
                    stats['found'] += 1
                    rank = parsed.get('rank', 0)
                    status = "✅ 발견  "
                    rank_str = f"#{rank:<3d}"
                else:
                    stats['not_found'] += 1
                    status = "❌ 미발견"
                    rank_str = "    "

                # 키워드 자르기 (표시폭 12 기준)
                keyword = parsed.get('keyword', '?')
                if get_display_width(keyword) > 12:
                    # 12폭에 맞게 자르기
                    cut_keyword = ''
                    for char in keyword:
                        if get_display_width(cut_keyword + char) > 12:
                            break
                        cut_keyword += char
                    keyword = cut_keyword

                # IP 서브넷 추출 (마지막 옥텟 제외)
                proxy_ip = parsed.get('proxy_ip', '')
                subnet = '.'.join(proxy_ip.split('.')[:3]) if proxy_ip else '?'

                # 서브넷별 통계 수집
                if subnet != '?':
                    if subnet not in subnet_stats:
                        subnet_stats[subnet] = {'total': 0, 'blocked': 0, 'found': 0}
                    subnet_stats[subnet]['total'] += 1
                    if parsed['blocked']:
                        subnet_stats[subnet]['blocked'] += 1
                    elif parsed['found']:
                        subnet_stats[subnet]['found'] += 1

                # IP별 통계 수집
                if proxy_ip:
                    if proxy_ip not in ip_stats:
                        ip_stats[proxy_ip] = {'total': 0, 'blocked': 0, 'found': 0}
                    ip_stats[proxy_ip]['total'] += 1
                    if parsed['blocked']:
                        ip_stats[proxy_ip]['blocked'] += 1
                    elif parsed['found']:
                        ip_stats[proxy_ip]['found'] += 1

                # 서브넷 차단 상태 업데이트 (연속 차단 추적)
                newly_blocked = update_subnet_status(subnet, parsed['blocked'])
                if newly_blocked:
                    print(f"  ⛔ 서브넷 {subnet}.* 연속 {BLOCK_THRESHOLD}회 차단 → 제외")

                # 요약 출력 (고정폭 정렬 + 타임스탬프)
                now = datetime.now().strftime('%H:%M:%S.%f')[:12]
                keyword_padded = pad_to_width(keyword, 12)
                cookie_id = parsed.get('cookie_id', '?')
                pl_id = parsed.get('pl_id', '?')
                tls_ver = parsed.get('tls_version', '?')
                init_status = parsed.get('init_status', '?')
                source = parsed.get('source', '?')
                cookie_ver = parsed.get('cookie_version', '?')

                # source 표시 (local→L, pg_sync→P)
                source_map = {'local': 'L', 'pg_sync': 'P'}
                source_short = source_map.get(source, '?')

                # 쿠키버전 메이저만 추출 (131.0.6778.264 → 131)
                cookie_major = cookie_ver.split('.')[0] if cookie_ver != '?' else '?'

                # 미발견 시 검색된 상품 수 및 에러/직접접속 title 표시
                title_info = ''
                if not parsed['found'] and not parsed['blocked']:
                    # 검색된 상품 수 표시
                    search_count = parsed.get('search_count', 0)
                    title_info = f' | ({search_count}개)'

                    # 페이지 에러가 있으면 우선 표시
                    page_errors = parsed.get('page_errors', '')
                    if page_errors:
                        title_info += f' [{page_errors}]'
                    else:
                        title = parsed.get('title', '')
                        if title and title != 'null':
                            # 제목 20자로 제한
                            if get_display_width(title) > 20:
                                cut_title = ''
                                for char in title:
                                    if get_display_width(cut_title + char) > 17:
                                        break
                                    cut_title += char
                                title = cut_title + '...'
                            title_info += f' {title}'
                        elif parsed.get('direct_blocked'):
                            title_info += ' (직접접속 차단)'

                # init_status 끝에 표시
                init_info = f' ({init_status})' if init_status else ''

                # 경과 시간 표시 (생성/최종성공)
                created_age = parsed.get('created_age', 0)
                last_success_age = parsed.get('last_success_age')
                age_str = f"C{created_age//60}m"
                if last_success_age is not None:
                    age_str += f"/S{last_success_age//60}m"

                print(f"[{now}] [{task_id:3d}] {status} {rank_str} | {keyword_padded} | PL#{pl_id:<5} | {cookie_id:>6} | [{source_short}] v{cookie_major:>3}/{tls_ver:<3} | {age_str:>10} | {subnet}{title_info}{init_info}")

                # 상세 출력
                if args.verbose:
                    print(result['stdout'])
                    print("-" * 70)

                # DB 저장 (차단 아닌 경우만)
                if not args.no_save and not parsed['blocked'] and parsed.get('keyword'):
                    if save_to_db(parsed):
                        stats['saved'] += 1

    except KeyboardInterrupt:
        # 이미 signal_handler에서 처리됨
        pass

    # 결과 요약
    print_summary(stats, start_time, subnet_stats, ip_stats, proxy_count, args.per_ip, interrupted=cancelled)


if __name__ == '__main__':
    main()
