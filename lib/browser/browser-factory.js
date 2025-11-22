/**
 * Browser Factory - 안전한 브라우저 초기화
 *
 * ⚠️ 경고: 브라우저 설정은 절대 수정 금지!
 * - 반드시 Chromium만 사용 (Firefox, Safari 금지)
 * - 반드시 시크릿 모드 (Incognito Context)
 * - args는 정확히 2개만 허용:
 *   1. --disable-blink-features=AutomationControlled
 *   2. --no-first-run
 *
 * 다른 설정 추가 시 Akamai 탐지됨!
 */

const { chromium } = require('playwright');

class BrowserFactory {
  /**
   * 안전한 브라우저 생성 (설정 고정)
   * @param {Object} options - headless, executablePath, proxy 허용
   * @param {boolean} options.headless - true/false만 가능 (기본: false)
   * @param {string} options.executablePath - Chrome 실행 파일 경로 (선택)
   * @param {Object} options.proxy - 프록시 설정 (선택) { server: 'socks5://host:port' }
   * @returns {Object} { browser, context, page }
   */
  static async createBrowser(options = {}) {
    const headless = options.headless !== undefined ? options.headless : false;
    const executablePath = options.executablePath;
    const proxy = options.proxy;

    if (executablePath) {
      console.log(`[BrowserFactory] Creating Chrome browser (executablePath, headless=${headless})...`);
      console.log(`[BrowserFactory] Path: ${executablePath}`);
    } else {
      console.log(`[BrowserFactory] Creating Chromium browser (Incognito, headless=${headless})...`);
    }

    if (proxy) {
      console.log(`[BrowserFactory] Proxy: ${proxy.server}`);
    }

    // ⚠️ 절대 수정 금지: Chromium + 정확히 2개 args
    const launchOptions = {
      headless: headless,
      args: [
        '--disable-blink-features=AutomationControlled',
        '--no-first-run'
      ]
    };

    // executablePath가 지정되면 사용
    if (executablePath) {
      launchOptions.executablePath = executablePath;
    }

    const browser = await chromium.launch(launchOptions);

    // ⚠️ 프록시는 newContext에 설정 (launch가 아님!)
    const contextOptions = {};
    if (proxy) {
      contextOptions.proxy = proxy;
    }

    const context = await browser.newContext(contextOptions);
    const page = await context.newPage();

    return { browser, context, page };
  }

  /**
   * 안전한 브라우저 종료
   */
  static async closeBrowser(browser) {
    if (browser) {
      await browser.close();
      console.log('[BrowserFactory] Browser closed');
    }
  }

  /**
   * 쿠키 추출
   */
  static async getCookies(context) {
    return await context.cookies();
  }
}

module.exports = BrowserFactory;
