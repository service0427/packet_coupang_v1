#!/usr/bin/env python3
"""
Rank Check API Server

Usage:
    python3 server.py              # 기본 포트 8088
    python3 server.py --port 8080  # 포트 지정
"""

import sys
from pathlib import Path

# lib 경로 추가 (기존 모듈들의 절대 경로 import 호환)
lib_path = Path(__file__).parent / 'lib'
if str(lib_path) not in sys.path:
    sys.path.insert(0, str(lib_path))

import argparse
import uvicorn

from api import app


def main():
    parser = argparse.ArgumentParser(description='Rank Check API Server')
    parser.add_argument('--host', default='0.0.0.0', help='Host (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=8088, help='Port (default: 8088)')
    parser.add_argument('--workers', type=int, default=1, help='Workers (default: 1)')
    args = parser.parse_args()

    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        workers=args.workers,
        log_level='info'
    )


if __name__ == '__main__':
    main()
