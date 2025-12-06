# Database Schema

## cookies 테이블

```sql
CREATE TABLE cookies (
    id INT AUTO_INCREMENT PRIMARY KEY,

    -- IP 바인딩
    proxy_ip VARCHAR(45) NOT NULL,      -- 프록시 외부 IP
    proxy_url VARCHAR(255),             -- host:port (socks5:// 제외)

    -- Chrome 버전
    chrome_version VARCHAR(50) NOT NULL,

    -- 쿠키 데이터
    cookie_data JSON NOT NULL,

    -- 초기 상태
    init_status ENUM('valid', 'denied', 'blocked', 'invalid') DEFAULT 'valid',

    -- 사용 통계
    use_count INT DEFAULT 0,
    success_count INT DEFAULT 0,
    fail_count INT DEFAULT 0,

    -- 시간
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    locked_at TIMESTAMP NULL,
    last_used_at TIMESTAMP NULL,

    INDEX idx_proxy_ip (proxy_ip),
    INDEX idx_created_at (created_at),
    INDEX idx_init_status (init_status)
);
```

## fingerprints 테이블 (구버전)

```sql
CREATE TABLE fingerprints (
    id INT AUTO_INCREMENT PRIMARY KEY,
    chrome_version VARCHAR(50) NOT NULL,
    chrome_major INT NOT NULL,
    platform VARCHAR(20) NOT NULL,
    ja3_text TEXT NOT NULL,
    ja3_hash VARCHAR(64),
    akamai_text TEXT,
    akamai_hash VARCHAR(64),
    user_agent TEXT,
    signature_algorithms JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE KEY uk_version_platform (chrome_version, platform)
);
```

## tls_profiles 테이블

TLS 핑거프린트 프로필 - PC/Mobile 플랫폼별 관리

```sql
CREATE TABLE tls_profiles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    profile_id VARCHAR(50) NOT NULL,            -- 고유 식별자 (예: win11_143_0_7446_0)
    platform ENUM('mobile', 'pc') NOT NULL,     -- 플랫폼
    browser_version INT NOT NULL,               -- Chrome major 버전 (예: 143)
    chrome_version_full VARCHAR(20),            -- 전체 버전 (예: 143.0.7446.0)
    ja3_text TEXT NOT NULL,                     -- JA3 핑거프린트
    signature_algorithms LONGTEXT NOT NULL,     -- TLS signature algorithms (JSON)
    akamai_text VARCHAR(200) NOT NULL,          -- Akamai HTTP/2 핑거프린트
    user_agent TEXT NOT NULL,                   -- User-Agent 문자열
    sec_ch_ua VARCHAR(200) NOT NULL,            -- sec-ch-ua 헤더
    sec_ch_ua_mobile VARCHAR(10) NOT NULL,      -- sec-ch-ua-mobile (예: ?0, ?1)
    sec_ch_ua_platform VARCHAR(20) NOT NULL,    -- sec-ch-ua-platform (예: "Linux")
    accept_header TEXT NOT NULL,                -- Accept 헤더
    enabled TINYINT(1) DEFAULT 1,               -- 활성화 여부
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE KEY uk_profile_id (profile_id),
    INDEX idx_platform (platform),
    INDEX idx_enabled (enabled)
);
```

### tls_profiles 사용 예시

```python
from lib.common.fingerprint import get_tls_profile, build_tls_extra_fp, build_tls_headers

# 랜덤 프로필 조회 (excluded_builds 제외)
excluded = ['131.0.6778.108', '136.0.7103.92']
profile = get_tls_profile(platform='pc', excluded_builds=excluded)

# curl-cffi extra_fp 생성
extra_fp = build_tls_extra_fp(profile)

# HTTP 헤더 생성
headers = build_tls_headers(profile, referer='https://www.coupang.com/')

# 전체 버전 조회
chrome_version = profile['chrome_version_full']  # 예: 143.0.7446.0
```

### 플랫폼별 프로필 수

| platform | 개수 | 버전 범위 |
|----------|------|-----------|
| pc       | 38개 | 127~144   |
| mobile   | 5개  | 138~142   |

## product_list 테이블

```sql
CREATE TABLE product_list (
    id INT AUTO_INCREMENT PRIMARY KEY,
    keyword VARCHAR(255) NOT NULL,
    product_id VARCHAR(50) NOT NULL,
    item_id VARCHAR(50),
    vendor_item_id VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_keyword (keyword),
    INDEX idx_product_id (product_id)
);
```

## 쿠키 상태 (init_status)

| 상태 | 설명 |
|------|------|
| valid | 정상 쿠키 (사용 가능) |
| denied | 생성 시점에 access denied |
| blocked | 생성 시점에 403 차단 |
| invalid | 쿠키 데이터 불완전 |

## ljc_flow_logs 테이블

LJC 플로우 실행 로그 - 각 스텝별 성공/실패 저장

```sql
CREATE TABLE ljc_flow_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,

    -- 검색 정보 (product_list 기준)
    product_list_id INT NULL,                   -- product_list.id 참조
    keyword VARCHAR(255) NOT NULL,
    target_product_id VARCHAR(50) NOT NULL,

    -- 쿠키/프록시 정보
    cookie_id INT NULL,                         -- cookies.id 참조
    proxy VARCHAR(100) NULL,                    -- host:port
    device VARCHAR(50) NULL,                    -- 기기 프로필

    -- 실행 파라미터 (CLI 옵션)
    member_srl VARCHAR(20) NULL,
    is_loyalty_member TINYINT(1) DEFAULT 0,
    sleep_seconds FLOAT DEFAULT 0,
    swap_old TINYINT(1) DEFAULT 0,
    old_cookie_id INT NULL,

    -- Step 1: 검색 페이지 요청
    step1_search_page TINYINT(1) NULL,          -- 1=성공, 0=실패, NULL=미실행
    step1_size INT NULL,
    step1_error VARCHAR(255) NULL,

    -- Step 2: srp_view_impression
    step2_srp_view TINYINT(1) NULL,
    step2_status INT NULL,

    -- Step 3: srp_product_unit_impression
    step3_product_impression TINYINT(1) NULL,
    step3_impression_count INT NULL,

    -- Step 3.5: impression_ranking
    step3_5_ranking TINYINT(1) NULL,
    step3_5_status INT NULL,

    -- Step 4: click_search_product
    step4_click TINYINT(1) NULL,
    step4_status INT NULL,

    -- Step 5: 상품 상세 페이지 요청
    step5_detail_page TINYINT(1) NULL,
    step5_size INT NULL,
    step5_error VARCHAR(255) NULL,

    -- Step 6: sdp_product_page_view
    step6_page_view TINYINT(1) NULL,
    step6_status INT NULL,

    -- Step 6.5: sdp_atf (Above The Fold)
    step6_5_atf TINYINT(1) NULL,
    step6_5_status INT NULL,

    -- Step 7: add_cart
    step7_cart TINYINT(1) NULL,
    step7_status INT NULL,

    -- 결과 요약
    success TINYINT(1) NOT NULL DEFAULT 0,
    found_rank INT NULL,
    error_message VARCHAR(500) NULL,

    -- 시간
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP NULL,
    duration_seconds FLOAT NULL,

    INDEX idx_product_list_id (product_list_id),
    INDEX idx_keyword (keyword),
    INDEX idx_target_product_id (target_product_id),
    INDEX idx_cookie_id (cookie_id),
    INDEX idx_success (success),
    INDEX idx_started_at (started_at)
);
```

### 스텝별 의미

| 스텝 | 이름 | 설명 |
|------|------|------|
| 1 | search_page | 검색 페이지 HTML 요청 |
| 2 | srp_view_impression | 검색 결과 페이지 노출 이벤트 |
| 3 | product_impression | 상품 노출 이벤트 (조회 카운트) |
| 3.5 | impression_ranking | 클릭 직전 랭킹 노출 |
| 4 | click_search_product | 상품 클릭 이벤트 |
| 5 | detail_page | 상품 상세 페이지 HTML 요청 |
| 6 | sdp_page_view | 상세 페이지 로드 이벤트 |
| 6.5 | sdp_atf | Above The Fold 노출 |
| 7 | add_cart | 장바구니 추가 이벤트 |

## proxy_url 저장 규칙

```python
# 저장: host:port 만 (socks5:// 제외)
proxy_url = "123.45.67.89:1080"

# 사용: socks5:// 추가
proxy = f'socks5://{proxy_url}'
```
