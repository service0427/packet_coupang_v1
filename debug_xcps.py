import base64
import json

# 캡처 데이터에서 추출한 x-cp-s 값
x_cp_s_b64 = "YzE9MSZjMj0xLjAuMCZjMz0xNzc1MDA4OTkyNDU2JmM0PXFwNzNuQmVVUVV5Z29FQWk0eVFHSzlqUmtHa29YNEtJRHpOTURoUjJCRVBJZDB0em1MREdEbXgvdEh6M3NhSnhWVmtoc3BFTys0RXVzemQxdVhIV1lJRHhKbWhFMld3VUJ1V0duM1dMV3F6ZnNaUHpFNDh3WG5yMmlqNmo3RndmQmEwRExsQVNQbEZZMmRnTEc4OTZNYU8xVWFmVkwvZ3hxdlVicHpOUTMzYTBjNk42UlJ4MUYyam1sRTgxQTlCbHpPWi9zektmU0JycVF2VHhzeHJGNmQ0MU1RSmErWEU9JmM1PWNvbS5jb3VwYW5nLm1vYmlsZSZjNj05LjEuNSZjNz1NRmt3RXdZSEtvWkl6ajBDQVFZSUtvWkl6ajBEQVFjRFFnQUVQQ1lkRnZhUmpTT2ZVbm5Cdmx6K3d1ZElIdVI1cmFrQWx6TERwR1RURldEejhzVTU1aFFkbXhaaG50ZXdqYjkrSU01YU9EQlBtbm5sU294VEl0bEkxZz09JmM4PTdlNzVjYmE1MzNiZDQ2ZDNhY2M3NTYwNTViZDZlYzJiJmM5PTM2JnMxPUtSTnY5RGx3Y3VPdTRsVEwyVENHZ2ZjUEhuNDErMzZNSXg3NTQ5d1dqeEk9JnMyPTEuMC4w"

decoded = base64.b64decode(x_cp_s_b64).decode('utf-8')
print("--- Decoded x-cp-s parameters ---")
params = {}
for part in decoded.split('&'):
    key, _, val = part.partition('=')
    params[key] = val
    print(f"{key}: {val}")

if 'c7' in params:
    print("\nc7 (Public Key):")
    print(params['c7'])
