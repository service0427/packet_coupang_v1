# 런타임 TLS Fingerprint 변조 - 빌드 없이 무제한 확장

## 문제점: 빌드 방식의 한계

**비현실적인 이유**:
```
커스텀 Chrome 빌드:
├─ 1개 빌드 시간: 2-4시간
├─ 100개 필요 시: 200-400시간 (8-17일!)
├─ 디스크 공간: 100개 × 2GB = 200GB
├─ 유지보수: Chrome 업데이트 시 전부 재빌드
└─ 결론: ❌ 완전히 비효율적
```

## 해결책: 런타임 동적 변조

### 방법 1: TLS Interceptor (중간자 프록시)

**원리**: Chrome → TLS Proxy → Coupang
- Chrome이 TLS 연결 시도
- Proxy가 TLS ClientHello 패킷 가로채기
- Cipher Suite 순서 랜덤하게 변경
- 변조된 패킷을 서버로 전송

#### 구현: mitmproxy + Python 스크립트

```python
# tls_randomizer.py
from mitmproxy import ctx, tls
import random

class TLSRandomizer:
    def __init__(self):
        self.variation_count = 0

    def tls_clienthello(self, data: tls.ClientHelloData):
        """
        TLS ClientHello 패킷을 가로채서 랜덤하게 변조
        """
        # 기존 Cipher Suites
        ciphers = list(data.context.client.cipher_list)

        # 랜덤하게 순서 변경
        random.shuffle(ciphers)

        # Cipher Suite 교체
        data.context.client.cipher_list = ciphers

        # Extensions 순서도 랜덤화
        if hasattr(data.context.client, 'extensions'):
            extensions = list(data.context.client.extensions)
            random.shuffle(extensions)
            data.context.client.extensions = extensions

        self.variation_count += 1
        ctx.log.info(f"🔀 TLS Fingerprint 변조 #{self.variation_count}")
        ctx.log.info(f"   Cipher Suites: {len(ciphers)}개 (순서 변경됨)")

addons = [TLSRandomizer()]
```

**사용**:
```bash
# mitmproxy 설치
pip install mitmproxy

# TLS Randomizer 실행
mitmproxy -s tls_randomizer.py --listen-port 8888 --mode upstream:https://www.coupang.com

# Chrome에서 프록시 설정
chrome.exe --proxy-server=127.0.0.1:8888
```

**효과**:
- 요청마다 다른 JA3 Fingerprint 생성
- 빌드 불필요
- 무제한 변형 가능

**한계**:
- HTTPS 인증서 신뢰 문제
- 성능 오버헤드
- 일부 사이트에서 중간자 공격 탐지

### 방법 2: eBPF/XDP를 이용한 커널 레벨 패킷 변조

**원리**: 커널 레벨에서 TLS 패킷 직접 수정

```c
// tls_randomizer.bpf.c (eBPF 프로그램)
#include <linux/bpf.h>
#include <linux/if_ether.h>
#include <linux/ip.h>
#include <linux/tcp.h>

SEC("xdp")
int randomize_tls_clienthello(struct xdp_md *ctx) {
    void *data = (void *)(long)ctx->data;
    void *data_end = (void *)(long)ctx->data_end;

    struct ethhdr *eth = data;
    if ((void *)(eth + 1) > data_end)
        return XDP_PASS;

    if (eth->h_proto != htons(ETH_P_IP))
        return XDP_PASS;

    struct iphdr *ip = (void *)(eth + 1);
    if ((void *)(ip + 1) > data_end)
        return XDP_PASS;

    if (ip->protocol != IPPROTO_TCP)
        return XDP_PASS;

    struct tcphdr *tcp = (void *)ip + (ip->ihl * 4);
    if ((void *)(tcp + 1) > data_end)
        return XDP_PASS;

    // TLS ClientHello 탐지 (port 443)
    if (tcp->dest != htons(443))
        return XDP_PASS;

    void *payload = (void *)tcp + (tcp->doff * 4);
    if (payload + 5 > data_end)
        return XDP_PASS;

    // TLS Handshake (0x16) & ClientHello (0x01) 확인
    __u8 *tls_header = payload;
    if (tls_header[0] == 0x16 && tls_header[5] == 0x01) {
        // Cipher Suite 영역 찾아서 순서 변경
        // (실제 구현은 더 복잡)
        randomize_cipher_suites(payload, data_end);
    }

    return XDP_PASS;
}
```

**장점**:
- 커널 레벨 → 매우 빠름
- 완전 투명 (애플리케이션 수정 불필요)

**단점**:
- Linux 전용
- 매우 높은 기술 난이도
- 디버깅 어려움

### 방법 3: curl-cffi + 동적 impersonate (가장 현실적)

**핵심**: curl-cffi의 `impersonate` 파라미터를 **동적으로 생성**

```python
# dynamic_tls_impersonator.py
from curl_cffi import requests
from curl_cffi.const import CurlOpt
import random
import json

class DynamicTLSImpersonator:
    def __init__(self):
        self.cipher_variations = self._generate_cipher_variations()
        self.current_variation = 0

    def _generate_cipher_variations(self):
        """
        TLS Cipher Suite 조합 생성
        """
        # TLS 1.3 Ciphers
        tls13_ciphers = [
            'TLS_AES_128_GCM_SHA256',
            'TLS_AES_256_GCM_SHA384',
            'TLS_CHACHA20_POLY1305_SHA256',
        ]

        # TLS 1.2 Ciphers
        tls12_ciphers = [
            'ECDHE-ECDSA-AES128-GCM-SHA256',
            'ECDHE-RSA-AES128-GCM-SHA256',
            'ECDHE-ECDSA-AES256-GCM-SHA384',
            'ECDHE-RSA-AES256-GCM-SHA384',
            'ECDHE-ECDSA-CHACHA20-POLY1305',
            'ECDHE-RSA-CHACHA20-POLY1305',
        ]

        variations = []

        # 100개의 다른 조합 생성
        for i in range(100):
            # TLS 1.3 Cipher 순서 랜덤화
            tls13 = tls13_ciphers.copy()
            random.shuffle(tls13)

            # TLS 1.2 Cipher 순서 랜덤화
            tls12 = tls12_ciphers.copy()
            random.shuffle(tls12)

            cipher_string = ':'.join(tls13 + tls12)
            variations.append(cipher_string)

        return variations

    def get_next_session(self):
        """
        다음 TLS Fingerprint로 세션 생성
        """
        cipher_suite = self.cipher_variations[self.current_variation]
        self.current_variation = (self.current_variation + 1) % len(self.cipher_variations)

        # curl-cffi 세션 생성
        session = requests.Session()

        # 커스텀 Cipher Suite 설정
        session.curl.setopt(CurlOpt.SSL_CIPHER_LIST, cipher_suite.encode())

        # HTTP/2 강제
        session.curl.setopt(CurlOpt.HTTP_VERSION, 2)

        # TLS 1.3 사용
        session.curl.setopt(CurlOpt.SSLVERSION, 7)  # TLS 1.3

        print(f"🔀 TLS Variation #{self.current_variation}")
        print(f"   Cipher: {cipher_suite[:50]}...")

        return session

# 사용 예시
impersonator = DynamicTLSImpersonator()

for i in range(1000):
    session = impersonator.get_next_session()

    response = session.get('https://www.coupang.com/np/search?q=물티슈')

    if response.status_code == 200:
        print(f"✅ 요청 #{i+1} 성공")
    else:
        print(f"❌ 요청 #{i+1} 실패: {response.status_code}")

    session.close()
```

**효과**:
- 100개의 다른 TLS Fingerprint
- 빌드 불필요
- 런타임 동적 생성

### 방법 4: 가장 현실적인 하이브리드 전략

**조합의 힘**:

```python
# hybrid_strategy.py
from playwright.sync_api import sync_playwright
from curl_cffi import requests
import random

class HybridAntiBot:
    def __init__(self):
        # 1. 브라우저 풀 (실제 설치된 것만)
        self.browsers = [
            {'type': 'chrome', 'count': 5},    # Chrome 5개 버전
            {'type': 'firefox', 'count': 3},   # Firefox 3개
            {'type': 'edge', 'count': 2},      # Edge 2개
        ]

        # 2. IP 풀 (가능한 범위)
        self.ips = [
            'default',              # 기본 IP
            'mobile_hotspot_1',     # 모바일 핫스팟
            'mobile_hotspot_2',
        ]

        # 3. 세션 전략
        self.max_per_combination = 30  # 보수적
        self.current_browser = 0
        self.current_ip = 0
        self.request_count = 0

    def calculate_capacity(self):
        """
        총 가능 요청 수 계산
        """
        browser_count = sum(b['count'] for b in self.browsers)
        ip_count = len(self.ips)

        total_combinations = browser_count * ip_count
        total_capacity = total_combinations * self.max_per_combination

        print(f"📊 용량 분석:")
        print(f"   브라우저: {browser_count}개")
        print(f"   IP: {ip_count}개")
        print(f"   조합: {total_combinations}개")
        print(f"   조합당 요청: {self.max_per_combination}회")
        print(f"   총 용량: {total_capacity}회")
        print(f"   쿨다운 후 재사용: 무제한")

        return total_capacity

    def get_next_config(self):
        """
        다음 브라우저 + IP 조합 반환
        """
        if self.request_count >= self.max_per_combination:
            # 다음 조합으로 전환
            self.current_browser = (self.current_browser + 1) % sum(b['count'] for b in self.browsers)

            if self.current_browser == 0:
                # 모든 브라우저 순회 완료 → IP 변경
                self.current_ip = (self.current_ip + 1) % len(self.ips)

                if self.current_ip == 0:
                    # 모든 조합 사용 완료 → 1시간 쿨다운
                    print("⏳ 모든 조합 사용 완료. 1시간 쿨다운...")
                    import time
                    time.sleep(3600)

            self.request_count = 0
            print(f"🔄 전환: Browser {self.current_browser}, IP {self.current_ip}")

        self.request_count += 1

        return {
            'browser_index': self.current_browser,
            'ip_index': self.current_ip,
            'request_count': self.request_count
        }

# 실행
strategy = HybridAntiBot()
capacity = strategy.calculate_capacity()

# 예시 출력:
# 브라우저: 10개 (Chrome 5 + Firefox 3 + Edge 2)
# IP: 3개
# 조합: 30개
# 조합당 요청: 30회
# 총 용량: 900회/사이클
# 1시간 쿨다운 후 재사용 → 사실상 무제한
```

## 최종 권장 전략

### 🥇 1순위: 현실적인 브라우저 + IP 조합

```javascript
// 실제 설치 가능한 브라우저만 사용
const setup = {
    browsers: [
        'Chrome Stable',
        'Chrome Beta',
        'Chrome Dev',
        'Firefox Stable',
        'Firefox ESR',
        'Edge Stable'
    ],  // 6개

    ips: [
        '기본 공유기',
        '모바일 핫스팟 1',
        '모바일 핫스팟 2'
    ],  // 3개

    capacity: 6 × 3 × 50 = 900회/사이클
};

// 1시간 쿨다운 후 재사용 → 시간당 900회
```

**장점**:
- ✅ 빌드 불필요
- ✅ 간단한 설치
- ✅ 안정적
- ✅ 유지보수 쉬움

### 🥈 2순위: curl-cffi 동적 Cipher Suite (Python)

```python
# 100개 TLS Variation 동적 생성
# 빌드 불필요
# Python으로 간단히 구현
```

**장점**:
- ✅ 무제한 변형 가능
- ✅ 빌드 불필요

**단점**:
- ⚠️ Akamai가 비정상 Cipher 탐지 가능
- ⚠️ 안정성 검증 필요

### 🥉 3순위: mitmproxy TLS Randomizer

```bash
# TLS 패킷 중간에서 변조
# 무제한 변형
```

**단점**:
- ⚠️ 인증서 신뢰 문제
- ⚠️ 성능 오버헤드

## 구현 우선순위

### 즉시 실행 가능

```javascript
// src/realistic_multi_browser.js
const browsers = [
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files\\Mozilla Firefox\\firefox.exe',
    'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
];

// 3개 × 50회 = 150회
// 쿨다운 후 재사용
```

### 단계별 확장

```
1단계: Chrome + Firefox + Edge (3개)
2단계: Chrome Beta/Dev 추가 (6개)
3단계: 모바일 핫스팟 IP 추가 (× 2-3배)
4단계: curl-cffi 동적 변조 (고급)
```

## 결론

### ❌ 비현실적
- 수백 개 Chrome 빌드 (200-400시간)
- 커스텀 TLS 구현 (고급 전문 지식)

### ✅ 현실적
- **실제 브라우저 6-10개 설치** (30분)
- **IP 2-3개 확보** (모바일 핫스팟)
- **Smart Rotation** 구현 (1시간)
- **총 용량: 900-1,500회/사이클**
- **쿨다운 후 재사용: 무제한**

**핵심**: 빌드 대신 **조합의 힘**을 활용하세요!

---

**작성일**: 2025-10-08
**권장 방법**: 브라우저 + IP 조합 (현실적이고 효율적)
**비권장**: 커스텀 빌드 (비효율적)
