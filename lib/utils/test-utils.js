/**
 * 테스트 유틸리티 모듈
 * - 상품 추출, 차단 감지, 중복 체크 등 공통 기능
 */

const { JSDOM } = require('jsdom');

class TestUtils {
  /**
   * HTML 응답이 차단되었는지 확인
   */
  static isBlocked(html) {
    if (html.length < 50000) return true;
    if (html.includes('ERR_') || html.includes('location.reload')) return true;
    if (!html.includes('product-list')) return true;
    return false;
  }

  /**
   * HTML에서 상품 개수 추출
   */
  static extractProductCount(html) {
    const dom = new JSDOM(html);
    const document = dom.window.document;
    const productList = document.querySelector('#product-list');
    if (!productList) return 0;

    const links = productList.querySelectorAll('a[href*="/products/"]');
    let count = 0;

    links.forEach(link => {
      const href = link.href;
      if (href.includes('/vp/products/') && href.includes('rank=')) {
        count++;
      }
    });

    return count;
  }

  /**
   * HTML에서 상품 목록 추출 (중복 체크용)
   */
  static extractProducts(html) {
    const dom = new JSDOM(html);
    const document = dom.window.document;

    const productList = document.querySelector('#product-list');
    if (!productList) return { ranking: [], ads: [], total: 0 };

    const links = productList.querySelectorAll('a[href*="/products/"]');
    const rankingProducts = new Map();
    const adProducts = new Map();

    links.forEach(link => {
      const href = link.href;
      if (!href.includes('/vp/products/')) return;

      const productIdMatch = href.match(/\/vp\/products\/(\d+)/);
      if (!productIdMatch) return;
      const productId = productIdMatch[1];

      const itemIdMatch = href.match(/[?&]itemId=(\d+)/);
      const vendorItemIdMatch = href.match(/[?&]vendorItemId=(\d+)/);

      const itemId = itemIdMatch ? itemIdMatch[1] : '';
      const vendorItemId = vendorItemIdMatch ? vendorItemIdMatch[1] : '';
      const uniqueKey = `${productId}_${itemId}_${vendorItemId}`;

      const hasRank = href.includes('rank=');
      let rank = null;

      if (hasRank) {
        try {
          const rankMatch = href.match(/[?&]rank=(\d+)/);
          if (rankMatch) rank = parseInt(rankMatch[1]);
        } catch(e) {}
      }

      const productCard = link.closest('li') || link.closest('div');
      const hasAdMark = productCard?.querySelector('[class*="AdMark"]') !== null;

      const nameEl = productCard?.querySelector('.name') ||
                     productCard?.querySelector('[class*="name"]') ||
                     link;
      const priceEl = productCard?.querySelector('.price-value') ||
                      productCard?.querySelector('[class*="price"]');

      const productData = {
        productId: productId,
        itemId: itemId,
        vendorItemId: vendorItemId,
        uniqueKey: uniqueKey,
        name: nameEl?.textContent?.trim() || '',
        price: priceEl?.textContent?.trim() || '',
        url: href,
        rank: rank,
        hasAdMark: hasAdMark
      };

      if (hasRank && rank !== null && !hasAdMark) {
        if (!rankingProducts.has(uniqueKey)) {
          rankingProducts.set(uniqueKey, productData);
        }
      } else {
        if (!adProducts.has(uniqueKey)) {
          adProducts.set(uniqueKey, productData);
        }
      }
    });

    return {
      ranking: Array.from(rankingProducts.values()),
      ads: Array.from(adProducts.values()),
      total: rankingProducts.size + adProducts.size
    };
  }

  /**
   * 중복 상품 분석
   * @param {Array<Object>} allProducts - 전체 페이지의 상품 목록
   * @returns {Object} 중복 분석 결과
   */
  static analyzeDuplicates(allProducts) {
    const uniqueKeys = new Set();
    const duplicateKeys = new Set();
    let totalCount = 0;

    allProducts.forEach(products => {
      products.forEach(product => {
        totalCount++;
        if (uniqueKeys.has(product.uniqueKey)) {
          duplicateKeys.add(product.uniqueKey);
        } else {
          uniqueKeys.add(product.uniqueKey);
        }
      });
    });

    const duplicateCount = duplicateKeys.size;
    const duplicateRate = totalCount > 0 ? (duplicateCount / totalCount * 100) : 0;

    return {
      totalProducts: totalCount,
      uniqueProducts: uniqueKeys.size,
      duplicateProducts: duplicateCount,
      duplicateRate: duplicateRate.toFixed(2),
      isAcceptable: duplicateRate <= 4.0  // 4% 기준치
    };
  }

  /**
   * 랜덤 딜레이 (100ms ~ 500ms)
   */
  static async randomDelay() {
    const delay = Math.floor(Math.random() * 400) + 100;
    await new Promise(resolve => setTimeout(resolve, delay));
  }

  /**
   * 결과를 마크다운 테이블로 포맷팅
   */
  static formatResultsTable(results) {
    const headers = '| Page | Status | Products | Ads | Response Size | Cookies |';
    const divider = '|------|--------|----------|-----|---------------|---------|';

    const rows = results.map(r => {
      const status = r.success ? '✅ SUCCESS' : '❌ BLOCKED';
      const size = r.responseSize ? `${(r.responseSize / 1024).toFixed(1)}KB` : 'N/A';
      const cookies = r.cookieCount || 'N/A';
      return `| ${r.page} | ${status} | ${r.rankingCount || 0} | ${r.adCount || 0} | ${size} | ${cookies} |`;
    }).join('\n');

    return `${headers}\n${divider}\n${rows}`;
  }

  /**
   * 쿠키 변화 분석
   */
  static analyzeCookieChanges(pageResults) {
    const cookieChanges = [];

    for (let i = 1; i < pageResults.length; i++) {
      const prev = pageResults[i - 1];
      const curr = pageResults[i];

      if (prev.cookieCount && curr.cookieCount) {
        const diff = curr.cookieCount - prev.cookieCount;
        if (diff !== 0) {
          cookieChanges.push({
            fromPage: prev.page,
            toPage: curr.page,
            change: diff,
            prevCount: prev.cookieCount,
            currCount: curr.cookieCount
          });
        }
      }
    }

    return cookieChanges;
  }
}

module.exports = TestUtils;
