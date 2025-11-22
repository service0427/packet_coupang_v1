/**
 * 경량화된 쿠키 생성기
 * 불필요한 리소스 차단으로 트래픽 최소화
 */

const { chromium } = require('patchright');
const path = require('path');
const fs = require('fs');

const CHROME_VERSIONS_DIR = path.join(__dirname, 'chrome-versions', 'files');
const COOKIES_DIR = path.join(__dirname, 'cookies');

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

async function createLightweightCookie() {
  // Chrome 136 선택
  const dirs = fs.readdirSync(CHROME_VERSIONS_DIR).filter(d =>
    fs.statSync(path.join(CHROME_VERSIONS_DIR, d)).isDirectory()
  );

  const selectedDir = dirs.find(d => d.includes('136')) || dirs[0];
  const chromePath = path.join(CHROME_VERSIONS_DIR, selectedDir, 'chrome-win64', 'chrome.exe');

  console.log(`Chrome 버전: ${selectedDir}`);
  console.log('경량화 모드로 쿠키 생성 시작...\n');

  const browser = await chromium.launch({
    executablePath: chromePath,
    headless: false
  });
  const context = await browser.newContext();
  const page = await context.newPage();

  // 통계
  let blockedCount = 0;
  let allowedCount = 0;
  const blockedUrls = [];
  const allowedUrls = [];

  // 요청 인터셉트
  await page.route('**/*', async (route) => {
    const request = route.request();
    const url = request.url();
    const resourceType = request.resourceType();

    // 리소스 타입 차단
    if (BLOCKED_TYPES.includes(resourceType)) {
      blockedCount++;
      blockedUrls.push({ url: url.substring(0, 80), reason: `type:${resourceType}` });
      return route.abort();
    }

    // 도메인 차단
    const shouldBlock = BLOCKED_DOMAINS.some(domain => url.includes(domain));
    if (shouldBlock) {
      blockedCount++;
      blockedUrls.push({ url: url.substring(0, 80), reason: 'domain' });
      return route.abort();
    }

    // 허용
    allowedCount++;
    allowedUrls.push(url.substring(0, 100));
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

  // 결과 출력
  console.log('='.repeat(60));
  console.log('경량화 결과');
  console.log('='.repeat(60));
  console.log(`\n허용된 요청: ${allowedCount}`);
  console.log(`차단된 요청: ${blockedCount}`);
  console.log(`총 요청: ${allowedCount + blockedCount}`);
  console.log(`최종 쿠키 수: ${cookies.length}`);
  console.log(`로드 시간: ${loadTime}ms`);

  // 허용된 요청 목록
  console.log('\n허용된 요청:');
  allowedUrls.forEach((url, i) => {
    console.log(`  ${i + 1}. ${url}`);
  });

  // Akamai 쿠키 확인
  const akamaiCookies = cookies.filter(c =>
    ['_abck', 'ak_bmsc', 'bm_s', 'bm_ss', 'bm_so', 'bm_sz', 'bm_lso'].includes(c.name)
  );

  console.log('\n='.repeat(60));
  console.log('Akamai 쿠키 상태:');
  console.log('='.repeat(60));

  if (akamaiCookies.length >= 5) {
    console.log(`✅ Akamai 쿠키 생성 성공: ${akamaiCookies.length}개`);
    akamaiCookies.forEach(c => {
      console.log(`  - ${c.name}: ${c.value.substring(0, 30)}...`);
    });
  } else {
    console.log(`❌ Akamai 쿠키 부족: ${akamaiCookies.length}개`);
  }

  // 전체 쿠키 목록
  console.log('\n전체 쿠키:');
  cookies.forEach(c => {
    console.log(`  ${c.name} (${c.domain})`);
  });

  // 쿠키 저장
  const cookieFile = path.join(COOKIES_DIR, 'lightweight_cookies.json');
  fs.writeFileSync(cookieFile, JSON.stringify(cookies, null, 2));
  console.log(`\n쿠키 저장됨: ${cookieFile}`);

  await browser.close();
  console.log('브라우저 종료됨');

  return {
    success: akamaiCookies.length >= 5,
    cookieCount: cookies.length,
    akamaiCount: akamaiCookies.length,
    allowedRequests: allowedCount,
    blockedRequests: blockedCount,
    loadTime
  };
}

createLightweightCookie().catch(console.error);
