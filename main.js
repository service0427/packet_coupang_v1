#!/usr/bin/env node
/**
 * Coupang Akamai Bypass System - Main Entry Point
 *
 * Usage:
 *   node main.js <command> [options]
 *
 * Commands:
 *   browser [version]       - 브라우저로 쿠키 생성
 *   browser-lite [version]  - 경량화 모드 (리소스 차단)
 *   test [version] [query]  - curl-cffi 테스트
 *   verify [version]        - 쿠키 생성 + 검증
 *   analyze                 - 네트워크 트래픽 분석
 */

const path = require('path');
const fs = require('fs');
const readline = require('readline');
const { spawn } = require('child_process');
const { chromium } = require('patchright');

// 디렉토리 설정
const CHROME_VERSIONS_DIR = path.join(__dirname, 'chrome-versions', 'files');
const TLS_DIR = path.join(__dirname, 'chrome-versions', 'tls');
const COOKIES_DIR = path.join(__dirname, 'cookies');
const REPORTS_DIR = path.join(__dirname, 'reports');
const CONFIG_FILE = path.join(__dirname, '.coupang-config.json');

// 디렉토리 생성
[COOKIES_DIR, REPORTS_DIR].forEach(dir => {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
});

// ============================================================
// 유틸리티 함수
// ============================================================

function loadConfig() {
  if (fs.existsSync(CONFIG_FILE)) {
    return JSON.parse(fs.readFileSync(CONFIG_FILE, 'utf-8'));
  }
  return { lastVersion: null, lastCookie: null };
}

function saveConfig(config) {
  fs.writeFileSync(CONFIG_FILE, JSON.stringify(config, null, 2));
}

function getChromeVersions() {
  if (!fs.existsSync(CHROME_VERSIONS_DIR)) return [];

  return fs.readdirSync(CHROME_VERSIONS_DIR)
    .filter(d => fs.statSync(path.join(CHROME_VERSIONS_DIR, d)).isDirectory())
    .map(d => {
      const version = d.replace('chrome-', '');
      const chromePath = path.join(CHROME_VERSIONS_DIR, d, 'chrome-win64', 'chrome.exe');
      return { version, chromePath, dir: d };
    })
    .filter(v => fs.existsSync(v.chromePath))
    .sort((a, b) => {
      const aParts = a.version.split('.').map(Number);
      const bParts = b.version.split('.').map(Number);
      for (let i = 0; i < 4; i++) {
        if (aParts[i] !== bParts[i]) return aParts[i] - bParts[i];
      }
      return 0;
    });
}

function getAvailableCookies() {
  if (!fs.existsSync(COOKIES_DIR)) return [];

  return fs.readdirSync(COOKIES_DIR)
    .filter(f => f.endsWith('_cookies.json'))
    .map(f => {
      const match = f.match(/chrome([\d.]+)_cookies\.json/);
      if (match) {
        return {
          version: match[1],
          file: path.join(COOKIES_DIR, f)
        };
      }
      return null;
    })
    .filter(Boolean);
}

async function selectVersion(versions, defaultVersion) {
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout
  });

  console.log('\n사용 가능한 Chrome 버전:');
  versions.forEach((v, i) => {
    const marker = v.version === defaultVersion ? ' (기본값)' : '';
    console.log(`  ${i + 1}. ${v.version}${marker}`);
  });

  return new Promise((resolve) => {
    rl.question(`\n선택 [${defaultVersion || 1}]: `, (answer) => {
      rl.close();
      if (!answer) {
        const defaultIdx = versions.findIndex(v => v.version === defaultVersion);
        resolve(versions[defaultIdx >= 0 ? defaultIdx : 0]);
      } else {
        const idx = parseInt(answer) - 1;
        resolve(versions[idx] || versions[0]);
      }
    });
  });
}

// ============================================================
// 브라우저 모드 (일반)
// ============================================================

async function runBrowserMode(selected) {
  const { browser, context, page } = await chromium.launch({
    executablePath: selected.chromePath,
    // ============================================================
    // 헤드리스 모드 사용 절대 금지 - Akamai Bot Manager가 탐지함
    // ============================================================
    headless: false
  }).then(async browser => {
    const context = await browser.newContext();
    const page = await context.newPage();
    return { browser, context, page };
  });

  console.log('쿠팡 로그인 페이지 접속 중...');
  const startTime = Date.now();

  await page.goto('https://login.coupang.com/login/login.pang');
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(2000);

  const loadTime = Date.now() - startTime;
  const cookies = await context.cookies();

  const cookieFile = path.join(COOKIES_DIR, `chrome${selected.version}_cookies.json`);
  fs.writeFileSync(cookieFile, JSON.stringify(cookies, null, 2));

  console.log(`\n쿠키 저장됨: ${cookieFile}`);
  console.log(`쿠키 개수: ${cookies.length}개`);
  console.log(`로드 시간: ${loadTime}ms`);

  await browser.close();
  console.log('브라우저 종료됨');

  return { success: true, cookieCount: cookies.length, loadTime };
}

// ============================================================
// 브라우저 모드 (경량화)
// ============================================================

async function runBrowserLiteMode(selected) {
  const { createOptimizedCookie } = require('./lib/cookie-optimizer');

  console.log(`모드: 경량화 (이미지/CSS/CDN 차단)\n`);

  const result = await createOptimizedCookie({
    version: selected.version,
    verbose: true
  });

  return result;
}

// ============================================================
// curl-cffi 테스트
// ============================================================

async function runCurlCffiTest(version, query = '노트북') {
  return new Promise((resolve, reject) => {
    const pythonScript = path.join(__dirname, 'lib', 'curl_cffi_client.py');
    const args = [pythonScript, version, query];

    const python = spawn('python', args);
    let stdout = '';

    python.stdout.on('data', (data) => {
      stdout += data.toString();
      process.stdout.write(data);
    });

    python.stderr.on('data', (data) => {
      process.stderr.write(data);
    });

    python.on('close', (code) => {
      const lines = stdout.trim().split('\n');
      const results = [];

      for (const line of lines) {
        const match = line.match(/Page (\d+): (\d+) \| ([\d,]+) bytes \| (\w+)/);
        if (match) {
          results.push({
            page: parseInt(match[1]),
            status_code: parseInt(match[2]),
            size: parseInt(match[3].replace(/,/g, '')),
            result: match[4]
          });
        }
        const errorMatch = line.match(/Page (\d+): ERROR - (.+)/);
        if (errorMatch) {
          results.push({
            page: parseInt(errorMatch[1]),
            error: errorMatch[2],
            result: 'ERROR'
          });
        }
      }

      resolve(results);
    });

    python.on('error', reject);
  });
}

// ============================================================
// 검증 모드
// ============================================================

async function runVerifyMode(version) {
  const { createOptimizedCookie } = require('./lib/cookie-optimizer');

  console.log('[1/2] 경량화 쿠키 생성 중...\n');

  const optimizeResult = await createOptimizedCookie({
    version,
    verbose: true
  });

  if (!optimizeResult.success) {
    console.log('\n❌ 쿠키 생성 실패');
    return { success: false, phase: 'optimize' };
  }

  console.log('\n[2/2] curl-cffi로 검증 중...\n');

  const testResults = await runCurlCffiTest(optimizeResult.version);
  const successCount = testResults.filter(r => r.result === 'SUCCESS').length;
  const allSuccess = successCount === testResults.length;

  console.log('\n' + '='.repeat(60));
  console.log('검증 결과');
  console.log('='.repeat(60));

  testResults.forEach(r => {
    if (r.result === 'SUCCESS') {
      console.log(`  Page ${r.page}: ✅ ${r.size.toLocaleString()} bytes`);
    } else {
      console.log(`  Page ${r.page}: ❌ ${r.error || 'BLOCKED'}`);
    }
  });

  console.log(`\n결과: ${successCount}/${testResults.length} 성공`);
  console.log(`상태: ${allSuccess ? '✅ VERIFIED' : '❌ FAILED'}`);

  return { success: allSuccess, optimize: optimizeResult, test: testResults };
}

// ============================================================
// 네트워크 분석
// ============================================================

async function runAnalyzeMode() {
  const versions = getChromeVersions();
  const selected = versions.find(v => v.version.includes('136')) || versions[0];

  console.log(`Chrome 버전: ${selected.dir}`);
  console.log('네트워크 트래픽 분석 시작...\n');

  const browser = await chromium.launch({
    executablePath: selected.chromePath,
    headless: false
  });
  const context = await browser.newContext();
  const page = await context.newPage();

  const requests = [];
  let cookieSetterCount = 0;

  page.on('request', request => {
    requests.push({
      url: request.url(),
      resourceType: request.resourceType()
    });
  });

  page.on('response', async response => {
    const headers = response.headers();
    if (headers['set-cookie']) cookieSetterCount++;
  });

  const startTime = Date.now();
  await page.goto('https://login.coupang.com/login/login.pang');
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(3000);
  const loadTime = Date.now() - startTime;

  const cookies = await context.cookies();

  // 분석 결과
  console.log('='.repeat(60));
  console.log('네트워크 분석 결과');
  console.log('='.repeat(60));
  console.log(`\n총 요청 수: ${requests.length}`);
  console.log(`최종 쿠키 수: ${cookies.length}`);
  console.log(`로드 시간: ${loadTime}ms`);

  // 리소스 타입별
  const byType = {};
  requests.forEach(r => {
    byType[r.resourceType] = (byType[r.resourceType] || 0) + 1;
  });

  console.log('\n리소스 타입별:');
  Object.entries(byType).sort((a, b) => b[1] - a[1]).forEach(([type, count]) => {
    console.log(`  ${type}: ${count}`);
  });

  // 도메인별
  const byDomain = {};
  requests.forEach(r => {
    try {
      const domain = new URL(r.url).hostname;
      byDomain[domain] = (byDomain[domain] || 0) + 1;
    } catch (e) {}
  });

  console.log('\n도메인별:');
  Object.entries(byDomain).sort((a, b) => b[1] - a[1]).forEach(([domain, count]) => {
    console.log(`  ${domain}: ${count}`);
  });

  // 쿠키 목록
  console.log('\n쿠키 목록:');
  cookies.forEach(c => {
    console.log(`  ${c.name} (${c.domain})`);
  });

  await browser.close();
  console.log('\n브라우저 종료됨');
}

// ============================================================
// 도움말
// ============================================================

function showHelp() {
  console.log(`
Coupang Akamai Bypass System

Usage:
  node main.js <command> [options]

Commands:
  browser [version]       브라우저로 쿠키 생성 (일반 모드)
  browser-lite [version]  경량화 모드 (이미지/CSS/CDN 차단)
  test [version] [query]  curl-cffi 테스트
  verify [version]        쿠키 생성 + 검증
  analyze                 네트워크 트래픽 분석

Examples:
  node main.js browser 136
  node main.js browser-lite 136
  node main.js test 136 "노트북"
  node main.js verify 136
  node main.js analyze
`);
}

// ============================================================
// 메인 함수
// ============================================================

async function main() {
  const args = process.argv.slice(2);
  const command = args[0];

  if (!command || command === '--help' || command === '-h') {
    showHelp();
    return;
  }

  console.log('='.repeat(50));
  console.log('Coupang Akamai Bypass System');
  console.log('='.repeat(50));

  const config = loadConfig();
  const versions = getChromeVersions();

  if (versions.length === 0) {
    console.error('Chrome 버전을 찾을 수 없습니다.');
    process.exit(1);
  }

  // 버전 선택
  let selected;
  const cliVersion = args[1];

  if (cliVersion && command !== 'analyze') {
    selected = versions.find(v => v.version === cliVersion || v.version.startsWith(cliVersion));
    if (!selected) {
      console.error(`버전을 찾을 수 없습니다: ${cliVersion}`);
      console.log('\n사용 가능한 버전:');
      versions.forEach(v => console.log(`  - ${v.version}`));
      process.exit(1);
    }
  } else if (command !== 'analyze') {
    selected = await selectVersion(versions, config.lastVersion || '136');
  }

  if (selected) {
    config.lastVersion = selected.version;
    saveConfig(config);
    console.log(`\n선택된 버전: ${selected.version}\n`);
  }

  // 명령 실행
  switch (command) {
    case 'browser':
      await runBrowserMode(selected);
      break;

    case 'browser-lite':
      const liteResult = await runBrowserLiteMode(selected);
      if (liteResult.success) {
        console.log('\n✅ 경량화 쿠키 생성 완료');
      } else {
        console.log('\n❌ 쿠키 생성 실패');
        process.exit(1);
      }
      break;

    case 'test':
      const query = args[2] || '노트북';
      const cookies = getAvailableCookies();
      const cookie = cookies.find(c => c.version === selected.version);

      if (!cookie) {
        console.error(`쿠키를 찾을 수 없습니다: Chrome ${selected.version}`);
        console.error('먼저 browser 또는 browser-lite로 쿠키를 생성하세요.');
        process.exit(1);
      }

      await runCurlCffiTest(selected.version, query);
      break;

    case 'verify':
      const verifyResult = await runVerifyMode(selected.version);
      process.exit(verifyResult.success ? 0 : 1);
      break;

    case 'analyze':
      await runAnalyzeMode();
      break;

    default:
      console.error(`알 수 없는 명령: ${command}`);
      showHelp();
      process.exit(1);
  }
}

main().catch(err => {
  console.error('에러:', err.message);
  process.exit(1);
});
