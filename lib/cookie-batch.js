/**
 * Cookie Batch Generator
 * 한 번의 브라우저 세션에서 여러 개의 독립적인 쿠키 생성
 *
 * 방식: 브라우저 실행 → 쿠키 생성 → 쿠키 삭제 → 새로고침 → 반복
 * 장점: 브라우저 재시작 오버헤드 없이 다수의 쿠키 생성
 */

const { chromium } = require('patchright');
const path = require('path');
const fs = require('fs');

const CHROME_VERSIONS_DIR = path.join(__dirname, '..', 'chrome-versions', 'files');
const COOKIES_DIR = path.join(__dirname, '..', 'cookies');

// 필수 허용 패턴 (Akamai 관련만)
const ALLOWED_PATTERNS = [
  '/login/login.pang',
  '/wmwK3qQug',
  '/akam/',
];

// 차단할 패턴
const BLOCKED_PATTERNS = [
  'qrcode',
  'login.min.js',
  'coupangcdn.com',
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

  let selectedDir = dirs.find(d => d.includes(version)) ||
                    dirs.find(d => d.includes('136')) ||
                    dirs[0];

  const chromePath = path.join(CHROME_VERSIONS_DIR, selectedDir, 'chrome-win64', 'chrome.exe');
  if (!fs.existsSync(chromePath)) {
    throw new Error(`Chrome 실행 파일 없음: ${chromePath}`);
  }

  return { selectedDir, chromePath };
}

/**
 * 배치 쿠키 생성
 * @param {Object} options
 * @param {string} options.version - Chrome 버전
 * @param {number} options.count - 생성할 쿠키 개수
 * @param {string} options.proxy - SOCKS5 프록시
 * @param {boolean} options.verbose - 상세 출력
 */
async function createBatchCookies(options = {}) {
  const {
    version = '136',
    count = 3,
    proxy = null,
    verbose = true
  } = options;

  const { selectedDir, chromePath } = findChromePath(version);
  const versionNumber = selectedDir.replace('chrome-', '');

  if (verbose) {
    console.log(`Chrome 버전: ${selectedDir}`);
    console.log(`생성할 쿠키: ${count}개`);
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

  // 통계
  let totalBytes = 0;
  const results = [];

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

    // document 허용
    if (resourceType === 'document') {
      return route.continue();
    }

    // 리소스 타입 차단
    if (['image', 'stylesheet', 'font', 'media'].includes(resourceType)) {
      return route.abort();
    }

    // 패턴 차단
    const shouldBlock = BLOCKED_PATTERNS.some(p => url.toLowerCase().includes(p.toLowerCase()));
    if (shouldBlock) {
      return route.abort();
    }

    // 허용 패턴
    const isAllowed = ALLOWED_PATTERNS.some(p => url.includes(p));
    if (isAllowed) {
      return route.continue();
    }

    return route.abort();
  });

  // 배치 생성 루프
  for (let i = 1; i <= count; i++) {
    const startTime = Date.now();

    if (verbose) {
      console.log(`\n[${'='.repeat(20)} 쿠키 #${i} ${'='.repeat(20)}]`);
    }

    // 첫 번째가 아니면 쿠키 삭제 후 새로고침
    if (i > 1) {
      // 모든 쿠키 삭제
      const currentCookies = await context.cookies();
      if (currentCookies.length > 0) {
        await context.clearCookies();
        if (verbose) {
          console.log(`이전 쿠키 ${currentCookies.length}개 삭제됨`);
        }
      }

      // 새로고침
      await page.reload();
      await page.waitForLoadState('networkidle');
    } else {
      // 첫 번째는 페이지 로드
      await page.goto('https://login.coupang.com/login/login.pang');
      await page.waitForLoadState('networkidle');
    }

    // Akamai 스크립트 실행 대기
    await page.waitForTimeout(3000);

    const loadTime = Date.now() - startTime;

    // 쿠키 추출
    const cookies = await context.cookies();

    // Akamai 쿠키 확인
    const akamaiCookieNames = ['_abck', 'ak_bmsc', 'bm_s', 'bm_sz'];
    const akamaiCookies = cookies.filter(c => akamaiCookieNames.includes(c.name));
    const success = akamaiCookies.length >= 3;

    // 쿠키 저장
    const fileName = `batch_${i}_chrome${versionNumber}_cookies.json`;
    const cookieFile = path.join(COOKIES_DIR, fileName);
    fs.writeFileSync(cookieFile, JSON.stringify(cookies, null, 2));

    const result = {
      index: i,
      success,
      cookieFile,
      cookieCount: cookies.length,
      akamaiCount: akamaiCookies.length,
      loadTime,
      // 주요 쿠키 값 (비교용)
      abck: akamaiCookies.find(c => c.name === '_abck')?.value.substring(0, 50) || 'N/A'
    };
    results.push(result);

    if (verbose) {
      console.log(`쿠키 수: ${cookies.length}`);
      console.log(`Akamai 쿠키: ${akamaiCookies.length}/4`);
      console.log(`로드 시간: ${loadTime}ms`);
      console.log(`상태: ${success ? '✅ SUCCESS' : '❌ FAILED'}`);
      console.log(`저장: ${fileName}`);
      console.log(`_abck: ${result.abck}...`);
    }
  }

  await browser.close();

  // 총 트래픽
  const trafficKB = (totalBytes / 1024).toFixed(2);

  if (verbose) {
    console.log('\n' + '='.repeat(60));
    console.log('배치 생성 완료');
    console.log('='.repeat(60));
    console.log(`\n총 쿠키: ${results.length}개`);
    console.log(`성공: ${results.filter(r => r.success).length}개`);
    console.log(`총 트래픽: ${trafficKB} KB`);
    console.log(`평균 트래픽: ${(totalBytes / 1024 / count).toFixed(2)} KB/쿠키`);

    // _abck 값 비교 (서로 다른지 확인)
    console.log('\n_abck 값 비교 (처음 50자):');
    results.forEach(r => {
      console.log(`  #${r.index}: ${r.abck}...`);
    });

    const uniqueAbck = new Set(results.map(r => r.abck)).size;
    console.log(`\n고유한 _abck 값: ${uniqueAbck}/${results.length}`);
    if (uniqueAbck === results.length) {
      console.log('✅ 모든 쿠키가 서로 다릅니다!');
    } else {
      console.log('⚠️ 일부 쿠키가 중복됩니다.');
    }
  }

  return {
    results,
    totalBytes,
    trafficKB: parseFloat(trafficKB),
    averageTrafficKB: parseFloat((totalBytes / 1024 / count).toFixed(2)),
    successCount: results.filter(r => r.success).length,
    version: versionNumber
  };
}

/**
 * curl-cffi로 쿠키 테스트
 */
async function testCookieWithCffi(cookieFile, version, query = '노트북') {
  const { spawn } = require('child_process');
  const pythonScript = path.join(__dirname, 'curl_cffi_client.py');

  return new Promise((resolve, reject) => {
    // 임시로 쿠키 파일을 표준 위치에 복사
    const standardCookieFile = path.join(COOKIES_DIR, `chrome${version}_cookies.json`);
    const originalContent = fs.existsSync(standardCookieFile)
      ? fs.readFileSync(standardCookieFile, 'utf-8')
      : null;

    // 테스트할 쿠키를 표준 위치에 복사
    fs.copyFileSync(cookieFile, standardCookieFile);

    const python = spawn('python', [pythonScript, version, query]);
    let stdout = '';

    python.stdout.on('data', (data) => {
      stdout += data.toString();
    });

    python.stderr.on('data', (data) => {
      // stderr 무시
    });

    python.on('close', (code) => {
      // 원래 쿠키 복원
      if (originalContent) {
        fs.writeFileSync(standardCookieFile, originalContent);
      }

      // 결과 파싱
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
      }

      resolve(results);
    });

    python.on('error', reject);
  });
}

/**
 * 배치 쿠키 생성 + 테스트
 */
async function createAndTestBatchCookies(options = {}) {
  const {
    version = '136',
    count = 3,
    proxy = null,
    verbose = true,
    testPages = 1,  // 각 쿠키당 테스트할 페이지 수
    query = '노트북'
  } = options;

  // 먼저 쿠키 생성
  const batchResult = await createBatchCookies({ version, count, proxy, verbose });

  if (verbose) {
    console.log('\n' + '='.repeat(60));
    console.log('curl-cffi 테스트 시작');
    console.log('='.repeat(60));
  }

  // 각 쿠키 테스트
  const testResults = [];

  for (const cookieResult of batchResult.results) {
    if (verbose) {
      console.log(`\n[쿠키 #${cookieResult.index} 테스트]`);
    }

    try {
      const cffiResults = await testCookieWithCffi(
        cookieResult.cookieFile,
        batchResult.version,
        query
      );

      const successCount = cffiResults.filter(r => r.result === 'SUCCESS').length;
      const success = successCount > 0;

      testResults.push({
        index: cookieResult.index,
        cookieFile: cookieResult.cookieFile,
        cffiResults,
        success,
        successCount,
        totalPages: cffiResults.length
      });

      if (verbose) {
        cffiResults.forEach(r => {
          const status = r.result === 'SUCCESS' ? '✅' : '❌';
          console.log(`  Page ${r.page}: ${status} ${r.size.toLocaleString()} bytes`);
        });
      }
    } catch (err) {
      testResults.push({
        index: cookieResult.index,
        cookieFile: cookieResult.cookieFile,
        error: err.message,
        success: false
      });

      if (verbose) {
        console.log(`  ❌ 에러: ${err.message}`);
      }
    }
  }

  // 최종 결과
  const totalSuccess = testResults.filter(r => r.success).length;

  if (verbose) {
    console.log('\n' + '='.repeat(60));
    console.log('최종 테스트 결과');
    console.log('='.repeat(60));
    console.log(`\n쿠키 생성: ${batchResult.results.length}개`);
    console.log(`테스트 성공: ${totalSuccess}/${testResults.length}개`);
    console.log(`총 트래픽: ${batchResult.trafficKB} KB`);

    console.log('\n개별 결과:');
    testResults.forEach(r => {
      const status = r.success ? '✅' : '❌';
      if (r.cffiResults) {
        const sizes = r.cffiResults.map(cr => cr.size).join(', ');
        console.log(`  #${r.index}: ${status} (${sizes} bytes)`);
      } else {
        console.log(`  #${r.index}: ${status} (${r.error})`);
      }
    });
  }

  return {
    batchResult,
    testResults,
    totalSuccess,
    totalCount: testResults.length
  };
}

module.exports = { createBatchCookies, createAndTestBatchCookies, testCookieWithCffi, findChromePath };

// CLI 실행
if (require.main === module) {
  const args = process.argv.slice(2);
  const withTest = args.includes('--test');

  // --test 플래그 제거 후 파싱
  const filteredArgs = args.filter(a => a !== '--test');
  const count = parseInt(filteredArgs[0]) || 3;
  const version = filteredArgs[1] || '136';
  const proxy = filteredArgs[2] || null;

  console.log('Cookie Batch Generator');
  console.log('='.repeat(60));

  if (withTest) {
    createAndTestBatchCookies({ count, version, proxy })
      .then(result => {
        console.log('\n최종 결과:', JSON.stringify({
          cookieCount: result.totalCount,
          testSuccess: result.totalSuccess,
          trafficKB: result.batchResult.trafficKB
        }, null, 2));
        process.exit(result.totalSuccess === result.totalCount ? 0 : 1);
      })
      .catch(err => {
        console.error('에러:', err.message);
        process.exit(1);
      });
  } else {
    createBatchCookies({ count, version, proxy })
      .then(result => {
        console.log('\n최종 결과:', JSON.stringify({
          successCount: result.successCount,
          totalCount: result.results.length,
          trafficKB: result.trafficKB,
          averageTrafficKB: result.averageTrafficKB
        }, null, 2));
        process.exit(result.successCount === result.results.length ? 0 : 1);
      })
      .catch(err => {
        console.error('에러:', err.message);
        process.exit(1);
      });
  }
}
