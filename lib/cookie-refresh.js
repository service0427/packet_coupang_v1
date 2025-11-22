/**
 * Cookie Refresh Generator
 * Akamai 쿠키 유지 + 쿠팡 쿠키만 갱신
 *
 * 방식: 기존 Akamai 쿠키 유지 → 새로고침 → 쿠팡 쿠키만 갱신
 * 트래픽 최소화를 위한 리프레시 방식
 */

const { chromium } = require('patchright');
const path = require('path');
const fs = require('fs');

const CHROME_VERSIONS_DIR = path.join(__dirname, '..', 'chrome-versions', 'files');
const COOKIES_DIR = path.join(__dirname, '..', 'cookies');
const USER_DATA_DIR = path.join(__dirname, '..', 'user-data');

// Akamai 쿠키 (유지할 쿠키)
const AKAMAI_COOKIES = ['_abck', 'ak_bmsc', 'bm_s', 'bm_sz', 'bm_ss', 'bm_so', 'bm_lso'];

// 쿠팡 쿠키 (삭제 후 갱신할 쿠키)
const COUPANG_COOKIES = [
  'sid', 'PCID', 'MARKETID', 'LOCALE',
  'x-coupang-accept-language', 'x-coupang-target-market',
  'authCodeVerifier', 'authLoginChallenge', 'authLoginSessionId', 'authRedirectUri',
  'CT_LSID', 'web-session-id'
];

// 차단할 리소스
const BLOCKED_TYPES = ['image', 'stylesheet', 'font', 'media'];
const BLOCKED_PATTERNS = ['coupangcdn.com', 'qrcode', 'login.min.js'];

/**
 * Chrome 실행 파일 경로 찾기
 */
function findChromePath(version) {
  const dirs = fs.readdirSync(CHROME_VERSIONS_DIR).filter(d =>
    fs.statSync(path.join(CHROME_VERSIONS_DIR, d)).isDirectory()
  );

  let selectedDir = dirs.find(d => d.includes(version)) ||
                    dirs.find(d => d.includes('136')) ||
                    dirs[0];

  if (!selectedDir) throw new Error('Chrome 버전을 찾을 수 없습니다.');

  const chromePath = path.join(CHROME_VERSIONS_DIR, selectedDir, 'chrome-win64', 'chrome.exe');
  if (!fs.existsSync(chromePath)) throw new Error(`Chrome 실행 파일 없음: ${chromePath}`);

  return { selectedDir, chromePath };
}

/**
 * 쿠키 리프레시 (Akamai 유지 + 쿠팡 갱신)
 */
async function refreshCookie(options = {}) {
  const {
    version = '136',
    verbose = true,
    proxy = null
  } = options;

  const { selectedDir, chromePath } = findChromePath(version);
  const versionNumber = selectedDir.replace('chrome-', '');
  const cookieFile = path.join(COOKIES_DIR, `chrome${versionNumber}_cookies.json`);

  // 기존 쿠키 로드
  let existingCookies = [];
  let hasExistingCookies = false;

  if (fs.existsSync(cookieFile)) {
    existingCookies = JSON.parse(fs.readFileSync(cookieFile, 'utf-8'));
    hasExistingCookies = existingCookies.length > 0;
  }

  if (verbose) {
    console.log(`Chrome 버전: ${selectedDir}`);
    console.log(`기존 쿠키: ${existingCookies.length}개`);
    console.log(`모드: ${hasExistingCookies ? '리프레시 (Akamai 유지)' : '새로 생성'}`);
    if (proxy) console.log(`프록시: ${proxy}`);
    console.log();
  }

  // 브라우저 실행
  const launchOptions = {
    executablePath: chromePath,
    headless: false
  };

  if (proxy) {
    launchOptions.proxy = { server: proxy };
  }

  const browser = await chromium.launch(launchOptions);
  const context = await browser.newContext();
  const page = await context.newPage();

  // 기존 Akamai 쿠키 주입 (있는 경우)
  if (hasExistingCookies) {
    const akamaiOnly = existingCookies.filter(c => AKAMAI_COOKIES.includes(c.name));
    if (akamaiOnly.length > 0) {
      await context.addCookies(akamaiOnly);
      if (verbose) {
        console.log(`Akamai 쿠키 주입: ${akamaiOnly.length}개`);
        akamaiOnly.forEach(c => console.log(`  - ${c.name}`));
        console.log();
      }
    }
  }

  // 통계
  let blockedCount = 0;
  let allowedCount = 0;
  let totalBytes = 0;

  // 응답 크기 측정
  page.on('response', async response => {
    try {
      const body = await response.body();
      totalBytes += body.length;
    } catch (e) {}
  });

  // 요청 인터셉트
  await page.route('**/*', async (route) => {
    const request = route.request();
    const url = request.url();
    const resourceType = request.resourceType();

    // document는 허용
    if (resourceType === 'document') {
      allowedCount++;
      return route.continue();
    }

    // 리소스 타입 차단
    if (BLOCKED_TYPES.includes(resourceType)) {
      blockedCount++;
      return route.abort();
    }

    // 패턴 차단
    const shouldBlock = BLOCKED_PATTERNS.some(p => url.includes(p));
    if (shouldBlock) {
      blockedCount++;
      return route.abort();
    }

    // Akamai 스크립트만 허용
    if (url.includes('/wmwK3qQug') || url.includes('/akam/')) {
      allowedCount++;
      return route.continue();
    }

    blockedCount++;
    return route.abort();
  });

  // 페이지 로드
  const startTime = Date.now();
  await page.goto('https://login.coupang.com/login/login.pang');
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(2000);
  const loadTime = Date.now() - startTime;

  // 쿠키 추출
  const cookies = await context.cookies();
  const trafficKB = (totalBytes / 1024).toFixed(2);

  // Akamai 쿠키 확인
  const akamaiCookies = cookies.filter(c => AKAMAI_COOKIES.includes(c.name));
  const success = akamaiCookies.length >= 3;

  if (verbose) {
    console.log('='.repeat(60));
    console.log('리프레시 결과');
    console.log('='.repeat(60));
    console.log(`\n허용된 요청: ${allowedCount}`);
    console.log(`차단된 요청: ${blockedCount}`);
    console.log(`총 트래픽: ${trafficKB} KB`);
    console.log(`최종 쿠키 수: ${cookies.length}`);
    console.log(`Akamai 쿠키: ${akamaiCookies.length}개`);
    console.log(`로드 시간: ${loadTime}ms`);
    console.log(`상태: ${success ? '✅ SUCCESS' : '❌ FAILED'}`);
  }

  // 쿠키 저장
  fs.writeFileSync(cookieFile, JSON.stringify(cookies, null, 2));

  if (verbose) {
    console.log(`\n쿠키 저장됨: ${cookieFile}`);
  }

  await browser.close();

  if (verbose) {
    console.log('브라우저 종료됨');
  }

  return {
    success,
    mode: hasExistingCookies ? 'refresh' : 'new',
    cookieFile,
    cookieCount: cookies.length,
    akamaiCount: akamaiCookies.length,
    allowedRequests: allowedCount,
    blockedRequests: blockedCount,
    totalBytes,
    trafficKB: parseFloat(trafficKB),
    loadTime,
    version: versionNumber
  };
}

module.exports = { refreshCookie, findChromePath };

// CLI 실행
if (require.main === module) {
  const args = process.argv.slice(2);
  const version = args[0] || '136';
  const proxy = args[1] || null;

  refreshCookie({ version, proxy })
    .then(result => {
      console.log('\n결과:', JSON.stringify({
        success: result.success,
        mode: result.mode,
        allowedRequests: result.allowedRequests,
        trafficKB: result.trafficKB,
        loadTime: result.loadTime
      }, null, 2));
      process.exit(result.success ? 0 : 1);
    })
    .catch(err => {
      console.error('에러:', err.message);
      process.exit(1);
    });
}
