/**
 * Playwright Browser Manager
 * - BrowserFactory를 사용한 안전한 브라우저 초기화
 * - 자연스러운 사용자 행동 시뮬레이션
 */

const BrowserFactory = require('./browser-factory');

class PlaywrightBrowser {
  constructor(options = {}) {
    this.headless = options.headless !== undefined ? options.headless : false;
    this.browser = null;
    this.context = null;
    this.page = null;
  }

  /**
   * 브라우저 실행 (BrowserFactory 사용)
   */
  async launch() {
    const { browser, context, page } = await BrowserFactory.createBrowser({
      headless: this.headless
    });

    this.browser = browser;
    this.context = context;
    this.page = page;

    return this;
  }

  /**
   * 페이지 이동
   */
  async goto(url, options = {}) {
    const waitTime = options.waitTime || 3000;

    await this.page.goto(url);
    await this.page.waitForTimeout(waitTime);

    return this.page;
  }

  /**
   * 자연스러운 검색 수행 (타이핑 시뮬레이션)
   */
  async performSearch(keyword, options = {}) {
    const typingDelay = options.typingDelay || 150;
    const waitAfterType = options.waitAfterType || 1000;
    const waitAfterSubmit = options.waitAfterSubmit || 5000;

    console.log(`[Browser] Performing search for "${keyword}"...`);

    // 검색창 찾기
    const searchInput = await this.page.waitForSelector('input[name="q"]');
    await searchInput.click();
    await this.page.waitForTimeout(1000);

    // 기존 내용 지우기
    await this.page.keyboard.press('Control+A');
    await this.page.waitForTimeout(500);

    // 한 글자씩 자연스럽게 타이핑
    await searchInput.type(keyword, { delay: typingDelay });
    await this.page.waitForTimeout(waitAfterType);

    // 검색 실행
    await this.page.keyboard.press('Enter');
    await this.page.waitForLoadState('domcontentloaded');
    await this.page.waitForTimeout(waitAfterSubmit);

    return this.page;
  }

  /**
   * 페이지당 상품 수 설정 (명시적 호출 시에만 사용)
   *
   * ⚠️ 주의:
   * - 기본값은 36개 (자동 클릭 안 함)
   * - 48, 60, 72개 필요 시 명시적으로 호출
   * - 대부분 72개 사용
   *
   * @param {number} size - 36, 48, 60, 72 중 선택 (기본값: 36)
   */
  async setListSize(size = 72) {
    console.log(`[Browser] Setting list size to ${size}...`);

    await this.page.evaluate((listSize) => {
      const label = document.querySelector(`label[for="listSize-${listSize}"]`);
      if (label) {
        label.click();
      }
    }, size);

    await this.page.waitForTimeout(3000);
    return this.page;
  }

  /**
   * 다음 페이지로 이동
   */
  async navigateToNextPage() {
    console.log(`[Browser] Clicking next page button...`);

    await this.page.evaluate(() => {
      const nextBtn = document.querySelector('a[data-page="next"]');
      if (nextBtn) {
        nextBtn.click();
      }
    });

    await this.page.waitForTimeout(3000);
    return this.page;
  }

  /**
   * 현재 페이지의 쿠키 가져오기
   */
  async getCookies() {
    const cookies = await this.context.cookies();
    return cookies;
  }

  /**
   * 현재 URL 가져오기
   */
  getCurrentUrl() {
    return this.page.url();
  }

  /**
   * 페이지 평가 (evaluate)
   */
  async evaluate(pageFunction) {
    return await this.page.evaluate(pageFunction);
  }

  /**
   * 대기
   */
  async wait(ms) {
    await this.page.waitForTimeout(ms);
  }

  /**
   * 브라우저 종료
   */
  async close() {
    if (this.browser) {
      await this.browser.close();
      console.log('[Browser] Closed');
    }
  }
}

module.exports = PlaywrightBrowser;
