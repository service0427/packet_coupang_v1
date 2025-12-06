"""
공통 함수 및 상수
"""

import io
import sys
import json
from datetime import datetime
from pathlib import Path

# 프로젝트 루트 (lib/work/common.py → lib/work → lib → packet_coupang_v1)
PROJECT_ROOT = Path(__file__).parent.parent.parent

# 로그 디렉토리
LOG_DIR = PROJECT_ROOT / 'logs'
MAX_LOG_FILES = 30


class ConsoleLogger:
    """콘솔 출력을 캡처하면서 동시에 화면에도 출력하는 클래스

    모든 출력에 타임스탬프를 자동 추가 (디버깅용)
    """

    def __init__(self, add_timestamp=True):
        self.buffer = io.StringIO()
        self.original_stdout = sys.stdout
        self.add_timestamp = add_timestamp
        self._line_start = True  # 새 줄 시작 여부

    def write(self, text):
        """stdout에 쓰면서 버퍼에도 저장 (타임스탬프 추가)"""
        if not text:
            return

        # 타임스탬프 추가 (화면 + 버퍼 동일)
        if self.add_timestamp:
            timestamped = self._add_timestamp(text)
            self.original_stdout.write(timestamped)
            self.buffer.write(timestamped)
        else:
            self.original_stdout.write(text)
            self.buffer.write(text)

    def _add_timestamp(self, text):
        """텍스트에 타임스탬프 추가"""
        result = []
        for char in text:
            if self._line_start and char != '\n':
                # 새 줄 시작 시 타임스탬프 추가
                ts = datetime.now().strftime('%H:%M:%S.%f')[:12]
                result.append(f"[{ts}] ")
                self._line_start = False
            result.append(char)
            if char == '\n':
                self._line_start = True
        return ''.join(result)

    def flush(self):
        """flush 호출 시 원본 stdout도 flush"""
        self.original_stdout.flush()

    def get_content(self):
        """캡처된 내용 반환"""
        return self.buffer.getvalue()

    def start(self):
        """캡처 시작"""
        sys.stdout = self

    def stop(self):
        """캡처 중지 및 원본 복원"""
        sys.stdout = self.original_stdout


def save_console_log(start_time: datetime, content: str):
    """콘솔 로그 저장 (최대 30개 유지)

    Args:
        start_time: 시작 시간
        content: 콘솔 출력 내용

    Returns:
        Path: 저장된 로그 파일 경로
    """
    console_dir = LOG_DIR / 'console'
    console_dir.mkdir(parents=True, exist_ok=True)

    # 로그 파일명: YYYYMMDD_HHMMSS.log
    log_filename = f"{start_time.strftime('%Y%m%d_%H%M%S')}.log"
    log_path = console_dir / log_filename

    # 저장
    with open(log_path, 'w', encoding='utf-8') as f:
        f.write(content)

    # 오래된 로그 삭제 (30개 초과 시)
    log_files = sorted(console_dir.glob('*.log'), key=lambda x: x.stat().st_mtime)
    while len(log_files) > MAX_LOG_FILES:
        oldest = log_files.pop(0)
        oldest.unlink()

    return log_path


def save_work_log(work_type: str, start_time: datetime, end_time: datetime,
                  stats: dict, parallel: int, count: int):
    """작업 완료 후 통계 로그 저장 (최대 30개 유지)"""
    stats_dir = LOG_DIR / 'stats'
    stats_dir.mkdir(parents=True, exist_ok=True)

    # 로그 파일명: YYYYMMDD_HHMMSS.json
    log_filename = f"{start_time.strftime('%Y%m%d_%H%M%S')}.json"
    log_path = stats_dir / log_filename

    elapsed = (end_time - start_time).total_seconds()

    # 로그 데이터
    log_data = {
        'type': work_type,
        'start_time': start_time.isoformat(),
        'end_time': end_time.isoformat(),
        'elapsed_seconds': round(elapsed, 1),
        'config': {
            'parallel': parallel,
            'count': count if count > 0 else 'infinite'
        },
        'stats': {
            'total': stats.get('total', 0),
            'found': stats.get('found', 0),
            'not_found': stats.get('not_found', 0),
            'blocked': stats.get('blocked', 0),
            'error': stats.get('error', 0),
            'no_work': stats.get('no_work', 0),
            'cancelled': stats.get('cancelled', 0)
        },
        'rates': {}
    }

    # 비율 계산
    total = stats.get('total', 0)
    if total > 0:
        log_data['rates']['found_rate'] = round(stats.get('found', 0) * 100 / total, 1)
        log_data['rates']['blocked_rate'] = round(stats.get('blocked', 0) * 100 / total, 1)

    # 저장
    with open(log_path, 'w', encoding='utf-8') as f:
        json.dump(log_data, f, ensure_ascii=False, indent=2)

    # 오래된 로그 삭제 (30개 초과 시)
    log_files = sorted(stats_dir.glob('*.json'), key=lambda x: x.stat().st_mtime)
    while len(log_files) > MAX_LOG_FILES:
        oldest = log_files.pop(0)
        oldest.unlink()

    return log_path
