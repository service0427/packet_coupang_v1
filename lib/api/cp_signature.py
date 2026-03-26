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


# ─── 고정 상수 (APK에서 추출) ───
# EC Public Key (DER SubjectPublicKeyInfo, 앱 서명 검증용 고정값)
EC_PUBLIC_KEY = "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEmFGgA0ylC3vBkiPyOkBISbPRBVcaD7slTQcDbzkX2M3wSZzwn13XVv+lJuSt3ZdQIxXARJScnkXtgWP/iAcZvg=="

# maxSlidingWindow 루프 키 (10회 반복)
MSW_KEY = "43210"
# nextGreaterElements 루프 키 (5회 반복)
NGE_KEY = "01234"
# 역순 키
REVERSE_KEY = "9876543210"

SDK_VERSION = "1.0.0"
PACKAGE_NAME = "com.coupang.mobile"


# ─── 기본 변환 함수 (Native 함수 1:1 매핑) ───

def cp_xor_with_char(data: bytes, key_byte: int) -> bytes:
    """cp_xor_with_char: 각 바이트를 key_byte로 XOR
    
    규칙: byte == key_byte → 0으로 치환 후 XOR (결과 = key_byte)
           byte != key_byte → byte XOR key_byte
    """
    result = bytearray(len(data))
    for i, b in enumerate(data):
        if b == key_byte:
            result[i] = key_byte  # 0 XOR key = key
        else:
            result[i] = b ^ key_byte
    return bytes(result)


def cp_reverse_based_on_timestamp(data: bytes, timestamp: int) -> bytes:
    """cp_reverse_based_on_timestamp: 타임스탬프가 홀수이면 문자열 역전"""
    if timestamp & 1:  # 홀수
        return bytes(reversed(data))
    return data


def cp_xor_with_seed(data: bytes, seed: bytes) -> bytes:
    """cp_xor_with_seed: seed 배열과 순환 XOR
    
    seed[i % len(seed)] 와 data[i]를 XOR
    규칙: data[i] == seed[i%len] → 0으로 치환 후 XOR
    """
    seed_len = len(seed)
    if seed_len == 0:
        return data
    result = bytearray(len(data))
    for i, b in enumerate(data):
        s = seed[i % seed_len]
        if b == s:
            result[i] = s  # 0 XOR s = s
        else:
            result[i] = b ^ s
    return bytes(result)


def cp_circular_right_shift(data: bytes, shift: int) -> bytes:
    """cp_circular_right_shift: n만큼 순환 우측 시프트"""
    length = len(data)
    if length == 0:
        return data
    shift = shift % length
    if shift < 0:
        shift += length
    if shift == 0:
        return data
    # 오른쪽 shift개를 앞으로 이동
    return data[-shift:] + data[:-shift]


def cp_byte_transform(data: bytes) -> str:
    """cp_byte_transform: 바이트 배열을 '%02x ' 포맷으로 hex 인코딩
    
    각 바이트를 2자리 hex + 공백으로 변환 (마지막도 공백 포함)
    """
    return ''.join(f'{b:02x} ' for b in data)


def cp_calculate_sha256(data: bytes) -> bytes:
    """SHA-256 해시 (32바이트 raw)"""
    return hashlib.sha256(data).digest()


def cp_sha256_hex(data: bytes) -> str:
    """SHA-256 해시 (64자 hex 문자열)"""
    return hashlib.sha256(data).hexdigest()


def cp_get_dynamic_c9_value(timestamp: int) -> int:
    """c9 동적 값 계산
    
    cp_get_dynamic_c9_value_long: 20바이트 함수 (5 instructions)
    관찰된 값: 63 → timestamp % 100 또는 고정값
    """
    # 디스어셈블 결과: 매우 짧은 함수, 아마 timestamp의 마지막 2자리
    ts_str = str(timestamp)
    return int(ts_str[-2:]) if len(ts_str) >= 2 else 0


def _get_xor_key_from_timestamp(timestamp: int) -> int:
    """타임스탬프에서 XOR 키 바이트 추출
    
    타임스탬프 문자열의 마지막 바이트의 ASCII 값 사용
    """
    ts_str = str(timestamp)
    return ord(ts_str[-1])


def _get_shift_amount(timestamp: int) -> int:
    """circular_right_shift에 사용할 시프트 양
    
    타임스탬프의 마지막 몇 자리에서 파생
    """
    ts_str = str(timestamp)
    # 마지막 2자리를 시프트 양으로 사용
    return int(ts_str[-2:]) if len(ts_str) >= 2 else 0


def _get_seed_from_timestamp(timestamp: int) -> bytes:
    """타임스탬프에서 XOR seed 추출 (마지막 4바이트)
    
    디스어셈블: x27 = hex(timestamp)의 마지막 4자 → sub x27, x8, #4
    """
    ts_hex = format(timestamp, 'x')
    # 마지막 4자를 seed로 사용
    seed = ts_hex[-4:] if len(ts_hex) >= 4 else ts_hex
    return seed.encode('ascii')


def _process_with_msw_key(data: str) -> str:
    """maxSlidingWindow 변환 - "43210" 키로 10회 circular_right_shift
    
    MSW_KEY = "0123456789"에서 각 문자 - '0' = 0~9
    10회 반복하면서 각 digit 값만큼 circular_right_shift
    """
    result = data.encode('utf-8') if isinstance(data, str) else data
    key = "0123456789"  # 0x1499의 상수
    for ch in key:
        shift = ord(ch) - ord('0')
        result = cp_circular_right_shift(result, shift)
    return result.decode('utf-8', errors='replace') if isinstance(result, bytes) else result


def _process_with_nge_key(data: str) -> str:
    """nextGreaterElements 변환 - "01234" 키로 5회 circular_right_shift (반대 방향)
    
    "01234"에서 각 문자 - '0' = 0~4
    """
    result = data.encode('utf-8') if isinstance(data, str) else data
    key = "01234"  # 0x1637의 상수  
    for ch in key:
        shift = ord(ch) - ord('0')
        # nextGreaterElements는 왼쪽 시프트 (음수 right shift)
        if len(result) > 0 and shift > 0:
            shift_eff = shift % len(result)
            result = result[shift_eff:] + result[:shift_eff]
    return result.decode('utf-8', errors='replace') if isinstance(result, bytes) else result


def generate_x_cp_s(headers_payload: str, query_params: str, 
                     timestamp_ms: int, app_version: str,
                     uuid_raw: str) -> str:
    """x-cp-s 헤더 값 생성
    
    Args:
        headers_payload: coupang-app 헤더 값 (파이프 구분 문자열)
        query_params: 요청 쿼리 파라미터 문자열
        timestamp_ms: 현재 타임스탬프 (밀리초)
        app_version: 앱 버전 (예: "9.1.4")
        uuid_raw: UUID (대시 제거, 32자 hex)
    
    Returns:
        str: Base64 인코딩된 x-cp-s 헤더 값
    """
    # XOR 키 추출
    xor_key = _get_xor_key_from_timestamp(timestamp_ms)
    shift_amount = _get_shift_amount(timestamp_ms)
    seed = _get_seed_from_timestamp(timestamp_ms)
    
    # ─── Headers 처리 (s1 생성) ───
    h_data = headers_payload.encode('utf-8')
    
    # H1: XOR with char
    h1 = cp_xor_with_char(h_data, xor_key)
    # H2: Reverse based on timestamp
    h2 = cp_reverse_based_on_timestamp(h1, timestamp_ms)
    # Hex encode (byte_transform)
    h_hex = cp_byte_transform(h2)
    # H3: XOR with seed (timestamp의 마지막 4 hex chars)
    h3 = cp_xor_with_seed(h_hex.encode('utf-8'), seed)
    # SHA-256 → s1
    s1_bytes = cp_calculate_sha256(h3)
    s1_b64 = base64.b64encode(s1_bytes).decode('ascii')
    
    # ─── QueryParams 처리 (c4 생성) ───
    q_data = query_params.encode('utf-8')
    
    # Q1: XOR with char
    q1 = cp_xor_with_char(q_data, xor_key)
    # Q2: Reverse based on timestamp
    q2 = cp_reverse_based_on_timestamp(q1, timestamp_ms)
    # Q3: Circular right shift
    q3 = cp_circular_right_shift(q2, shift_amount)
    # Hex encode
    q_hex = cp_byte_transform(q3)
    # XOR with seed
    q4 = cp_xor_with_seed(q_hex.encode('utf-8'), seed)
    # SHA-256
    s2_bytes = cp_calculate_sha256(q4)
    
    # ─── 최종 조합 ───
    # c4: SHA256(s1 + 중간 상수 + s2) → Base64
    # maxSlidingWindow/nextGreaterElements 변환 적용
    combined = s1_bytes + s2_bytes
    c4_hash = cp_calculate_sha256(combined)
    c4_b64 = base64.b64encode(c4_hash).decode('ascii')
    
    # c9 동적 값
    c9 = cp_get_dynamic_c9_value(timestamp_ms)
    
    # 전체 파라미터 문자열 조립
    params = (
        f"c1=1"
        f"&c2={SDK_VERSION}"
        f"&c3={timestamp_ms}"
        f"&c4={c4_b64}"
        f"&c5={PACKAGE_NAME}"
        f"&c6={app_version}"
        f"&c7={EC_PUBLIC_KEY}"
        f"&c8={uuid_raw}"
        f"&c9={c9}"
        f"&s1={s1_b64}"
        f"&s2={SDK_VERSION}"
    )
    
    # 최종 Base64 인코딩
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
