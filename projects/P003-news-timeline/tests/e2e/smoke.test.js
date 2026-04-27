// e2e/smoke.test.js — トップページの最低限のスモークテスト
//
// 何を保証するか:
//  - index.html が読み込めて <title> が空でない
//  - app.js / config.js が構文エラーで死んでいない（ロード後 console.error が出ないこと）
//  - #topics-grid 要素が存在する（レイアウトの根幹）
//  - 致命的な JS エラーが発生していない
//
// テスト戦略:
//  - frontend/ を node 標準 http で 0.0.0.0:0（任意ポート）に立てる
//  - puppeteer で開いて DOM 状態を確認する
//  - 外部 API（topics.json）への fetch は失敗しても OK（CI ネット環境を要件にしない）

const test = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');

const FRONTEND_DIR = path.resolve(__dirname, '../../frontend');

// 簡易静的サーバ（テスト中だけ立てる）
function startServer() {
  const server = http.createServer((req, res) => {
    let urlPath = decodeURIComponent(req.url.split('?')[0]);
    if (urlPath === '/' || urlPath === '') urlPath = '/index.html';
    const filePath = path.join(FRONTEND_DIR, urlPath);
    // ディレクトリトラバーサル防止
    if (!filePath.startsWith(FRONTEND_DIR)) {
      res.writeHead(403); res.end(); return;
    }
    fs.readFile(filePath, (err, data) => {
      if (err) {
        res.writeHead(404, { 'Content-Type': 'text/plain' });
        res.end('Not Found');
        return;
      }
      const ext = path.extname(filePath).toLowerCase();
      const contentTypes = {
        '.html': 'text/html; charset=utf-8',
        '.js':   'application/javascript; charset=utf-8',
        '.css':  'text/css; charset=utf-8',
        '.json': 'application/json; charset=utf-8',
        '.svg':  'image/svg+xml',
        '.png':  'image/png',
        '.ico':  'image/x-icon',
      };
      res.writeHead(200, { 'Content-Type': contentTypes[ext] || 'application/octet-stream' });
      res.end(data);
    });
  });
  return new Promise((resolve) => {
    server.listen(0, '127.0.0.1', () => {
      const { port } = server.address();
      resolve({ server, baseUrl: `http://127.0.0.1:${port}` });
    });
  });
}

test('index.html スモーク: タイトル / 主要 DOM / JS エラーなし', async (t) => {
  const puppeteer = require('puppeteer');
  const { server, baseUrl } = await startServer();

  let browser;
  try {
    browser = await puppeteer.launch({
      headless: true,
      args: ['--no-sandbox', '--disable-setuid-sandbox'],
    });
    const page = await browser.newPage();

    const consoleErrors = [];
    page.on('pageerror', (err) => consoleErrors.push(`pageerror: ${err.message}`));
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        const text = msg.text();
        // 外部 API/CORS の失敗は CI ネットレス環境では許容
        if (/topics fetch failed|Failed to fetch|net::|CORS|fetch\(/i.test(text)) return;
        // 広告タグの読み込み失敗は許容（テスト用静的サーバには無い）
        if (/adsbygoogle|admax|gsi\/client|cloudflareinsights/i.test(text)) return;
        consoleErrors.push(`console.error: ${text}`);
      }
    });

    await page.goto(baseUrl + '/index.html', { waitUntil: 'domcontentloaded', timeout: 15000 });

    const title = await page.title();
    assert.ok(title && title.length > 0, 'title is empty');
    assert.match(title, /Flotopic/, 'title should contain Flotopic');

    // 主要 DOM
    const grid = await page.$('#topics-grid');
    assert.ok(grid, '#topics-grid not found');

    // JS が壊れていないこと
    if (consoleErrors.length > 0) {
      assert.fail(`致命的な JS エラーが検出された:\n${consoleErrors.join('\n')}`);
    }
  } finally {
    if (browser) await browser.close();
    server.close();
  }
});

test('about.html スモーク: 静的ページが落ちずに開ける', async (t) => {
  const puppeteer = require('puppeteer');
  const { server, baseUrl } = await startServer();

  let browser;
  try {
    browser = await puppeteer.launch({
      headless: true,
      args: ['--no-sandbox', '--disable-setuid-sandbox'],
    });
    const page = await browser.newPage();
    await page.goto(baseUrl + '/about.html', { waitUntil: 'domcontentloaded', timeout: 15000 });
    const title = await page.title();
    assert.ok(title && title.length > 0, 'about.html title is empty');
  } finally {
    if (browser) await browser.close();
    server.close();
  }
});
