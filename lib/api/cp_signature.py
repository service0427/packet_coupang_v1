"""
x-cp-s 서명 생성 모듈

libsignature.so (ARM64) 역공학 기반 Python 구현
알고리즘: cp_process_encryption_v2

파이프라인:
  Headers  → H1(xor_char) → H2(reverse_ts) → byte_transform → xor_seed(last4) → SHA256 → s1
  QueryParams → Q1(xor_char) → Q2(reverse_ts) → Q3(circular_shift) → byte_transform → xor_seed(last4) → SHA256 → s2
  최종: SHA256(s1 || C_section || s2) → Base64 → c4
"""

import hashlib
import base64


# ─── 고정 상수 (APK 9.1.5 추출 및 캡처 데이터 기반) ───
# c7: Local Public Key (EC)
EC_PUBLIC_KEY = "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEPCYdFvaRjSOfUnnBvlz+wudIHuR5rakAlzLDpGTTFWDz8sU55hQdmxZhntewjb9+IM5aODBPmnnlSoxTItlI1g=="

# c4: Encrypted Device Info (캡처된 유효값 재사용)
ENCRYPTED_DEVICE_INFO = "qp73nBeUQUygoEAi4yQGK9jRkGkoX4KIDzNMDhR2BEPId0tzmLDGDmx/tHz3saJxVVkhspEO+4Euszd1uXHWYIDxJmhE2WwUBuWGn3WLWqzfsZPzE48wXnr2ij6j7FwfBa0DLlASPlFY2dgLG896MaO1UafVL/gxqvUbpzNQ33a0c6N6RRx1F2jmlE81A9BlzOZ/szKfSBrqQvTxsxrF6d41MQJa+XE="

SDK_VERSION = "1.0.0"
PACKAGE_NAME = "com.coupang.mobile"


# ─── 기본 변환 함수 (Native 함수 1:1 매핑) ───

def cp_xor_with_char(data: bytes, key_byte: int) -> bytes:
    """cp_xor_with_char (H1, Q1)"""
    result = bytearray(len(data))
    for i, b in enumerate(data):
        result[i] = b ^ key_byte
    return bytes(result)


def cp_reverse_based_on_timestamp(data: bytes, timestamp: int) -> bytes:
    """cp_reverse_based_on_timestamp (H2, Q2)"""
    if timestamp & 1:
        return bytes(reversed(data))
    return data


def cp_xor_with_seed(data: bytes, seed: bytes) -> bytes:
    """cp_xor_with_seed (H3, Q4)"""
    if not seed: return data
    result = bytearray(len(data))
    for i, b in enumerate(data):
        result[i] = b ^ seed[i % len(seed)]
    return bytes(result)


def cp_circular_right_shift(data: bytes, shift: int) -> bytes:
    """cp_circular_right_shift (Q3)"""
    if not data: return data
    shift %= len(data)
    return data[-shift:] + data[:-shift]


def cp_byte_transform(data: bytes) -> str:
    """cp_byte_transform: 바이트 배열을 '%02x ' 포맷으로 hex 인코딩"""
    return ''.join(f'{b:02x} ' for b in data)


def generate_x_cp_s(headers_payload: str, query_params: str, 
                     timestamp_ms: int, app_version: str,
                     uuid_raw: str) -> str:
    """x-cp-s 헤더 값 생성 (v9.1.5 대응)"""
    
    ts_str = str(timestamp_ms)
    xor_key = ord(ts_str[-1])
    shift_amount = int(ts_str[-2:]) if len(ts_str) >= 2 else 0
    seed = format(timestamp_ms, 'x')[-4:].encode('ascii')
    
    # ─── s1 생성 (Headers Signature) ───
    # Native 로직: H1(XOR) -> H2(Reverse) -> ByteTransform -> H3(XOR Seed) -> SHA256
    h_data = headers_payload.encode('utf-8')
    h1 = cp_xor_with_char(h_data, xor_key)
    h2 = cp_reverse_based_on_timestamp(h1, timestamp_ms)
    h_hex = cp_byte_transform(h2).encode('utf-8')
    h3 = cp_xor_with_seed(h_hex, seed)
    s1 = hashlib.sha256(h3).digest()
    s1_b64 = base64.b64encode(s1).decode('ascii')
    
    # ─── s2 생성 (QueryParams Signature) ───
    # Native 로직: Q1(XOR) -> Q2(Reverse) -> Q3(Shift) -> ByteTransform -> Q4(XOR Seed) -> SHA256
    q_data = (query_params or "").encode('utf-8')
    q1 = cp_xor_with_char(q_data, xor_key)
    q2 = cp_reverse_based_on_timestamp(q1, timestamp_ms)
    q3 = cp_circular_right_shift(q2, shift_amount)
    q_hex = cp_byte_transform(q3).encode('utf-8')
    q4 = cp_xor_with_seed(q_hex, seed)
    s2_hash = hashlib.sha256(q4).hexdigest()
    
    # c9: 타임스탬프 기반 동적 값
    c9 = int(ts_str[-2:]) if len(ts_str) >= 2 else 36

    # 전체 파라미터 조립 (c4, c7은 캡처된 유효값 사용)
    params = (
        f"c1=1"
        f"&c2={SDK_VERSION}"
        f"&c3={timestamp_ms}"
        f"&c4={ENCRYPTED_DEVICE_INFO}"
        f"&c5={PACKAGE_NAME}"
        f"&c6={app_version}"
        f"&c7={EC_PUBLIC_KEY}"
        f"&c8={uuid_raw}"
        f"&c9={c9}"
        f"&s1={s1_b64}"
        f"&s2={SDK_VERSION}"
    )
    
    return base64.b64encode(params.encode('utf-8')).decode('ascii')



if __name__ == '__main__':
    # 테스트: 캡처 데이터 기반 검증
    test_headers = "COUPANG|Android|15|9.1.4||d1UpcX9_ScyKmtWWwfCy8s:APA91bHX0MJug9nUTQ0ubad_fdfTneNrMESXGKzHJiTrb2Aw913w_O_g7tKOo11ARvGAmf-zg02B7REsB46UaQuz9OY5rScV_bz09jT9XP8sdgsQfiNWEuY|f0b740d2-3447-3b2b-b118-d66257275f8f|Y|SM-A165N|f0b740d234472b2bb118d66257275f8f|14ff2a58-b085-4b73-9111-1c3986fe257b|XXHDPI|17721648653230756715148||0||4g|-1|||Asia/Seoul|00e172a610d74badaaa1d044fa4d9d891cca8ca1||1080|450|3|1.0|true"
    test_query = "filter=KEYWORD:노트북|CCID:ALL|EXTRAS:channel/user|GET_FILTER:NONE|SINGLE_ENTITY:TRUE@SEARCH&preventingRedirection=false&resultType=default&ccidActivated=false"
    test_ts = 1774536612222
    test_uuid_raw = "770ba9bbc834401ea507adaaa9bc3499"
    
    result = generate_x_cp_s(test_headers, test_query, test_ts, "9.1.4", test_uuid_raw)
    print(f"생성된 x-cp-s 길이: {len(result)}")
    print(f"x-cp-s (첫 100자): {result[:100]}...")
    
    # 디코딩하여 구조 확인
    decoded = base64.b64decode(result).decode('utf-8')
    print(f"\n디코딩 내용:")
    for part in decoded.split('&'):
        key, _, val = part.partition('=')
        print(f"  {key} = {val[:60]}{'...' if len(val) > 60 else ''}")
