/**
 * Browser Module - Chrome 버전별 리얼 브라우저 실행 모듈
 *
 * 기능:
 * - Chrome 버전별 Playwright 실행
 * - 자연스러운 검색 플로우 (homepage → search → results)
 * - Akamai 스크립트 차단으로 100% 우회
 * - 쿠키 저장 및 재사용
 */

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

class BrowserModule {
    constructor(config = {}) {
        this.chromeBasePath = config.chromeBasePath || path.join(__dirname, '..', '..', 'chrome-versions');
        this.cookiesPath = config.cookiesPath || path.join(__dirname, '..', '..', 'cookies');
        this.searchKeyword = config.searchKeyword || '종합테스트';
        this.blockThreshold = config.blockThreshold || 50000;
        this.headless = config.headless !== undefined ? config.headless : true;

        // 디렉토리 생성
        fs.mkdirSync(this.cookiesPath, { recursive: true });
    }

    /**
     * Chrome 실행 파일 찾기
     */
    findChromeExecutable(version) {
        const versionDirs = fs.readdirSync(this.chromeBasePath)
            .filter(dir => dir.startsWith(`chrome-${version}`));

        if (versionDirs.length === 0) {
            return null;
        }

        const possiblePaths = [
            path.join(this.chromeBasePath, versionDirs[0], 'chrome-win64', 'chrome.exe'),
            path.join(this.chromeBasePath, versionDirs[0], 'chrome.exe'),
            path.join(this.chromeBasePath, versionDirs[0], 'Application', 'chrome.exe'),
        ];

        for (const chromePath of possiblePaths) {
            if (fs.existsSync(chromePath)) {
                return chromePath;
            }
        }

        return null;
    }

    /**
     * Akamai 스크립트 차단 라우팅
     */
    async setupAkamaiBlocking(page) {
        await page.route('**/*', async (route) => {
            const url = route.request().url();
            const akamaiPatterns = [
                /\/akam\//,
                /\/akamai\//,
                /akamaihd\.net/,
                /sensor/,
                /bmak/,
                /bot-manager/,
                /fingerprint/
            ];

            if (akamaiPatterns.some(p => p.test(url))) {
                await route.abort();
            } else {
                await route.continue();
            }
        });
    }

    /**
     * 자연스러운 검색 플로우 실행
     */
    async performNaturalSearch(page, keyword) {
        // 1. Homepage 이동
        console.log('  [1/4] Homepage 이동...');
        await page.goto('https://www.coupang.com/', { timeout: 30000 });
        await page.waitForTimeout(3000);

        // 2. 검색창 클릭
        console.log('  [2/4] 검색창 클릭...');
        const searchInput = await page.waitForSelector('input[name="q"]', { timeout: 10000 });
        await searchInput.click();
        await page.waitForTimeout(1000);

        // 3. 검색어 입력
        console.log('  [3/4] 검색어 입력...');
        await page.keyboard.press('Control+A');
        await page.waitForTimeout(500);
        await searchInput.type(keyword, { delay: 150 });
        await page.waitForTimeout(1000);

        // 4. 검색 실행
        console.log('  [4/4] 검색 실행...');
        await page.keyboard.press('Enter');
        await page.waitForLoadState('domcontentloaded');
        await page.waitForTimeout(5000);

        return await page.content();
    }

    /**
     * 쿠키 저장
     */
    async saveCookies(context, version) {
        const cookies = await context.cookies();
        const cookieFile = path.join(this.cookiesPath, `chrome${version}_cookies.json`);
        fs.writeFileSync(cookieFile, JSON.stringify(cookies, null, 2));
        return cookieFile;
    }

    /**
     * 쿠키 로드
     */
    loadCookies(version) {
        const cookieFile = path.join(this.cookiesPath, `chrome${version}_cookies.json`);
        if (fs.existsSync(cookieFile)) {
            return JSON.parse(fs.readFileSync(cookieFile, 'utf-8'));
        }
        return null;
    }

    /**
     * 브라우저 모드로 요청 실행
     */
    async request(version, url = null) {
        console.log(`\n[Browser Module] Chrome ${version} 실행 중...`);

        const chromePath = this.findChromeExecutable(version);
        if (!chromePath) {
            throw new Error(`Chrome ${version} 실행 파일을 찾을 수 없습니다`);
        }

        console.log(`  Chrome 경로: ${chromePath}`);

        try {
            // Browser 실행
            const browser = await chromium.launch({
                executablePath: chromePath,
                headless: this.headless,
                args: [
                    '--disable-blink-features=AutomationControlled',
                    '--no-first-run'
                ]
            });

            const context = await browser.newContext();
            const page = await context.newPage();

            // Akamai 차단 설정
            await this.setupAkamaiBlocking(page);

            let content;
            if (url) {
                // 직접 URL 사용 (단, 홈페이지부터 시작)
                console.log(`  [URL 모드] ${url}`);
                await page.goto('https://www.coupang.com/', { timeout: 30000 });
                await page.waitForTimeout(2000);
                await page.goto(url, { timeout: 30000 });
                await page.waitForTimeout(5000);
                content = await page.content();
            } else {
                // 자연스러운 검색 플로우
                content = await this.performNaturalSearch(page, this.searchKeyword);
            }

            const pageSize = content.length;
            console.log(`  응답 크기: ${pageSize} bytes`);

            const success = pageSize > this.blockThreshold;

            // 성공 시 쿠키 저장
            let cookieFile = null;
            if (success) {
                cookieFile = await this.saveCookies(context, version);
                console.log(`  [SUCCESS] 쿠키 저장: ${cookieFile}`);
            } else {
                console.log(`  [BLOCKED] 응답 크기 부족`);
            }

            await browser.close();

            return {
                success,
                pageSize,
                content,
                cookieFile,
                chromePath
            };

        } catch (error) {
            console.error(`  [ERROR] ${error.message}`);
            throw error;
        }
    }

    /**
     * 여러 페이지 요청 (페이지네이션)
     */
    async requestMultiplePages(version, maxPages = 10) {
        console.log(`\n[Browser Module] Chrome ${version} - ${maxPages}페이지 크롤링`);

        const chromePath = this.findChromeExecutable(version);
        if (!chromePath) {
            throw new Error(`Chrome ${version} 실행 파일을 찾을 수 없습니다`);
        }

        const results = [];

        try {
            const browser = await chromium.launch({
                executablePath: chromePath,
                headless: this.headless,
                args: [
                    '--disable-blink-features=AutomationControlled',
                    '--no-first-run'
                ]
            });

            const context = await browser.newContext();
            const page = await context.newPage();
            await this.setupAkamaiBlocking(page);

            // 첫 검색
            const firstContent = await this.performNaturalSearch(page, this.searchKeyword);
            results.push({
                page: 1,
                size: firstContent.length,
                success: firstContent.length > this.blockThreshold
            });
            console.log(`  페이지 1: ${firstContent.length} bytes`);

            // 쿠키 저장
            const cookieFile = await this.saveCookies(context, version);

            // 나머지 페이지
            for (let pageNum = 2; pageNum <= maxPages; pageNum++) {
                const url = `https://www.coupang.com/np/search?q=${encodeURIComponent(this.searchKeyword)}&page=${pageNum}`;

                await page.goto(url, { timeout: 30000 });
                await page.waitForTimeout(3000);

                const content = await page.content();
                const success = content.length > this.blockThreshold;

                results.push({
                    page: pageNum,
                    size: content.length,
                    success
                });

                console.log(`  페이지 ${pageNum}: ${content.length} bytes ${success ? '✅' : '❌'}`);

                if (!success) {
                    console.log(`  [STOP] 페이지 ${pageNum}에서 차단 감지`);
                    break;
                }

                await page.waitForTimeout(2000);
            }

            await browser.close();

            const successCount = results.filter(r => r.success).length;
            console.log(`\n  [결과] ${successCount}/${results.length} 페이지 성공`);

            return {
                success: successCount > 0,
                cookieFile,
                results,
                successRate: successCount / results.length
            };

        } catch (error) {
            console.error(`  [ERROR] ${error.message}`);
            throw error;
        }
    }
}

module.exports = BrowserModule;
