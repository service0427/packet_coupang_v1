# Packet Mode Cookie Generation - Research Results (2025)

## Question: Can we generate Akamai cookies in pure packet mode without GUI browser?

**Answer: YES, but with significant complexity and cost** 💰

---

## Discovery: Commercial Solutions Exist

### 1. Hyper Solutions SDK ⭐ (Most Promising)

**GitHub**: https://github.com/Hyper-Solutions/hyper-sdk-py

**What it does**:
- Generates Akamai sensor data programmatically
- No browser required - pure API calls
- Supports Python, Go, JavaScript/TypeScript
- Generates `_abck` and other Akamai cookies

**Technical Approach**:
```python
from hyper import HyperAkamai

# Initialize with API key
akamai = HyperAkamai(api_key="your_key")

# Generate sensor data
sensor = akamai.generate_sensor(
    url="https://www.coupang.com/",
    user_agent="Chrome/140.0.0.0",
    cookies=existing_cookies
)

# Use generated cookies for requests
requests.get(url, cookies=sensor.cookies)
```

**How it works**:
1. Parses Akamai's dynamic script endpoint
2. Reverse-engineers sensor generation algorithm
3. Generates sensor data mimicking browser behavior
4. Returns valid `_abck`, `bm_sz`, etc. cookies

**Requirements**:
- TLS client with modern cipher suites
- Consistent header order
- HTTP/2 support
- Consistent IP and User-Agent

**Pricing**:
- Pay-as-you-go model
- Subscription plans available
- Specific pricing at https://hypersolutions.co (not publicly listed)

**Pros**:
- ✅ No GUI browser needed
- ✅ Pure HTTP requests
- ✅ Fast (API call latency only)
- ✅ Supports multiple languages

**Cons**:
- ❌ Paid service (API key required)
- ❌ External dependency
- ❌ Must maintain TLS fingerprint consistency
- ❌ Requires regular updates as Akamai evolves

---

### 2. ZenRows Web Scraping API

**Website**: https://www.zenrows.com/blog/bypass-akamai

**What it does**:
- Full web scraping API with Akamai bypass built-in
- Handles cookies, TLS, and anti-bot automatically
- Returns clean HTML

**Pricing**: Starting at $69/month

**Technical Approach**:
```python
import requests

response = requests.get(
    "https://api.zenrows.com/v1/",
    params={
        "url": "https://www.coupang.com/...",
        "apikey": "your_key",
        "js_render": "false",  # No need for JS rendering
    }
)
```

**Pros**:
- ✅ Simplest integration
- ✅ Handles everything automatically
- ✅ No maintenance needed

**Cons**:
- ❌ $69/month minimum
- ❌ Per-request pricing on top
- ❌ External service dependency
- ❌ Less control over cookies

---

### 3. Scrapy-Impersonate (Open Source)

**GitHub**: https://github.com/ljnsn/scrapy-impersonate

**What it does**:
- Scrapy middleware using curl-impersonate
- 90% success rate with Akamai in simple cases
- Free and open source

**Technical Approach**:
```python
# settings.py
DOWNLOADER_MIDDLEWARES = {
    'scrapy_impersonate.ImpersonateMiddleware': 543,
}

IMPERSONATE_BROWSER = 'chrome120'
```

**Pros**:
- ✅ Free and open source
- ✅ Works with existing Scrapy projects
- ✅ No external API needed

**Cons**:
- ❌ 90% success rate (not 100%)
- ❌ Cannot generate sensor data
- ❌ Only works for simple Akamai setups
- ❌ Likely won't work for Coupang (too sophisticated)

---

## Comparison Table

| Method | Cost | Success Rate | Complexity | Browser Required |
|--------|------|--------------|------------|------------------|
| **Current (GUI Browser)** | Free | 100% | Low | ✅ Yes |
| **Hyper Solutions SDK** | $$$ | ~95% | Medium | ❌ No |
| **ZenRows API** | $69/mo | ~90% | Very Low | ❌ No |
| **Scrapy-Impersonate** | Free | ~90% | Medium | ❌ No |

---

## Technical Deep Dive: Sensor Generation

### What Akamai Sensor Data Contains

Based on research, Akamai sensor data includes:

```javascript
// Encrypted payload containing:
{
  "canvas_fingerprint": "...",
  "webgl_fingerprint": "...",
  "screen_info": {...},
  "timing_data": [...],
  "mouse_movements": [...],
  "keyboard_events": [...],
  "navigator_properties": {...},
  "performance_metrics": {...}
}
```

### How Hyper Solutions Generates This

1. **Parse Akamai Script**:
   - Extract script from `/akam/13/...` endpoint
   - Analyze encryption algorithm

2. **Generate Fake Fingerprints**:
   - Create realistic canvas/WebGL fingerprints
   - Generate plausible timing data
   - Simulate mouse/keyboard patterns

3. **Encrypt Payload**:
   - Use cookie-derived hash (from `bm_sz`)
   - Apply Akamai's encryption algorithm
   - Generate `_abck` cookie value

4. **Return Cookies**:
   - `_abck`: Main bot detection cookie
   - `bm_sz`: Session size tracking
   - `bm_sv`: Session validation
   - Others as needed

### Why This is Hard to DIY

1. **Constantly Evolving**: Akamai updates algorithms regularly
2. **Complex Encryption**: Proprietary encryption schemes
3. **Fingerprint Accuracy**: Must match real browser closely
4. **Timing Precision**: Event timing must be realistic
5. **Maintenance Burden**: Requires constant reverse engineering

---

## Recommendation for Coupang Project

### Option 1: Current Approach (Keep GUI Browser) ✅ RECOMMENDED

**Rationale**:
- ✅ 100% success rate proven
- ✅ Free (no API costs)
- ✅ Complete control
- ✅ 5 seconds per refresh is acceptable
- ✅ Cookie valid for 10-30 minutes

**Cost-Benefit**:
- Browser Mode: 5s once per 10-30 minutes
- Enables: 100+ Packet Mode requests at 100ms each
- **Total time saved**: Massive

**Keep this approach unless**:
- Need to scale to 1000+ concurrent sessions
- Cannot run GUI browser in production
- Cost of commercial API < cost of browser infrastructure

### Option 2: Hybrid with Hyper Solutions (If Scaling)

**Use case**: If you need 1000+ concurrent sessions

```python
# For initial cookie generation
if need_cookies_urgently and browser_unavailable:
    sensor = hyper_sdk.generate_sensor(...)
    cookies = sensor.cookies
else:
    # Use existing Browser Mode approach
    cookies = get_cookies_from_browser()

# Then use Packet Mode as usual
packet_mode.request(url, cookies)
```

**When to consider**:
- Scaling to enterprise level (1000+ sessions)
- Running in cloud without GUI support
- Budget allows for API costs

### Option 3: ZenRows API (If Outsourcing)

**Use case**: If you want zero maintenance

**Not recommended for Coupang because**:
- Less control over cookie management
- Higher cost per request
- Our current system works perfectly

---

## Technical Feasibility Assessment

### Can We Implement Hyper Solutions Approach Ourselves?

**Difficulty**: ⭐⭐⭐⭐⭐ (Expert Level)

**Required Skills**:
- Reverse engineering JavaScript
- Understanding encryption algorithms
- Browser fingerprinting knowledge
- Continuous algorithm updates

**Time Investment**:
- Initial implementation: 2-4 weeks
- Maintenance: 1-2 days per month (when Akamai updates)

**Risk**:
- Akamai updates can break implementation overnight
- Legal concerns (reverse engineering)
- Lower success rate than GUI browser

### Should We?

**❌ NO - Not Worth It**

**Reasons**:
1. Current GUI browser approach works perfectly (100%)
2. 5 seconds per refresh is acceptable overhead
3. Maintenance burden is minimal
4. Risk of breaking is low
5. DIY sensor generation is expert-level work
6. Commercial solutions already exist if needed

---

## Conclusion

**Current approach is optimal** for our use case:

```
GUI Browser (5s) → 60 cookies → 10-30 min validity → 100+ fast requests

VS

API Call (100ms) → Sensor data → Per-request cost → Maintenance burden
```

**Keep GUI browser approach unless**:
- Scaling to 1000+ concurrent sessions
- Cloud environment prohibits GUI
- API cost < infrastructure cost

**Future consideration**:
- Monitor Hyper Solutions SDK pricing
- Evaluate if scaling requirements change
- Consider hybrid approach (GUI browser + API fallback)

---

## References

1. Hyper Solutions SDK: https://github.com/Hyper-Solutions/hyper-sdk-py
2. ZenRows Akamai Guide: https://www.zenrows.com/blog/bypass-akamai
3. Akamai Sensor Analysis: https://medium.com/@glizzykingdreko/akamai-v3-sensor-data-deep-dive
4. Scrapy-Impersonate: https://github.com/ljnsn/scrapy-impersonate

---

## Decision Log

**Date**: 2025-10-11
**Decision**: Keep current GUI browser approach
**Reasoning**:
- 100% success rate
- Free solution
- Acceptable overhead (5s per 10-30 min)
- Commercial APIs not cost-effective for our scale
**Review Date**: When scaling requirements change
