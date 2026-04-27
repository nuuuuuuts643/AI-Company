#!/usr/bin/env node
// scripts/check_mobile_layout.js
// 目的: モバイル幅 (375px / iPhone SE) で frontend ページを描画し、
// 横スクロールが発生していないか (scrollWidth <= innerWidth) を物理確認する。
// 失敗パターン: 固定幅エレメント、はみ出し画像、長い URL の折り返し抜け、padding 計算ミスなど。
//
// 使い方:
//   node scripts/check_mobile_layout.js
//   node scripts/check_mobile_layout.js --pages=index.html,mypage.html
//
// 環境変数:
//   FRONTEND_DIR  : frontend ディレクトリのパス (default: projects/P003-news-timeline/frontend)
//   PUPPETEER_EXECUTABLE_PATH : 既存 Chrome バイナリ (puppeteer の bundled chromium 不使用時)
//
// exit code: 0=合格, 1=overflow 検出, 2=実行エラー

'use strict';

const http = require('http');
const fs = require('fs');
const path = require('path');

const REPO_ROOT = path.resolve(__dirname, '..');
const FRONTEND_DIR = process.env.FRONTEND_DIR
  ? path.resolve(process.env.FRONTEND_DIR)
  : path.join(REPO_ROOT, 'projects', 'P003-news-timeline', 'frontend');

const VIEWPORT_WIDTH = 375;
const VIEWPORT_HEIGHT = 667;
const TOLERANCE_PX = 1; // sub-pixel rounding 用

// 検査対象ページ。topic/storymap は detail.js 経由 fetch 失敗で空表示になるため
// レイアウト検証としてはまず静的構造の主要ページを対象にする。
const DEFAULT_PAGES = [
  'index.html',
  'mypage.html',
  'catchup.html',
  'about.html',
  'storymap.html',
];

function parseArgs(argv) {
  const out = { pages: DEFAULT_PAGES };
  for (const a of argv.slice(2)) {
    const m = a.match(/^--pages=(.+)$/);
    if (m) out.pages = m[1].split(',').map(s => s.trim()).filter(Boolean);
  }
  return out;
}

function mimeFor(p) {
  const ext = path.extname(p).toLowerCase();
  return {
    '.html': 'text/html; charset=utf-8',
    '.js': 'application/javascript; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.svg': 'image/svg+xml',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.webp': 'image/webp',
    '.ico': 'image/x-icon',
  }[ext] || 'application/octet-stream';
}

function startServer(rootDir) {
  return new Promise((resolve, reject) => {
    const server = http.createServer((req, res) => {
      try {
        let url = decodeURIComponent((req.url || '/').split('?')[0]);
        if (url.endsWith('/')) url += 'index.html';
        const filePath = path.join(rootDir, url);
        if (!filePath.startsWith(rootDir)) {
          res.writeHead(403); res.end(); return;
        }
        if (!fs.existsSync(filePath) || !fs.statSync(filePath).isFile()) {
          // API パス (/api/*) は空オブジェクトで応答してフロントを死なせない
          if (url.startsWith('/api/')) {
            res.writeHead(200, { 'Content-Type': 'application/json' });
            res.end('{"topics":[],"updatedAt":"1970-01-01T00:00:00Z"}');
            return;
          }
          res.writeHead(404); res.end(); return;
        }
        res.writeHead(200, { 'Content-Type': mimeFor(filePath) });
        fs.createReadStream(filePath).pipe(res);
      } catch (e) {
        res.writeHead(500); res.end(String(e));
      }
    });
    server.listen(0, '127.0.0.1', () => {
      const { port } = server.address();
      resolve({ server, port });
    });
    server.on('error', reject);
  });
}

async function main() {
  const args = parseArgs(process.argv);

  if (!fs.existsSync(FRONTEND_DIR)) {
    console.error(`[check_mobile_layout] FRONTEND_DIR not found: ${FRONTEND_DIR}`);
    process.exit(2);
  }

  let puppeteer;
  try {
    // P003 の node_modules を最優先で探索 (CI と local の差異を吸収)
    const candidatePaths = [
      path.join(REPO_ROOT, 'projects', 'P003-news-timeline', 'node_modules'),
      path.join(REPO_ROOT, 'node_modules'),
    ];
    let resolved;
    for (const p of candidatePaths) {
      try { resolved = require.resolve('puppeteer', { paths: [p] }); break; } catch (_) {}
    }
    if (!resolved) resolved = require.resolve('puppeteer'); // fallback
    puppeteer = require(resolved);
  } catch (e) {
    console.error('[check_mobile_layout] puppeteer not installed.');
    console.error('[check_mobile_layout] Run: cd projects/P003-news-timeline && npm install');
    console.error('[check_mobile_layout] error:', e.message);
    process.exit(2);
  }

  const { server, port } = await startServer(FRONTEND_DIR);
  const baseUrl = `http://127.0.0.1:${port}`;
  console.log(`[check_mobile_layout] serving ${FRONTEND_DIR} at ${baseUrl}`);

  let browser;
  const overflows = [];
  try {
    const launchOpts = {
      headless: 'new',
      args: ['--no-sandbox', '--disable-setuid-sandbox'],
    };
    if (process.env.PUPPETEER_EXECUTABLE_PATH) {
      launchOpts.executablePath = process.env.PUPPETEER_EXECUTABLE_PATH;
    }
    browser = await puppeteer.launch(launchOpts);

    for (const pageName of args.pages) {
      const page = await browser.newPage();
      await page.setViewport({ width: VIEWPORT_WIDTH, height: VIEWPORT_HEIGHT, deviceScaleFactor: 2 });
      // 外部リクエスト (広告・解析) は遮断してテスト安定化
      await page.setRequestInterception(true);
      page.on('request', (req) => {
        const u = req.url();
        if (u.startsWith(baseUrl)) return req.continue();
        // データ系パスは継続（local server が空応答する）
        if (u.includes('/api/')) return req.continue();
        return req.abort();
      });
      const url = `${baseUrl}/${pageName}`;
      try {
        await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 15000 });
        // body 描画後のレイアウト確定まで少し待つ
        await new Promise(r => setTimeout(r, 500));
        const measure = await page.evaluate(() => {
          const doc = document.documentElement;
          const inner = window.innerWidth;
          const scroll = doc.scrollWidth;
          // 個別オーバーフロー要素を抽出 (上位 5 件)
          const offenders = [];
          const all = document.body ? document.body.querySelectorAll('*') : [];
          for (const el of all) {
            const r = el.getBoundingClientRect();
            if (r.right > inner + 1) {
              offenders.push({
                tag: el.tagName.toLowerCase(),
                cls: (el.className && typeof el.className === 'string') ? el.className.slice(0, 60) : '',
                id: el.id || '',
                right: Math.round(r.right),
                width: Math.round(r.width),
              });
              if (offenders.length >= 5) break;
            }
          }
          return { inner, scroll, offenders };
        });
        const diff = measure.scroll - measure.inner;
        const ok = diff <= TOLERANCE_PX;
        const mark = ok ? '✅' : '❌';
        console.log(`${mark} ${pageName}  inner=${measure.inner}  scroll=${measure.scroll}  diff=${diff}`);
        if (!ok) {
          overflows.push({ page: pageName, ...measure, diff });
          for (const o of measure.offenders) {
            console.log(`   overflow: <${o.tag}${o.id ? '#' + o.id : ''}${o.cls ? '.' + o.cls.split(/\s+/).join('.') : ''}> right=${o.right}px width=${o.width}px`);
          }
        }
      } finally {
        await page.close();
      }
    }
  } catch (e) {
    console.error('[check_mobile_layout] runtime error:', e.message);
    process.exitCode = 2;
  } finally {
    if (browser) await browser.close();
    server.close();
  }

  if (overflows.length > 0) {
    console.error(`[check_mobile_layout] FAIL: ${overflows.length} page(s) have horizontal overflow at ${VIEWPORT_WIDTH}px viewport`);
    process.exit(1);
  }
  console.log(`[check_mobile_layout] PASS: ${args.pages.length} page(s) fit within ${VIEWPORT_WIDTH}px viewport`);
  process.exit(0);
}

main().catch((e) => {
  console.error('[check_mobile_layout] fatal:', e);
  process.exit(2);
});
