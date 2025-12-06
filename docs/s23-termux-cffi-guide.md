# S23+ Termux curl-cffi 테스트 가이드

실기기(Galaxy S23+)에서 Termux + curl-cffi를 사용하여 쿠팡 검색 테스트

## 1. Termux 환경 설정

```bash
# 패키지 업데이트
pkg update && pkg upgrade -y

# Python 및 필수 패키지 설치
pkg install python python-pip clang libffi openssl -y

# curl-cffi 설치
pip install curl-cffi
```

## 2. 테스트 스크립트

`coupang_test.py` 파일 생성:

```python
#!/usr/bin/env python3
"""
S23+ curl-cffi 쿠팡 검색 테스트

실기기에서 실행하여 쿠키 유효성 확인
쿠키는 실기기 Chrome에서 추출한 것을 사용
"""

from curl_cffi import requests

# ═══════════════════════════════════════════════════════════════
# S23+ Chrome 142 TLS 핑거프린트 설정
# ═══════════════════════════════════════════════════════════════

# Chrome 131 impersonate 사용 (curl-cffi 지원 버전 중 가장 최신)
# 실제 S23+ Chrome 142와 유사한 TLS 핑거프린트 생성
IMPERSONATE = "chrome131"

# S23+ 실기기 추출 쿠키 (Chrome 개발자도구에서 복사)
# 아래 값은 예시이며, 실제 쿠키로 교체 필요
COOKIE = """x-coupang-target-market=KR; x-coupang-accept-language=ko-KR; PCID=17645014843114959915470; MARKETID=17645014843114959915470; sid=b6ca0e5183694f30b3940fa05a7b84997bdcfea0; bm_ss=ab8e18ef4e; bottom_sheet_nudge_banner_ids=CRM-182110_1st_web%2CCRM-182110_1st_web%2CCRM-182110_2nd_web%2CCRM-182110_2nd_web; bm_mi=C81562E6AD53E8F68DF0FF73CBD3ED2D~YAAQsjpvPdOlX9SaAQAA/gYZ1R2Eu7RAidWrTG9k0hFp4ZoMKA/zFPP8Uuq4G25OOPfUt9rLf81wkcLoHVHQoZHCMliDoxfdxyHD0/s7ImIMrFbMRrPPNRcpTVFKepd4usmipNNvbuIlGLmuSBbFksgA9k43VsWJVQ4Czbui5aNu27xCLowlIzodsUeVZxh6S1mKP6E1rvYTYY26kpgIF9QDf+x9qOHB60ZkKkxjX9gH+/F7fJOI1yEP8pj+gZye5OjT2HAdo8AmRpOwaAqBVb4Vu/WKHcBTVACNkn5ILtr8DXd/F9japjQyhHrnfrMRmcaoNk+QUKs=~1; bm_so=79E6E0BED63882DB5E5537D614208E3A7177B3D01FE7069E7F1BCBAF3E6972F8~YAAQsjpvPdWlX9SaAQAA/gYZ1QU8fkcw5Lewr3i5JxtR7SSzlNlPf5ep2q5RM6JoNQfnvP7D/F3dnH0+IWbRHp/8tXCkMvBUKQx36XW1uCItPmBPwOQ2nCHFYXWvxGnWuADLLhE1XiBOKiBIaVc4iWyfmpwkUhvheJ+Pla80KlWgR6R9nbiIARC8v3xFlqPxm8ZFftByNlra1jLFbTSOEIu46evSF2AbWJ4mr+Z0eGV0PUX5eVrKOuew7bh+dPnfQBNrk0vHJgI4Dpjlqw/MPbUjzFL9mvMvm0Y55FN9osHEyne+X/fU3J7ADWuzpq3AZQKB68m5gLy5KlSbvkmrvd/dXmgsm+FqnsOKvJX80+Lx8F1w8wbw5X5sRTF1pKubRBGNDBdriXTEji7+12s2yI5xThxVFcciMcBCI93fdXlqENol2RmtG/CocnJ2+Wm1g03FFgtn2Y8XgnpLldoz; _abck=E507B21A0E41D963D7BC046827525B0B~0~YAAQyzpvPboMq9maAQAAkgcZ1Q41jajh37wOHIsLHnW0Lu9tupBWvxvaChsknwKcTpFdU1/mfzyh4LoWjd4AVVNbfvjbw2FO2bh3E1a9LCvx7QaMhbRw+a6hwpN9j3yMO8QxXcmuOy2svxOjWtv1Yucic6nxPLAvUXg8RG0JSVYtch6PyiWtuQxxw/4P2rhBPlnQbxO6UwDgZ2tUjy7NxhAOgIOkr6PAEC0Oqgl/jbx5iHSThO8x2MgsfCvizU75p1wRlkEAnxu28TChlAy2zOTUHrshFauWDKXjMQHr2eqkK5qjvEB7AvkAPA6mc+yEs3IWkKzRfV5NgfpkmlVAtSW0NmbgVDYkDkMKQ3xgtXYup/fwin6u4D1Z7o3sBgQ/scWLA0kcWAEmLRLw2dsZqBqNjjoO4PebMfy6BVVfh9dYX80VFcNf4HPGe1tpNQxlSdfAe8Ax0kJ9aI4O6PxOG2rcXk+9grOFGewHxBhFNGJty7wYxEj0/lhXtRNxd7I3c40b568E/HhtcP9f3IXsj83XoyQ5JKkbMyZfM6y2BR9oWeLnXE0w6Etc5DbXQO3Fw3UIPJWt24G7uP6CvD5z1TCPzl1FZutF7XyFJZVgldAWa/3oM3euRzSBedxak0rd69bUAMYSumLYEK0MWTNe+SB31QubKGv/SZrgoTkMkmrEBpkSsMrll16ikvmBbTF0/6y3cYMqaW8T~-1~-1~1764512286~AAQAAAAE%2f%2f%2f%2f%2f5+3+W67otFflFKn6aL7Pmw2494wJ%2fm5i83thB%2fP7GQsezZJHsA4MDVyufRuI2kVJXCXwB1jJN3UBZwEiVJEmhkQC1K5kTI87yaxhDNSWXU8byirwAzQIJpbL%2fE37Nm8Gp8hAw5ZwnRs27+gbBKU%2fBgRPCNEZWacoFPe8hdhqg%3d%3d~-1; redirect_app_organic_traffic_target=N; bm_lso=79E6E0BED63882DB5E5537D614208E3A7177B3D01FE7069E7F1BCBAF3E6972F8~YAAQsjpvPdWlX9SaAQAA/gYZ1QU8fkcw5Lewr3i5JxtR7SSzlNlPf5ep2q5RM6JoNQfnvP7D/F3dnH0+IWbRHp/8tXCkMvBUKQx36XW1uCItPmBPwOQ2nCHFYXWvxGnWuADLLhE1XiBOKiBIaVc4iWyfmpwkUhvheJ+Pla80KlWgR6R9nbiIARC8v3xFlqPxm8ZFftByNlra1jLFbTSOEIu46evSF2AbWJ4mr+Z0eGV0PUX5eVrKOuew7bh+dPnfQBNrk0vHJgI4Dpjlqw/MPbUjzFL9mvMvm0Y55FN9osHEyne+X/fU3J7ADWuzpq3AZQKB68m5gLy5KlSbvkmrvd/dXmgsm+FqnsOKvJX80+Lx8F1w8wbw5X5sRTF1pKubRBGNDBdriXTEji7+12s2yI5xThxVFcciMcBCI93fdXlqENol2RmtG/CocnJ2+Wm1g03FFgtn2Y8XgnpLldoz^1764511779256; ak_bmsc=174007DCE08F0EBBD30FC982B51537B9~000000000000000000000000000000~YAAQyzpvPdIQq9maAQAAtQoZ1R3hky1j5hD2EuOZC6XXuo8g9DYuq7+l5GdJjRRBjlOlp43nxRcUwWX22CvRXk06ZGDJxlWe8pBnkQeK3DamssIzdmUFlDbYQi0EQZEDpBZkl/tC7VTnC5PP1SuQiFaxAkbG2QXMRTk5KTSpDRiACjYkQ9KW04boRykaBerOiEPLRClHVZccGXAg+PU7zaJ2EDCVnLvcrt8ZXk+XxUXIRvPcDgPcbeVY3aCNX8bFgQbMDFUPkhiOlESoP7JBd7lc50fIU44bMD9bev3AuROuj+6DCXGYXM8wc2DRNq5dWdo8U7D9Uh3y3tasWesv9cqEQ3dke+BrFVlVlVwBW5LGCu/2lqqKY1atDlZsJ6AeXD+FV285xfKlKh1PwPO86wJ6tpT3H16bKmHVN0SzBI6ztAT8uIvTTZtFmidCTBj/SPWoJCVkO9g06bR0qPmG09OhDkdnrMMaPkS4Fxj/2k1SmGZQpP7wmNzbWA==; bm_sz=CAC11337FDEB9E56C0410043679452BD~YAAQyzpvPWFUq9maAQAAVUAZ1R2+7h/RcPEgbrKBXOIYaegskJLJVeJBkAgDwR3as4icdgJOAqat8EE4/NRzURJ1E2Z3HECNsLQCzh8UB+qx0nanw8/os/ElzuFknyjMnRinx1tfDG9ingIRgYQ7FqQqmg6Wqfyrkc9CDLiDrSLMoenkLcBZxJ3gwWrNI1NMLS37IGhD9a5NXtGm1XeJDrLaVBH0KvyLaOMvhMQXyKNH3z0I1XtG1OmTBb7hgHmawzXRO+UJE1C1+9mCxm0REH3wapJhkko5XuarGM+dUvmgHikoZ9sWBrPmEjkuPKd1cMkJJiavLfSO4UAssbH+jv5ZWgndrydhLdtkXlMqukHq2jPdDZG8dXoOvD68r/CKDhzCuQyHGJMwn0R+Gkwv7U/dDr8WEY+0Mum2DDaU9mwMzBFVWP+dVhE=~3425861~3683138; bm_s=YAAQyzpvPdlaq9maAQAAk0UZ1QQqQJS2JGBCtXNLm8esuE96yOijWDwSQbnj24aVgCBpVNSQZgBqYBPdtOdCDIY0pg/fbkB1X4ty93DmF3eurlZ6x2ikHbjxOsbW4MyffL+ct7LD2oe4TpLg+uiQ9TGQRTDOWQxEXhmFCyAruWZ9/cv8SH0N4nTMlTHJCGlMW67a+ZkydKQVRa/YqaHCxz9nilzqYh2DMcEACxq8Nc/i9ZR3Sj3QOBJzY93G0PLT7CSZ0L5VmkKKX49ODmjnxWfRg/Znvq8NsDVv0AxcR5n3kviXKxSkzu77z6bFuiEoNexTGyizm3QsqdyfFDTC5bz9cfoofpHFUAIb/k09Hdw+iBUSA3UF+upX4UEZDaheYt8ypzijIVDLuwOB8/h63RGBQWaBAkrCyNpygrbICcBQ71fEyWVIFJd1WQtsghpa/StqoEFu0D3THaDqmh0BsmFhY6fbCGPkD0K5rLCRXx992mOYKG9B29lHFY3BXXSKFXcFCroEaxZ9V+R4LbmjBBMaQD5b/ukmaGWAif+XdS2WFRniHyExnTrzN+n8swz1Qm1cD6T8TSkZtf8=; bm_sv=CC58DCF9BCEFD2229B031DC600D39BB9~YAAQyzpvPSmcq9maAQAAx3UZ1R3boDyAqcdXghNVfFzBFkUgwiUdT04FmQyrem3vWzaDI8d3oA6k7O/ioduZPqMEvQ2Qp96nxRq52a71Elhg4ABWCJZ6LUW0MAcj9SBRTlb6Q1e6HWFpC+/yG8KENDSn6kM0exd0xjjoS3boIUtlPvA1/1c8tVHFw9vWNKHF2bgKShesN/ngVTlCjjvhqTKN8RmyinwYGWq74pIT9Np5IMDP0JnuWy2IAeL+ES+wAcQ=~1"""

# ═══════════════════════════════════════════════════════════════
# S23+ Chrome 142 HTTP 헤더 (실기기 추출)
# ═══════════════════════════════════════════════════════════════

HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "accept-language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "cache-control": "max-age=0",
    "priority": "u=0, i",
    "sec-ch-ua": '"Chromium";v="142", "Google Chrome";v="142", "Not_A Brand";v="99"',
    "sec-ch-ua-mobile": "?1",
    "sec-ch-ua-platform": '"Android"',
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "same-origin",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
    "referer": "https://www.coupang.com/",
    "cookie": COOKIE,
}

# ═══════════════════════════════════════════════════════════════
# 추가 TLS 핑거프린트 설정 (S23+ Chrome 142 기준)
# ═══════════════════════════════════════════════════════════════

# S23+ Chrome 142 JA3 해시: dce8ccd531577dfc72f4a5e821a6e5bf
# Akamai 해시: 52d84b11737d980aef856699f885ca86

EXTRA_FP = {
    # TLS extensions
    "tls_signature_algorithms": [
        "ecdsa_secp256r1_sha256",
        "rsa_pss_rsae_sha256",
        "rsa_pkcs1_sha256",
        "ecdsa_secp384r1_sha384",
        "rsa_pss_rsae_sha384",
        "rsa_pkcs1_sha384",
        "rsa_pss_rsae_sha512",
        "rsa_pkcs1_sha512",
    ],
    # HTTP/2 SETTINGS (Akamai 핑거프린트)
    # 1:65536;2:0;4:6291456;6:262144|15663105|0|m,a,s,p
    "h2_settings": {
        "HEADER_TABLE_SIZE": 65536,
        "ENABLE_PUSH": 0,
        "INITIAL_WINDOW_SIZE": 6291456,
        "MAX_HEADER_LIST_SIZE": 262144,
    },
    "h2_window_update": 15663105,
}


def test_search(query="notebook"):
    """쿠팡 검색 테스트"""
    url = f"https://www.coupang.com/np/search?component=&q={query}&channel=user"

    print("=" * 60)
    print("S23+ curl-cffi 쿠팡 검색 테스트")
    print("=" * 60)
    print(f"URL: {url}")
    print(f"Impersonate: {IMPERSONATE}")
    print()

    try:
        resp = requests.get(
            url,
            headers=HEADERS,
            impersonate=IMPERSONATE,
            timeout=30,
        )

        size = len(resp.content)
        status = resp.status_code

        print(f"Status: {status}")
        print(f"Size: {size:,} bytes")

        # 결과 판정
        if size > 50000:
            print("\n🎉 SUCCESS! (>50KB)")

            # 상품 개수 확인
            if "search-product" in resp.text or "product-list" in resp.text:
                count = resp.text.count("search-product")
                print(f"상품 수 (추정): {count}개")
        elif "Access Denied" in resp.text:
            print("\n⛔ BLOCKED (Access Denied)")
        else:
            print(f"\n⚠️ 불확실한 응답 ({size} bytes)")

        # 응답 쿠키 확인
        print("\n응답 쿠키:")
        for name, value in resp.cookies.items():
            print(f"  {name}: {len(value)} chars")

        return resp

    except Exception as e:
        print(f"\n❌ 오류: {e}")
        return None


def test_mobile_search(query="notebook"):
    """쿠팡 모바일 검색 테스트"""
    url = f"https://m.coupang.com/nm/search?q={query}"

    # 모바일 헤더
    mobile_headers = HEADERS.copy()
    mobile_headers["referer"] = "https://m.coupang.com/"

    print("=" * 60)
    print("S23+ curl-cffi 쿠팡 모바일 검색 테스트")
    print("=" * 60)
    print(f"URL: {url}")
    print()

    try:
        resp = requests.get(
            url,
            headers=mobile_headers,
            impersonate=IMPERSONATE,
            timeout=30,
        )

        size = len(resp.content)
        print(f"Status: {resp.status_code}")
        print(f"Size: {size:,} bytes")

        if size > 50000:
            print("\n🎉 SUCCESS!")
        elif "Access Denied" in resp.text:
            print("\n⛔ BLOCKED")
        else:
            print(f"\n⚠️ 불확실 ({size} bytes)")

        return resp

    except Exception as e:
        print(f"\n❌ 오류: {e}")
        return None


if __name__ == "__main__":
    import sys

    query = sys.argv[1] if len(sys.argv) > 1 else "notebook"

    # PC 사이트 테스트
    print("\n" + "=" * 60)
    print("1. PC 사이트 테스트 (www.coupang.com)")
    print("=" * 60)
    test_search(query)

    # 모바일 사이트 테스트
    print("\n" + "=" * 60)
    print("2. 모바일 사이트 테스트 (m.coupang.com)")
    print("=" * 60)
    test_mobile_search(query)
```

## 3. 쿠키 추출 방법

### Chrome 개발자도구에서 추출

1. S23+ Chrome에서 `www.coupang.com` 접속
2. 검색 수행 (예: "notebook" 검색)
3. 개발자도구 열기 (주소창에 `chrome://inspect`)
4. Network 탭 → 검색 요청 선택
5. Headers → Request Headers → Cookie 복사
6. 스크립트의 `COOKIE` 변수에 붙여넣기

### fetch 명령으로 추출 (Console)

```javascript
// Chrome Console에서 실행
copy(document.cookie);
```

## 4. 실행

```bash
# 기본 테스트
python coupang_test.py

# 특정 검색어
python coupang_test.py "아이폰 17"
```

## 5. S23+ TLS 핑거프린트 정보 (참고용)

```
JA3 Hash: dce8ccd531577dfc72f4a5e821a6e5bf
JA3 Text: 771,4865-4866-4867-49195-49199-49196-49200-52393-52392-49171-49172-156-157-47-53,10-18-35-43-5-0-16-17613-23-45-65281-13-65037-51-11-27,4588-29-23-24,0

Akamai Hash: 52d84b11737d980aef856699f885ca86
Akamai Text: 1:65536;2:0;4:6291456;6:262144|15663105|0|m,a,s,p

User-Agent: Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Mobile Safari/537.36
```

## 6. 성공 기준

| 항목 | 성공 | 실패 |
|------|------|------|
| Response Size | > 50,000 bytes | ≤ 50,000 bytes |
| Status Code | 200 | 403 또는 리다이렉트 |
| Content | `#product-list` 포함 | `Access Denied` |

## 7. 문제 해결

### 쿠키 만료
- _abck 쿠키는 짧은 수명을 가짐
- 차단 시 Chrome에서 새 쿠키 추출 후 재시도

### IP 불일치
- 쿠키 생성 IP와 요청 IP가 동일해야 함
- 같은 WiFi/LTE 네트워크에서 테스트

### curl-cffi 설치 실패 (Termux)
```bash
# 빌드 도구 설치
pkg install build-essential cmake

# 다시 시도
pip install curl-cffi --no-cache-dir
```
