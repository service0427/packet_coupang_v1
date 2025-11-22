/**
 * File Manager
 * - 결과 저장 및 쿠키 관리
 */

const fs = require('fs');
const path = require('path');

class FileManager {
  /**
   * 디렉토리 생성 (존재하지 않는 경우)
   */
  static ensureDir(dirPath) {
    if (!fs.existsSync(dirPath)) {
      fs.mkdirSync(dirPath, { recursive: true });
    }
  }

  /**
   * 쿠키 저장
   */
  static saveCookies(cookies, pageNum, baseDir = '.') {
    const cookieDir = path.join(baseDir, 'cookies');
    this.ensureDir(cookieDir);

    const cookieFile = path.join(cookieDir, `page${pageNum}_cookies.json`);
    fs.writeFileSync(cookieFile, JSON.stringify(cookies, null, 2));
    console.log(`[SAVED] ${cookieFile}`);

    return cookieFile;
  }

  /**
   * 쿠키 로드
   */
  static loadCookies(pageNum, baseDir = '.') {
    const cookieFile = path.join(baseDir, 'cookies', `page${pageNum}_cookies.json`);

    if (!fs.existsSync(cookieFile)) {
      throw new Error(`Cookie file not found: ${cookieFile}`);
    }

    const cookies = JSON.parse(fs.readFileSync(cookieFile, 'utf-8'));
    return cookies;
  }

  /**
   * 결과 저장
   */
  static saveResults(results, keyword, baseDir = '.') {
    const resultsDir = path.join(baseDir, 'results');
    this.ensureDir(resultsDir);

    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').substring(0, 19);
    const filename = path.join(resultsDir, `multipage_results_${timestamp}.json`);

    const summary = {
      timestamp: new Date().toISOString(),
      keyword: keyword,
      totalPages: results.length,
      successfulPages: results.filter(r => r.success).length,
      totalRankingProducts: results.reduce((sum, r) => sum + (r.rankingCount || 0), 0),
      totalAdProducts: results.reduce((sum, r) => sum + (r.adCount || 0), 0),
      pages: results
    };

    fs.writeFileSync(filename, JSON.stringify(summary, null, 2));
    console.log(`\n[SAVED] ${filename}`);

    return filename;
  }

  /**
   * 결과 요약 출력
   */
  static printSummary(results, keyword) {
    console.log(`\n${'='.repeat(80)}`);
    console.log(`[FINAL SUMMARY]`);
    console.log(`${'='.repeat(80)}`);
    console.log(`Keyword: ${keyword}`);
    console.log(`Total Pages: ${results.length}`);
    console.log(`Successful Pages: ${results.filter(r => r.success).length}`);
    console.log(`Failed Pages: ${results.filter(r => !r.success).length}`);

    const totalRanking = results.reduce((sum, r) => sum + (r.rankingCount || 0), 0);
    const totalAds = results.reduce((sum, r) => sum + (r.adCount || 0), 0);

    console.log(`Total Ranking Products: ${totalRanking}`);
    console.log(`Total Ad Products: ${totalAds}`);

    console.log(`\n[PER-PAGE RESULTS]:`);
    results.forEach(r => {
      const status = r.success ? 'OK' : 'FAIL';
      console.log(`  [${status}] Page ${r.page}: Ranking ${r.rankingCount || 0}개, Ads ${r.adCount || 0}개`);
    });

    console.log(`${'='.repeat(80)}\n`);
  }
}

module.exports = FileManager;
