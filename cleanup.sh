#!/bin/bash
# 좀비 프로세스 정리

echo "정리 중..."

# Chrome 프로세스 종료
CHROME_COUNT=$(pgrep -f 'chrome-linux64/chrome' | wc -l)
if [ "$CHROME_COUNT" -gt 0 ]; then
    pkill -f 'chrome-linux64/chrome'
    echo "✅ Chrome 프로세스 $CHROME_COUNT개 종료"
else
    echo "Chrome 프로세스 없음"
fi

# Node cookie 스크립트 종료
NODE_COUNT=$(pgrep -f 'cookie-loop.js\|cookie-db.js' | wc -l)
if [ "$NODE_COUNT" -gt 0 ]; then
    pkill -f 'cookie-loop.js\|cookie-db.js'
    echo "✅ Node 프로세스 $NODE_COUNT개 종료"
else
    echo "Node cookie 프로세스 없음"
fi

# 상태 확인
echo ""
echo "현재 상태:"
ps aux | grep -E 'chrome|cookie' | grep -v grep || echo "관련 프로세스 없음"
