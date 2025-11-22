# Packet Mode Test Report

## Test Information

- **Test Date**: 2025-10-11T05:31:19.548Z
- **Keyword**: 키보드
- **Pages**: 1 ~ 10
- **Test Type**: Cookie Persistence (Browser Mode)
- **Total Time**: 62s (1.0 min)

## Test Results

### Overall Statistics

- **Total Pages**: 10/10
- **Successful Pages**: 10
- **Failed Pages**: 0
- **Success Rate**: 100.0%
- **Average Time**: 6.2s per page

### Product Statistics

- **Total Ranking Products**: 630
- **Total Ad Products**: 110
- **Total Products**: 740

## Duplicate Analysis

- **Total Products Collected**: 630
- **Unique Products**: 620
- **Duplicate Products**: 10
- **Duplicate Rate**: 1.59%
- **Status**: ✅ **PASS** (≤4% threshold)

## Cookie Persistence Analysis

### Cookie Changes

Total cookie changes: **0 times**


✅ **No cookie changes detected** - Cookies remained stable across all pages.

## Page-by-Page Results

| Page | Status | Products | Ads | Response Size | Cookies |
|------|--------|----------|-----|---------------|---------|
| 1 | ✅ SUCCESS | 63 | 29 | 1574.3KB | 89 |
| 2 | ✅ SUCCESS | 63 | 9 | 951.5KB | 89 |
| 3 | ✅ SUCCESS | 63 | 9 | 948.9KB | 89 |
| 4 | ✅ SUCCESS | 63 | 9 | 957.7KB | 89 |
| 5 | ✅ SUCCESS | 63 | 9 | 952.5KB | 89 |
| 6 | ✅ SUCCESS | 63 | 9 | 970.6KB | 89 |
| 7 | ✅ SUCCESS | 63 | 9 | 967.1KB | 89 |
| 8 | ✅ SUCCESS | 63 | 9 | 969.7KB | 89 |
| 9 | ✅ SUCCESS | 63 | 9 | 966.5KB | 89 |
| 10 | ✅ SUCCESS | 63 | 9 | 970.5KB | 89 |

## Conclusion

✅ **Test PASSED**

- All 10 pages were successfully crawled without blocking
- Duplicate rate (1.59%) is within acceptable threshold (≤4%)
- Cookies were maintained properly across page navigation

---

## Proxy Test Results (2025-10-12)

### Test: Proxy + curl-cffi Packet Mode

**Objective**: Test if proxy improves curl-cffi success rate

**Setup**:
- Keyword: 키보드
- Version: Chrome 124.0.6367.207
- Proxy: socks5://14.37.117.98:10027 (External IP: 39.7.50.138)
- Attempts: 10 requests

**Results**:

| Attempt | Status | Response Size | Products |
|---------|--------|---------------|----------|
| 1 | ✅ SUCCESS | 1,431,849 bytes | 27 ranking + 29 ads |
| 2 | ✅ SUCCESS | 1,431,854 bytes | 27 ranking + 29 ads |
| 3 | ✅ SUCCESS | 1,431,734 bytes | 27 ranking + 29 ads |
| 4 | ✅ SUCCESS | 1,431,855 bytes | 27 ranking + 29 ads |
| 5 | ✅ SUCCESS | 1,431,733 bytes | 27 ranking + 29 ads |
| 6 | ✅ SUCCESS | 1,431,734 bytes | 27 ranking + 29 ads |
| 7 | ✅ SUCCESS | 1,431,733 bytes | 27 ranking + 29 ads |
| 8 | ✅ SUCCESS | 1,431,734 bytes | 27 ranking + 29 ads |
| 9 | ✅ SUCCESS | 1,431,736 bytes | 27 ranking + 29 ads |
| 10 | ✅ SUCCESS | 1,431,735 bytes | 27 ranking + 29 ads |

**Summary**:
- **Success Rate**: 10/10 (100%)
- **Average Response Size**: 1.43 MB

### Comparison: Proxy vs No Proxy

| Condition | Proxy | curl-cffi Success Rate |
|-----------|-------|------------------------|
| Same IP (no proxy) | ❌ None | 20% (2/10) |
| Fresh Proxy | ✅ socks5://14.37.117.98:10027 | **100% (10/10)** |

### Key Findings

1. **Proxy Dramatically Improves Success Rate**:
   - Without proxy: 20% success (probabilistic TLS detection)
   - With fresh proxy: 100% success

2. **Akamai Detection Mechanism**:
   - **TLS Fingerprinting**: Primary detection (curl-cffi vs real Chrome)
   - **IP Reputation**: Secondary factor (IP history affects strictness)
   - **Combined Approach**: Both TLS + IP reputation used together

3. **Fresh Proxy Strategy**:
   - Proxies toggled within 200 seconds (before 90-second idle time)
   - Clean IP history → relaxed TLS detection
   - PostgreSQL proxy pool management

### Implications for Packet Mode

**Recommended Approach**:
```
Phase 1: Fresh proxy selection (PostgreSQL, <200s since toggle)
Phase 2: Proxy browser → cookie generation
Phase 3: Same proxy → curl-cffi packet requests (100% success)
Phase 4: Cookie expiry → rotate to new proxy
```

**Benefits**:
- 100% success rate with proxy pool
- Fast requests (~100-200ms per page)
- Scalable with proper proxy rotation
- IP reputation management

---

*Last updated: 2025-10-12T22:30:00.000Z*
