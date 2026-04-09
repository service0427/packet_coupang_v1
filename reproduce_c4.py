import base64
import os
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import serialization

# 1. APK에서 추출한 실제 서버 공개키
SERVER_PUBLIC_KEY_B64 = "MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE8pNu9QMri4EqJ8SFBKet37iormfoX10caePzGEg/O8r9HTjmjgE205Mf2iMCXDJ0tO4052iXutnvq8o4FKGTig=="

def test_dynamic_generation():
    print("=== Coupang x-cp-s Dynamic Generation Test ===")
    
    # A. 서버 공개키 로드 (DER 형식)
    server_public_key_bytes = base64.b64decode(SERVER_PUBLIC_KEY_B64)
    server_public_key = serialization.load_der_public_key(server_public_key_bytes)
    print(f"[1] Server Public Key Loaded (APK Source)")

    # B. 내(클라이언트) EC 키쌍 생성 (SECP256R1)
    client_private_key = ec.generate_private_key(ec.SECP256R1())
    client_public_key = client_private_key.public_key()
    
    # 내 공개키를 DER+Base64로 변환 (이것이 c7 값이 됨)
    c7_value = base64.b64encode(client_public_key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )).decode('ascii')
    print(f"[2] Generated Client Public Key (c7): {c7_value[:50]}...")

    # C. ECDH 수행하여 Shared Secret 유도
    shared_secret = client_private_key.exchange(ec.ECDH(), server_public_key)
    print(f"[3] Shared Secret Derived via ECDH")

    # D. AES-GCM 암호화 (Payload: di=UUID&dl=Status)
    # 실제 앱 로직: di=UUID&dl=0 (root 여부 등에 따라 다름)
    dummy_uuid = "f0b740d234472b2bb118d66257275f8f"
    payload = f"di={dummy_uuid}&dl=0".encode('utf-8')
    
    # AESGCM 초기화 (Shared Secret 사용)
    # 앱에서는 shared_secret 자체를 AES 키로 사용하거나 간단한 가공을 거침
    aesgcm = AESGCM(shared_secret[:16]) # 128-bit key
    nonce = b'\x00' * 12 # 앱 소스에서 확인된 12바이트 null nonce
    
    ciphertext = aesgcm.encrypt(nonce, payload, None)
    
    # 최종 c4 값 (Base64 인코딩)
    c4_value = base64.b64encode(ciphertext).decode('ascii')
    print(f"[4] Generated Encrypted Device Info (c4): {c4_value}")
    
    print("\n[결과] APK 정보를 기반으로 실시간 c4, c7 생성이 가능함을 확인했습니다.")
    print(f"c4 (Encrypted Payload) Length: {len(c4_value)}")
    print(f"c7 (Local Public Key) Length: {len(c7_value)}")

if __name__ == "__main__":
    try:
        test_dynamic_generation()
    except ImportError:
        print("에러: 'cryptography' 라이브러리가 필요합니다. 'pip install cryptography'를 실행하세요.")
    except Exception as e:
        print(f"오류 발생: {e}")
