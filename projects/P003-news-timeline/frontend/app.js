// app.js — メイン。auth.js / favorites.js / comments.js を先に読み込むこと。
// 読み込み順: config.js → js/auth.js → js/favorites.js → js/comments.js → app.js

// ── 設定定数 ──────────────────────────────────────────────────
const CONFIG = {
  HOT_STRIP_HOURS: 2,                   // 今急上昇中セクションの対象時間（時間）
  NEW_BADGE_HOURS: 1,                   // NEWバッジを表示する最大経過時間（時間）
  AD_CARD_INTERVAL: 10,                 // 広告を挿入する間隔（カード枚数）
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

const GENRES = ['すべて','総合','政治','ビジネス','株・金融','テクノロジー','スポーツ','エンタメ','科学','健康','国際'];
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
let allTopics = [], currentStatus = _prefs.status || 'all', currentGenre = _prefs.genre || 'すべて', currentSearch = '';
let currentPage = 1;
let lastFetchTime = null;

function esc(s) {
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
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
  const isFav = userFavorites.has(t.topicId);
  const adCardHtml = `<div class="ad-card"><span class="ad-label">PR</span><!-- ADSENSE_SLOT_HERE --></div>`;
  return `
    <div class="topic-card-wrapper" style="position:relative;">
      ${renderBadges(t)}
      <a class="topic-card ${esc(t.status)}" href="topic.html?id=${esc(t.topicId)}">
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
    </div>${(i + 1) % CONFIG.AD_CARD_INTERVAL === 0 ? adCardHtml : ''}`;
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
  if (currentGenre  !== 'すべて') list = list.filter(t => (t.genres||[t.genre]).includes(currentGenre));
  if (currentStatus === 'all')    list = list.filter(t => t.lifecycleStatus !== 'archived');
  if (showFavsOnly) list = list.filter(t => userFavorites.has(t.topicId));

  // ジャンル多様性を確保（テック偏り防止）
  list = applyGenreDiversity(list, currentGenre !== 'すべて');

  const lmContainer = document.getElementById('load-more-container');
  if (!list.length) {
    grid.innerHTML = showFavsOnly
      ? '<div class="loading">お気に入りのトピックがありません</div>'
      : '<div class="loading">該当するトピックがありません</div>';
    if (lmContainer) lmContainer.innerHTML = '';
    return;
  }

  const pageList = list.slice(0, currentPage * CONFIG.TOPICS_PER_PAGE);
  grid.innerHTML = pageList.reduce((html, t, i) => html + renderTopicCard(t, i), '');

  if (lmContainer) {
    if (pageList.length < list.length) {
      const remaining = list.length - pageList.length;
      lmContainer.innerHTML = `<button class="load-more-btn">もっと見る（残り${remaining}件）</button>`;
      lmContainer.querySelector('.load-more-btn').addEventListener('click', () => { currentPage++; renderTopics(allTopics); });
    } else {
      lmContainer.innerHTML = '';
    }
  }

  // お気に入りボタン
  grid.querySelectorAll('.fav-btn').forEach(btn => {
    btn.addEventListener('click', e => {
      e.preventDefault();
      e.stopPropagation();
      toggleFavorite(btn.dataset.topicId, btn);
    });
  });

  showTrendingBanner(allTopics);
}

function buildFilters() {
  const sbar = document.getElementById('status-filter');
  if (sbar) {
    const btns = [{k:'all',l:'すべて'},{k:'rising',l:'🔥 急上昇'},{k:'peak',l:'⚡ 注目中'},{k:'declining',l:'📉 落ち着き'}];
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
    // velocityScore → score → lastUpdated 降順でソート（盛り上がり順）
    allTopics = raw.sort((a, b) => {
      const vs = Number(b.velocityScore || 0) - Number(a.velocityScore || 0);
      if (vs !== 0) return vs;
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

// ===== 詳細ページ =====
let chartInstance = null, viewsChartInstance = null;

function trackView(topicId) {
  if (typeof TRACKER_URL === 'undefined') return;
  fetch(TRACKER_URL, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({topicId}),
  }).catch(() => {});
}

function updateOGP(meta) {
  const title   = meta.generatedTitle || meta.title || 'Flotopic';
  const rawDesc = cleanSummary(meta.generatedSummary) || '';
  const desc    = rawDesc.length > 0 ? rawDesc.slice(0, 100) : 'Flotopicでトピックの推移をAIが分析';
  const url     = `https://flotopic.com/topic.html?id=${meta.topicId || ''}`;
  const setMeta = (prop, val) => {
    const el = document.querySelector(`meta[property="${prop}"]`);
    if (el) el.setAttribute('content', val);
  };
  setMeta('og:title',       title);
  setMeta('og:description', desc);
  setMeta('og:url',         url);

  // canonical URL を動的更新
  const canonical = document.getElementById('canonical-url');
  if (canonical) canonical.setAttribute('href', url);

  // JSON-LD 構造化データ（NewsArticle）を動的更新
  const jsonLdEl = document.getElementById('jsonld-newsarticle');
  if (jsonLdEl && meta.topicId) {
    const iso = (ts) => {
      if (!ts) return new Date().toISOString();
      try { return new Date(ts).toISOString(); } catch { return new Date().toISOString(); }
    };
    const datePublished = iso(meta.firstArticleAt || meta.createdAt);
    const dateModified  = iso(meta.lastArticleAt  || meta.lastUpdated);
    const jsonLd = {
      '@context': 'https://schema.org',
      '@type': 'NewsArticle',
      'headline': title.slice(0, 110),
      'description': desc,
      'url': url,
      'datePublished': datePublished,
      'dateModified':  dateModified,
      'publisher': {
        '@type': 'Organization',
        'name': 'Flotopic',
        'url': 'https://flotopic.com',
        'logo': { '@type': 'ImageObject', 'url': 'https://flotopic.com/icon-192.png' }
      },
      'mainEntityOfPage': { '@type': 'WebPage', '@id': url }
    };
    jsonLdEl.textContent = JSON.stringify(jsonLd);
  }
}


function renderDetail(data) {
  const {meta, timeline, views} = data;
  if (!meta) return;

  recordTopicView(meta);
  document.title = `${meta.generatedTitle||meta.title} | Flotopic`;
  updateOGP(meta);

  const titleEl = document.getElementById('topic-title');
  if (titleEl) titleEl.textContent = meta.generatedTitle || meta.title;

  const shareBtn = document.getElementById('share-btn');
  if (shareBtn && navigator.share) {
    shareBtn.style.display = 'inline-flex';
    shareBtn.onclick = () => navigator.share({
      title: meta.generatedTitle || meta.title,
      text: cleanSummary(meta.generatedSummary) || '',
      url: location.href,
    });
  }

  // X（旧Twitter）シェアボタン
  const xBtn = document.getElementById('x-share-btn');
  if (xBtn) {
    const pageUrl  = `https://flotopic.com/topic.html?id=${encodeURIComponent(meta.topicId || '')}`;
    const xTitle   = encodeURIComponent(meta.generatedTitle || meta.title || 'Flotopic');
    xBtn.href = `https://twitter.com/intent/tweet?text=${xTitle}&url=${encodeURIComponent(pageUrl)}`;
    xBtn.style.display = 'inline-flex';
  }

  // はてなブックマーク シェアボタン
  const hatenaBtn = document.getElementById('hatena-share-btn');
  if (hatenaBtn) {
    const pageUrl   = `https://flotopic.com/topic.html?id=${encodeURIComponent(meta.topicId || '')}`;
    const pageTitle = encodeURIComponent(meta.generatedTitle || meta.title || 'Flotopic');
    hatenaBtn.href = `https://b.hatena.ne.jp/add?mode=confirm&url=${encodeURIComponent(pageUrl)}&title=${pageTitle}`;
    hatenaBtn.style.display = 'inline-flex';
  }

  // Threads シェアボタン
  const threadsBtn = document.getElementById('threads-share-btn');
  if (threadsBtn) {
    const pageUrl    = `https://flotopic.com/topic.html?id=${encodeURIComponent(meta.topicId || '')}`;
    const shareTitle = meta.generatedTitle || meta.title || 'Flotopic';
    const shareText  = encodeURIComponent(`${shareTitle}\n${pageUrl}`);
    threadsBtn.href = `https://www.threads.net/intent/post?text=${shareText}`;
    threadsBtn.style.display = 'inline-flex';
  }

  // <time> タグ（最終更新日時）
  const timeEl = document.getElementById('topic-last-updated');
  if (timeEl) {
    const lastUpdated = meta.lastArticleAt || meta.lastUpdated;
    if (lastUpdated) {
      try {
        const d = new Date(lastUpdated);
        timeEl.setAttribute('datetime', d.toISOString());
        timeEl.textContent = d.toLocaleString('ja-JP', { year: 'numeric', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' });
      } catch {}
    }
  }

  const badge = document.getElementById('status-badge');
  if (badge) { badge.textContent = STATUS_LABEL[meta.status]||meta.status; badge.className=`status-badge ${meta.status}`; badge.style.display='inline-block'; }
  const genreEl = document.getElementById('genre-badge');
  if (genreEl) {
    const gs = meta.genres || (meta.genre ? [meta.genre] : []);
    if (gs.length) { genreEl.textContent = gs.join(' / '); genreEl.style.display='inline-block'; }
  }

  const summaryEl = document.querySelector('.summary-placeholder, .summary-text');
  if (summaryEl) {
    const cleanedSummary = cleanSummary(meta.generatedSummary);
    const hasAISummary  = cleanedSummary && !meta.pendingAI;
    const hasExtractive = cleanedSummary && meta.pendingAI;
    if (hasAISummary) {
      summaryEl.textContent = cleanedSummary;
      summaryEl.className = 'summary-text';
    } else if (hasExtractive) {
      const cnt = meta.articleCount || 1;
      const sources = (meta.sources || []).slice(0, 3).join('・');
      summaryEl.innerHTML =
        `<p style="margin:0 0 8px;line-height:1.7;">${esc(cleanedSummary)}</p>` +
        `<span style="color:var(--text-muted);font-size:.78rem;">⏳ AI要約生成中（1日3回更新）・${cnt}件の記事を追跡${sources ? `（${sources} ほか）` : ''}</span>`;
      summaryEl.className = 'summary-placeholder';
    } else {
      const cnt = meta.articleCount || 1;
      const sources = (meta.sources || []).slice(0, 3).join('・');
      summaryEl.innerHTML = `<span style="color:var(--text-muted);font-size:.85rem;">⏳ AI要約を生成中です（1日3回更新）。</span><br><span style="font-size:.82rem;color:var(--text-secondary);">${cnt}件の記事を追跡中${sources ? `（${sources} ほか）` : ''}。</span>`;
      summaryEl.className = 'summary-placeholder';
    }
  }

  const canvas = document.getElementById('score-chart');
  const vCanvas = document.getElementById('views-chart');
  const noData = document.getElementById('no-data');
  if (canvas) {
    if (timeline.length < 2) {
      canvas.style.display='none'; if(vCanvas) vCanvas.style.display='none'; if(noData) noData.style.display='block';
    } else {
      canvas.style.display='block'; if(vCanvas) vCanvas.style.display='block'; if(noData) noData.style.display='none';

      const buildCharts = (rangeHours) => {
        const now = Date.now();
        const cutoff = rangeHours ? now - rangeHours * 3600 * 1000 : 0;
        const filtered = rangeHours ? timeline.filter(s => new Date(s.timestamp).getTime() >= cutoff) : timeline;
        const src = filtered.length >= 2 ? filtered : timeline;

        const aggregate = rangeHours === null || rangeHours >= 72;
        let labels, scores, mediaCnts;
        if (aggregate) {
          const byDay = {};
          src.forEach(s => {
            const day = new Date(s.timestamp).toLocaleDateString('ja-JP',{month:'numeric',day:'numeric'});
            if (!byDay[day]) byDay[day] = {scores:[], media:[]};
            byDay[day].scores.push(Number(s.score||0));
            byDay[day].media.push(Number(s.articleCount||0));
          });
          labels    = Object.keys(byDay);
          scores    = labels.map(d => Math.max(...byDay[d].scores));
          mediaCnts = labels.map(d => Math.max(...byDay[d].media));
        } else {
          labels    = src.map(s => fmtDate(s.timestamp));
          scores    = src.map(s => Number(s.score||0));
          mediaCnts = src.map(s => Number(s.articleCount||0));
        }

        const viewsSorted = [...(views||[])].sort((a,b) => a.date.localeCompare(b.date));
        const vLabels   = viewsSorted.map(v => `${parseInt(v.date.slice(4,6))}/${parseInt(v.date.slice(6,8))}`);
        const vAbsolute = viewsSorted.map(v => v.count);
        const vDelta    = viewsSorted.map((v, i) => i === 0 ? 0 : v.count - viewsSorted[i-1].count);

        const zoomOpts = meta.status === 'archived' ? {} : {
          zoom: { wheel:{enabled:true}, pinch:{enabled:true}, mode:'x' },
          pan:  { enabled:true, mode:'x' },
        };
        const makeScaleY0 = (data) => {
          const vals = data.filter(v => v !== null);
          const max = vals.length ? Math.max(...vals) : 10;
          return { min:0, max: max + Math.max(max * 0.2, 1), ticks:{ precision:0, maxTicksLimit:5 }, grid:{ color:'rgba(0,0,0,.06)' } };
        };
        const makeScaleDelta = (data) => {
          const vals = data.filter(v => v !== null);
          const max = vals.length ? Math.max(...vals) : 1;
          const min = vals.length ? Math.min(...vals) : 0;
          const pad = Math.max(Math.abs(max - min) * 0.2, 1);
          return {
            min: min < 0 ? min - pad : 0, max: max + pad,
            ticks: { precision:0, maxTicksLimit:5 },
            grid: { color: ctx => ctx.tick.value === 0 ? 'rgba(0,0,0,.3)' : 'rgba(0,0,0,.06)', lineWidth: ctx => ctx.tick.value === 0 ? 2 : 1 },
          };
        };

        if (chartInstance) chartInstance.destroy();
        chartInstance = new Chart(canvas.getContext('2d'), {
          type: 'bar',
          data: { labels: vLabels, datasets: [{ label:'閲覧数増減（昨日比）', data: vDelta,
            backgroundColor: vDelta.map(v => v >= 0 ? 'rgba(16,185,129,.85)' : 'rgba(239,68,68,.75)'),
            borderRadius: 4, borderSkipped: false }]},
          options: {
            responsive: true, maintainAspectRatio: false,
            interaction: { mode:'index', intersect:false },
            plugins: { legend: { display:true, position:'bottom', labels:{boxWidth:12, font:{size:11}} }, zoom: zoomOpts },
            scales: { y: makeScaleDelta(vDelta) },
          },
        });

        if (vCanvas) {
          if (viewsChartInstance) viewsChartInstance.destroy();
          viewsChartInstance = new Chart(vCanvas.getContext('2d'), {
            type: 'line',
            data: { labels: vLabels, datasets: [{ label:'閲覧数', data: vAbsolute,
              borderColor:'#10b981',
              backgroundColor: (ctx) => {
                const {ctx:c, chartArea} = ctx.chart;
                if (!chartArea) return 'rgba(16,185,129,.2)';
                const g = c.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
                g.addColorStop(0, 'rgba(16,185,129,.4)'); g.addColorStop(1, 'rgba(16,185,129,.02)');
                return g;
              },
              borderWidth:2, pointRadius:3, pointHoverRadius:6, tension:0.4, fill:true }]},
            options: {
              responsive: true, maintainAspectRatio: false,
              interaction: { mode:'index', intersect:false },
              plugins: { legend: { display:true, position:'bottom', labels:{boxWidth:12, font:{size:11}} }, zoom: zoomOpts },
              scales: { y: makeScaleY0(vAbsolute) },
            },
          });
        }
      };

      buildCharts(24);
      document.querySelectorAll('.tr-btn').forEach(btn => {
        btn.addEventListener('click', () => {
          document.querySelectorAll('.tr-btn').forEach(b => b.classList.remove('active'));
          btn.classList.add('active');
          const r = btn.dataset.range;
          buildCharts(r==='1d'?24 : r==='3d'?72 : r==='7d'?168 : r==='1m'?720 : r==='3m'?2160 : r==='6m'?4320 : r==='1y'?8760 : null);
        });
      });
    }
  }

  if (meta.childTopics && meta.childTopics.length > 0) {
    const storymapContainer = document.getElementById('storymap-link-container');
    if (storymapContainer) {
      storymapContainer.innerHTML = `<a href="storymap.html?id=${esc(meta.topicId)}" class="storymap-btn">🗺 このストーリーの分岐を見る (${meta.childTopics.length}件)</a>`;
    }
  }

  const storyEl = document.getElementById('story-timeline');
  if (storyEl && timeline.length) {
    const seenUrls = new Set();
    const allArticles = [];
    [...timeline].reverse().forEach(snap => {
      (snap.articles || []).forEach(a => {
        if (!seenUrls.has(a.url)) { seenUrls.add(a.url); allArticles.push({ ...a, _snapTs: snap.timestamp }); }
      });
    });
    allArticles.sort((a, b) => new Date(b._snapTs) - new Date(a._snapTs));

    const totalCount = allArticles.length;
    let timelineOrder = 'desc';
    const fmtTl = (ts) => {
      const d = new Date(ts);
      return `${d.getMonth()+1}月${d.getDate()}日 ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`;
    };
    const ARTICLES_PER_DAY = 3;
    const DAYS_INITIAL     = 7;
    const WDAY = ['日','月','火','水','木','金','土'];
    const fmtDay = (ts) => {
      const d = new Date(typeof ts === 'number' && ts < 1e11 ? ts * 1000 : ts);
      return `${d.getMonth()+1}月${d.getDate()}日（${WDAY[d.getDay()]}）`;
    };

    const renderTimeline = () => {
      const dayMap = {};
      allArticles.forEach(a => {
        const _pubMs = a.publishedAt ? a.publishedAt * 1000 : (a.pubDate ? new Date(a.pubDate).getTime() : 0);
        const ts  = _pubMs || new Date(a._snapTs).getTime();
        const key = fmtDay(new Date(ts));
        if (!dayMap[key]) dayMap[key] = { ts, articles: [] };
        dayMap[key].articles.push({ ...a, _ts: ts });
      });
      let days = Object.entries(dayMap).sort((a, b) =>
        timelineOrder === 'asc' ? a[1].ts - b[1].ts : b[1].ts - a[1].ts
      );
      const totalDays = days.length;
      let showAll = false;

      const buildHTML = () => {
        const visibleDays = showAll ? days : days.slice(0, DAYS_INITIAL);
        return `
          <div class="sort-toggle">
            <span class="sort-label">並び順:</span>
            <button class="sort-btn ${timelineOrder === 'desc' ? 'active' : ''}" data-order="desc">新しい順 ▾</button>
            <button class="sort-btn ${timelineOrder === 'asc' ? 'active' : ''}" data-order="asc">古い順</button>
          </div>
          <div class="article-total-count">全${totalCount}件の記事 · ${totalDays}日間</div>
          <div class="story-timeline-wrap">
            ${visibleDays.map(([dayKey, g]) => {
              const sorted = [...g.articles].sort((a, b) => b._ts - a._ts);
              const shown  = sorted.slice(0, ARTICLES_PER_DAY);
              const rest   = sorted.slice(ARTICLES_PER_DAY);
              return `<div class="timeline-item">
                <div class="timeline-dot"></div>
                <div class="timeline-content">
                  <div class="timeline-time">${dayKey}<span class="day-article-count"> · ${g.articles.length}件</span></div>
                  <div class="day-articles">
                    ${shown.map(a => {
                      const _artMs = a.publishedAt ? a.publishedAt * 1000 : (a.pubDate ? new Date(a.pubDate).getTime() : 0);
                      const isNew = _artMs && (Date.now() - _artMs) < 6 * 3600 * 1000;
                      return `<div class="timeline-article">
                        <a href="${esc(a.url)}" class="timeline-article-link" target="_blank" rel="noopener noreferrer">${esc(a.title)}${isNew ? '<span class="new-badge">NEW</span>' : ''}</a>
                        <div class="timeline-source"><img class="source-favicon" src="https://www.google.com/s2/favicons?domain=${esc(a.source)}&sz=16" alt="" width="12" height="12">${esc(a.source)}</div>
                      </div>`;
                    }).join('')}
                    ${rest.length ? `<details class="day-more-details"><summary class="day-more-btn">他${rest.length}件を表示</summary>${rest.map(a => `<div class="timeline-article">
                        <a href="${esc(a.url)}" class="timeline-article-link" target="_blank" rel="noopener noreferrer">${esc(a.title)}</a>
                        <div class="timeline-source"><img class="source-favicon" src="https://www.google.com/s2/favicons?domain=${esc(a.source)}&sz=16" alt="" width="12" height="12">${esc(a.source)}</div>
                      </div>`).join('')}</details>` : ''}
                  </div>
                </div>
              </div>`;
            }).join('')}
          </div>
          ${!showAll && totalDays > DAYS_INITIAL ? `<button class="timeline-show-all-btn" id="tl-show-all">📅 全${totalDays}日間を表示</button>` : ''}
        `;
      };

      storyEl.innerHTML = buildHTML();
      storyEl.querySelectorAll('.sort-btn').forEach(btn => {
        btn.addEventListener('click', () => { timelineOrder = btn.dataset.order; renderTimeline(); });
      });
      const showAllBtn = document.getElementById('tl-show-all');
      if (showAllBtn) {
        showAllBtn.addEventListener('click', () => { showAll = true; storyEl.innerHTML = buildHTML(); storyEl.querySelectorAll('.sort-btn').forEach(b => b.addEventListener('click', () => { timelineOrder = b.dataset.order; renderTimeline(); })); });
      }
    };

    renderTimeline();

    const relatedEl = document.getElementById('related-articles');
    if (relatedEl && allArticles.length) {
      const picked = [];
      const usedSources = new Set();
      const sorted = [...allArticles].sort((a, b) => new Date(a._snapTs) - new Date(b._snapTs));
      if (sorted.length) { picked.push(sorted[0]); usedSources.add(sorted[0].source); }
      const latest = allArticles[0];
      if (latest && latest.url !== (picked[0] && picked[0].url)) { picked.push(latest); usedSources.add(latest.source); }
      for (const a of allArticles) {
        if (picked.length >= 3) break;
        if (!usedSources.has(a.source) && a.url !== picked[0].url && a.url !== (picked[1] && picked[1].url)) {
          picked.push(a); usedSources.add(a.source);
        }
      }
      if (picked.length === 0) picked.push(allArticles[0]);
      relatedEl.innerHTML = picked.map(a => `
        <div class="article-item">
          <a href="${esc(a.url)}" target="_blank" rel="noopener noreferrer">${esc(a.title)}</a>
          <div class="article-meta">
            <img class="source-favicon" src="https://www.google.com/s2/favicons?domain=${esc(a.source)}&sz=16" alt="" width="12" height="12" style="vertical-align:middle;margin-right:3px;">
            ${esc(a.source)} · ${fmtTl(a._snapTs)}
          </div>
        </div>
      `).join('');
    }

  }

  renderDiscovery(meta);
}

// ===== Discovery: 深掘り & 拡張 =====
let _allTopicsCache = null;
async function fetchAllTopicsOnce() {
  if (_allTopicsCache) return _allTopicsCache;
  try {
    const r = await fetch(apiUrl('topics'));
    const d = await r.json();
    _allTopicsCache = d.topics || [];
    return _allTopicsCache;
  } catch { return []; }
}

function fmtElapsed(isoOrTs) {
  try {
    const d = typeof isoOrTs === 'number' ? new Date(isoOrTs * 1000) : new Date(isoOrTs);
    if (isNaN(d)) return '';
    const diff = (Date.now() - d.getTime()) / 1000;
    if (diff < 3600)   return `${Math.floor(diff / 60)}分前`;
    if (diff < 86400)  return `${Math.floor(diff / 3600)}時間前`;
    if (diff < 604800) return `${Math.floor(diff / 86400)}日前`;
    return `${d.getMonth()+1}/${d.getDate()}`;
  } catch { return ''; }
}

function discCard(topic, badge) {
  const title = topic.generatedTitle || topic.title || '';
  const ago   = fmtElapsed(topic.lastArticleAt || topic.lastUpdated || 0);
  const cnt   = topic.articleCount || 0;
  const dot   = topic.lifecycleStatus === 'active' ? '🔴' : topic.lifecycleStatus === 'cooling' ? '🟡' : '⚪';
  const badgeHtml = badge ? `<span class="disc-badge disc-badge-${badge.cls}">${esc(badge.label)}</span>` : '';
  return `
    <a href="topic.html?id=${esc(topic.topicId)}" class="disc-card">
      ${badgeHtml}
      <div class="disc-card-title">${esc(title)}</div>
      <div class="disc-card-meta">${dot} ${cnt}件${ago ? ` · ${esc(ago)}` : ''}</div>
    </a>`;
}

function coordsToRegion(lat, lon) {
  if (lat > 41.5)                       return { name: '北海道', kw: '北海道' };
  if (lat > 38.5)                       return { name: '東北',   kw: '東北' };
  if (lat > 36.5 && lon >= 140.5)       return { name: '関東北部', kw: '栃木' };
  if (lat > 35.4 && lon >= 138.5)       return { name: '関東',   kw: '東京' };
  if (lat > 35.0 && lon < 137.0)        return { name: '関西',   kw: '大阪' };
  if (lat > 35.0 && lon >= 137.0)       return { name: '東海',   kw: '名古屋' };
  if (lat > 33.5 && lon < 132.0)        return { name: '中国',   kw: '広島' };
  if (lat > 33.5)                        return { name: '四国',   kw: '愛媛' };
  return { name: '九州', kw: '福岡' };
}

function renderDiscovery(meta) {
  const section = document.getElementById('discovery-section');
  if (!section) return;

  fetchAllTopicsOnce().then(allTopics => {
    const curId = meta.topicId;
    const tMap  = {};
    for (const t of allTopics) tMap[t.topicId] = t;

    const items = [];
    const usedIds = new Set([curId]);

    // 1. 親トピック（上位の流れ）
    if (meta.parentTopicId && tMap[meta.parentTopicId]) {
      items.push({ t: tMap[meta.parentTopicId], badge: { label: '← 大きな流れ', cls: 'parent' } });
      usedIds.add(meta.parentTopicId);
    }

    // 2. エンティティ類似トピック（relatedTopics・最も確実な関連性）
    for (const rt of (meta.relatedTopics || [])) {
      if (items.length >= 5) break;
      if (usedIds.has(rt.topicId)) continue;
      const t = tMap[rt.topicId];
      if (!t) continue;
      const tags = (rt.sharedEntities || []).slice(0, 2).map(e => `<span class="entity-tag">#${esc(e)}</span>`).join('');
      items.push({ t, badge: null, extraHtml: tags });
      usedIds.add(rt.topicId);
    }

    // 3. 子トピック（この話題から派生した流れ）
    for (const ref of (meta.childTopics || [])) {
      if (items.length >= 5) break;
      if (usedIds.has(ref.topicId)) continue;
      const t = tMap[ref.topicId] || ref;
      if (!t) continue;
      items.push({ t, badge: { label: '↳ 分岐', cls: 'child' } });
      usedIds.add(ref.topicId);
    }

    if (items.length === 0) {
      section.innerHTML = '';
      return;
    }

    const smLink = (meta.childTopics && meta.childTopics.length > 0)
      ? `<a href="storymap.html?id=${esc(meta.topicId)}" class="disc-see-all">🗺 ストーリーマップ（${meta.childTopics.length}件の分岐）→</a>`
      : '';

    section.innerHTML = `
      <div class="card disc-card-wrapper">
        <h2>関連する話題</h2>
        <p class="disc-header-sub">エンティティの重複・親子関係から検出</p>
        <div class="disc-col-body">
          ${items.map(({ t, badge, extraHtml }) => {
            const title = t.generatedTitle || t.title || '';
            const ago   = fmtElapsed(t.lastArticleAt || t.lastUpdated || 0);
            const cnt   = t.articleCount || 0;
            const dot   = t.lifecycleStatus === 'active' ? '🔴' : t.lifecycleStatus === 'cooling' ? '🟡' : '⚪';
            const badgeHtml = badge ? `<span class="disc-badge disc-badge-${badge.cls}">${esc(badge.label)}</span>` : '';
            return `
              <a href="topic.html?id=${esc(t.topicId)}" class="disc-card">
                ${badgeHtml}
                <div class="disc-card-title">${esc(title)}</div>
                <div class="disc-card-footer">
                  <span class="disc-card-meta">${dot} ${cnt}件${ago ? ` · ${esc(ago)}` : ''}</span>
                  ${extraHtml || ''}
                </div>
              </a>`;
          }).join('')}
        </div>
        ${smLink}
      </div>`;
  });
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

  const topicId = new URLSearchParams(location.search).get('id');
  if (topicId) {
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
            if (data.meta) { try { renderDetail(data); } catch {} return; }
          }
        }
      } catch {}
      // 2. DynamoDB経由（S3にない古いトピック）
      try {
        const gw = typeof _GW !== 'undefined' ? _GW : null;
        if (gw) {
          const r2 = await fetch(`${gw}/topic/${topicId}`);
          if (r2.ok) {
            const data2 = await r2.json();
            if (data2.meta) { try { renderDetail(data2); } catch {} return; }
          }
        }
      } catch {}
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
    loadFavorites().finally(() => {
      refreshTopics();
      setInterval(refreshTopics, CONFIG.REFRESH_INTERVAL_MS);
      setInterval(updateFreshnessDisplay, CONFIG.FRESHNESS_INTERVAL_MS);
    });
  }
});
