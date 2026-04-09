import base64
from urllib.parse import parse_qs

def decode_signature(sig_base64):
    print("=== Coupang Signature (x-cp-s) Decoder ===")
    print(f"Original Base64: {sig_base64[:50]}...")
    
    try:
        # 1. Base64 Decode
        decoded_bytes = base64.b64decode(sig_base64)
        decoded_str = decoded_bytes.decode('utf-8')
        print(f"\nDecoded String:\n{decoded_str}\n")
        
        # 2. Parse Query Parameters
        params = parse_qs(decoded_str)
        
        print("=== Parameter Analysis ===")
        for key, values in sorted(params.items()):
            # parse_qs returns a list for each key
            val = values[0]
            
            # 특정 필드 설명 (추측 포함)
            description = ""
            if key == 'c1': description = "(Version?)"
            elif key == 'c3': description = "(Timestamp?)"
            elif key == 'c5': description = "(Package Name)"
            elif key == 'c6': description = "(App Version)"
            elif key == 'c7': description = "(Public Key/Token?)"
            elif key == 'c8': description = "(Device ID/UUID?)"
            elif key == 's1': description = "(HMAC/Signature Value)"
            
            print(f"{key:3}: {val[:80]}{'...' if len(val) > 80 else ''} {description}")
            
    except Exception as e:
        print(f"Error decoding signature: {e}")

if __name__ == "__main__":
    target_sig = "YzE9MSZjMj0xLjAuMCZjMz0xNzc1MDA4OTk5MzYyJmM0PXFwNzNuQmVVUVV5Z29FQWk0eVFHSzlqUmtHa29YNEtJRHpOTURoUjJCRVBJZDB0em1MREdEbXgvdEh6M3NhSnhWVmtoc3BFTys0RXVzemQxdVhIV1lJRHhKbWhFMld3VUJ1V0duM1dMV3F6ZnNaUHpFNDh3WG5yMmlqNmo3RndmQmEwRExsQVNQbEZZMmRnTEc4OTZNYU8xVWFmVkwvZ3hxdlVicHpOUTMzYTBjNk42UlJ4MUYyam1sRTgxQTlCbHpPWi9zektmU0JycVF2VHhzeHJGNmQ0MU1RSmErWEU9JmM1PWNvbS5jb3VwYW5nLm1vYmlsZSZjNj05LjEuNSZjNz1NRmt3RXdZSEtvWkl6ajBDQVFZSUtvWkl6ajBEQVFjRFFnQUVQQ1lkRnZhUmpTT2ZVbm5Cdmx6K3d1ZElIdVI1cmFrQWx6TERwR1RURldEejhzVTU1aFFkbXhaaG50ZXdqYjkrSU01YU9EQlBtbm5sU294VEl0bEkxZz09JmM4PTE2ODFmZjE3NjQyZjQ5Mzk5ZTgzM2Q2ODUyNjBhYWY2JmM5PTQ0JnMxPVoxNWRjTUpCUERqOEQrUXBnMFR2M0VleWFlMDJOQ2JuMVppSE1xS2RJUVU9JnMyPTEuMC4w"
    decode_signature(target_sig)
