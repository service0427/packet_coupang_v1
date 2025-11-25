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

## fingerprints 테이블

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

## proxy_url 저장 규칙

```python
# 저장: host:port 만 (socks5:// 제외)
proxy_url = "123.45.67.89:1080"

# 사용: socks5:// 추가
proxy = f'socks5://{proxy_url}'
```
