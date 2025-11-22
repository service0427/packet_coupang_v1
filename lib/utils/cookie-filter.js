/**
 * 쿠키 필터링 유틸리티
 * - 사용자 추적 쿠키 제거 (PCID, sid)
 * - 나머지 쿠키는 유지
 */

class CookieFilter {
  /**
   * 제거할 추적 쿠키 목록 (검색 히스토리 추적 방지)
   */
  static TRACKING_COOKIES = [
    'PCID',       // 쿠팡 사용자 고유 ID (이전 검색 기록 추적)
    'sid',        // 세션 ID (행동 패턴 분석)
  ];

  /**
   * 추적 쿠키 제거 (PCID, sid만 제거)
   * @param {Array} cookies - 전체 쿠키 배열
   * @param {boolean} enabled - 필터링 활성화 여부 (기본: true)
   * @returns {Array} 추적 쿠키가 제거된 배열 (비활성화 시 전체 쿠키 반환)
   */
  static removeTrackingCookies(cookies, enabled = true) {
    if (!enabled) {
      return cookies;
    }

    const filtered = cookies.filter(cookie =>
      !this.TRACKING_COOKIES.includes(cookie.name)
    );

    const removed = cookies.length - filtered.length;

    return filtered;
  }

  /**
   * Akamai 핵심 쿠키만 필터링 (이전 방식 - 호환성 유지)
   * @deprecated Use removeTrackingCookies instead
   */
  static filterAkamaiOnly(cookies, enabled = true) {
    return this.removeTrackingCookies(cookies, enabled);
  }

  /**
   * 쿠키 통계 출력
   */
  static printStats(cookies, label = 'Cookies') {
    const trackingCookies = cookies.filter(c =>
      this.TRACKING_COOKIES.includes(c.name)
    );

    const coupangCookies = cookies.filter(c =>
      c.domain.includes('coupang.com')
    );

    const adCookies = cookies.filter(c =>
      !c.domain.includes('coupang.com')
    );

    console.log(`[${label}]`);
    console.log(`  Total: ${cookies.length} cookies`);
    console.log(`  - Tracking (PCID/sid): ${trackingCookies.length}`);
    console.log(`  - Coupang: ${coupangCookies.length}`);
    console.log(`  - Ad tracking: ${adCookies.length}`);

    return {
      total: cookies.length,
      tracking: trackingCookies.length,
      coupang: coupangCookies.length,
      ad: adCookies.length
    };
  }

  /**
   * 쿠키 필터링이 활성화되어 있는지 확인
   */
  static isEnabled(options = {}) {
    return options.minimalCookies !== false;
  }
}

module.exports = CookieFilter;
