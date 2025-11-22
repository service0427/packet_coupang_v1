/**
 * Coupang TLS Test - 브라우저 쿠키 취득 및 curl-cffi 테스트
 *
 * Usage:
 *   npm run coupang browser [version]     # 브라우저로 쿠키 생성
 *   npm run coupang test [version] [query] # curl-cffi 테스트
 *   npm run coupang                        # 대화형 모드
 */

const { launch } = require('./lib/browser/browser-launcher');
const { spawn } = require('child_process');
const readline = require('readline');
const fs = require('fs');
const path = require('path');

const CHROME_FILES_DIR = path.join(__dirname, 'chrome-versions', 'files');
const COOKIES_DIR = path.join(__dirname, 'cookies');
const USER_DATA_DIR = path.join(__dirname, 'user-data');
const REPORTS_DIR = path.join(__dirname, 'reports');
const TLS_DIR = path.join(__dirname, 'chrome-versions', 'tls');
const CONFIG_FILE = path.join(__dirname, '.coupang-test-config.json');

// 디렉토리 생성
[COOKIES_DIR, USER_DATA_DIR, REPORTS_DIR].forEach(dir => {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
});

// 리포트 생성
function createReport(data) {
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  const reportFile = path.join(REPORTS_DIR, `report-${timestamp}.json`);

  const report = {
    timestamp: new Date().toISOString(),
    ...data,
    goal: 'Browser cookie → curl-cffi 활용 테스트',
    nextSteps: []
  };

  // 결과에 따른 다음 단계 제안
  if (data.cookieCount > 0) {
    report.nextSteps.push('curl-cffi로 쿠키 테스트 필요');
  }
  if (data.networkErrors && data.networkErrors.length > 0) {
    report.nextSteps.push('네트워크 에러 분석 필요');
  }

  fs.writeFileSync(reportFile, JSON.stringify(report, null, 2));
  return reportFile;
}

// 설정 로드
function loadConfig() {
  try {
    if (fs.existsSync(CONFIG_FILE)) {
      return JSON.parse(fs.readFileSync(CONFIG_FILE, 'utf-8'));
    }
  } catch (e) {}
  return {};
}

// 설정 저장
function saveConfig(config) {
  fs.writeFileSync(CONFIG_FILE, JSON.stringify(config, null, 2));
}

// Chrome 버전 목록 가져오기
function getChromeVersions() {
  return fs.readdirSync(CHROME_FILES_DIR)
    .filter(dir => dir.startsWith('chrome-'))
    .map(dir => {
      const version = dir.replace('chrome-', '');
      const chromePath = path.join(CHROME_FILES_DIR, dir, 'chrome-win64', 'chrome.exe');
      if (fs.existsSync(chromePath)) {
        return { version, chromePath };
      }
      return null;
    })
    .filter(Boolean)
    .sort((a, b) => {
      const aParts = a.version.split('.').map(Number);
      const bParts = b.version.split('.').map(Number);
      for (let i = 0; i < aParts.length; i++) {
        if (aParts[i] !== bParts[i]) return aParts[i] - bParts[i];
      }
      return 0;
    });
}

// 버전 선택 프롬프트
async function selectVersion(versions, defaultVersion) {
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout
  });

  console.log('\n사용 가능한 Chrome 버전:\n');
  versions.forEach((v, i) => {
    const marker = v.version === defaultVersion ? ' (기본값)' : '';
    console.log(`  ${i + 1}. ${v.version}${marker}`);
  });

  const defaultIndex = versions.findIndex(v => v.version === defaultVersion);
  const defaultPrompt = defaultIndex >= 0 ? ` [${defaultIndex + 1}]` : '';

  return new Promise((resolve) => {
    rl.question(`\n선택${defaultPrompt}: `, (answer) => {
      rl.close();

      if (!answer && defaultIndex >= 0) {
        resolve(versions[defaultIndex]);
        return;
      }

      const index = parseInt(answer) - 1;
      if (index >= 0 && index < versions.length) {
        resolve(versions[index]);
      } else {
        console.log('잘못된 선택입니다.');
        process.exit(1);
      }
    });
  });
}

// 사용 가능한 쿠키 파일 목록
function getAvailableCookies() {
  if (!fs.existsSync(COOKIES_DIR)) return [];

  return fs.readdirSync(COOKIES_DIR)
    .filter(f => f.startsWith('chrome') && f.endsWith('_cookies.json'))
    .map(f => {
      // 상세 버전 매칭 (예: chrome141.0.7340.0_cookies.json)
      const match = f.match(/chrome([\d.]+)_cookies\.json/);
      if (match) {
        const version = match[1];
        const filePath = path.join(COOKIES_DIR, f);
        const stats = fs.statSync(filePath);
        return {
          version,
          majorVersion: version.split('.')[0],
          fileName: f,
          filePath,
          mtime: stats.mtime
        };
      }
      return null;
    })
    .filter(Boolean)
    .sort((a, b) => b.mtime - a.mtime); // 최신순
}

// 경과 시간 계산
function getElapsedTime(mtime) {
  const now = Date.now();
  const diff = now - mtime.getTime();
  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);

  if (days > 0) {
    return `${days}일 전`;
  } else if (hours > 0) {
    return `${hours}시간 전`;
  } else if (minutes > 0) {
    return `${minutes}분 전`;
  } else {
    return '방금 전';
  }
}

// 쿠키 선택 프롬프트
async function selectCookie(cookies, defaultCookie) {
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout
  });

  console.log('\n사용 가능한 쿠키 파일:\n');
  cookies.forEach((c, i) => {
    const marker = c.version === defaultCookie ? ' (기본값)' : '';
    const date = c.mtime.toLocaleString('ko-KR');
    const elapsed = getElapsedTime(c.mtime);
    console.log(`  ${i + 1}. Chrome ${c.version} - ${date} (${elapsed})${marker}`);
  });

  const defaultIndex = cookies.findIndex(c => c.version === defaultCookie);
  const defaultPrompt = defaultIndex >= 0 ? ` [${defaultIndex + 1}]` : '';

  return new Promise((resolve) => {
    rl.question(`\n선택${defaultPrompt}: `, (answer) => {
      rl.close();

      if (!answer && defaultIndex >= 0) {
        resolve(cookies[defaultIndex]);
        return;
      }

      const index = parseInt(answer) - 1;
      if (index >= 0 && index < cookies.length) {
        resolve(cookies[index]);
      } else {
        console.log('잘못된 선택입니다.');
        process.exit(1);
      }
    });
  });
}

// curl-cffi 테스트 실행
async function runCurlCffiTest(cookieInfo, query = '노트북', pages = 5) {
  // TLS 프로파일 찾기 (상세 버전으로 정확히 매칭)
  const tlsFile = path.join(TLS_DIR, `${cookieInfo.version}.json`);

  if (!fs.existsSync(tlsFile)) {
    console.error(`TLS 프로파일을 찾을 수 없습니다: ${tlsFile}`);
    return null;
  }

  const tlsProfile = JSON.parse(fs.readFileSync(tlsFile, 'utf-8'));

  // 쿠키 로드
  const cookies = JSON.parse(fs.readFileSync(cookieInfo.filePath, 'utf-8'));
  const cookieDict = {};
  cookies.forEach(c => { cookieDict[c.name] = c.value; });

  console.log(`\n${'='.repeat(60)}`);
  console.log(`Chrome 버전: ${cookieInfo.version}`);
  console.log(`JA3 Hash: ${tlsProfile.ja3_hash || 'N/A'}`);
  console.log(`Akamai Hash: ${tlsProfile.akamai_hash || 'N/A'}`);
  console.log(`쿠키 개수: ${cookies.length}개`);
  console.log(`${'='.repeat(60)}\n`);

  // Python curl-cffi 실행
  return new Promise((resolve) => {
    // JSON을 Base64로 인코딩하여 전달 (특수문자 문제 회피)
    const tlsBase64 = Buffer.from(JSON.stringify(tlsProfile)).toString('base64');
    const cookiesBase64 = Buffer.from(JSON.stringify(cookieDict)).toString('base64');

    const pythonScript = `
# -*- coding: utf-8 -*-
import json
import sys
import io
import time
from pathlib import Path

# Windows stdout 인코딩 설정
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 공통 모듈 사용
sys.path.insert(0, str(Path('${__dirname.replace(/\\/g, '/')}') / 'lib'))
from curl_cffi_client import CoupangClient

version = '${cookieInfo.version}'
base_dir = Path('${__dirname.replace(/\\/g, '/')}')

client = CoupangClient(version, base_dir)

results = []
for page in range(1, ${pages + 1}):
    try:
        response = client.search('${query}', page=page)
        size = len(response.content)
        status = "SUCCESS" if size > 50000 else "BLOCKED"
        results.append({'page': page, 'status_code': response.status_code, 'size': size, 'result': status})
        print(f"Page {page}: {response.status_code} | {size:,} bytes | {status}")
        # 요청 간 딜레이
        if page < ${pages}:
            time.sleep(2)
    except Exception as e:
        results.append({'page': page, 'error': str(e), 'result': 'ERROR'})
        print(f"Page {page}: ERROR - {e}")

success_count = sum(1 for r in results if r.get('result') == 'SUCCESS')
print(f"\\nResult: {success_count}/${pages} pages success (custom JA3/Akamai)")
print(json.dumps(results))
`;

    const python = spawn('python', ['-c', pythonScript]);
    let output = '';

    python.stdout.on('data', (data) => {
      const text = data.toString();
      // JSON 결과 제외하고 출력
      if (!text.trim().startsWith('[')) {
        process.stdout.write(text);
      }
      output += text;
    });

    python.stderr.on('data', (data) => {
      process.stderr.write(data);
    });

    python.on('close', (code) => {
      if (code === 0) {
        // 마지막 줄에서 JSON 결과 파싱
        const lines = output.trim().split('\n');
        const lastLine = lines[lines.length - 1];
        try {
          const results = JSON.parse(lastLine);
          resolve(results);
        } catch (e) {
          resolve(null);
        }
      } else {
        resolve(null);
      }
    });
  });
}

// 브라우저 모드 실행
async function runBrowserMode(selected) {
  const { browser, context, page } = await launch({
    executablePath: selected.chromePath,
    // ============================================================
    // 헤드리스 모드 사용 절대 금지 - Akamai Bot Manager가 탐지함
    // ============================================================
    // 탐지 요소:
    // 1. navigator.webdriver = true (헤드리스 브라우저 표시)
    // 2. User-Agent에 'HeadlessChrome' 문자열 포함
    // 3. navigator.plugins 배열이 비어있음
    // 4. JavaScript 핑거프린팅 (OS, 폰트, 화면 크기 불일치)
    // 5. 마우스 움직임, 스크롤 등 행동 패턴 없음
    // 6. WebGL/Canvas 핑거프린트 불일치
    //
    // 테스트 결과 (2025-11-22):
    // - Chrome 142.0.7444.59: 1,173 bytes BLOCKED
    // - Chrome 144.0.7504.0: 1,210 bytes BLOCKED
    // - Chrome 143.0.7499.5: 1,211 bytes BLOCKED
    // - Chrome 140.0.7339.207: 1,174 bytes BLOCKED
    //
    // Patchright(Playwright Stealth) 적용 상태에서도 우회 불가
    // 상용 서비스(Bright Data, Oxylabs 등)만 가능
    // ============================================================
    headless: false
  });

  console.log('쿠팡 로그인 페이지 접속 중...');
  const startTime = Date.now();

  await page.goto('https://login.coupang.com/login/login.pang');
  await page.waitForLoadState('networkidle');

  // 메인 페이지에서 잠시 대기 (더 자연스러운 행동)
  await page.waitForTimeout(2000);

  const loadTime = Date.now() - startTime;

  // 쿠키 추출 및 저장 (상세 버전으로 저장)
  const cookies = await context.cookies();
  const cookieFile = path.join(COOKIES_DIR, `chrome${selected.version}_cookies.json`);
  fs.writeFileSync(cookieFile, JSON.stringify(cookies, null, 2));
  console.log(`\n쿠키 저장됨: ${cookieFile}`);
  console.log(`쿠키 개수: ${cookies.length}개`);
  console.log(`로드 시간: ${loadTime}ms`);

  // 리포트 생성
  const reportFile = createReport({
    chromeVersion: selected.version,
    mode: 'browser',
    action: 'coupang_main_access',
    cookieFile,
    cookieCount: cookies.length,
    loadTime,
    status: 'SUCCESS'
  });
  console.log(`리포트 저장됨: ${reportFile}`);

  // 자동으로 브라우저 닫기
  await browser.close();
  console.log('브라우저 종료됨');
}

// 메인 함수
async function main() {
  console.log('='.repeat(50));
  console.log('Coupang TLS Test');
  console.log('='.repeat(50));

  const config = loadConfig();

  // CLI 인자 파싱
  const args = process.argv.slice(2);
  let mode = null;
  let cliVersion = null;
  let query = '노트북';

  // 모드 파싱
  if (args[0] === 'browser' || args[0] === 'browser-lite' || args[0] === 'test') {
    mode = args[0];
    args.shift();
  }

  // 나머지 인자 파싱
  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (!arg.startsWith('-')) {
      if (!cliVersion) {
        cliVersion = arg;
      } else {
        query = arg;
      }
    }
  }

  // 모드 선택 (대화형)
  if (!mode) {
    const rl = readline.createInterface({
      input: process.stdin,
      output: process.stdout
    });

    console.log('\n모드 선택:\n');
    console.log('  1. browser      - 브라우저로 쿠키 생성');
    console.log('  2. browser-lite - 경량화 모드 (리소스 차단)');
    console.log('  3. test         - curl-cffi 테스트');

    mode = await new Promise((resolve) => {
      rl.question('\n선택 [1]: ', (answer) => {
        rl.close();
        if (!answer || answer === '1') {
          resolve('browser');
        } else if (answer === '2') {
          resolve('browser-lite');
        } else if (answer === '3') {
          resolve('test');
        } else {
          resolve('browser');
        }
      });
    });
  }

  if (mode === 'browser') {
    // 브라우저 모드
    const versions = getChromeVersions();
    if (versions.length === 0) {
      console.error('Chrome 버전을 찾을 수 없습니다.');
      process.exit(1);
    }

    let selected;
    if (cliVersion) {
      selected = versions.find(v => v.version === cliVersion || v.version.startsWith(cliVersion));
      if (!selected) {
        console.error(`버전을 찾을 수 없습니다: ${cliVersion}`);
        console.log('\n사용 가능한 버전:');
        versions.forEach(v => console.log(`  - ${v.version}`));
        process.exit(1);
      }
    } else {
      selected = await selectVersion(versions, config.lastVersion);
    }

    config.lastVersion = selected.version;
    config.lastCookie = selected.version;
    saveConfig(config);

    console.log(`\n선택된 버전: ${selected.version}`);
    console.log(`경로: ${selected.chromePath}\n`);

    await runBrowserMode(selected);

  } else if (mode === 'browser-lite') {
    // 경량화 브라우저 모드 (리소스 차단)
    const { createOptimizedCookie } = require('./lib/cookie-optimizer');

    const versions = getChromeVersions();
    if (versions.length === 0) {
      console.error('Chrome 버전을 찾을 수 없습니다.');
      process.exit(1);
    }

    let selected;
    if (cliVersion) {
      selected = versions.find(v => v.version === cliVersion || v.version.startsWith(cliVersion));
      if (!selected) {
        console.error(`버전을 찾을 수 없습니다: ${cliVersion}`);
        console.log('\n사용 가능한 버전:');
        versions.forEach(v => console.log(`  - ${v.version}`));
        process.exit(1);
      }
    } else {
      selected = await selectVersion(versions, config.lastVersion);
    }

    config.lastVersion = selected.version;
    config.lastCookie = selected.version;
    saveConfig(config);

    console.log(`\n선택된 버전: ${selected.version}`);
    console.log(`모드: 경량화 (이미지/CSS/CDN 차단)\n`);

    const result = await createOptimizedCookie({
      version: selected.version,
      verbose: true
    });

    if (result.success) {
      console.log('\n✅ 경량화 쿠키 생성 완료');
    } else {
      console.log('\n❌ 쿠키 생성 실패');
      process.exit(1);
    }

  } else if (mode === 'test') {
    // curl-cffi 테스트 모드
    const cookies = getAvailableCookies();
    if (cookies.length === 0) {
      console.error('쿠키 파일이 없습니다. 먼저 browser 모드로 쿠키를 생성하세요.');
      process.exit(1);
    }

    let selectedCookie;
    if (cliVersion) {
      // 버전 부분 매칭 (예: 141 → 141.0.7340.0)
      selectedCookie = cookies.find(c => c.version === cliVersion || c.version.startsWith(cliVersion + '.'));
      if (!selectedCookie) {
        console.error(`쿠키를 찾을 수 없습니다: Chrome ${cliVersion}`);
        console.log('\n사용 가능한 쿠키:');
        cookies.forEach(c => console.log(`  - Chrome ${c.version}`));
        process.exit(1);
      }
    } else {
      // 기본값이 없으면 최신 쿠키를 기본값으로 설정
      const defaultCookie = config.lastCookie || cookies[0].version;
      selectedCookie = await selectCookie(cookies, defaultCookie);
    }

    config.lastCookie = selectedCookie.version;
    saveConfig(config);

    const results = await runCurlCffiTest(selectedCookie, query);

    if (results) {
      // 리포트 저장
      const reportFile = path.join(REPORTS_DIR, `curl-cffi-test-${selectedCookie.version}.json`);
      const report = {
        timestamp: new Date().toISOString(),
        chromeVersion: selectedCookie.version,
        mode: 'test',
        query,
        results,
        successRate: results.filter(r => r.result === 'SUCCESS').length / results.length
      };
      fs.writeFileSync(reportFile, JSON.stringify(report, null, 2));
      console.log(`\n리포트 저장됨: ${reportFile}`);
    }
  }
}

main().catch(err => {
  console.error('Error:', err);
  process.exit(1);
});
