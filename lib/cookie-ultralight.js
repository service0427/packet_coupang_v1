/**
 * Cookie Ultra-Light Generator
 * Akamai 쿠키 생성에 필요한 최소 요청만 허용
 *
 * 목표: SOCKS5 프록시 환경에서 최소 트래픽으로 쿠키 생성
 */

const { chromium } = require('patchright');
const path = require('path');
const fs = require('fs');

const CHROME_VERSIONS_DIR = path.join(__dirname, '..', 'chrome-versions', 'files');
const COOKIES_DIR = path.join(__dirname, '..', 'cookies');
const USER_DATA_DIR = path.join(__dirname, '..', 'user-data');

// 필수 허용 패턴 (Akamai 관련만)
const ALLOWED_PATTERNS = [
  // 메인 document
  '/login/login.pang',
  // Akamai Bot Manager 스크립트
  '/wmwK3qQug',  // sensor_data 수집 스크립트
  '/akam/',      // Akamai 픽셀/검증
];

// 차단할 패턴 (명시적)
const BLOCKED_PATTERNS = [
  // 불필요한 스크립트
  'qrcode',
  'login.min.js',
  // CDN
  'coupangcdn.com',
  // 추적/분석
  'analytics',
  'tracking',
  'google',
  'facebook',
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
    selectedDir = dirs.find(d => d.includes('136')) || dirs[0];
  }

  const chromePath = path.join(CHROME_VERSIONS_DIR, selectedDir, 'chrome-win64', 'chrome.exe');

  if (!fs.existsSync(chromePath)) {
    throw new Error(`Chrome 실행 파일을 찾을 수 없습니다: ${chromePath}`);
  }

  return { selectedDir, chromePath };
}

/**
 * 초경량 쿠키 생성
 */
async function createUltralightCookie(options = {}) {
  const {
    version = '136',
    outputName = null,
    verbose = true,
    proxy = null,  // SOCKS5 프록시 지원
    reuseProfile = true  // 유저 프로필 재활용 (캐시 활용)
  } = options;

  const { selectedDir, chromePath } = findChromePath(version);
  const versionNumber = selectedDir.replace('chrome-', '');

  if (verbose) {
    console.log(`Chrome 버전: ${selectedDir}`);
    console.log('초경량 모드로 쿠키 생성 시작...');
    if (proxy) console.log(`프록시: ${proxy}`);
    if (reuseProfile) console.log(`프로필 재활용: ${USER_DATA_DIR}`);
    console.log();
  }

  // 유저 데이터 디렉토리 생성
  if (reuseProfile && !fs.existsSync(USER_DATA_DIR)) {
    fs.mkdirSync(USER_DATA_DIR, { recursive: true });
  }

  // 브라우저 옵션
  const launchOptions = {
    executablePath: chromePath,
    headless: false
  };

  // SOCKS5 프록시 설정
  if (proxy) {
    launchOptions.proxy = { server: proxy };
  }

  // 유저 프로필 재활용 (캐시 활용)
  const contextOptions = {};
  if (reuseProfile) {
    // persistentContext 대신 storageState 사용
    const storageFile = path.join(USER_DATA_DIR, 'storage-state.json');
    if (fs.existsSync(storageFile)) {
      contextOptions.storageState = storageFile;
    }
  }

  const browser = await chromium.launch(launchOptions);
  const context = await browser.newContext(contextOptions);
  const page = await context.newPage();

  // 통계
  let blockedCount = 0;
  let allowedCount = 0;
  let totalBytes = 0;
  const allowedUrls = [];
  const blockedUrls = [];

  // 응답 크기 측정
  page.on('response', async response => {
    try {
      const body = await response.body();
      totalBytes += body.length;
    } catch (e) {
      // 일부 응답은 body를 가져올 수 없음
    }
  });

  // 요청 인터셉트 - 최소 허용
  await page.route('**/*', async (route) => {
    const request = route.request();
    const url = request.url();
    const resourceType = request.resourceType();

    // document는 항상 허용
    if (resourceType === 'document') {
      allowedCount++;
      allowedUrls.push(url);
      return route.continue();
    }

    // 이미지, 스타일시트, 폰트, 미디어 차단
    if (['image', 'stylesheet', 'font', 'media'].includes(resourceType)) {
      blockedCount++;
      blockedUrls.push({ url, reason: resourceType });
      return route.abort();
    }

    // 명시적 차단 패턴 확인
    const shouldBlock = BLOCKED_PATTERNS.some(pattern =>
      url.toLowerCase().includes(pattern.toLowerCase())
    );

    if (shouldBlock) {
      blockedCount++;
      blockedUrls.push({ url, reason: 'blocked_pattern' });
      return route.abort();
    }

    // 필수 허용 패턴 확인
    const isAllowed = ALLOWED_PATTERNS.some(pattern => url.includes(pattern));

    if (isAllowed) {
      allowedCount++;
      allowedUrls.push(url);
      return route.continue();
    }

    // 기본: 차단
    blockedCount++;
    blockedUrls.push({ url, reason: 'not_in_allowlist' });
    return route.abort();
  });

  // 페이지 로드
  const startTime = Date.now();
  await page.goto('https://login.coupang.com/login/login.pang');
  await page.waitForLoadState('networkidle');

  // Akamai 스크립트 실행 대기 (sensor_data 생성)
  await page.waitForTimeout(3000);

  const loadTime = Date.now() - startTime;

  // 쿠키 추출
  const cookies = await context.cookies();

  // Akamai 필수 쿠키 확인
  const akamaiCookieNames = ['_abck', 'ak_bmsc', 'bm_s', 'bm_sz'];
  const akamaiCookies = cookies.filter(c => akamaiCookieNames.includes(c.name));
  const success = akamaiCookies.length >= 3;

  // 트래픽 계산
  const trafficKB = (totalBytes / 1024).toFixed(2);

  if (verbose) {
    console.log('='.repeat(60));
    console.log('초경량 결과');
    console.log('='.repeat(60));
    console.log(`\n허용된 요청: ${allowedCount}`);
    console.log(`차단된 요청: ${blockedCount}`);
    console.log(`총 트래픽: ${trafficKB} KB`);
    console.log(`최종 쿠키 수: ${cookies.length}`);
    console.log(`Akamai 필수 쿠키: ${akamaiCookies.length}/4`);
    console.log(`로드 시간: ${loadTime}ms`);
    console.log(`상태: ${success ? '✅ SUCCESS' : '❌ FAILED'}`);

    console.log('\n허용된 요청:');
    allowedUrls.forEach((url, i) => {
      const shortUrl = url.length > 80 ? url.substring(0, 80) + '...' : url;
      console.log(`  ${i + 1}. ${shortUrl}`);
    });

    console.log('\nAkamai 쿠키:');
    akamaiCookies.forEach(c => {
      console.log(`  - ${c.name}: ${c.value.substring(0, 30)}...`);
    });
  }

  // 쿠키 저장
  const fileName = outputName || `chrome${versionNumber}_cookies.json`;
  const cookieFile = path.join(COOKIES_DIR, fileName);
  fs.writeFileSync(cookieFile, JSON.stringify(cookies, null, 2));

  // storageState 저장 (프로필 재활용용)
  if (reuseProfile) {
    const storageFile = path.join(USER_DATA_DIR, 'storage-state.json');
    await context.storageState({ path: storageFile });
  }

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
    totalBytes,
    trafficKB: parseFloat(trafficKB),
    loadTime,
    version: versionNumber,
    allowedUrls,
    akamaiCookies: akamaiCookies.map(c => c.name)
  };
}

module.exports = {
  createUltralightCookie,
  findChromePath,
  ALLOWED_PATTERNS,
  BLOCKED_PATTERNS
};

// CLI 실행
if (require.main === module) {
  const args = process.argv.slice(2);
  const version = args[0] || '136';
  const proxy = args[1] || null;  // 예: socks5://127.0.0.1:1080

  createUltralightCookie({ version, proxy })
    .then(result => {
      console.log('\n결과:', JSON.stringify({
        success: result.success,
        allowedRequests: result.allowedRequests,
        blockedRequests: result.blockedRequests,
        trafficKB: result.trafficKB,
        akamaiCookies: result.akamaiCookies,
        loadTime: result.loadTime
      }, null, 2));
      process.exit(result.success ? 0 : 1);
    })
    .catch(err => {
      console.error('에러:', err.message);
      process.exit(1);
    });
}
