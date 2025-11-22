/**
 * Request Capture Module
 * - 브라우저의 실제 요청 헤더 캡처
 * - 패킷 모드에서 재현하기 위한 정보 수집
 */

class RequestCapture {
  constructor(page) {
    this.page = page;
    this.capturedRequests = [];
  }

  /**
   * 요청 캡처 시작
   */
  async startCapture() {
    this.page.on('request', (request) => {
      const url = request.url();

      // Coupang 검색 페이지 요청만 캡처
      if (url.includes('coupang.com/np/search')) {
        const headers = request.headers();

        this.capturedRequests.push({
          url,
          method: request.method(),
          headers,
          timestamp: Date.now()
        });

        console.log('[RequestCapture] Captured search request');
      }
    });
  }

  /**
   * 가장 최근 캡처된 요청 가져오기
   */
  getLatestRequest() {
    if (this.capturedRequests.length === 0) {
      return null;
    }

    return this.capturedRequests[this.capturedRequests.length - 1];
  }

  /**
   * 모든 캡처된 요청 가져오기
   */
  getAllRequests() {
    return this.capturedRequests;
  }

  /**
   * 캡처 초기화
   */
  clear() {
    this.capturedRequests = [];
  }
}

module.exports = RequestCapture;
