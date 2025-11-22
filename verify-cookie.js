/**
 * Cookie Verifier
 * 경량화 쿠키 생성 후 curl-cffi로 실제 작동 검증
 */

const { createOptimizedCookie } = require('./lib/cookie-optimizer');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

const TLS_DIR = path.join(__dirname, 'chrome-versions', 'tls');
const COOKIES_DIR = path.join(__dirname, 'cookies');

/**
 * curl-cffi로 쿠키 테스트
 */
function testWithCurlCffi(version, query = '노트북') {
  return new Promise((resolve, reject) => {
    const pythonScript = path.join(__dirname, 'lib', 'curl_cffi_client.py');
    const tlsProfile = path.join(TLS_DIR, `${version}.json`);
    const cookieFile = path.join(COOKIES_DIR, `chrome${version}_cookies.json`);

    if (!fs.existsSync(tlsProfile)) {
      return reject(new Error(`TLS 프로파일을 찾을 수 없습니다: ${tlsProfile}`));
    }

    if (!fs.existsSync(cookieFile)) {
      return reject(new Error(`쿠키 파일을 찾을 수 없습니다: ${cookieFile}`));
    }

    // curl_cffi_client.py는 단순히 버전과 검색어만 받음
    const args = [pythonScript, version, query];

    const python = spawn('python', args);
    let stdout = '';
    let stderr = '';

    python.stdout.on('data', (data) => {
      stdout += data.toString();
      // 실시간 출력
      process.stdout.write(data);
    });

    python.stderr.on('data', (data) => {
      stderr += data.toString();
    });

    python.on('close', (code) => {
      // 마지막 줄에서 Result 파싱
      const lines = stdout.trim().split('\n');
      const results = [];

      for (const line of lines) {
        // Page 1: 200 | 1,423,708 bytes | SUCCESS
        const match = line.match(/Page (\d+): (\d+) \| ([\d,]+) bytes \| (\w+)/);
        if (match) {
          results.push({
            page: parseInt(match[1]),
            status_code: parseInt(match[2]),
            size: parseInt(match[3].replace(/,/g, '')),
            result: match[4]
          });
        }
        // Page 1: ERROR - ...
        const errorMatch = line.match(/Page (\d+): ERROR - (.+)/);
        if (errorMatch) {
          results.push({
            page: parseInt(errorMatch[1]),
            error: errorMatch[2],
            result: 'ERROR'
          });
        }
      }

      if (results.length > 0) {
        resolve(results);
      } else {
        reject(new Error(`결과 파싱 실패: ${stdout}`));
      }
    });

    python.on('error', (err) => {
      reject(err);
    });
  });
}

/**
 * 메인 검증 프로세스
 */
async function verify(version = '136') {
  console.log('='.repeat(60));
  console.log('Cookie Optimizer + Verifier');
  console.log('='.repeat(60));
  console.log(`\n[1/2] 경량화 쿠키 생성 중...`);

  // 1. 경량화 쿠키 생성
  const optimizeResult = await createOptimizedCookie({
    version,
    verbose: true
  });

  if (!optimizeResult.success) {
    console.log('\n❌ 쿠키 생성 실패 - Akamai 쿠키 부족');
    return {
      success: false,
      phase: 'optimize',
      ...optimizeResult
    };
  }

  console.log('\n[2/2] curl-cffi로 검증 중...');

  // 2. curl-cffi로 테스트
  try {
    const testResults = await testWithCurlCffi(optimizeResult.version);

    const successCount = testResults.filter(r => r.result === 'SUCCESS').length;
    const totalCount = testResults.length;
    const allSuccess = successCount === totalCount;

    console.log('\n='.repeat(60));
    console.log('검증 결과');
    console.log('='.repeat(60));

    testResults.forEach(r => {
      if (r.result === 'SUCCESS') {
        console.log(`  Page ${r.page}: ✅ ${r.size.toLocaleString()} bytes`);
      } else {
        console.log(`  Page ${r.page}: ❌ ${r.error || 'BLOCKED'}`);
      }
    });

    console.log(`\n결과: ${successCount}/${totalCount} 성공`);
    console.log(`상태: ${allSuccess ? '✅ VERIFIED' : '❌ FAILED'}`);

    // 요약
    console.log('\n='.repeat(60));
    console.log('요약');
    console.log('='.repeat(60));
    console.log(`  차단된 요청: ${optimizeResult.blockedRequests}개`);
    console.log(`  허용된 요청: ${optimizeResult.allowedRequests}개`);
    console.log(`  쿠키 개수: ${optimizeResult.cookieCount}개`);
    console.log(`  Akamai 쿠키: ${optimizeResult.akamaiCount}개`);
    console.log(`  로드 시간: ${optimizeResult.loadTime}ms`);
    console.log(`  검증 결과: ${allSuccess ? 'PASS' : 'FAIL'}`);

    return {
      success: allSuccess,
      phase: 'verify',
      optimize: optimizeResult,
      test: {
        successCount,
        totalCount,
        results: testResults
      }
    };

  } catch (err) {
    console.log(`\n❌ 테스트 실패: ${err.message}`);
    return {
      success: false,
      phase: 'test',
      error: err.message,
      optimize: optimizeResult
    };
  }
}

// CLI 실행
if (require.main === module) {
  const args = process.argv.slice(2);
  const version = args[0] || '136';

  verify(version)
    .then(result => {
      process.exit(result.success ? 0 : 1);
    })
    .catch(err => {
      console.error('에러:', err.message);
      process.exit(1);
    });
}

module.exports = { verify, testWithCurlCffi };
