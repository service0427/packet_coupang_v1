# TLS Direct Usage Manual - NO Impersonate Profiles

**POLICY**: We NEVER use impersonate profiles. Always use direct TLS fingerprints.

## Why Direct TLS?

❌ **Impersonate Problems**:
- `impersonate='chrome136'` uses generic Chrome 136 fingerprint
- May not match exact build version (136.0.7103.113 vs 136.0.7103.0)
- curl-cffi maintainers control the fingerprint, not us

✅ **Direct TLS Benefits**:
- Use EXACT fingerprint from real Chrome browser
- Full control over JA3, Akamai, HTTP/2 settings
- Can test different builds of same major version
- Perfect matching = Better Akamai bypass

## Our TLS Collection System

### 1. TLS Profile Collection

**Location**: `chrome-versions/tls/{full_version}.json`

**Collection Process**:
```bash
# Collect TLS from all Chrome builds
cd install
python batch_tls_extractor.py --yes

# Create cache for faster access
node create_tls_cache.js
```

**What Gets Collected**:
- Real browser visits: browserleaks.com, peet.ws, howsmyssl.com
- JA3 fingerprint (5-part string)
- Akamai fingerprint (HTTP/2 SETTINGS)
- Cipher suites, extensions, curves
- User-Agent string

**Cache System**:
- **Cache File**: `chrome-versions/tls/tls_profiles_cache.json`
- **Purpose**: Pre-processed data for all 48 Chrome versions
- **Performance**: Instant loading vs. parsing individual files
- **Strategy**: Cache-first with automatic fallback to individual files

### 2. TLS Profile Structure

**File**: `chrome-versions/tls/136.0.7103.113.json`

```json
{
  "build_version": "136.0.7103.113",
  "extraction_date": "2025-10-11 22:03:52",
  "raw_fingerprints": {
    "https://tls.browserleaks.com/json": {
      "ja3_text": "771,4865-4866-4867-49195-49199-49196-49200-52393-52392-49171-49172-156-157-47-53,45-0-11-17613-65037-23-13-65281-18-27-10-16-35-5-43-51,4588-29-23-24,0",
      "akamai_text": "1:65536;2:0;4:6291456;6:262144|15663105|0|m,a,s,p",
      "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
    },
    "https://tls.peet.ws/api/all": {
      "tls": { "ciphers": [...], "extensions": [...] },
      "http2": { "akamai_fingerprint": "1:65536;2:0;..." }
    }
  }
}
```

## Direct TLS Usage in curl-cffi

### Basic Usage

```python
from curl_cffi import requests
import json

# Load TLS profile
with open('chrome-versions/tls/136.0.7103.113.json') as f:
    tls_data = json.load(f)

# Extract fingerprints
browserleaks = tls_data['raw_fingerprints']['https://tls.browserleaks.com/json']
ja3 = browserleaks['ja3_text']
akamai = browserleaks['akamai_text']
user_agent = browserleaks['user_agent']

# Request with direct TLS
response = requests.get(
    'https://www.coupang.com/np/search?q=키보드',
    cookies=cookies,
    ja3=ja3,                    # ✅ Direct JA3
    akamai=akamai,              # ✅ Direct Akamai
    headers={'User-Agent': user_agent},
    timeout=30
)
```

### JA3 String Format

**5 Parts** (comma-separated):
```
SSLVersion,Ciphers,Extensions,SupportedGroups,ECPointFormats
```

**Example**:
```
771,4865-4866-4867-49195-49199,0-23-65281-10-11,29-23-24,0
│   │                          │                │         └─ EC Point Formats
│   │                          │                └─────────── Supported Groups
│   │                          └──────────────────────────── Extension IDs
│   └─────────────────────────────────────────────────────── Cipher Suites
└─────────────────────────────────────────────────────────── SSL/TLS Version (771=TLS 1.2)
```

### Akamai String Format

**HTTP/2 SETTINGS**:
```
SETTING_ID:VALUE;...|WINDOW_UPDATE|PRIORITY|STREAM_DEPENDENCIES
```

**Example**:
```
1:65536;2:0;4:6291456;6:262144|15663105|0|m,a,s,p
│                              │        │  └─────── Stream dependencies (method, authority, scheme, path)
│                              │        └────────── Priority
│                              └─────────────────── Window update value
└────────────────────────────────────────────────── HTTP/2 SETTINGS frame
```

## Our Implementation

### Script: `src/tls_custom_request.py`

**Usage**:
```bash
python src/tls_custom_request.py <url> <cookie_file> <chrome_version>
```

**Example**:
```bash
python src/tls_custom_request.py \
    "https://www.coupang.com/np/search?q=키보드&page=1" \
    "cookies/136.0.7103.113.json" \
    "136.0.7103.113"
```

**What It Does**:
1. Load TLS profile from `chrome-versions/tls/{version}.json`
2. Extract JA3 and Akamai strings
3. Make request with `curl_cffi.requests.get(ja3=..., akamai=...)`
4. Return HTML response

### Full Automation: `find-allowed-chrome-version.js`

**Process**:
```
For each Chrome build (high to low):
  1. Browser Mode: Get cookies
  2. Load TLS Profile: chrome-versions/tls/{version}.json
  3. Packet Mode: curl-cffi with direct TLS
  4. Test until 3 consecutive blocks
  5. Report allowed versions
```

**Run**:
```bash
node find-allowed-chrome-version.js
```

## Advanced: extra_fp Parameters

**Fine-tune beyond JA3/Akamai**:
```python
extra_fp = {
    "tls_signature_algorithms": [
        "ecdsa_secp256r1_sha256",
        "rsa_pss_rsae_sha256",
        "rsa_pkcs1_sha256"
    ],
    "tls_min_version": "TLS1.2",
    "tls_grease": True,
    "http2_stream_weight": 256
}

response = requests.get(
    url,
    ja3=ja3,
    akamai=akamai,
    extra_fp=extra_fp  # Additional fine-tuning
)
```

## Verification

### Check JA3 Match
```bash
# Visit browserleaks.com with our TLS
python src/tls_custom_request.py \
    "https://tls.browserleaks.com/json" \
    "cookies/136.0.7103.113.json" \
    "136.0.7103.113"

# Compare JA3 hash with collected profile
```

### Check Akamai Match
```bash
# Visit peet.ws with our TLS
python src/tls_custom_request.py \
    "https://tls.peet.ws/api/all" \
    "cookies/136.0.7103.113.json" \
    "136.0.7103.113"

# Compare akamai_fingerprint
```

## Key Differences

| Aspect | Impersonate Profile | Direct TLS |
|--------|-------------------|-----------|
| **Precision** | Generic major version | Exact build version |
| **Control** | curl-cffi decides | We decide |
| **Matching** | Approximate | Perfect |
| **Testing** | Can't test builds | Can test each build |
| **Updates** | curl-cffi updates | We control |

## Policy Summary

### ✅ DO

- Use `ja3=` and `akamai=` parameters
- Load from `chrome-versions/tls/` profiles
- Test each Chrome build individually
- Collect TLS from real browsers
- Document exact fingerprints

### ❌ DON'T

- Use `impersonate='chrome120'` or any profile
- Rely on curl-cffi's built-in profiles
- Skip TLS collection step
- Assume major version is enough
- Forget why we collected TLS profiles

## Reference

**curl-cffi Documentation**:
- https://curl-cffi.readthedocs.io/en/stable/impersonate/customize.html

**Our Documentation**:
- `docs/CURL_CFFI_CUSTOM_TLS.md` - Technical details
- `docs/TLS_DIRECT_USAGE_MANUAL.md` - This file
- `docs/AKAMAI_BYPASS_GUIDE.md` - Overall strategy

## Testing Results Location

**Results**: `test_results/`
- Per version: `{version}.json`
- Summary: `summary_{timestamp}.json`

**Check Progress**:
```bash
# Watch results
ls -lt test_results/

# Check summary
cat test_results/summary_*.json | jq '.allowedVersions'
```

## Troubleshooting

**Issue**: Request fails with TLS error
- Check JA3 string format (5 parts, comma-separated)
- Verify Akamai string has pipe separators
- Ensure User-Agent matches Chrome version

**Issue**: Still getting blocked
- Browser mode worked but packet mode blocked?
- Verify cookies are fresh (< 10 min)
- Check if PCID/sid need removal
- Try different Chrome build version

**Issue**: TLS profile not found
- Run `python install/batch_tls_extractor.py --yes`
- Check `chrome-versions/tls/` has JSON files
- Verify Chrome build exists in `chrome-versions/files/`

## Never Forget

🔴 **CRITICAL**: We collected 48 Chrome TLS profiles for a reason
🔴 **POLICY**: NEVER use impersonate profiles
🔴 **METHOD**: Always use direct JA3 + Akamai strings
🔴 **PURPOSE**: Find exact Chrome build that bypasses Akamai
