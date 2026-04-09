#!/usr/bin/env python3
"""BLOCKED 디버그: 노안안경 2건"""

import sys, os, json, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lib'))

from api.rank_checker_direct import check_rank

tests = [
    {"keyword": "노안안경", "pid": "8829762097", "iid": "25727394025", "vid": "91510831149"},
    {"keyword": "노안안경", "pid": "8463628005", "iid": "24486662476", "vid": "91499984992"},
]

for i, t in enumerate(tests):
    print(f"\n{'='*60}")
    print(f"[{i+1}] P:{t['pid']} I:{t['iid']} V:{t['vid']}")
    print(f"{'='*60}")
    
    result = check_rank(t['keyword'], t['pid'], t['iid'], t['vid'], max_page=15)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    
    if result['success'] and result['found']:
        print(f"✅ 발견: {result['rank']}위")
    elif result['success']:
        print(f"❌ 미발견 (P{result['pages_searched']})")
    else:
        print(f"🚫 실패: {result['error_code']} - {result['error_message']}")
        if result.get('error_detail'):
            print(f"   detail: {result['error_detail']}")
    
    time.sleep(1)
