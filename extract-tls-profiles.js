/**
 * TLS Profile Extractor - Playwright + Patchright
 * https://tls.browserleaks.com 에서 TLS 정보 추출
 */

const { chromium } = require('patchright');
const fs = require('fs');
const path = require('path');

const CHROME_FILES_DIR = path.join(__dirname, 'chrome-versions', 'files');
const TLS_OUTPUT_DIR = path.join(__dirname, 'chrome-versions', 'tls');

fs.mkdirSync(TLS_OUTPUT_DIR, { recursive: true });

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
    .filter(Boolean);
}

async function extractTLS(chromeInfo) {
  const { version, chromePath } = chromeInfo;
  console.log(`\n[${version}] 추출 중...`);

  let browser = null;

  try {
    browser = await chromium.launch({
      executablePath: chromePath,
      headless: false,
      args: ['--disable-blink-features=AutomationControlled', '--no-first-run']
    });

    const context = await browser.newContext();
    const page = await context.newPage();

    // 네트워크 응답 캡처
    let tlsData = null;

    page.on('response', async (response) => {
      const url = response.url();
      if (url.includes('tls.browserleaks.com') && response.headers()['content-type']?.includes('application/json')) {
        try {
          tlsData = await response.json();
        } catch (e) {}
      }
    });

    await page.goto('https://tls.browserleaks.com/', {
      timeout: 30000,
      waitUntil: 'networkidle'
    });
    await page.waitForTimeout(5000);

    // 응답이 없으면 페이지에서 JSON 찾기
    if (!tlsData) {
      const content = await page.content();
      const jsonMatch = content.match(/\{[\s\S]*"ja3_hash"[\s\S]*\}/);
      if (jsonMatch) {
        try {
          tlsData = JSON.parse(jsonMatch[0]);
        } catch (e) {}
      }
    }

    await browser.close();

    if (!tlsData) {
      throw new Error('TLS 데이터를 찾을 수 없음');
    }

    // 저장
    const outputFile = path.join(TLS_OUTPUT_DIR, `${version}.json`);
    fs.writeFileSync(outputFile, JSON.stringify(tlsData, null, 2));
    console.log(`  [OK] ${outputFile}`);
    if (tlsData.ja3_hash) console.log(`  JA3: ${tlsData.ja3_hash}`);

    return { success: true, version };

  } catch (error) {
    console.error(`  [ERROR] ${error.message}`);
    if (browser) await browser.close();
    return { success: false, version, error: error.message };
  }
}

async function main() {
  console.log('TLS Profile Extractor\n');

  const chromeVersions = getChromeVersions();
  console.log(`Chrome 버전: ${chromeVersions.length}개\n`);

  const results = [];

  for (let i = 0; i < chromeVersions.length; i++) {
    console.log(`[${i + 1}/${chromeVersions.length}]`);
    const result = await extractTLS(chromeVersions[i]);
    results.push(result);

    if (i < chromeVersions.length - 1) {
      await new Promise(resolve => setTimeout(resolve, 2000));
    }
  }

  // 요약
  const success = results.filter(r => r.success).length;
  const failed = results.filter(r => !r.success);

  console.log(`\n${'='.repeat(40)}`);
  console.log(`완료: ${success}/${results.length}`);
  if (failed.length > 0) {
    console.log(`실패: ${failed.map(r => r.version).join(', ')}`);
  }
}

main().catch(err => {
  console.error('Error:', err);
  process.exit(1);
});
