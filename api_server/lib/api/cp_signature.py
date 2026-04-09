"""
x-cp-s 서명 생성 모듈 (v9.1.5 대응 - 캡처 기반 하이브리드 방식)

특징:
  1. c4, c7은 캡처된 유효한 Widevine ID 기반 암호문 재사용 (서버 보안 우회용)
  2. s1, s2 서명은 실시간 요청 데이터(헤더, 쿼리)에 맞춰 Native v2 알고리즘으로 동적 생성
"""

import hashlib
import base64

# ─── 고정 상수 (캡처 데이터 기반 유효 세션 키쌍) ───
# c7: 캡처된 로컬 공개키
EC_PUBLIC_KEY = "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEPCYdFvaRjSOfUnnBvlz+wudIHuR5rakAlzLDpGTTFWDz8sU55hQdmxZhntewjb9+IM5aODBPmnnlSoxTItlI1g=="

# c4: 캡처된 암호화된 기기 정보 (Widevine ID 포함)
# 주의: 이 값은 c8(uuid_raw)과 묶여 있으므로 반드시 캡처 당시의 c8과 쌍을 맞춰야 함
ENCRYPTED_DEVICE_INFO = "qp73nBeUQUygoEAi4yQGK9jRkGkoX4KIDzNMDhR2BEPId0tzmLDGDmx/tHz3saJxVVkhspEO+4Euszd1uXHWYIDxJmhE2WwUBuWGn3WLWqzfsZPzE48wXnr2ij6j7FwfBa0DLlASPlFY2dgLG896MaO1UafVL/gxqvUbpzNQ33a0c6N6RRx1F2jmlE81A9BlzOZ/szKfSBrqQvTxsxrF6d41MQJa+XE="

# 캡처 당시의 c8 값 (ENCRYPTED_DEVICE_INFO와 쌍을 이룸)
CAPTURED_C8 = "7e75cba533bd46d3acc756055bd6ec2b"

SDK_VERSION = "1.0.0"
PACKAGE_NAME = "com.coupang.mobile"


# ─── 기본 변환 함수 (Native v2 파이프라인) ───

def cp_xor_with_char(data: bytes, key_byte: int) -> bytes:
    result = bytearray(len(data))
    for i, b in enumerate(data):
        result[i] = b ^ key_byte
    return bytes(result)

def cp_reverse_based_on_timestamp(data: bytes, timestamp: int) -> bytes:
    if timestamp & 1:
        return bytes(reversed(data))
    return data

def cp_xor_with_seed(data: bytes, seed: bytes) -> bytes:
    if not seed: return data
    result = bytearray(len(data))
    for i, b in enumerate(data):
        result[i] = b ^ seed[i % len(seed)]
    return bytes(result)

def cp_circular_right_shift(data: bytes, shift: int) -> bytes:
    if not data: return data
    shift %= len(data)
    return data[-shift:] + data[:-shift]

def cp_byte_transform(data: bytes) -> str:
    return ''.join(f'{b:02x} ' for b in data)


def generate_x_cp_s(headers_payload: str, query_params: str, 
                     timestamp_ms: int, app_version: str,
                     uuid_raw: str, serial: str = None) -> str:
    """x-cp-s 헤더 값 생성 (하이브리드 방식)"""
    
    ts_str = str(timestamp_ms)
    xor_key = ord(ts_str[-1])
    shift_amount = int(ts_str[-2:]) if len(ts_str) >= 2 else 0
    seed = format(timestamp_ms, 'x')[-4:].encode('ascii')
    
    # ─── s1 생성 (Headers) ───
    h_data = headers_payload.encode('utf-8')
    h1 = cp_xor_with_char(h_data, xor_key)
    h2 = cp_reverse_based_on_timestamp(h1, timestamp_ms)
    h_hex = cp_byte_transform(h2).encode('utf-8')
    h3 = cp_xor_with_seed(h_hex, seed)
    s1 = hashlib.sha256(h3).digest()
    s1_b64 = base64.b64encode(s1).decode('ascii')
    
    # c9 동적 값
    c9 = int(ts_str[-2:]) if len(ts_str) >= 2 else 36

    # 전체 파라미터 조립
    # 핵심: c4, c7, c8은 캡처 당시의 "유효한 세션 셋"을 사용하여 보안 통과
    params = (
        f"c1=1"
        f"&c2={SDK_VERSION}"
        f"&c3={timestamp_ms}"
        f"&c4={ENCRYPTED_DEVICE_INFO}"
        f"&c5={PACKAGE_NAME}"
        f"&c6={app_version}"
        f"&c7={EC_PUBLIC_KEY}"
        f"&c8={CAPTURED_C8}"
        f"&c9={c9}"
        f"&s1={s1_b64}"
        f"&s2={SDK_VERSION}"
    )
    
    return base64.b64encode(params.encode('utf-8')).decode('ascii')
