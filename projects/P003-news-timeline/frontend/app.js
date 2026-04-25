// app.js — メイン。auth.js / favorites.js / comments.js を先に読み込むこと。
// 読み込み順: config.js → js/auth.js → js/favorites.js → js/comments.js → app.js

// ── 設定定数 ──────────────────────────────────────────────────
const CONFIG = {
  HOT_STRIP_HOURS: 2,                   // 今急上昇中セクションの対象時間（時間）
  NEW_BADGE_HOURS: 1,                   // NEWバッジを表示する最大経過時間（時間）
  AD_CARD_INTERVAL: 9,                  // 広告を挿入する間隔（3の倍数にすること）
  FRESHNESS_INTERVAL_MS: 60000,         // 鮮度表示テキストの更新間隔（ミリ秒）
  TOPICS_PER_PAGE: 20,                  // 1ページに表示するトピック数
  REFRESH_INTERVAL_MS: 5 * 60 * 1000,  // トピック一覧の自動更新間隔（ミリ秒）
  MAX_GENRE_RATIO: 0.4,                 // 1ジャンルが全体に占める最大割合（多様性制御）
};

// ── ローカルストレージ キー定数 ──────────────────────────────
const LS_KEYS = {
  FAVORITES:     'flotopic_favorites',
  HISTORY:       'flotopic_history',
  AVATAR:        'flotopic_avatar',
  PROFILE_SET:   'flotopic_profile_set',
  DARK_MODE:     'flotopic_dark',
  PREFS:         'flotopic_prefs',
  PWA_DISMISSED: 'pwa_dismissed',
};

function showToast(msg, duration = 3000) {
  let el = document.getElementById('flotopic-toast');
  if (!el) {
    el = document.createElement('div');
    el.id = 'flotopic-toast';
    el.style.cssText = 'position:fixed;bottom:24px;left:50%;transform:translateX(-50%) translateY(60px);background:#1a1a1a;color:#fff;padding:10px 20px;border-radius:24px;font-size:.88rem;font-weight:600;z-index:9999;opacity:0;transition:all .3s ease;pointer-events:none;white-space:nowrap;';
    document.body.appendChild(el);
  }
  el.textContent = msg;
  el.style.opacity = '1';
  el.style.transform = 'translateX(-50%) translateY(0)';
  clearTimeout(el._tid);
  el._tid = setTimeout(() => {
    el.style.opacity = '0';
    el.style.transform = 'translateX(-50%) translateY(60px)';
  }, duration);
}

/**
 * エラーバナーを5秒間表示する
 * @param {string} message - 表示するエラーメッセージ
 */
function showErrorBanner(message) {
  const banner = document.getElementById('error-banner');
  if (banner) {
    banner.textContent = message;
    banner.style.display = 'block';
    setTimeout(() => { banner.style.display = 'none'; }, 5000);
  }
}

const STATUS_LABEL = { rising:'🔥 急上昇', peak:'⚡ 注目中', declining:'📉 落ち着き' };

function cleanSummary(s) {
  if (!s) return s;
  return s
    .replace(/^#{1,3}\s+.+?\n+/gm, '')
    .replace(/^[-*]\s+/gm, '')
    .replace(/^\d+\.\s+/gm, '')
    .replace(/\n{2,}/g, ' ')
    .replace(/\n/g, ' ')
    .trim();
}

const GENRES = ['総合','政治','ビジネス','株・金融','テクノロジー','スポーツ','エンタメ','科学','健康','国際'];
const GENRE_EMOJI = {'政治':'🏛️','ビジネス':'💼','株・金融':'📈','テクノロジー':'💻','スポーツ':'⚽','エンタメ':'🎬','科学':'🔬','健康':'💊','国際':'🌏','総合':'📰'};

// ===== パーソナライズ =====

function recordTopicView(topic) {
  if (!topic || !topic.topicId) return;
  try {
    let history = JSON.parse(localStorage.getItem(LS_KEYS.HISTORY) || '[]');
    history = history.filter(h => h.topicId !== topic.topicId);
    history.unshift({ topicId: topic.topicId, title: topic.generatedTitle || topic.title || '', viewedAt: Date.now() });
    if (history.length > 20) history = history.slice(0, 20);
    localStorage.setItem(LS_KEYS.HISTORY, JSON.stringify(history));
  } catch {}
}
function loadPrefs() {
  try { return JSON.parse(localStorage.getItem(LS_KEYS.PREFS) || '{}'); } catch { return {}; }
}
function savePrefs(prefs) {
  try { localStorage.setItem(LS_KEYS.PREFS, JSON.stringify(prefs)); } catch {}
}

// ===== 共通ユーティリティ =====
const _prefs = loadPrefs();
let allTopics = [], currentStatus = _prefs.status || 'all', currentGenre = _prefs.genre || '総合', currentSearch = '';
let currentPage = 1;
let lastFetchTime = null;
let _nativeAdIdx = -1;

function esc(s) {
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

const SOURCE_DOMAIN_MAP = {
  'NHK': 'nhk.or.jp',
  'ITmedia': 'itmedia.co.jp',
  '読売新聞': 'yomiuri.co.jp',
  '毎日新聞': 'mainichi.jp',
  '朝日新聞': 'asahi.com',
  '日本経済新聞': 'nikkei.com',
  '東洋経済': 'toyokeizai.net',
  'ダイヤモンド': 'diamond.jp',
  '産経新聞': 'sankei.com',
  'Yahoo!ニュース': 'news.yahoo.co.jp',
  'PRESIDENT Online': 'president.jp',
  '文春オンライン': 'bunshun.jp',
  'Business Insider Japan': 'businessinsider.jp',
  'Forbes Japan': 'forbesjapan.com',
  'GIGAZINE': 'gigazine.net',
  'ASCII.jp': 'ascii.jp',
  'CNET Japan': 'japan.cnet.com',
  'PC Watch': 'pc.watch.impress.co.jp',
  'ケータイWatch': 'k-tai.watch.impress.co.jp',
  'livedoorニュース': 'livedoor.com',
  'BuzzFeed Japan': 'buzzfeed.com',
  'Gizmodo Japan': 'gizmodo.jp',
  '47NEWS': 'www.47news.jp',
  '首相官邸': 'kantei.go.jp',
  'TBS NEWS DIG': 'newsdig.tbs.co.jp',
  'FNN プライムオンライン': 'fnn.jp',
  'テレ朝news': 'news.tv-asahi.co.jp',
  '日テレNEWS': 'news.ntv.co.jp',
  'NHKニュース': 'nhk.or.jp',
};
function srcFaviconUrl(source) {
  if (!source) return '';
  const domain = SOURCE_DOMAIN_MAP[source] || (source.includes('.') && !source.includes(' ') ? source : null);
  if (!domain) return '';
  return `https://www.google.com/s2/favicons?domain=${encodeURIComponent(domain)}&sz=16`;
}
function srcFaviconImg(source) {
  const url = srcFaviconUrl(source);
  if (!url) return '';
  return `<img class="source-favicon" src="${url}" alt="" width="12" height="12" onerror="this.style.display='none'">`;
}

function genreEmoji(genre) { return GENRE_EMOJI[genre] || '📰'; }
function fmtDate(s) {
  if (!s) return '';
  try { return new Date(s).toLocaleString('ja-JP',{month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit'}); }
  catch { return s; }
}
function apiUrl(path) { return API_BASE + path + '.json'; }

// ===== 一覧ページ =====

/**
 * topics.json をフェッチし、キーワードストリップを描画してトピック配列を返す
 * @returns {Promise<Array>} トピックの配列
 */
async function loadTopics() {
  const r = await fetch(apiUrl('topics'));
  const data = await r.json();
  renderKeywordStrip(data.trendingKeywords || []);
  return data.topics || [];
}

function renderKeywordStrip(keywords) {
  const strip = document.getElementById('keyword-strip');
  if (!strip) return;
  if (!keywords || !keywords.length) { strip.style.display = 'none'; return; }
  strip.style.display = 'flex';
  strip.innerHTML = '<span class="keyword-strip-label">注目</span>' +
    keywords.slice(0, 12).map(kw => {
      const word = typeof kw === 'string' ? kw : (kw.keyword || '');
      return word ? `<button class="kw-chip" data-kw="${esc(word)}">#${esc(word)}</button>` : '';
    }).join('');
  strip.querySelectorAll('.kw-chip').forEach(btn => {
    btn.addEventListener('click', () => {
      const input = document.getElementById('search-input');
      if (input) { input.value = btn.dataset.kw; currentSearch = btn.dataset.kw; currentPage = 1; renderTopics(allTopics); }
    });
  });
}

/**
 * NEWバッジのHTMLを生成する（lastUpdated が NEW_BADGE_HOURS 以内の場合のみ表示）
 * @param {Object} t - トピックオブジェクト
 * @returns {string} バッジのHTML文字列
 */
function toUnixSec(v) {
  if (!v) return 0;
  const n = Number(v);
  if (!isNaN(n) && n > 1e9) return n;
  const t = new Date(v).getTime();
  return isNaN(t) ? 0 : t / 1000;
}
function renderBadges(t) {
  const ts = toUnixSec(t.lastUpdated);
  const isNew = ts > 0 && ts >= Date.now() / 1000 - CONFIG.NEW_BADGE_HOURS * 3600;
  return isNew ? '<span class="card-new-badge">NEW</span>' : '';
}

/**
 * カードのメタ情報HTML（記事件数・読書時間・ソース数・ジャンル・更新日時）を生成する
 * @param {Object} t - トピックオブジェクト
 * @returns {string} メタ情報のHTML文字列
 */
function renderCardMeta(t) {
  const readMins = Math.min(30, Math.max(1, Math.round((t.articleCount || 1) * 0.8)));
  const srcCount = t.uniqueSourceCount || (t.sources ? t.sources.length : 0);
  const srcLabel = srcCount > 1
    ? `<span class="src-count-label" title="${srcCount}社のソースが報道">📰 ${srcCount}社が報道</span>`
    : (srcCount === 1 ? `<span class="src-count-label src-single" title="1社のみの報道">📰 1社のみ</span>` : '');
  const genres = t.genres || [t.genre || '総合'];
  return `
    <div class="topic-meta">
      <span class="article-count">📄 ${t.articleCount}件 · 約${readMins}分</span>
      ${srcLabel}
      ${genres.map(g => `<span class="genre-tag">${esc(g)}</span>`).join('')}
      <span>${fmtDate(t.lastUpdated)}</span>
    </div>`;
}

/**
 * 信頼性シグナルHTML（⚠情報確認中・情報精査中バッジ）を生成する
 * 断定せず判断材料を提供する設計（法的リスク低減）
 * @param {Object} t - トピックオブジェクト
 * @returns {string} シグナルのHTML文字列（シグナルなしの場合は空文字列）
 */
function renderReliabilitySignal(t) {
  const reliabilityBadge = (t.reliability === 'unverified' && (t.score || 0) < 80)
    ? `<span class="reliability-badge" title="複数の記事で不確実な表現が多く見られます">⚠️ 情報確認中</span>`
    : '';
  const conflictBadge = t.hasConflict
    ? `<span class="conflict-badge" title="記事間で数値に食い違いが見られる場合があります">情報精査中</span>`
    : '';
  if (!reliabilityBadge && !conflictBadge) return '';
  return `<div class="reliability-signals">${reliabilityBadge}${conflictBadge}</div>`;
}

/**
 * 1枚のトピックカードHTML文字列を生成する
 * AD_CARD_INTERVAL 枚ごとに広告カードも末尾に追加する
 * @param {Object} t - トピックオブジェクト
 * @param {number} i - ゼロ始まりのインデックス（広告挿入判定に使用）
 * @returns {string} カードHTML文字列
 */
function renderTopicCard(t, i) {
  const primaryGenre = (t.genres || [t.genre || '総合'])[0];
  const thumbHtml = t.imageUrl
    ? `<div class="card-thumb"><img class="card-thumb-img" src="${esc(t.imageUrl)}" alt="" loading="lazy" onerror="this.parentNode.innerHTML='<div class=\\'card-thumb-placeholder ${esc(t.status)}\\'>${genreEmoji(primaryGenre)}</div>'"></div>`
    : `<div class="card-thumb"><div class="card-thumb-placeholder ${esc(t.status)}">${genreEmoji(primaryGenre)}</div></div>`;
  const isFav    = userFavorites.has(t.topicId);
  const isViewed = viewedTopics.has(t.topicId);
  return `
    <div class="topic-card-wrapper" style="position:relative;">
      ${renderBadges(t)}
      <a class="topic-card ${esc(t.status)}${isViewed ? ' viewed' : ''}" href="topic.html?id=${esc(t.topicId)}" data-tid="${esc(t.topicId)}">
        ${thumbHtml}
        <div class="card-body">
          <div class="topic-status ${esc(t.status)}">${STATUS_LABEL[t.status] || t.status}</div>
          <h3>${esc(t.generatedTitle || t.title)}</h3>
          ${t.generatedSummary ? `<p class="card-summary">${esc(t.generatedSummary)}</p>` : ''}
          ${renderCardMeta(t)}
          ${renderReliabilitySignal(t)}
        </div>
      </a>
      <button class="fav-btn ${isFav ? 'fav-active' : ''}" data-topic-id="${esc(t.topicId)}" title="${isFav ? 'お気に入りを解除' : 'お気に入りに追加'}" aria-label="お気に入り">♥</button>
    </div>`;
}

/**
 * ジャンル多様性を確保したトピックリストを返す
 * 1ジャンルが全体の CONFIG.MAX_GENRE_RATIO を超えないようにする
 * 上限を超えたトピックは末尾に回し、表示は維持する
 * @param {Array} topics - ソート済みトピック配列
 * @param {boolean} genreFiltered - ジャンルフィルターが選択中かどうか
 * @returns {Array} 多様性を確保したトピック配列
 */
function applyGenreDiversity(topics, genreFiltered) {
  if (genreFiltered) return topics; // フィルター選択中はそのまま返す
  if (!topics.length) return topics;

  const maxPerGenre = Math.ceil(topics.length * CONFIG.MAX_GENRE_RATIO);
  const genreCount = {};
  const result = [];
  const overflow = []; // 上限超えのトピックは末尾に回す

  for (const t of topics) {
    const genre = (t.genres && t.genres[0]) || t.genre || 'その他';
    genreCount[genre] = (genreCount[genre] || 0) + 1;
    if (genreCount[genre] <= maxPerGenre) {
      result.push(t);
    } else {
      overflow.push(t);
    }
  }

  return [...result, ...overflow];
}

function renderTopics(topics) {
  const grid = document.getElementById('topics-grid');
  if (!grid) return;
  let list = topics;
  if (currentSearch) {
    const q = currentSearch.toLowerCase();
    list = list.filter(t => (t.generatedTitle||t.title||'').toLowerCase().includes(q));
  }
  if (currentStatus !== 'all')    list = list.filter(t => t.status === currentStatus);
  if (currentGenre  !== '総合') list = list.filter(t => (t.genres||[t.genre]).includes(currentGenre));
  if (currentStatus === 'all')    list = list.filter(t => t.lifecycleStatus !== 'archived');
  if (showFavsOnly) list = list.filter(t => userFavorites.has(t.topicId));

  // ジャンル多様性を確保（テック偏り防止）
  list = applyGenreDiversity(list, currentGenre !== '総合');

  const lmContainer = document.getElementById('load-more-container');
  if (!list.length) {
    grid.innerHTML = showFavsOnly
      ? '<div class="loading">お気に入りのトピックがありません</div>'
      : '<div class="loading">該当するトピックがありません</div>';
    if (lmContainer) lmContainer.innerHTML = '';
    return;
  }

  const pageList = list.slice(0, currentPage * CONFIG.TOPICS_PER_PAGE);
  grid.innerHTML = pageList.reduce((html, t, i) => {
    if ((i + 1) % CONFIG.AD_CARD_INTERVAL !== 0) return html + renderTopicCard(t, i);
    const adHtml = `<div class="topic-card-wrapper ad-card-wrapper">
      <div class="ad-grid-card">
        <span class="ad-grid-badge">広告</span>
        <div class="admax-iframe-slot"></div>
      </div>
    </div>`;
    return html + renderTopicCard(t, i) + adHtml;
  }, '');

  // 忍者AdMax: iframeのsrcdocで同期実行（document.write対応）
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  const iframeBg = isDark ? '#1e2035' : '#ffffff';
  grid.querySelectorAll('.admax-iframe-slot').forEach(slot => {
    const iframe = document.createElement('iframe');
    iframe.scrolling = 'no';
    iframe.setAttribute('frameborder', '0');
    iframe.style.cssText = 'width:100%;height:160px;border:none;display:block;';
    iframe.setAttribute('sandbox', 'allow-scripts allow-popups allow-popups-to-escape-sandbox');
    iframe.srcdoc = `<!DOCTYPE html><html><head><style>body{margin:0;padding:4px;overflow:hidden;background:${iframeBg};display:flex;align-items:center;justify-content:center;}</style></head><body><script type="text/javascript" src="https://adm.shinobi.jp/s/570fe6c87677ba7c5417119c60ca979d"><\/script></body></html>`;
    slot.appendChild(iframe);
  });

  if (lmContainer) {
    if (pageList.length < list.length) {
      const remaining = list.length - pageList.length;
      lmContainer.innerHTML = `<button class="load-more-btn">もっと見る（残り${remaining}件）</button>`;
      lmContainer.querySelector('.load-more-btn').addEventListener('click', () => { currentPage++; renderTopics(allTopics); });
    } else {
      lmContainer.innerHTML = '';
    }
  }

  // お気に入りボタン + 既読マーク
  grid.querySelectorAll('.fav-btn').forEach(btn => {
    btn.addEventListener('click', e => {
      e.preventDefault();
      e.stopPropagation();
      toggleFavorite(btn.dataset.topicId, btn);
    });
  });
  grid.querySelectorAll('.topic-card[data-tid]').forEach(a => {
    a.addEventListener('click', () => {
      markViewed(a.dataset.tid);
      a.classList.add('viewed');
    });
  });

  showTrendingBanner(allTopics);
}

function buildFilters() {
  const sbar = document.getElementById('status-filter');
  if (sbar) {
    const btns = [{k:'all',l:'総合'},{k:'rising',l:'🔥 急上昇'},{k:'peak',l:'⚡ 注目中'},{k:'declining',l:'📉 落ち着き'}];
    sbar.innerHTML = btns.map(b=>`<button class="filter-btn ${currentStatus===b.k?'active':''}" data-status="${b.k}">${b.l}</button>`).join('');
    sbar.querySelectorAll('.filter-btn').forEach(btn => btn.addEventListener('click', () => {
      sbar.querySelectorAll('.filter-btn').forEach(b=>b.classList.remove('active'));
      btn.classList.add('active'); currentStatus = btn.dataset.status;
      savePrefs({...loadPrefs(), status: currentStatus});
      currentPage = 1; renderTopics(allTopics);
    }));
  }
  const gbar = document.getElementById('genre-filter');
  if (gbar) {
    gbar.innerHTML = GENRES.map(g=>`<button class="filter-btn genre-btn ${currentGenre===g?'active':''}" data-genre="${g}">${g}</button>`).join('');
    gbar.querySelectorAll('.genre-btn').forEach(btn => btn.addEventListener('click', () => {
      gbar.querySelectorAll('.genre-btn').forEach(b=>b.classList.remove('active'));
      btn.classList.add('active'); currentGenre = btn.dataset.genre;
      savePrefs({...loadPrefs(), genre: currentGenre});
      currentPage = 1; renderTopics(allTopics);
    }));
  }
}

const WMO = {
  0:'☀️ 快晴',1:'🌤 晴れ',2:'⛅ 曇り時々晴れ',3:'☁️ 曇り',
  45:'🌫 霧',48:'🌫 霧',
  51:'🌦 小雨',53:'🌧 雨',55:'🌧 強雨',
  61:'🌦 小雨',63:'🌧 雨',65:'🌧 強雨',
  71:'🌨 小雪',73:'❄️ 雪',75:'❄️ 大雪',
  80:'🌦 にわか雨',81:'🌧 にわか雨',82:'⛈ 激しいにわか雨',
  95:'⛈ 雷雨',96:'⛈ 雷雨',99:'⛈ 激しい雷雨',
};
async function loadWeather() {
  const el = document.getElementById('weather-widget');
  if (!el) return;
  try {
    const url = `https://api.open-meteo.com/v1/forecast?latitude=35.68&longitude=139.69&current=temperature_2m,weather_code&timezone=Asia%2FTokyo&forecast_days=1`;
    const r = await fetch(url);
    const d = await r.json();
    const temp = Math.round(d.current.temperature_2m);
    const desc = WMO[d.current.weather_code] || '―';
    el.innerHTML = `<span class="weather-city">東京</span><span class="weather-desc">${desc}</span><span class="weather-temp">${temp}°C</span>`;
  } catch { el.textContent = ''; }
}

function setupSearch() {
  const input = document.getElementById('search-input');
  if (!input) return;
  input.addEventListener('input', () => {
    currentSearch = input.value.trim();
    currentPage = 1;
    renderTopics(allTopics);
  });
}

/**
 * トピック一覧をフェッチしてUIを更新する（REFRESH_INTERVAL_MS ごとに自動呼び出し）
 * @returns {Promise<void>}
 */
async function refreshTopics() {
  try {
    const raw = await loadTopics();
    // velocityScore に時間減衰を適用してソート（古いトピックを下に送る）
    const nowSec2 = Date.now() / 1000;
    const decayedVS = t => {
      const vs  = Number(t.velocityScore || 0);
      const age = nowSec2 - toUnixSec(t.lastUpdated); // 秒
      if (age <= 0 || !toUnixSec(t.lastUpdated)) return vs;
      const h = age / 3600;
      // 6h未満: 100% / 12h: 85% / 24h: 65% / 48h: 40% / 72h以上: 20%
      const decay = h < 6  ? 1.0
                  : h < 12 ? 0.85
                  : h < 24 ? 0.65
                  : h < 48 ? 0.40
                  :          0.20;
      return vs * decay;
    };
    allTopics = raw.sort((a, b) => {
      const vs = decayedVS(b) - decayedVS(a);
      if (Math.abs(vs) > 0.5) return vs;
      const sc = Number(b.score || 0) - Number(a.score || 0);
      if (sc !== 0) return sc;
      return (b.lastUpdated || '').localeCompare(a.lastUpdated || '');
    });
    lastFetchTime = Date.now();
    updateFreshnessDisplay();
    renderHotStrip(allTopics);
    renderTopics(allTopics);
  } catch(e) {
    console.error(e);
    showErrorBanner('データの読み込みに失敗しました。しばらくしてから再度お試しください。');
  }
}

function updateFreshnessDisplay() {
  const el = document.getElementById('last-updated');
  if (!el || !lastFetchTime) return;
  const diffMin = Math.floor((Date.now() - lastFetchTime) / 60000);
  const diffH   = Math.floor(diffMin / 60);
  const diffD   = Math.floor(diffH   / 24);
  if (diffMin < 1)       el.textContent = '🔄 たった今更新';
  else if (diffMin < 60) el.textContent = `🔄 ${diffMin}分前に更新`;
  else if (diffH  < 24)  el.textContent = `🔄 ${diffH}時間前に更新`;
  else                   el.textContent = `🔄 ${diffD}日前に更新`;
}

/**
 * 「今急上昇中」ストリップを描画する
 * HOT_STRIP_HOURS 以内に更新されたトピックを velocityScore 降順で最大5件表示する
 * @param {Array} topics - 全トピックの配列
 */
function renderHotStrip(topics) {
  let strip = document.getElementById('hot-strip');
  if (!strip) {
    const grid = document.getElementById('topics-grid');
    if (!grid) return;
    strip = document.createElement('section');
    strip.id = 'hot-strip';
    strip.className = 'hot-strip';
    grid.parentNode.insertBefore(strip, grid);
  }
  const nowSec = Date.now() / 1000;
  const hot = (topics || [])
    .filter(t => t.lifecycleStatus !== 'archived' && toUnixSec(t.lastUpdated) >= nowSec - CONFIG.HOT_STRIP_HOURS * 3600)
    .sort((a, b) => Number(b.velocityScore || b.score || 0) - Number(a.velocityScore || a.score || 0))
    .slice(0, 5);
  if (!hot.length) { strip.remove(); return; }
  strip.style.display = 'block';
  strip.innerHTML = `
    <div class="hot-strip-header">🔥 今急上昇中</div>
    <div class="hot-strip-chips">
      ${hot.map(t => {
        const cnt = t.articleCount || 0;
        return `<a href="topic.html?id=${esc(t.topicId)}" class="hot-chip">${esc(t.generatedTitle || t.title)}${cnt ? `（${cnt}件）` : ''}</a>`;
      }).join('')}
    </div>`;
}

function showTrendingBanner(topics) {
  const grid = document.getElementById('topics-grid');
  if (!grid) return;
  const existing = document.getElementById('trending-banner');
  if (existing) existing.remove();
  const rising = (topics || [])
    .filter(t => t.status === 'rising' && Number(t.score || 0) >= 30)
    .slice(0, 3);
  if (!rising.length) return;
  const links = rising.map(t =>
    `<a href="topic.html?id=${esc(t.topicId)}" class="trending-link">${esc(t.generatedTitle || t.title)}</a>`
  ).join(' <span class="trending-sep">/</span> ');
  const banner = document.createElement('div');
  banner.id = 'trending-banner';
  banner.className = 'trending-banner';
  banner.innerHTML = `<span class="trending-label">🔥 急上昇:</span> ${links}`;
  grid.parentNode.insertBefore(banner, grid);
}

// ===== 詳細ページ（detail.js に分割）=====
// renderDetail, renderDiscovery, trackView, updateOGP 等は detail.js を参照

// ===== 既読管理 =====
const LS_VIEWED = 'flotopic_viewed';
let viewedTopics = new Set();
function loadViewedTopics() {
  try { viewedTopics = new Set(JSON.parse(localStorage.getItem(LS_VIEWED) || '[]')); } catch {}
}
function markViewed(topicId) {
  viewedTopics.add(topicId);
  try {
    const arr = [...viewedTopics].slice(-200);
    localStorage.setItem(LS_VIEWED, JSON.stringify(arr));
  } catch {}
}
loadViewedTopics();

// ===== ページトップへ戻るボタン =====
function initBackToTop() {
  let btn = document.getElementById('back-to-top');
  if (!btn) {
    btn = document.createElement('button');
    btn.id = 'back-to-top';
    btn.className = 'back-to-top-btn';
    btn.setAttribute('aria-label', 'ページトップへ');
    btn.innerHTML = '↑';
    document.body.appendChild(btn);
  }
  const onScroll = () => btn.classList.toggle('visible', window.scrollY > 400);
  window.addEventListener('scroll', onScroll, { passive: true });
  btn.addEventListener('click', () => window.scrollTo({ top: 0, behavior: 'smooth' }));
}

// ===== スクロール位置復元（一覧→詳細→戻る） =====
function initScrollRestoration() {
  const key = 'flotopic_scroll_pos';
  const saved = sessionStorage.getItem(key);
  if (saved) { requestAnimationFrame(() => { window.scrollTo(0, Number(saved)); sessionStorage.removeItem(key); }); }
  document.addEventListener('click', e => {
    const card = e.target.closest('.topic-card');
    if (card) sessionStorage.setItem(key, String(window.scrollY));
  });
}

// ===== 読書進捗バー（詳細ページ） =====
function initReadingProgress() {
  const bar = document.createElement('div');
  bar.id = 'reading-progress';
  bar.className = 'reading-progress-bar';
  document.body.prepend(bar);
  const update = () => {
    const total = document.documentElement.scrollHeight - window.innerHeight;
    bar.style.width = total > 0 ? `${Math.min(100, window.scrollY / total * 100)}%` : '0%';
  };
  window.addEventListener('scroll', update, { passive: true });
}

// ===== キーボードショートカット =====
function initKeyboardShortcuts() {
  let focusedIdx = -1;
  const getCards = () => [...document.querySelectorAll('.topic-card-wrapper:not(.ad-card-wrapper)')];

  document.addEventListener('keydown', e => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
      if (e.key === 'Escape') { e.target.blur(); return; }
      return;
    }
    switch (e.key) {
      case '/': {
        e.preventDefault();
        const inp = document.getElementById('search-input');
        if (inp) inp.focus();
        break;
      }
      case 'j': case 'ArrowDown': {
        const cards = getCards();
        if (!cards.length) break;
        focusedIdx = Math.min(focusedIdx + 1, cards.length - 1);
        cards[focusedIdx].scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        cards[focusedIdx].querySelector('.topic-card')?.focus();
        break;
      }
      case 'k': case 'ArrowUp': {
        const cards = getCards();
        if (!cards.length) break;
        focusedIdx = Math.max(focusedIdx - 1, 0);
        cards[focusedIdx].scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        cards[focusedIdx].querySelector('.topic-card')?.focus();
        break;
      }
      case 'Enter': {
        const cards = getCards();
        if (focusedIdx >= 0 && cards[focusedIdx]) {
          const a = cards[focusedIdx].querySelector('.topic-card');
          if (a) a.click();
        }
        break;
      }
      case 'f': {
        const btn = document.getElementById('fav-toggle-btn');
        if (btn) btn.click();
        break;
      }
      case 'Escape': {
        const modal = document.getElementById('auth-modal');
        if (modal && modal.style.display !== 'none') { modal.style.display = 'none'; }
        const inp = document.getElementById('search-input');
        if (inp && document.activeElement === inp) inp.blur();
        break;
      }
    }
  });
}

// ===== オフライン検知 =====
function initOfflineDetection() {
  window.addEventListener('offline', () => showToast('オフラインです。一部機能が制限されます。', 5000));
  window.addEventListener('online',  () => showToast('オンラインに復帰しました'));
}

// ===== ボトムナビ アクティブ制御 =====
function initBottomNav() {
  const nav = document.getElementById('bottom-nav');
  if (!nav) return;
  const path = location.pathname;
  const isIndex   = path.endsWith('index.html') || path === '/' || path.endsWith('/');
  const isTopic   = path.includes('topic.html');
  const isMypage  = path.includes('mypage.html');

  const items = {
    'bn-home':    isIndex,
    'bn-search':  isIndex && document.getElementById('search-input') !== null,
    'bn-favs':    false,
    'bn-mypage':  isMypage,
  };

  Object.entries(items).forEach(([id, active]) => {
    const el = document.getElementById(id);
    if (el && active) el.classList.add('active');
  });

  const searchEl = document.getElementById('bn-search');
  if (searchEl) {
    searchEl.addEventListener('click', () => {
      const inp = document.getElementById('search-input');
      if (inp) { inp.focus(); inp.scrollIntoView({ behavior: 'smooth', block: 'center' }); }
      else location.href = 'index.html#search-input';
    });
  }

  const favsEl = document.getElementById('bn-favs');
  if (favsEl) {
    favsEl.addEventListener('click', () => {
      const btn = document.getElementById('fav-toggle-btn');
      if (btn) btn.click();
      else location.href = 'index.html';
    });
  }
}

// ===== スケルトンローダー =====
function showSkeletonCards(gridId = 'topics-grid', count = 6) {
  const grid = document.getElementById(gridId);
  if (!grid) return;
  const skels = Array.from({ length: count }, () => `
    <div class="topic-card-wrapper skel-wrapper">
      <div class="topic-card skel-card">
        <div class="card-thumb skel-thumb skel-pulse"></div>
        <div class="card-body">
          <div class="skel-line skel-pulse" style="width:40%;height:12px;margin-bottom:8px;"></div>
          <div class="skel-line skel-pulse" style="width:90%;height:16px;margin-bottom:6px;"></div>
          <div class="skel-line skel-pulse" style="width:70%;height:16px;margin-bottom:12px;"></div>
          <div class="skel-line skel-pulse" style="width:55%;height:11px;"></div>
        </div>
      </div>
    </div>`).join('');
  grid.innerHTML = skels;
}

// ===== ページ初期化 =====
document.addEventListener('DOMContentLoaded', () => {
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js').catch(err => console.warn('SW registration failed:', err));
  }

  // PWAインストールバナー
  (function initPwaBanner() {
    if (localStorage.getItem(LS_KEYS.PWA_DISMISSED) === '1') return;
    let deferredPrompt = null;
    const banner     = document.getElementById('pwa-install-banner');
    const installBtn = document.getElementById('pwa-install-btn');
    const dismissBtn = document.getElementById('pwa-dismiss-btn');
    window.addEventListener('beforeinstallprompt', e => {
      e.preventDefault(); deferredPrompt = e;
      if (banner) banner.style.display = 'flex';
    });
    if (installBtn) {
      installBtn.addEventListener('click', () => {
        if (!deferredPrompt) return;
        deferredPrompt.prompt();
        deferredPrompt.userChoice.then(choice => {
          if (choice.outcome === 'accepted' && banner) banner.style.display = 'none';
          deferredPrompt = null;
        });
      });
    }
    if (dismissBtn) {
      dismissBtn.addEventListener('click', () => {
        if (banner) banner.style.display = 'none';
        localStorage.setItem(LS_KEYS.PWA_DISMISSED, '1');
      });
    }
    window.addEventListener('appinstalled', () => { if (banner) banner.style.display = 'none'; deferredPrompt = null; });
  })();

  initGoogleAuth();
  initBackToTop();
  initKeyboardShortcuts();
  initOfflineDetection();
  initBottomNav();

  const topicId = new URLSearchParams(location.search).get('id');
  if (topicId) {
    initReadingProgress();
    trackView(topicId);
    const showError = () => {
      const titleEl = document.getElementById('topic-title');
      if (titleEl) titleEl.textContent = '読み込みに失敗しました';
    };
    const refresh = async () => {
      // 1. S3静的ファイル（CloudFrontキャッシュ）
      try {
        const r = await fetch(apiUrl(`topic/${topicId}`));
        if (r.ok) {
          const ct = r.headers.get('content-type') || '';
          if (ct.includes('json')) {
            const data = await r.json();
            if (data.meta) { try { renderDetail(data); } catch(e) { console.error('renderDetail:', e); } return; }
          }
        }
      } catch(e) { console.error('topic fetch:', e); }
      // 2. DynamoDB経由（S3にない古いトピック）
      try {
        const gw = typeof _GW !== 'undefined' ? _GW : null;
        if (gw) {
          const r2 = await fetch(`${gw}/topic/${topicId}`);
          if (r2.ok) {
            const data2 = await r2.json();
            if (data2.meta) { try { renderDetail(data2); } catch(e) { console.error('renderDetail(fallback):', e); } return; }
          }
        }
      } catch(e) { console.error('topic fallback:', e); }
      // 3. topics.jsonからメタデータのみ（最終手段）
      try {
        const r3 = await fetch(apiUrl('topics'));
        const d3 = await r3.json();
        const t = (d3.topics || []).find(t => t.topicId === topicId);
        if (t) { try { renderDetail({ meta: t, timeline: [], views: [] }); } catch {} return; }
      } catch {}
      showError();
    };
    refresh();
    setInterval(refresh, CONFIG.REFRESH_INTERVAL_MS);
    loadComments(topicId);
    setupCommentForm(topicId);
    setInterval(() => loadComments(topicId), 3 * 60 * 1000);
  } else if (document.getElementById('topics-grid')) {
    buildFilters();
    setupSearch();
    setupFavsToggle();
    loadWeather();
    initScrollRestoration();
    showSkeletonCards();
    loadFavorites().finally(() => {
      refreshTopics();
      setInterval(refreshTopics, CONFIG.REFRESH_INTERVAL_MS);
      setInterval(updateFreshnessDisplay, CONFIG.FRESHNESS_INTERVAL_MS);
    });
  }
});
