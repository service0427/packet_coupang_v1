"""
Browser 모듈 - Playwright 기반 쿠키 생성

- cookie_generator: 브라우저로 Akamai 쿠키 생성
- cookie_cmd: cookie 명령어 처리
"""

from .cookie_generator import generate_cookies
from .cookie_cmd import run_cookie

__all__ = ['generate_cookies', 'run_cookie']
