#!/bin/bash
#
# Chrome for Testing - 다중 버전 다운로드 스크립트
# 130 ~ 최신 버전까지 각 메이저 버전의 최신 빌드를 다운로드
#

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 설정
CHROME_API="https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json"
INSTALL_DIR="$(pwd)/chrome-versions/files"
TEMP_DIR="/tmp/chrome-downloads"
MIN_VERSION=130

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Chrome for Testing - Multi Version Installer${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 디렉토리 생성
mkdir -p "$INSTALL_DIR"
mkdir -p "$TEMP_DIR"

# JSON 데이터 가져오기 및 버전 파싱
echo -e "${YELLOW}Fetching Chrome versions from API...${NC}"

# Python으로 한 번에 처리
python3 << 'PYTHON_SCRIPT'
import json
import urllib.request
import os
import zipfile
import shutil
from collections import defaultdict

# 설정
CHROME_API = "https://googlechromelabs.github.io/chrome-for-testing/known-good-versions-with-downloads.json"
INSTALL_DIR = os.environ.get('INSTALL_DIR', './chrome-versions/files')
TEMP_DIR = os.environ.get('TEMP_DIR', '/tmp/chrome-downloads')
MIN_VERSION = 130

# 색상
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
NC = '\033[0m'

def main():
    # API에서 데이터 가져오기
    print(f"{YELLOW}Downloading version manifest...{NC}")
    with urllib.request.urlopen(CHROME_API) as response:
        data = json.loads(response.read().decode())

    versions = data.get('versions', [])

    # 메이저 버전별 최신 빌드 수집
    major_builds = defaultdict(lambda: {'version': '', 'revision': 0, 'url': ''})

    for v in versions:
        version = v.get('version', '')
        downloads = v.get('downloads', {})

        if 'chrome' not in downloads:
            continue

        # linux64 URL 찾기
        linux_url = None
        for d in downloads.get('chrome', []):
            if d.get('platform') == 'linux64':
                linux_url = d.get('url')
                break

        if not linux_url:
            continue

        parts = version.split('.')
        if len(parts) >= 4:
            major = int(parts[0])
            revision = int(parts[3])

            if major >= MIN_VERSION:
                if revision > major_builds[major]['revision']:
                    major_builds[major] = {
                        'version': version,
                        'revision': revision,
                        'url': linux_url
                    }

    # 설치할 버전 목록
    versions_to_install = sorted(major_builds.keys())
    total = len(versions_to_install)

    print(f"\n{BLUE}Found {total} versions to install (Chrome {min(versions_to_install)}-{max(versions_to_install)}){NC}\n")

    success = 0
    failed = 0
    skipped = 0

    for i, major in enumerate(versions_to_install, 1):
        info = major_builds[major]
        version = info['version']
        url = info['url']

        install_path = os.path.join(INSTALL_DIR, f'chrome-{version}')
        chrome_binary = os.path.join(install_path, 'chrome-linux64', 'chrome')

        print(f"{BLUE}[{i}/{total}] Chrome {major} ({version}){NC}")

        # 이미 설치되어 있는지 확인
        if os.path.exists(chrome_binary):
            print(f"  {YELLOW}Already installed, skipping{NC}")
            skipped += 1
            continue

        try:
            # 다운로드
            zip_path = os.path.join(TEMP_DIR, f'chrome-{version}.zip')
            print(f"  Downloading...")
            urllib.request.urlretrieve(url, zip_path)

            # 압축 해제
            print(f"  Extracting...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(TEMP_DIR)

            # 설치
            os.makedirs(install_path, exist_ok=True)
            extracted_dir = os.path.join(TEMP_DIR, 'chrome-linux64')
            target_dir = os.path.join(install_path, 'chrome-linux64')

            if os.path.exists(target_dir):
                shutil.rmtree(target_dir)
            shutil.move(extracted_dir, target_dir)

            # 실행 권한 (모든 Chrome 바이너리)
            for binary in ['chrome', 'chrome_crashpad_handler', 'chrome_sandbox', 'chrome-wrapper']:
                binary_path = os.path.join(target_dir, binary)
                if os.path.exists(binary_path):
                    os.chmod(binary_path, 0o755)

            # 정리
            os.remove(zip_path)

            # 확인
            import subprocess
            result = subprocess.run([os.path.join(target_dir, 'chrome'), '--version'],
                                    capture_output=True, text=True)
            installed_version = result.stdout.strip().split()[-1] if result.returncode == 0 else version

            print(f"  {GREEN}✓ Installed: Chrome {installed_version}{NC}")
            success += 1

        except Exception as e:
            print(f"  {RED}✗ Failed: {e}{NC}")
            failed += 1

    # 결과 요약
    print(f"\n{GREEN}========================================{NC}")
    print(f"{GREEN}Installation Complete{NC}")
    print(f"{GREEN}Success: {success}, Skipped: {skipped}, Failed: {failed}{NC}")
    print(f"{GREEN}========================================{NC}")
    print(f"\n{BLUE}Chrome installations are in: {INSTALL_DIR}{NC}")

if __name__ == '__main__':
    main()
PYTHON_SCRIPT
