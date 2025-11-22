# Windows에서 여러 Chrome 버전 설치하기

## 문제
- Windows는 하나의 Chrome만 설치 가능 (Program Files에)
- 여러 버전을 동시에 사용하려면 Portable 버전 필요

## 해결 방법

### 방법 1: Chrome Portable 다운로드 (추천)

1. **Chromium Portable 다운로드**:
   - https://chromium.woolyss.com/download/
   - 각 버전별로 다운로드 가능
   - 압축 해제하여 별도 폴더에 저장

2. **디렉토리 구조**:
```
D:\chrome-versions\
  ├── chrome-120\
  │   └── chrome.exe
  ├── chrome-125\
  │   └── chrome.exe
  ├── chrome-130\
  │   └── chrome.exe
  ├── chrome-135\
  │   └── chrome.exe
  └── chrome-140\
      └── chrome.exe
```

### 방법 2: Chrome for Testing 사용

Google이 제공하는 테스트용 Chrome:
- https://googlechromelabs.github.io/chrome-for-testing/
- 특정 버전별로 다운로드 가능
- zip 파일로 제공 (설치 없이 실행 가능)

**다운로드 예시**:
```bash
# Chrome 120
https://edgedl.me.gstatic.com/edgedl/chrome/chrome-for-testing/120.0.6099.109/win64/chrome-win64.zip

# Chrome 125
https://edgedl.me.gstatic.com/edgedl/chrome/chrome-for-testing/125.0.6422.60/win64/chrome-win64.zip

# Chrome 130
https://edgedl.me.gstatic.com/edgedl/chrome/chrome-for-testing/130.0.6723.58/win64/chrome-win64.zip
```

### 방법 3: 자동 다운로드 스크립트

```powershell
# download_chrome_versions.ps1

$versions = @(
    "120.0.6099.109",
    "125.0.6422.60",
    "130.0.6723.58",
    "135.0.7049.95",
    "140.0.7339.111"
)

$baseUrl = "https://edgedl.me.gstatic.com/edgedl/chrome/chrome-for-testing"
$outputDir = "D:\chrome-versions"

foreach ($version in $versions) {
    $major = $version.Split('.')[0]
    $url = "$baseUrl/$version/win64/chrome-win64.zip"
    $zipPath = "$outputDir\chrome-$major.zip"
    $extractPath = "$outputDir\chrome-$major"

    Write-Host "Downloading Chrome $version..."
    Invoke-WebRequest -Uri $url -OutFile $zipPath

    Write-Host "Extracting to $extractPath..."
    Expand-Archive -Path $zipPath -DestinationPath $extractPath -Force

    Remove-Item $zipPath
}

Write-Host "Complete! All Chrome versions installed."
```

## 실행 방법

설치 후 코드 수정:

```javascript
const chromeVersions = {
    '120': 'D:\\chrome-versions\\chrome-120\\chrome-win64\\chrome.exe',
    '125': 'D:\\chrome-versions\\chrome-125\\chrome-win64\\chrome.exe',
    '130': 'D:\\chrome-versions\\chrome-130\\chrome-win64\\chrome.exe',
    '135': 'D:\\chrome-versions\\chrome-135\\chrome-win64\\chrome.exe',
    '140': 'D:\\chrome-versions\\chrome-140\\chrome-win64\\chrome.exe'
};

// 사용
const chromePath = chromeVersions['125'];
```

## 주의사항

1. **디스크 공간**: 각 Chrome 버전은 약 300MB
   - 20개 버전 = 약 6GB 필요

2. **User Data Dir**: 각 버전마다 별도 user-data-dir 필요
   ```javascript
   `--user-data-dir=D:\\chrome-data\\chrome-${version}`
   ```

3. **TLS 핑거프린트**: 각 버전은 고유한 JA3 값을 가짐
   - Chrome 120: `0906abad57995ba85a94c97105fda256`
   - Chrome 125: `6da27a000eb2564e0d2808103f05a502`
   - Chrome 130: `310b84b9fa9a993d23c28b2c058c6d9c`
   - Chrome 135: `2cd7ed9892be5fde26968beaec071392`
   - Chrome 140: `fbe4d7dd8f8f29e06d01904ed5c8df66`

## 현재 상황

현재는 **User Agent만 변경**했기 때문에:
- 실제 Chrome 버전: 동일 (설치된 버전)
- TLS 핑거프린트: 동일
- JA3 해시: 동일
- **결과**: 우회 효과 없음

**진짜 우회하려면**: 실제로 다른 Chrome 실행 파일을 사용해야 함
