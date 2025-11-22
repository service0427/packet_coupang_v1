"""
TraceID Generator for Coupang Search
"""
import time
import string


def generate_traceid():
    """
    Generate Coupang traceId (timestamp-based base36)

    Returns:
        str: 8-character traceId (e.g., 'mha2ebbm')
    """
    timestamp_ms = int(time.time() * 1000)
    base36_chars = string.digits + string.ascii_lowercase

    result = []
    ts = timestamp_ms
    while ts > 0:
        result.append(base36_chars[ts % 36])
        ts //= 36

    return ''.join(reversed(result))


if __name__ == '__main__':
    print("Testing traceId generation:")
    for i in range(5):
        traceid = generate_traceid()
        print(f"  {i+1}: {traceid}")
        time.sleep(0.1)
