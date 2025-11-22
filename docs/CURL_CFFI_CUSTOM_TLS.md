# curl-cffi Custom TLS Configuration

**CRITICAL**: curl-cffi supports detailed TLS customization beyond simple impersonate profiles.

## Reference
- **Documentation**: https://curl-cffi.readthedocs.io/en/stable/impersonate/customize.html
- **Purpose**: Use real Chrome TLS fingerprints collected in `chrome-versions/tls/`

## Three Methods

### 1. JA3 + Akamai Strings (Primary Method)

**JA3 String Format** (5 parts):
```
SSLVersion,Ciphers,Extensions,SupportedGroups,ECPointFormats
```

**Akamai String Format**:
```
SETTINGS_1:value1;SETTINGS_2:value2;...|window_update|priority|stream_dependencies
```

**Example**:
```python
ja3 = "771,4865-4866-4867-49195-49196,0-23-65281-10-11,29-23-24,0"
akamai = "1:65536;2:0;4:6291456;6:262144|15663105|0|m,a,s,p"

response = requests.get(
    url,
    cookies=cookies,
    ja3=ja3,
    akamai=akamai
)
```

### 2. extra_fp Parameters (Fine-tuning)

**Available Parameters**:
```python
extra_fp = {
    "tls_signature_algorithms": [
        "ecdsa_secp256r1_sha256",
        "rsa_pss_rsae_sha256",
        "rsa_pkcs1_sha256",
        # ...
    ],
    "tls_min_version": "TLS1.2",  # or TLS1.3
    "tls_grease": True,
    "tls_permute_extensions": False,
    "tls_cert_compression": "brotli",
    "http2_stream_weight": 256,
    "http2_stream_exclusive": 1
}

response = requests.get(url, ja3=ja3, akamai=akamai, extra_fp=extra_fp)
```

### 3. Combined with impersonate (Hybrid)

Start with base impersonate, then override:
```python
response = requests.get(
    url,
    cookies=cookies,
    impersonate="chrome136",  # Base profile
    ja3=custom_ja3,           # Override JA3
    akamai=custom_akamai      # Override HTTP/2
)
```

## Our TLS Profile Structure

**File**: `chrome-versions/tls/{version}.json`

**Key Fields**:
```json
{
  "raw_fingerprints": {
    "https://tls.browserleaks.com/json": {
      "ja3_text": "771,4865-4866-4867-...",
      "akamai_text": "1:65536;2:0;4:6291456;..."
    },
    "https://tls.peet.ws/api/all": {
      "tls": {
        "ciphers": ["TLS_AES_128_GCM_SHA256", ...],
        "extensions": [...]
      },
      "http2": {
        "akamai_fingerprint": "1:65536;2:0;..."
      }
    }
  }
}
```

## Implementation Strategy

### For Chrome Version Testing

**Goal**: Test if specific Chrome TLS fingerprint bypasses Akamai

**Approach**:
1. Load TLS profile from `chrome-versions/tls/{version}.json`
2. Extract JA3 and Akamai strings
3. Use curl-cffi with custom JA3/Akamai (NOT impersonate)
4. Test until blocked

**Code**:
```python
import json
from curl_cffi import requests

# Load TLS profile
with open(f'chrome-versions/tls/{version}.json') as f:
    tls_data = json.load(f)

# Extract fingerprints
browserleaks = tls_data['raw_fingerprints']['https://tls.browserleaks.com/json']
ja3 = browserleaks['ja3_text']
akamai = browserleaks['akamai_text']

# Request with exact TLS fingerprint
response = requests.get(
    url,
    cookies=cookies,
    ja3=ja3,
    akamai=akamai,
    timeout=30
)
```

## Important Notes

1. **JA3 Priority**: JA3/Akamai strings override impersonate profiles
2. **GREASE Values**: May need to handle GREASE (0x?a?a) in cipher suites
3. **Extension Order**: Order matters for fingerprint matching
4. **HTTP/2 Settings**: Akamai string includes HTTP/2 SETTINGS frame data
5. **User-Agent**: Must match Chrome version in TLS profile

## Why This Matters

**Problem**: curl-cffi's built-in impersonate profiles may not exactly match real Chrome builds
**Solution**: Use actual TLS fingerprints from real Chrome browsers
**Result**: Perfect TLS fingerprint matching = Better Akamai bypass

## Testing Workflow

```
1. Browser Mode: Get cookies with real Chrome
2. Load TLS Profile: Read chrome-versions/tls/{version}.json
3. Extract JA3/Akamai: From raw_fingerprints
4. Packet Mode: curl-cffi with custom JA3/Akamai
5. Test Until Blocked: Find which versions bypass Akamai
```

## Never Forget

✅ curl-cffi CAN customize TLS beyond impersonate
✅ Use JA3 + Akamai strings from TLS profiles
✅ This is why we collected chrome-versions/tls/
❌ Don't rely only on impersonate profiles
❌ Don't ignore collected TLS fingerprints
