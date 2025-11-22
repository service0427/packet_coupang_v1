/**
 * Controller - Browser/Packet 모듈 통합 제어 프로그램
 *
 * 기능:
 * - Chrome 버전별 Browser/Packet 모드 자동 전환
 * - Hybrid 요청 (Packet 실패 시 Browser fallback)
 * - 배치 요청 및 통계 생성
 * - TLS 추출 자동화
 */

const BrowserModule = require('./modules/browser_module');
const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

class Controller {
    constructor(config = {}) {
        this.browserModule = new BrowserModule({
            chromeBasePath: config.chromeBasePath,
            cookiesPath: config.cookiesPath,
            searchKeyword: config.searchKeyword,
            blockThreshold: config.blockThreshold,
            headless: config.headless !== undefined ? config.headless : true
        });

        this.tlsConfigsPath = config.tlsConfigsPath || path.join(__dirname, '..', 'tls_configs');
        this.pythonPath = config.pythonPath || 'python';
        this.packetModulePath = path.join(__dirname, 'modules', 'packet_module.py');

        // 통계
        this.stats = {
            total_requests: 0,
            browser_requests: 0,
            packet_requests: 0,
            successes: 0,
            failures: 0
        };
    }

    /**
     * TLS 설정 파일 존재 여부 확인
     */
    hasTLSConfig(version) {
        const configFile = path.join(this.tlsConfigsPath, `chrome${version}_profile.json`);
        return fs.existsSync(configFile);
    }

    /**
     * TLS 추출 실행
     */
    async extractTLS(version) {
        console.log(`\n[Controller] Chrome ${version} TLS 추출 중...`);

        const chromePath = this.browserModule.findChromeExecutable(version);
        if (!chromePath) {
            throw new Error(`Chrome ${version} 실행 파일을 찾을 수 없습니다`);
        }

        const outputFile = path.join(this.tlsConfigsPath, `chrome${version}_profile.json`);
        const extractScript = path.join(__dirname, 'profiling', 'tls_profiling', 'extract_browser_tls.py');

        if (!fs.existsSync(extractScript)) {
            throw new Error(`TLS 추출 스크립트를 찾을 수 없습니다: ${extractScript}`);
        }

        try {
            const command = `${this.pythonPath} "${extractScript}" "${chromePath}" "${outputFile}"`;
            console.log(`  실행: ${command}`);

            execSync(command, {
                stdio: 'inherit',
                timeout: 120000  // 2분
            });

            console.log(`  [SUCCESS] TLS 설정 저장: ${outputFile}`);
            return outputFile;

        } catch (error) {
            console.error(`  [ERROR] TLS 추출 실패: ${error.message}`);
            throw error;
        }
    }

    /**
     * Packet 요청 실행 (Python 모듈 호출)
     */
    async packetRequest(version, url) {
        console.log(`\n[Controller] Packet 모드 요청`);

        try {
            const command = `${this.pythonPath} "${this.packetModulePath}" ${version} "${url}"`;

            const output = execSync(command, {
                encoding: 'utf-8',
                timeout: 30000
            });

            // 출력에서 응답 크기 파싱
            const match = output.match(/응답 크기:\s*(\d+)\s*bytes/);
            const sizeMatch = output.match(/Size:\s*(\d+)\s*bytes/);

            const size = match ? parseInt(match[1]) : (sizeMatch ? parseInt(sizeMatch[1]) : 0);
            const success = size > this.browserModule.blockThreshold;

            this.stats.total_requests++;
            this.stats.packet_requests++;
            if (success) this.stats.successes++;
            else this.stats.failures++;

            return {
                mode: 'packet',
                success,
                size,
                output
            };

        } catch (error) {
            console.error(`  [ERROR] Packet 요청 실패: ${error.message}`);
            this.stats.total_requests++;
            this.stats.packet_requests++;
            this.stats.failures++;

            return {
                mode: 'packet',
                success: false,
                error: error.message
            };
        }
    }

    /**
     * Browser 요청 실행
     */
    async browserRequest(version, url = null) {
        console.log(`\n[Controller] Browser 모드 요청`);

        try {
            const result = await this.browserModule.request(version, url);

            this.stats.total_requests++;
            this.stats.browser_requests++;
            if (result.success) this.stats.successes++;
            else this.stats.failures++;

            return {
                mode: 'browser',
                ...result
            };

        } catch (error) {
            console.error(`  [ERROR] Browser 요청 실패: ${error.message}`);
            this.stats.total_requests++;
            this.stats.browser_requests++;
            this.stats.failures++;

            return {
                mode: 'browser',
                success: false,
                error: error.message
            };
        }
    }

    /**
     * Hybrid 요청 (Packet → Browser fallback)
     */
    async hybridRequest(version, url, options = {}) {
        const {
            maxRetries = 2,
            preferBrowser = false
        } = options;

        console.log(`\n[Controller] Hybrid 모드 요청`);
        console.log(`  Chrome 버전: ${version}`);
        console.log(`  URL: ${url}`);

        // 1. TLS 설정 확인
        const hasTLS = this.hasTLSConfig(version);
        const hasCookies = this.browserModule.loadCookies(version) !== null;

        if (!hasTLS) {
            console.log(`  [알림] TLS 설정 없음 → TLS 추출 실행`);
            await this.extractTLS(version);
        }

        if (!hasCookies) {
            console.log(`  [알림] 쿠키 없음 → Browser 모드로 쿠키 생성`);
            const result = await this.browserRequest(version, url);
            return result;
        }

        // 2. 모드 선택
        if (preferBrowser) {
            console.log(`  [전략] Browser 모드 우선`);
            return await this.browserRequest(version, url);
        }

        // 3. Packet 시도
        console.log(`  [전략] Packet 모드 시도 (실패 시 Browser fallback)`);

        for (let attempt = 1; attempt <= maxRetries; attempt++) {
            console.log(`\n  === Packet 시도 ${attempt}/${maxRetries} ===`);

            const result = await this.packetRequest(version, url);

            if (result.success) {
                console.log(`  [SUCCESS] Packet 모드 성공`);
                return result;
            }

            console.log(`  [FAILED] Packet 모드 실패`);

            if (attempt < maxRetries) {
                console.log(`  재시도 중... (${attempt + 1}/${maxRetries})`);
            }
        }

        // 4. Browser fallback
        console.log(`\n  === Browser Fallback ===`);
        return await this.browserRequest(version, url);
    }

    /**
     * 배치 요청
     */
    async batchRequest(version, urls, options = {}) {
        console.log(`\n[Controller] 배치 요청 시작`);
        console.log(`  Chrome 버전: ${version}`);
        console.log(`  URL 개수: ${urls.length}`);

        const results = [];

        for (let i = 0; i < urls.length; i++) {
            console.log(`\n[${i + 1}/${urls.length}] ${urls[i]}`);

            const result = await this.hybridRequest(version, urls[i], options);
            results.push({
                url: urls[i],
                ...result
            });

            // 다음 요청 전 대기
            if (i < urls.length - 1) {
                const delay = options.delay || 2000;
                console.log(`\n  다음 요청까지 ${delay}ms 대기...`);
                await new Promise(resolve => setTimeout(resolve, delay));
            }
        }

        console.log(`\n[Controller] 배치 요청 완료`);
        this.printStats();

        return results;
    }

    /**
     * 통계 출력
     */
    printStats() {
        console.log(`\n${'='.repeat(80)}`);
        console.log('통계');
        console.log('='.repeat(80));
        console.log(`총 요청: ${this.stats.total_requests}`);
        console.log(`  - Browser 모드: ${this.stats.browser_requests}`);
        console.log(`  - Packet 모드: ${this.stats.packet_requests}`);
        console.log(`성공: ${this.stats.successes}`);
        console.log(`실패: ${this.stats.failures}`);

        if (this.stats.total_requests > 0) {
            const successRate = (this.stats.successes / this.stats.total_requests * 100).toFixed(1);
            console.log(`성공률: ${successRate}%`);
        }
    }

    /**
     * 통계 초기화
     */
    resetStats() {
        this.stats = {
            total_requests: 0,
            browser_requests: 0,
            packet_requests: 0,
            successes: 0,
            failures: 0
        };
    }
}

// CLI 인터페이스
if (require.main === module) {
    const controller = new Controller({ headless: false });

    const args = process.argv.slice(2);
    const command = args[0];

    if (!command) {
        console.log('Usage:');
        console.log('  node controller.js browser <version> [url]');
        console.log('  node controller.js packet <version> <url>');
        console.log('  node controller.js hybrid <version> <url>');
        console.log('  node controller.js extract-tls <version>');
        console.log('');
        console.log('Examples:');
        console.log('  node controller.js browser 130');
        console.log('  node controller.js packet 130 "https://www.coupang.com/np/search?q=물티슈"');
        console.log('  node controller.js hybrid 130 "https://www.coupang.com/np/search?q=물티슈"');
        console.log('  node controller.js extract-tls 130');
        process.exit(1);
    }

    const version = parseInt(args[1]);

    (async () => {
        try {
            if (command === 'browser') {
                const url = args[2] || null;
                const result = await controller.browserRequest(version, url);
                console.log('\n결과:', result);

            } else if (command === 'packet') {
                const url = args[2];
                if (!url) {
                    console.error('Error: URL이 필요합니다');
                    process.exit(1);
                }
                const result = await controller.packetRequest(version, url);
                console.log('\n결과:', result);

            } else if (command === 'hybrid') {
                const url = args[2];
                if (!url) {
                    console.error('Error: URL이 필요합니다');
                    process.exit(1);
                }
                const result = await controller.hybridRequest(version, url);
                console.log('\n결과:', result);

            } else if (command === 'extract-tls') {
                await controller.extractTLS(version);

            } else {
                console.error(`Unknown command: ${command}`);
                process.exit(1);
            }

            controller.printStats();

        } catch (error) {
            console.error(`\n[FATAL ERROR] ${error.message}`);
            process.exit(1);
        }
    })();
}

module.exports = Controller;
