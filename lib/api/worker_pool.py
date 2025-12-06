"""
워커 풀 관리

ThreadPoolExecutor를 사용한 동시 요청 처리
"""

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor, Future
from datetime import datetime
from typing import Callable, Any


class WorkerPool:
    """워커 풀 관리자

    동시 요청을 ThreadPoolExecutor로 처리하고 상태를 추적
    """

    def __init__(self, max_workers: int = 20):
        """
        Args:
            max_workers: 최대 동시 워커 수
        """
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.start_time = datetime.now()

        # 상태 추적
        self._lock = threading.Lock()
        self._active_count = 0
        self._total_processed = 0
        self._queue_size = 0

    def submit(self, fn: Callable, *args, **kwargs) -> Future:
        """작업 제출

        Args:
            fn: 실행할 함수
            *args, **kwargs: 함수 인자

        Returns:
            Future: 결과 Future
        """
        with self._lock:
            self._active_count += 1
            self._queue_size += 1

        def wrapper():
            try:
                return fn(*args, **kwargs)
            finally:
                with self._lock:
                    self._active_count -= 1
                    self._total_processed += 1
                    self._queue_size -= 1

        return self.executor.submit(wrapper)

    async def submit_async(self, fn: Callable, *args, **kwargs) -> Any:
        """비동기 작업 제출

        FastAPI와 함께 사용하기 위한 async wrapper

        Args:
            fn: 실행할 함수
            *args, **kwargs: 함수 인자

        Returns:
            Any: 함수 실행 결과
        """
        loop = asyncio.get_event_loop()

        with self._lock:
            self._active_count += 1
            self._queue_size += 1

        try:
            result = await loop.run_in_executor(self.executor, lambda: fn(*args, **kwargs))
            return result
        finally:
            with self._lock:
                self._active_count -= 1
                self._total_processed += 1
                self._queue_size -= 1

    def get_status(self) -> dict:
        """현재 상태 조회

        Returns:
            dict: 상태 정보
        """
        with self._lock:
            uptime = (datetime.now() - self.start_time).total_seconds()
            return {
                'status': 'running',
                'workers': self.max_workers,
                'active': self._active_count,
                'queue_size': self._queue_size,
                'total_processed': self._total_processed,
                'uptime_seconds': int(uptime)
            }

    def shutdown(self, wait: bool = True):
        """워커 풀 종료

        Args:
            wait: 현재 작업 완료 대기 여부
        """
        self.executor.shutdown(wait=wait)


# 전역 워커 풀 인스턴스
_worker_pool: WorkerPool | None = None


def get_worker_pool() -> WorkerPool:
    """전역 워커 풀 인스턴스 반환"""
    global _worker_pool
    if _worker_pool is None:
        _worker_pool = WorkerPool(max_workers=20)
    return _worker_pool


def init_worker_pool(max_workers: int = 20) -> WorkerPool:
    """워커 풀 초기화

    Args:
        max_workers: 최대 동시 워커 수

    Returns:
        WorkerPool: 초기화된 워커 풀
    """
    global _worker_pool
    if _worker_pool is not None:
        _worker_pool.shutdown(wait=False)
    _worker_pool = WorkerPool(max_workers=max_workers)
    return _worker_pool
