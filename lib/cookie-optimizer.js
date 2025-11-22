/**
 * Cookie Optimizer
 * 불필요한 리소스 차단으로 트래픽 최소화하면서 쿠키 생성
 */

const { chromium } = require('patchright');
const path = require('path');
const fs = require('fs');

const CHROME_VERSIONS_DIR = path.join(__dirname, '..', 'chrome-versions', 'files');
const COOKIES_DIR = path.join(__dirname, '..', 'cookies');

// 차단할 도메인 패턴
const BLOCKED_DOMAINS = [
  'asset2.coupangcdn.com',
  'static.coupangcdn.com',
  'img1a.coupangcdn.com',
  'front.coupangcdn.com',
  'ads.coupang.com',
  'analytics.',
  'tracking.',
  'googletagmanager.com',
  'google-analytics.com',
  'facebook.',
  'doubleclick.'
];

// 차단할 리소스 타입
const BLOCKED_TYPES = [
  'image',
  'stylesheet',
  'font',
  'media'
];

/**
 * Chrome 실행 파일 경로 찾기
 */
function findChromePath(version) {
  const dirs = fs.readdirSync(CHROME_VERSIONS_DIR).filter(d =>
    fs.statSync(path.join(CHROME_VERSIONS_DIR, d)).isDirectory()
  );

  if (dirs.length === 0) {
    throw new Error('Chrome 버전을 찾을 수 없습니다.');
  }

  let selectedDir;
  if (version) {
    selectedDir = dirs.find(d => d.includes(version));
    if (!selectedDir) {
      throw new Error(`Chrome ${version} 버전을 찾을 수 없습니다.`);
    }
  } else {
    // 기본값: 136
    selectedDir = dirs.find(d => d.includes('136')) || dirs[0];
  }

  const chromePath = path.join(CHROME_VERSIONS_DIR, selectedDir, 'chrome-win64', 'chrome.exe');

  if (!fs.existsSync(chromePath)) {
    throw new Error(`Chrome 실행 파일을 찾을 수 없습니다: ${chromePath}`);
  }

  return { selectedDir, chromePath };
}

/**
 * 경량화 쿠키 생성
 */
async function createOptimizedCookie(options = {}) {
  const {
    version = '136',
    outputName = null,
    verbose = true
  } = options;

  const { selectedDir, chromePath } = findChromePath(version);
  const versionNumber = selectedDir.replace('chrome-', '');

  if (verbose) {
    console.log(`Chrome 버전: ${selectedDir}`);
    console.log('경량화 모드로 쿠키 생성 시작...\n');
  }

  const browser = await chromium.launch({
    executablePath: chromePath,
    // ============================================================
    // 헤드리스 모드 사용 절대 금지 - Akamai Bot Manager가 탐지함
    // ============================================================
    headless: false
  });
  const context = await browser.newContext();
  const page = await context.newPage();

  // 통계
  let blockedCount = 0;
  let allowedCount = 0;

  // 요청 인터셉트
  await page.route('**/*', async (route) => {
    const request = route.request();
    const url = request.url();
    const resourceType = request.resourceType();

    // 리소스 타입 차단
    if (BLOCKED_TYPES.includes(resourceType)) {
      blockedCount++;
      return route.abort();
    }

    // 도메인 차단
    const shouldBlock = BLOCKED_DOMAINS.some(domain => url.includes(domain));
    if (shouldBlock) {
      blockedCount++;
      return route.abort();
    }

    // 허용
    allowedCount++;
    return route.continue();
  });

  // 페이지 로드
  const startTime = Date.now();
  await page.goto('https://login.coupang.com/login/login.pang');
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(3000);
  const loadTime = Date.now() - startTime;

  // 쿠키 추출
  const cookies = await context.cookies();

  // Akamai 쿠키 확인
  const akamaiCookies = cookies.filter(c =>
    ['_abck', 'ak_bmsc', 'bm_s', 'bm_ss', 'bm_so', 'bm_sz', 'bm_lso'].includes(c.name)
  );

  const success = akamaiCookies.length >= 5;

  if (verbose) {
    console.log('='.repeat(60));
    console.log('경량화 결과');
    console.log('='.repeat(60));
    console.log(`\n허용된 요청: ${allowedCount}`);
    console.log(`차단된 요청: ${blockedCount}`);
    console.log(`최종 쿠키 수: ${cookies.length}`);
    console.log(`Akamai 쿠키: ${akamaiCookies.length}개`);
    console.log(`로드 시간: ${loadTime}ms`);
    console.log(`상태: ${success ? '✅ SUCCESS' : '❌ FAILED'}`);
  }

  // 쿠키 저장
  const fileName = outputName || `chrome${versionNumber}_cookies.json`;
  const cookieFile = path.join(COOKIES_DIR, fileName);
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
    cookieFile,
    cookieCount: cookies.length,
    akamaiCount: akamaiCookies.length,
    allowedRequests: allowedCount,
    blockedRequests: blockedCount,
    loadTime,
    version: versionNumber
  };
}

module.exports = {
  createOptimizedCookie,
  findChromePath,
  BLOCKED_DOMAINS,
  BLOCKED_TYPES
};

// CLI 실행
if (require.main === module) {
  const args = process.argv.slice(2);
  const version = args[0] || '136';

  createOptimizedCookie({ version })
    .then(result => {
      console.log('\n결과:', JSON.stringify(result, null, 2));
      process.exit(result.success ? 0 : 1);
    })
    .catch(err => {
      console.error('에러:', err.message);
      process.exit(1);
    });
}
