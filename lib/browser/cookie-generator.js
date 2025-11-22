/**
 * Cookie Generation Module
 *
 * 쿠키 생성 전략을 모듈화하여 메인 페이지 방식과 검색 페이지 방식을 선택 가능
 */

const BrowserFactory = require('./browser-factory');
const CookieFilter = require('../utils/cookie-filter');
const fs = require('fs');
const path = require('path');

class CookieGenerator {
  /**
   * 쿠키 생성 전략
   * @param {Object} options
   * @param {string} options.strategy - 'main' | 'search'
   * @param {string} options.keyword - 검색 키워드 (strategy='search'일 때 필요)
   * @param {string} options.executablePath - Chrome 실행 파일 경로
   * @param {boolean} options.headless - headless 모드
   * @param {string} options.cookieFile - 쿠키 저장 파일명 (확장자 제외)
   * @returns {Promise<Object>} { success, pageSize, cookieCount, akamaiCount, cookieFile, blocked }
   */
  static async generate(options) {
    const {
      strategy = 'main',
      keyword = '',
      executablePath,
      headless = false,
      cookieFile = 'cookies'
    } = options;

    if (strategy === 'search' && !keyword) {
      throw new Error('Search strategy requires keyword');
    }

    const cookiesDir = path.join(process.cwd(), 'cookies');
    if (!fs.existsSync(cookiesDir)) {
      fs.mkdirSync(cookiesDir, { recursive: true });
    }

    const cookiePath = path.join(cookiesDir, `${cookieFile}.json`);

    try {
      const { browser, context, page } = await BrowserFactory.createBrowser({
        headless,
        executablePath
      });

      let html;
      let pageType;

      if (strategy === 'main') {
        // 메인 페이지 방식
        console.log('[Cookie] Strategy: Main page');
        console.log('[Cookie] Visiting https://www.coupang.com/...');

        await page.goto('https://www.coupang.com/');
        await page.waitForTimeout(5000);

        html = await page.content();
        pageType = 'main';

      } else if (strategy === 'search') {
        // 검색 페이지 방식 (메인 → 검색 입력 → 검색)
        console.log('[Cookie] Strategy: Search page');
        console.log(`[Cookie] Keyword: ${keyword}`);

        // 1. 메인 페이지 방문
        console.log('[Cookie] Step 1: Visit main page');
        await page.goto('https://www.coupang.com/');
        await page.waitForTimeout(3000);

        // 2. 검색창 찾기
        console.log('[Cookie] Step 2: Find search input');
        const searchInput = await page.waitForSelector('input[name="q"]', { timeout: 5000 });
        await searchInput.click();
        await page.waitForTimeout(1000);

        // 3. 검색어 입력
        console.log('[Cookie] Step 3: Type keyword');
        await page.keyboard.press('Control+A');
        await page.waitForTimeout(500);
        await searchInput.type(keyword, { delay: 150 });
        await page.waitForTimeout(1000);

        // 4. 검색 실행
        console.log('[Cookie] Step 4: Press Enter');
        await page.keyboard.press('Enter');
        await page.waitForLoadState('domcontentloaded');
        await page.waitForTimeout(5000);

        html = await page.content();
        pageType = 'search';
      }

      const pageSize = html.length;
      console.log(`[Cookie] Page size: ${pageSize.toLocaleString()} bytes`);

      // 차단 여부 확인
      const isBlocked = this.checkBlocked(html, pageSize, pageType);

      if (isBlocked) {
        console.log('[❌ BLOCKED] Page shows blocking response');
        await browser.close();
        return {
          success: false,
          blocked: true,
          pageSize,
          cookieCount: 0,
          akamaiCount: 0,
          cookieFile: null
        };
      }

      // 쿠키 추출
      const cookies = await context.cookies();
      console.log(`[Cookie] Extracted ${cookies.length} cookies`);

      // 추적 쿠키 제거
      const filteredCookies = CookieFilter.removeTrackingCookies(cookies, true);
      console.log(`[Cookie] Filtered to ${filteredCookies.length} cookies`);

      // Akamai 쿠키 확인
      const akamaiCookies = filteredCookies.filter(c =>
        c.name.startsWith('_abck') ||
        c.name.startsWith('bm_') ||
        c.name.startsWith('ak_')
      );
      console.log(`[Cookie] Akamai cookies: ${akamaiCookies.length}개`);

      // 쿠키 저장
      fs.writeFileSync(cookiePath, JSON.stringify(filteredCookies, null, 2));
      console.log(`[Cookie] Saved to ${path.basename(cookiePath)}`);

      await browser.close();

      return {
        success: true,
        blocked: false,
        pageSize,
        cookieCount: filteredCookies.length,
        akamaiCount: akamaiCookies.length,
        cookieFile: cookieFile
      };

    } catch (error) {
      console.error('[Cookie] Error:', error.message);
      return {
        success: false,
        blocked: false,
        error: error.message,
        cookieCount: 0,
        akamaiCount: 0,
        cookieFile: null
      };
    }
  }

  /**
   * 차단 여부 확인
   */
  static checkBlocked(html, pageSize, pageType) {
    // HTTP/2 에러
    if (html.includes('ERR_HTTP2_PROTOCOL_ERROR')) {
      return true;
    }

    // Challenge 페이지
    if (html.includes('location.reload') && pageSize < 10000) {
      return true;
    }

    if (pageType === 'main') {
      // 메인 페이지: 50KB 이하면 차단
      return pageSize < 50000;
    } else if (pageType === 'search') {
      // 검색 페이지: 50KB 이하면 차단
      return pageSize < 50000;
    }

    return false;
  }
}

module.exports = CookieGenerator;
