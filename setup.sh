#!/bin/bash
#
# Coupang Akamai Bypass System - 초기 셋업 스크립트
#
# Usage:
#   ./setup.sh              # 전체 셋업
#   ./setup.sh --deps       # 의존성만 설치
#   ./setup.sh --chrome     # Chrome 다운로드만
#   ./setup.sh --status     # 현재 상태 확인
#

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# 경로 설정
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHROME_FILES_DIR="$SCRIPT_DIR/chrome-versions/files"
TLS_DIR="$SCRIPT_DIR/chrome-versions/tls"

echo -e "${CYAN}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║  Coupang Akamai Bypass System - Setup                  ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════════╝${NC}"
echo ""

# 의존성 설치
install_deps() {
    echo -e "${CYAN}[의존성 설치]${NC}"
    echo ""

    # Python 확인
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}Error: Python3 not installed.${NC}"
        echo -e "${YELLOW}Install: sudo apt install python3 python3-pip${NC}"
        exit 1
    fi

    local py_version=$(python3 --version | cut -d' ' -f2)
    local py_major=$(echo $py_version | cut -d. -f1)
    local py_minor=$(echo $py_version | cut -d. -f2)

    echo -e "  Python: ${GREEN}$py_version${NC}"

    # Python 3.11+ 권장
    if [ "$py_major" -eq 3 ] && [ "$py_minor" -lt 11 ]; then
        echo -e "  ${YELLOW}⚠ Python 3.11+ 권장 (현재 $py_version)${NC}"
        echo -e "  ${YELLOW}  최신 버전 설치: sudo add-apt-repository ppa:deadsnakes/ppa${NC}"
        echo -e "  ${YELLOW}                 sudo apt install python3.12 python3.12-venv${NC}"
    fi

    # pip 확인
    if ! python3 -m pip --version &> /dev/null; then
        echo -e "${RED}Error: pip not installed.${NC}"
        echo -e "${YELLOW}Install: sudo apt install python3-pip${NC}"
        exit 1
    fi

    echo ""
    echo -e "${YELLOW}Installing Python packages...${NC}"

    # Python 패키지 설치
    pip3 install --upgrade curl-cffi pymysql beautifulsoup4 playwright

    # Playwright 브라우저 설치
    echo ""
    echo -e "${YELLOW}Installing Playwright browsers...${NC}"
    python3 -m playwright install chromium

    echo ""
    echo -e "${GREEN}✓ 의존성 설치 완료${NC}"
    echo ""
}

# 상태 확인
check_status() {
    echo -e "${CYAN}[현재 상태]${NC}"
    echo ""

    # Chrome 버전 확인
    if [ -d "$CHROME_FILES_DIR" ]; then
        local chrome_count=$(find "$CHROME_FILES_DIR" -maxdepth 1 -type d -name "chrome-*" 2>/dev/null | wc -l)
        echo -e "  Chrome 버전: ${GREEN}$chrome_count${NC}개"

        if [ "$chrome_count" -gt 0 ]; then
            for dir in "$CHROME_FILES_DIR"/chrome-*; do
                if [ -d "$dir" ]; then
                    local ver=$(basename "$dir" | sed 's/chrome-//' | cut -d. -f1)
                    echo "    - Chrome $ver"
                fi
            done
        fi
    else
        echo -e "  Chrome 버전: ${RED}0${NC}"
    fi

    echo ""

    # TLS 프로파일 확인
    if [ -d "$TLS_DIR/u22" ]; then
        local tls_count=$(find "$TLS_DIR/u22" -name "*.json" -type f 2>/dev/null | wc -l)
        echo -e "  TLS 프로파일: ${GREEN}$tls_count${NC}개"
    else
        echo -e "  TLS 프로파일: ${RED}0${NC}"
    fi

    echo ""

    # Python 패키지 확인
    echo -e "  Python 패키지:"
    for pkg in curl_cffi pymysql bs4 playwright; do
        if python3 -c "import $pkg" 2>/dev/null; then
            echo -e "    - $pkg: ${GREEN}✓${NC}"
        else
            echo -e "    - $pkg: ${RED}✗${NC}"
        fi
    done

    echo ""
}

# Chrome 다운로드
download_chrome() {
    echo -e "${CYAN}[Chrome 다운로드]${NC}"
    echo ""

    if [ -f "$SCRIPT_DIR/install-chrome-versions.sh" ]; then
        bash "$SCRIPT_DIR/install-chrome-versions.sh"
    else
        echo -e "${RED}Error: install-chrome-versions.sh not found${NC}"
        exit 1
    fi

    echo ""
    echo -e "${GREEN}✓ Chrome 다운로드 완료${NC}"
    echo ""
}

# 도움말
show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --deps       의존성만 설치"
    echo "  --chrome     Chrome 다운로드만"
    echo "  --status     현재 상태 확인"
    echo "  --help       도움말"
    echo ""
    echo "설치 후 사용법:"
    echo "  # 쿠키 생성"
    echo "  python3 coupang.py cookie -t 2 -l 10"
    echo ""
    echo "  # 상품 등수 체크"
    echo "  python3 coupang.py rank --product-id 12345678"
    echo ""
}

# 전체 셋업
full_setup() {
    install_deps
    download_chrome

    echo -e "${CYAN}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║  Setup Complete!                                       ║${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════════════════════╝${NC}"
    echo ""

    check_status

    echo -e "${GREEN}사용법:${NC}"
    echo "  # 쿠키 생성"
    echo "  python3 coupang.py cookie -t 2 -l 10"
    echo ""
    echo "  # 상품 등수 체크"
    echo "  python3 coupang.py rank --product-id 12345678"
    echo ""
}

# 메인
case "${1:-}" in
    --deps|-d)
        install_deps
        ;;
    --chrome|-c)
        download_chrome
        ;;
    --status|-s)
        check_status
        ;;
    --help|-h)
        show_help
        ;;
    "")
        full_setup
        ;;
    *)
        echo -e "${RED}Unknown option: $1${NC}"
        show_help
        exit 1
        ;;
esac
