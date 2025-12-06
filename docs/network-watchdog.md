# Network Watchdog - 네트워크 자동 복구 시스템

> 서버 과부하로 인한 네트워크 장애를 자동으로 감지하고 복구하는 시스템

## 배경

2024-12-02 발생한 장애:
- Chrome 인스턴스 과다 생성 → inotify watch 고갈
- D-Bus 통신 타임아웃 → NetworkManager 포함 시스템 서비스 연쇄 종료
- 이더넷 인터페이스 사라짐 → 재부팅으로만 복구 가능

## 동작 원리

```
30초마다 네트워크 체크 (ping 8.8.8.8, 1.1.1.1, gateway)
        │
        ▼ 3회 연속 실패
┌───────────────────────────────────────────┐
│ Level 1: NetworkManager 재시작 (3회 시도) │
└───────────────────────────────────────────┘
        │ 실패
        ▼
┌───────────────────────────────────────────┐
│ Level 2: 인터페이스 down/up (2회 시도)     │
└───────────────────────────────────────────┘
        │ 실패
        ▼
┌───────────────────────────────────────────┐
│ Level 3: 드라이버 리로드 (1회 시도)        │
└───────────────────────────────────────────┘
        │ 실패
        ▼
┌───────────────────────────────────────────┐
│ Level 4: 시스템 재부팅                     │
│ (1시간 내 2회 초과 시 중단 → 수동 점검)    │
└───────────────────────────────────────────┘
```

## 설치

### 신규 서버 설치

```bash
# 1. 파일 복사
scp -r tech@U22-10:~/packet_coupang_v1/network-watchdog /tmp/

# 2. 설치
sudo bash /tmp/network-watchdog/install.sh
```

### 설치 시 자동 적용되는 항목

| 항목 | 값 | 설명 |
|------|-----|------|
| `fs.inotify.max_user_watches` | 524288 | Chrome 다중 실행 지원 |
| `fs.inotify.max_user_instances` | 1024 | 인스턴스 수 확대 |
| systemd 서비스 | enabled | 부팅 시 자동 시작 |

## 설치된 파일

```
/opt/network-watchdog/
├── network-watchdog.sh      # 메인 스크립트
└── config.env               # 설정 파일

/etc/systemd/system/
└── network-watchdog.service # systemd 서비스

/etc/sysctl.d/
└── 99-network-watchdog.conf # inotify 커널 설정

/var/log/
└── network-watchdog.log     # 로그

/var/lib/network-watchdog/
└── reboot_history           # 재부팅 기록 (쿨다운 체크용)
```

## 설정 변경

```bash
sudo vi /opt/network-watchdog/config.env
sudo systemctl restart network-watchdog
```

### 주요 설정값

```bash
# 체크 간격 (초)
CHECK_INTERVAL=30

# 핑 대상
PING_TARGETS="8.8.8.8 1.1.1.1"

# 각 레벨 재시도 횟수
LEVEL1_RETRIES=3
LEVEL2_RETRIES=2
LEVEL3_RETRIES=1

# 재부팅 안전장치
REBOOT_COOLDOWN_MINUTES=60
MAX_REBOOTS_IN_COOLDOWN=2

# 알림 (선택)
SLACK_WEBHOOK=""
TELEGRAM_BOT_TOKEN=""
TELEGRAM_CHAT_ID=""
```

## 운영 명령어

```bash
# 상태 확인
systemctl status network-watchdog

# 로그 실시간 확인
tail -f /var/log/network-watchdog.log
journalctl -u network-watchdog -f

# 서비스 재시작
sudo systemctl restart network-watchdog

# 서비스 중지
sudo systemctl stop network-watchdog

# 제거
sudo bash /opt/network-watchdog/uninstall.sh
# 또는
sudo bash ~/packet_coupang_v1/network-watchdog/uninstall.sh
```

## 알림 설정 (선택)

### Slack

```bash
# config.env에 추가
SLACK_WEBHOOK="https://hooks.slack.com/services/XXX/YYY/ZZZ"
```

### Telegram

```bash
# config.env에 추가
TELEGRAM_BOT_TOKEN="123456789:ABCdefGHI..."
TELEGRAM_CHAT_ID="-1001234567890"
```

## 로그 예시

```
[2025-12-03 10:07:33] [U22-10] [INFO] Network Watchdog 시작 (체크 간격: 30초)
[2025-12-03 21:30:45] [U22-10] [WARN] 네트워크 체크 실패 (1/3)
[2025-12-03 21:31:15] [U22-10] [WARN] 네트워크 체크 실패 (2/3)
[2025-12-03 21:31:45] [U22-10] [WARN] 네트워크 체크 실패 (3/3)
[2025-12-03 21:31:45] [U22-10] [ERROR] 네트워크 연결 실패 감지 - 복구 프로세스 시작
[2025-12-03 21:31:45] [U22-10] [WARN] Level 1: NetworkManager 재시작 시도
[2025-12-03 21:31:45] [U22-10] [INFO] Level 1: 시도 1/3
[2025-12-03 21:32:15] [U22-10] [INFO] Level 1: 복구 성공
```

## 배포된 서버 목록

| 서버 | IP | 설치일 | 상태 |
|------|-----|--------|------|
| U22-10 | (로컬) | 2025-12-03 | ✅ 테스트 중 |

---

## 트러블슈팅

### 서비스가 시작되지 않는 경우

```bash
journalctl -u network-watchdog -n 50 --no-pager
```

### 재부팅 루프 방지로 중단된 경우

```bash
# 재부팅 기록 초기화
sudo rm /var/lib/network-watchdog/reboot_history
sudo systemctl restart network-watchdog
```

### 수동으로 네트워크 복구 테스트

```bash
# Level 1 테스트
sudo systemctl restart NetworkManager

# Level 2 테스트
sudo ip link set enp42s0 down && sleep 2 && sudo ip link set enp42s0 up

# Level 3 테스트 (주의: 연결 끊김)
sudo modprobe -r r8169 && sudo modprobe r8169
```
