/**
 * Browser Launcher Module
 *
 * Patchright 브라우저 실행을 위한 기본 모듈
 * - 트레이싱 없음 (자동완성 문제 방지)
 * - 최소한의 args만 사용
 */

const { chromium } = require('patchright');

/**
 * 브라우저 실행
 * @param {Object} options
 * @param {string} options.executablePath - Chrome 실행 파일 경로
 * @param {boolean} [options.headless=false] - 헤드리스 모드
 * @param {string} [options.proxy=null] - 프록시 서버 (예: 'socks5://ip:port')
 * @returns {Promise<{browser: Browser, context: BrowserContext, page: Page}>}
 */
async function launch(options = {}) {
  const { executablePath, headless = false, proxy = null } = options;

  if (!executablePath) {
    throw new Error('executablePath is required');
  }

  const browser = await chromium.launch({
    executablePath,
    headless,
    args: [
      '--disable-blink-features=AutomationControlled',
      '--no-first-run'
    ]
  });

  const contextOptions = {
    locale: 'ko-KR',
    timezoneId: 'Asia/Seoul'
  };

  if (proxy) {
    contextOptions.proxy = { server: proxy };
  }

  const context = await browser.newContext(contextOptions);

  const page = await context.newPage();

  return { browser, context, page };
}

/**
 * 기본 Chromium으로 브라우저 실행 (executablePath 없이)
 * @param {Object} options
 * @param {boolean} [options.headless=false] - 헤드리스 모드
 * @returns {Promise<{browser: Browser, context: BrowserContext, page: Page}>}
 */
async function launchDefault(options = {}) {
  const { headless = false } = options;

  const browser = await chromium.launch({
    headless,
    args: [
      '--disable-blink-features=AutomationControlled',
      '--no-first-run'
    ]
  });

  const context = await browser.newContext({
    locale: 'ko-KR',
    timezoneId: 'Asia/Seoul'
  });

  const page = await context.newPage();

  return { browser, context, page };
}

module.exports = {
  launch,
  launchDefault
};
