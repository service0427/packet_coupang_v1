/**
 * 로그인 페이지 네트워크 분석
 * 쿠키 생성에 필요한 요청만 찾기
 */

const { chromium } = require('patchright');
const path = require('path');
const fs = require('fs');

const CHROME_VERSIONS_DIR = path.join(__dirname, 'chrome-versions', 'files');

async function analyzeNetwork() {
  // Chrome 버전 선택
  const dirs = fs.readdirSync(CHROME_VERSIONS_DIR).filter(d =>
    fs.statSync(path.join(CHROME_VERSIONS_DIR, d)).isDirectory()
  );

  if (dirs.length === 0) {
    console.error('Chrome 버전을 찾을 수 없습니다.');
    return;
  }

  // Chrome 136 사용 (안정적인 버전)
  const selectedDir = dirs.find(d => d.includes('136')) || dirs[0];
  const chromePath = path.join(CHROME_VERSIONS_DIR, selectedDir, 'chrome-win64', 'chrome.exe');

  console.log(`Chrome 버전: ${selectedDir}`);
  console.log('네트워크 트래픽 분석 시작...\n');

  const browser = await chromium.launch({
    executablePath: chromePath,
    headless: false
  });
  const context = await browser.newContext();
  const page = await context.newPage();

  // 네트워크 요청 수집
  const requests = [];
  const responses = [];
  const cookieSetters = [];

  // 요청 이벤트
  page.on('request', request => {
    requests.push({
      url: request.url(),
      method: request.method(),
      resourceType: request.resourceType(),
      headers: request.headers()
    });
  });

  // 응답 이벤트 - Set-Cookie 헤더 확인
  page.on('response', async response => {
    const url = response.url();
    const headers = response.headers();
    const setCookie = headers['set-cookie'];

    responses.push({
      url,
      status: response.status(),
      setCookie: setCookie ? true : false
    });

    if (setCookie) {
      cookieSetters.push({
        url,
        cookies: setCookie
      });
    }
  });

  // 페이지 로드
  const startTime = Date.now();
  await page.goto('https://login.coupang.com/login/login.pang');
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(3000);
  const loadTime = Date.now() - startTime;

  // 쿠키 확인
  const cookies = await context.cookies();

  // 분석 결과 출력
  console.log('='.repeat(60));
  console.log('네트워크 분석 결과');
  console.log('='.repeat(60));

  console.log(`\n총 요청 수: ${requests.length}`);
  console.log(`총 응답 수: ${responses.length}`);
  console.log(`쿠키 설정 응답 수: ${cookieSetters.length}`);
  console.log(`최종 쿠키 수: ${cookies.length}`);
  console.log(`로드 시간: ${loadTime}ms`);

  // 리소스 타입별 분류
  const byType = {};
  requests.forEach(r => {
    byType[r.resourceType] = (byType[r.resourceType] || 0) + 1;
  });

  console.log('\n리소스 타입별 요청 수:');
  Object.entries(byType).sort((a, b) => b[1] - a[1]).forEach(([type, count]) => {
    console.log(`  ${type}: ${count}`);
  });

  // 도메인별 분류
  const byDomain = {};
  requests.forEach(r => {
    try {
      const domain = new URL(r.url).hostname;
      byDomain[domain] = (byDomain[domain] || 0) + 1;
    } catch (e) {}
  });

  console.log('\n도메인별 요청 수:');
  Object.entries(byDomain).sort((a, b) => b[1] - a[1]).forEach(([domain, count]) => {
    console.log(`  ${domain}: ${count}`);
  });

  // 쿠키를 설정하는 URL 출력
  console.log('\n='.repeat(60));
  console.log('쿠키를 설정하는 URL (Set-Cookie 헤더):');
  console.log('='.repeat(60));

  cookieSetters.forEach((setter, i) => {
    console.log(`\n${i + 1}. ${setter.url}`);
    if (typeof setter.cookies === 'string') {
      // 쿠키 이름만 추출
      const cookieNames = setter.cookies.split(',').map(c => {
        const match = c.trim().match(/^([^=]+)=/);
        return match ? match[1] : c.split('=')[0];
      });
      console.log(`   쿠키: ${cookieNames.join(', ')}`);
    }
  });

  // 최종 쿠키 목록
  console.log('\n='.repeat(60));
  console.log('최종 쿠키 목록:');
  console.log('='.repeat(60));

  cookies.forEach(cookie => {
    console.log(`  ${cookie.name} (${cookie.domain})`);
  });

  // 차단 가능한 리소스 타입
  console.log('\n='.repeat(60));
  console.log('차단 권장 리소스:');
  console.log('='.repeat(60));

  const blockable = ['image', 'stylesheet', 'font', 'media'];
  blockable.forEach(type => {
    if (byType[type]) {
      console.log(`  ${type}: ${byType[type]}개 요청 차단 가능`);
    }
  });

  // 결과 파일 저장
  const analysisResult = {
    timestamp: new Date().toISOString(),
    totalRequests: requests.length,
    totalResponses: responses.length,
    cookieSetterCount: cookieSetters.length,
    finalCookieCount: cookies.length,
    loadTime,
    byResourceType: byType,
    byDomain,
    cookieSetters: cookieSetters.map(s => ({
      url: s.url,
      cookies: typeof s.cookies === 'string' ? s.cookies.substring(0, 500) : s.cookies
    })),
    finalCookies: cookies.map(c => ({
      name: c.name,
      domain: c.domain,
      path: c.path
    }))
  };

  const resultFile = path.join(__dirname, 'network-analysis.json');
  fs.writeFileSync(resultFile, JSON.stringify(analysisResult, null, 2));
  console.log(`\n분석 결과 저장: ${resultFile}`);

  await browser.close();
  console.log('\n브라우저 종료됨');
}

analyzeNetwork().catch(console.error);
