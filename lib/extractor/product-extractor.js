/**
 * Product Extractor
 * - 쿠팡 검색 결과 페이지에서 상품 정보 추출
 * - 랭킹 상품 vs 광고 상품 구분
 * - 3-part unique key 사용 (product_id + item_id + vendor_item_id)
 */

class ProductExtractor {
  /**
   * 페이지에서 상품 정보 추출 (브라우저 컨텍스트에서 실행)
   */
  static extractProductsFromPage() {
    const productList = document.querySelector('#product-list');
    if (!productList) return { ranking: [], ads: [], total: 0 };

    const links = productList.querySelectorAll('a[href*="/products/"]');
    const rankingProducts = new Map();
    const adProducts = new Map();

    links.forEach(link => {
      const href = link.href;

      // /vp/products/ 형태만 허용
      if (!href.includes('/vp/products/')) return;

      // product_id, item_id, vendor_item_id 추출
      const productIdMatch = href.match(/\/vp\/products\/(\d+)/);
      if (!productIdMatch) return;
      const productId = productIdMatch[1];

      const itemIdMatch = href.match(/[?&]itemId=(\d+)/);
      const vendorItemIdMatch = href.match(/[?&]vendorItemId=(\d+)/);

      const itemId = itemIdMatch ? itemIdMatch[1] : '';
      const vendorItemId = vendorItemIdMatch ? vendorItemIdMatch[1] : '';

      // 고유 키: product_id + item_id + vendor_item_id
      const uniqueKey = `${productId}_${itemId}_${vendorItemId}`;

      // rank 파라미터 확인
      const hasRank = href.includes('rank=');
      let rank = null;

      if (hasRank) {
        try {
          const rankMatch = href.match(/[?&]rank=(\d+)/);
          if (rankMatch) rank = parseInt(rankMatch[1]);
        } catch(e) {}
      }

      // AdMark 클래스 확인
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

      // rank 파라미터가 있고 AdMark가 없으면 순수 랭킹 상품
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
   * 중복 체크 (여러 페이지의 결과를 분석)
   */
  static checkDuplicates(results) {
    const allProductKeys = [];
    const pageProducts = {};
    const productDetails = {};

    for (const result of results) {
      if (result.success && result.rankingProducts) {
        const pageNum = result.page;
        const productKeys = result.rankingProducts.map(p => p.uniqueKey);
        allProductKeys.push(...productKeys);
        pageProducts[pageNum] = new Set(productKeys);

        result.rankingProducts.forEach(p => {
          if (!productDetails[p.uniqueKey]) {
            productDetails[p.uniqueKey] = [];
          }
          productDetails[p.uniqueKey].push({
            page: pageNum,
            url: p.url,
            name: p.name,
            rank: p.rank
          });
        });
      }
    }

    const totalProducts = allProductKeys.length;
    const uniqueProducts = new Set(allProductKeys).size;
    const duplicateCount = totalProducts - uniqueProducts;

    return {
      total: totalProducts,
      unique: uniqueProducts,
      duplicates: duplicateCount,
      duplicate_rate: totalProducts > 0 ? (duplicateCount / totalProducts * 100) : 0,
      pageProducts: pageProducts,
      productDetails: productDetails
    };
  }

  /**
   * 중복 정보 출력
   */
  static printDuplicates(duplicateStats) {
    console.log(`\n${'='.repeat(80)}`);
    console.log(`[DUPLICATE CHECK - RANKING PRODUCTS (product_id + item_id + vendor_item_id)]`);
    console.log(`${'='.repeat(80)}`);

    console.log(`Total Ranking Products: ${duplicateStats.total}`);
    console.log(`Unique Products: ${duplicateStats.unique}`);
    console.log(`Duplicates: ${duplicateStats.duplicates}`);

    if (duplicateStats.duplicates > 0) {
      console.log(`\n[WARNING] ${duplicateStats.duplicates}개 중복 상품 발견!`);

      const productCounter = {};
      const allKeys = [];

      for (const pageProducts of Object.values(duplicateStats.pageProducts)) {
        for (const key of pageProducts) {
          allKeys.push(key);
        }
      }

      allKeys.forEach(key => {
        productCounter[key] = (productCounter[key] || 0) + 1;
      });

      const duplicates = Object.entries(productCounter).filter(([_, count]) => count > 1);

      console.log(`\n[DUPLICATE PRODUCTS WITH FULL URLS]:`);
      duplicates.forEach(([key, count]) => {
        console.log(`\n  Key ${key}: ${count}번 등장`);

        const pagesWithDuplicate = [];
        for (const [pageNum, productSet] of Object.entries(duplicateStats.pageProducts)) {
          if (productSet.has(key)) {
            pagesWithDuplicate.push(pageNum);
          }
        }
        console.log(`    Pages: ${pagesWithDuplicate.join(', ')}`);

        const details = duplicateStats.productDetails[key];
        if (details) {
          details.forEach(detail => {
            console.log(`    Page ${detail.page}:`);
            console.log(`      URL: ${detail.url}`);
            console.log(`      Name: ${detail.name.substring(0, 50)}...`);
            console.log(`      Rank: ${detail.rank}`);
          });
        }
      });
    } else {
      console.log(`\n[OK] 중복 없음! 모든 상품이 고유합니다.`);
    }

    return duplicateStats;
  }
}

module.exports = ProductExtractor;
