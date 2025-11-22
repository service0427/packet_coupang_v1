# TLS Cache System - Fast TLS Profile Access

**Purpose**: Pre-processed TLS profiles for instant access without parsing individual JSON files

## Overview

Instead of loading and parsing `chrome-versions/tls/{version}.json` every time, we created a consolidated cache file that contains all necessary data in optimized format.

## Cache File Structure

**Location**: `chrome-versions/tls/tls_profiles_cache.json`

**Format**:
```json
{
  "141.0.7390.76": {
    "ja3": "771,4865-4866-4867-49195-49199-...",
    "akamai": "1:65536;2:0;4:6291456;6:262144|15663105|0|m,a,s,p",
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36...",
    "build_version": "141.0.7390.76",
    "extraction_date": "2025-10-11 22:03:52"
  },
  ...48 versions total
}
```

## Benefits

**Performance**:
- ⚡ Instant loading: Single file read vs. 48 individual file parses
- 💾 Reduced I/O: One disk access instead of multiple
- 🔄 Optimized data structure: Direct access without nested JSON traversal

**Maintenance**:
- 📋 Single source of truth for all TLS profiles
- 🔍 Easy verification and validation
- 📊 Quick overview of all available versions

## Usage

### Creating/Updating Cache

```bash
# After collecting TLS profiles
cd install
python batch_tls_extractor.py --yes

# Create cache
cd ..
node install/create_tls_cache.js
```

**Output**:
```
Found 51 TLS profile files
  ✓ 120.0.6099.0
  ✓ 120.0.6099.109
  ...
  ✓ 141.0.7390.76

✅ Created TLS profiles cache
   Versions cached: 48
   File: D:\dev\git\local-packet-coupang\chrome-versions\tls\tls_profiles_cache.json
```

### Automatic Usage in Code

**Python (src/tls_custom_request.py)**:
```python
def load_tls_profile(version):
    """
    Load TLS profile with cache-first strategy

    Strategy:
    1. Try cache file first (fast)
    2. Fallback to individual file (if cache missing)
    """
    cache_file = project_root / 'chrome-versions' / 'tls' / 'tls_profiles_cache.json'

    # Try cache first
    if cache_file.exists():
        with open(cache_file, 'r', encoding='utf-8') as f:
            cache = json.load(f)

        if version in cache:
            profile = cache[version]
            return {
                'ja3': profile['ja3'],
                'akamai': profile['akamai'],
                'user_agent': profile['user_agent']
            }

    # Fallback: Load individual file
    tls_file = project_root / 'chrome-versions' / 'tls' / f'{version}.json'
    # ...existing fallback logic
```

## Workflow

```
TLS Collection                Cache Creation              Cache Usage
     ↓                             ↓                            ↓
48 Chrome builds         create_tls_cache.js        tls_custom_request.py
     ↓                             ↓                            ↓
batch_tls_extractor      Extract ja3/akamai         Load from cache
     ↓                             ↓                            ↓
Individual JSON files    Single cache file          Fast access
```

## File Organization

```
chrome-versions/tls/
├── 120.0.6099.0.json           # Individual TLS profiles
├── 120.0.6099.109.json
├── ...
├── 141.0.7390.76.json
└── tls_profiles_cache.json     # ⚡ Consolidated cache (48 versions)
```

## Maintenance

**When to Update Cache**:
- After collecting new TLS profiles
- After modifying existing profiles
- When adding new Chrome build versions

**Verification**:
```bash
# Check cache contents
node -e "console.log(Object.keys(require('./chrome-versions/tls/tls_profiles_cache.json')).length)"
# Expected: 48
```

## Implementation Details

**Cache Creation Script**: `install/create_tls_cache.js`
- Scans `chrome-versions/tls/*.json`
- Extracts JA3, Akamai, User-Agent
- Combines into single optimized file
- Skips non-profile files (summaries, mappings)

**Loading Strategy**: Cache-first with fallback
- Primary: Load from cache (instant)
- Fallback: Load from individual file (compatible)
- Ensures backward compatibility and resilience

## Policy Compliance

✅ **NEVER use impersonate profiles** - Only direct TLS fingerprints (ja3 + akamai + extra_fp)
✅ **Cache system maintains policy** - All data from real Chrome TLS profiles
✅ **Transparency** - Cache is human-readable JSON
✅ **Fallback safety** - Individual files remain authoritative source

### Verified Configuration
```python
# ✅ CORRECT - Full custom TLS without impersonate
from curl_cffi import requests
from curl_cffi.const import CurlSslVersion

extra_fp = {
    'tls_signature_algorithms': [
        'ecdsa_secp256r1_sha256',
        'rsa_pss_rsae_sha256',
        'rsa_pkcs1_sha256',
        'ecdsa_secp384r1_sha384',
        'rsa_pss_rsae_sha384',
        'rsa_pkcs1_sha384',
        'rsa_pss_rsae_sha512',
        'rsa_pkcs1_sha512'
    ],
    'tls_min_version': CurlSslVersion.TLSv1_2,
    'tls_grease': True,
    'tls_cert_compression': 'brotli',
}

response = requests.get(
    url,
    cookies=cookies,
    ja3=tls_profile['ja3'],
    akamai=tls_profile['akamai'],
    extra_fp=extra_fp,
    headers=headers,
    http_version='v2',
    timeout=30
)
```

**Test Results** (Chrome 136.0.7103.113):
- tls.peet.ws: ✅ SUCCESS (200, 9KB response)
- coupang.com: ✅ SUCCESS (200, 1.5MB response)
- Verified: 2025-10-11

## References

- **Policy**: `PROJECT_POLICY.md` - Core TLS usage rules
- **Manual**: `TLS_DIRECT_USAGE_MANUAL.md` - Complete usage guide
- **Technical**: `CURL_CFFI_CUSTOM_TLS.md` - curl-cffi details
- **Implementation**: `src/tls_custom_request.py` - Cache-aware loader
