/**
 * Packet Mode (curl-cffi)
 * - 쿠키를 재사용하여 빠른 요청 수행
 * - Real Browser에서 추출한 쿠키 필요
 */

const { execSync } = require('child_process');
const path = require('path');

class PacketMode {
  constructor(options = {}) {
    this.pythonScript = options.pythonScript || path.join(__dirname, '..', '..', 'src', 'packet_request.py');
    this.cookiesDir = options.cookiesDir || path.join(__dirname, '..', '..', 'cookies');
  }

  /**
   * 패킷 모드로 요청 수행 (Python curl-cffi 사용)
   * @param {string} url - 요청 URL
   * @param {number|string} cookieFileOrPageNum - 쿠키 파일명 또는 페이지 번호
   * @returns {Promise<string>} HTML 응답
   */
  async request(url, cookieFileOrPageNum = 1) {
    // 숫자면 page{N}_cookies.json, 문자열이면 {name}.json
    const cookieFile = typeof cookieFileOrPageNum === 'number'
      ? path.join(this.cookiesDir, `page${cookieFileOrPageNum}_cookies.json`)
      : path.join(this.cookiesDir, `${cookieFileOrPageNum}.json`);

    const displayName = typeof cookieFileOrPageNum === 'number'
      ? `page ${cookieFileOrPageNum}`
      : cookieFileOrPageNum;

    console.log(`[Packet] Requesting ${url} with cookies from ${displayName}...`);

    try {
      const command = `python "${this.pythonScript}" "${url}" "${cookieFile}"`;
      const result = execSync(command, { encoding: 'utf-8', maxBuffer: 10 * 1024 * 1024 });

      console.log(`[Packet] Response received: ${result.length} bytes`);
      return result;

    } catch (error) {
      console.error(`[Packet] Request failed:`, error.message);
      throw error;
    }
  }

  /**
   * 여러 URL 배치 요청
   */
  async batchRequest(urls, pageNum = 1) {
    const results = [];

    for (const url of urls) {
      try {
        const html = await this.request(url, pageNum);
        results.push({ url, success: true, html });
      } catch (error) {
        results.push({ url, success: false, error: error.message });
      }
    }

    return results;
  }
}

module.exports = PacketMode;
