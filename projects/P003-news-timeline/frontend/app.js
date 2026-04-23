const REFRESH_MS = 5 * 60 * 1000;

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
const STATUS_LABEL = { rising:'🔥 急上昇', peak:'⚡ 注目中', declining:'📉 落ち着き' };
const GENRES = ['すべて','総合','政治','ビジネス','株・金融','テクノロジー','スポーツ','エンタメ','科学','健康','国際'];
const GENRE_EMOJI = {'政治':'🏛️','ビジネス':'💼','株・金融':'📈','テクノロジー':'💻','スポーツ':'⚽','エンタメ':'🎬','科学':'🔬','健康':'💊','国際':'🌏','総合':'📰'};

// ===== パーソナライズ: ローカルストレージで設定を保存 =====
const PREF_KEY = 'flotopic_prefs';

// ===== 閲覧履歴 =====
const HISTORY_KEY = 'flotopic_history';
function recordTopicView(topic) {
  if (!topic || !topic.topicId) return;
  try {
    let history = JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]');
    // Remove existing entry for this topic so we can prepend fresh
    history = history.filter(function (h) { return h.topicId !== topic.topicId; });
    history.unshift({
      topicId:  topic.topicId,
      title:    topic.generatedTitle || topic.title || '',
      viewedAt: Date.now(),
    });
    // Keep last 20 entries
    if (history.length > 20) history = history.slice(0, 20);
    localStorage.setItem(HISTORY_KEY, JSON.stringify(history));
  } catch (e) {}
}
function loadPrefs() {
  try { return JSON.parse(localStorage.getItem(PREF_KEY) || '{}'); } catch { return {}; }
}
function savePrefs(prefs) {
  try { localStorage.setItem(PREF_KEY, JSON.stringify(prefs)); } catch {}
}

// ===== Google Auth =====
// GOOGLE_CLIENT_ID は config.js で設定
let currentUser = null;

function loadUser() {
  try { return JSON.parse(localStorage.getItem('flotopic_user') || 'null'); } catch { return null; }
}
function saveUser(user) {
  try {
    if (user) localStorage.setItem('flotopic_user', JSON.stringify(user));
    else localStorage.removeItem('flotopic_user');
  } catch {}
}

// ニックネーム: 設定済みなら優先、なければGoogleの名前の名前部分のみ
function getDisplayName(user) {
  if (!user) return '';
  if (user.nickname) return user.nickname;
  const full = user.name || '';
  return full.split(/\s+/)[0] || full || 'ユーザー';
}
function saveNickname(nickname) {
  try {
    const u = loadUser();
    if (u) { u.nickname = nickname; saveUser(u); if (currentUser) currentUser.nickname = nickname; }
  } catch {}
}

function updateAuthUI() {
  const signInBtn  = document.getElementById('auth-signin-btn');
  const signOutBtn = document.getElementById('auth-signout-btn');
  const userAvatar = document.getElementById('auth-user-avatar');
  const userName   = document.getElementById('auth-user-name');

  const mypageLink = document.getElementById('mypage-link');

  if (mypageLink) mypageLink.style.display = 'inline-flex';
  const googleBtnWrap = document.getElementById('google-btn-wrap');
  if (currentUser) {
    if (signInBtn)     signInBtn.style.display     = 'none';
    if (googleBtnWrap) googleBtnWrap.style.display = 'none';
    if (signOutBtn)    signOutBtn.style.display    = 'inline-flex';
    if (userAvatar) {
      userAvatar.src     = currentUser.picture || '';
      userAvatar.style.display = currentUser.picture ? 'inline-block' : 'none';
    }
    if (userName) userName.textContent = getDisplayName(currentUser);
  } else {
    if (signInBtn)     signInBtn.style.display     = 'none';
    if (googleBtnWrap) googleBtnWrap.style.display = 'inline-block';
    if (signOutBtn)    signOutBtn.style.display    = 'none';
    if (userAvatar)    userAvatar.style.display    = 'none';
    if (userName)      userName.textContent        = '';
  }
}

async function handleGoogleCredentialResponse(response) {
  const idToken = response.credential;
  if (!idToken) return;

  // AUTH_URL は config.js で定義
  if (typeof AUTH_URL === 'undefined' || !AUTH_URL) {
    // AUTH_URL 未設定の場合はトークンからローカルでユーザー情報を取得
    try {
      const parts  = idToken.split('.');
      const payload = JSON.parse(atob(parts[1]));
      currentUser = {
        userId:  payload.sub,
        name:    payload.name || '',
        picture: payload.picture || '',
        token:   idToken,
      };
      saveUser(currentUser);
      updateAuthUI();
      showToast(`${getDisplayName(currentUser) || 'ログイン'} でログインしました`);
    } catch {}
    return;
  }

  function localLoginFromToken(token) {
    try {
      const payload = JSON.parse(atob(token.split('.')[1]));
      currentUser = { userId: payload.sub, name: payload.name || '', picture: payload.picture || '', token };
      saveUser(currentUser);
      updateAuthUI();
      showToast(`${getDisplayName(currentUser) || 'ログイン'} でログインしました`);
      const topicId = new URLSearchParams(location.search).get('id');
      if (topicId) setupCommentForm(topicId);
    } catch {}
  }

  try {
    const r = await fetch(AUTH_URL, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ idToken }),
    });
    if (r.ok) {
      const data = await r.json();
      currentUser = { ...data, token: idToken };
      saveUser(currentUser);
      updateAuthUI();
      showToast(`${getDisplayName(currentUser) || 'ログイン'} でログインしました`);
      const topicId = new URLSearchParams(location.search).get('id');
      if (topicId) setupCommentForm(topicId);
    } else {
      localLoginFromToken(idToken);
    }
  } catch (e) {
    console.error('Auth error:', e);
    localLoginFromToken(idToken);
  }
}

function signOut() {
  currentUser = null;
  saveUser(null);
  updateAuthUI();
  // Google セッションもサインアウト
  if (window.google && google.accounts && google.accounts.id) {
    google.accounts.id.disableAutoSelect();
  }
  // コメントフォームを再描画
  const topicId = new URLSearchParams(location.search).get('id');
  if (topicId) setupCommentForm(topicId);
}

function initGoogleAuth() {
  currentUser = loadUser();
  updateAuthUI();

  const clientId = (typeof GOOGLE_CLIENT_ID !== 'undefined') ? GOOGLE_CLIENT_ID : '';
  if (!clientId) return;

  const signOutBtn = document.getElementById('auth-signout-btn');
  if (signOutBtn) signOutBtn.addEventListener('click', signOut);

  function setupGIS() {
    if (!window.google || !google.accounts || !google.accounts.id) return;
    google.accounts.id.initialize({
      client_id: clientId,
      callback:  handleGoogleCredentialResponse,
      auto_select: false,
      ux_mode: 'popup',
    });
    const signInBtn = document.getElementById('auth-signin-btn');
    if (signInBtn) {
      // renderButtonでGoogle標準ボタンを差し込む（One Tapより確実）
      const btnWrap = document.createElement('div');
      btnWrap.id = 'google-btn-wrap';
      btnWrap.style.display = 'inline-block';
      signInBtn.parentNode.insertBefore(btnWrap, signInBtn);
      signInBtn.style.display = 'none';
      google.accounts.id.renderButton(btnWrap, {
        type: 'standard', theme: 'outline', size: 'medium',
        text: 'signin_with', locale: 'ja',
      });
      // ログイン済みなら wrapper も即非表示
      if (currentUser) btnWrap.style.display = 'none';
    }
  }

  if (window.google && google.accounts && google.accounts.id) {
    setupGIS();
  } else {
    // GISスクリプトのonload後に初期化（async deferのため）
    window.__gsiReady = setupGIS;
  }
}

const _prefs = loadPrefs();
let allTopics = [], currentStatus = _prefs.status || 'all', currentGenre = _prefs.genre || 'すべて', currentSearch = '';
let userFavorites = new Set();
let showFavsOnly = false;
let currentPage = 1;
const PAGE_SIZE = 20;

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

// ===== お気に入り =====

const FAV_LS_KEY = 'flotopic_favs';
function loadLocalFavs() {
  try {
    const raw = JSON.parse(localStorage.getItem(FAV_LS_KEY) || '[]');
    return Array.isArray(raw) ? raw : [];
  } catch { return []; }
}
function saveLocalFavs(set) {
  try { localStorage.setItem(FAV_LS_KEY, JSON.stringify([...set])); } catch {}
}

function favApiUrl() {
  if (typeof FAVORITES_URL === 'undefined' || !FAVORITES_URL) return null;
  return FAVORITES_URL.replace(/\/$/, '');
}

async function loadFavorites() {
  // Always load from localStorage first as a baseline
  loadLocalFavs().forEach(id => userFavorites.add(id));

  if (!currentUser) return;
  const base = favApiUrl();
  if (!base) return;
  try {
    const r = await fetch(`${base}/favorites/${currentUser.userId}`);
    if (r.ok) {
      const data = await r.json();
      const apiFavs = (data.favorites || []).map(f => f.topicId);
      userFavorites = new Set([...userFavorites, ...apiFavs]);
      saveLocalFavs(userFavorites);
    }
  } catch {}
}

async function toggleFavorite(topicId, heartBtn) {
  if (!currentUser) {
    alert('お気に入りするにはGoogleでログインしてください');
    return;
  }
  const base = favApiUrl();
  if (!base) return;

  const isFav = userFavorites.has(topicId);
  const method = isFav ? 'DELETE' : 'POST';

  heartBtn.disabled = true;
  try {
    const r = await fetch(`${base}/favorites`, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        userId:  currentUser.userId,
        idToken: currentUser.token,
        topicId,
      }),
    });
    if (r.ok) {
      if (isFav) {
        userFavorites.delete(topicId);
        heartBtn.classList.remove('fav-active');
        heartBtn.title = 'お気に入りに追加';
      } else {
        userFavorites.add(topicId);
        heartBtn.classList.add('fav-active');
        heartBtn.title = 'お気に入りを解除';
      }
      saveLocalFavs(userFavorites);
    }
  } catch {}
  heartBtn.disabled = false;
}

// ===== 一覧ページ =====
async function loadTopics() {
  const r = await fetch(apiUrl('topics'));
  const data = await r.json();
  const trendingKeywords = data.trendingKeywords || [];
  renderKeywordStrip(trendingKeywords);
  return data.topics || [];
}

function renderKeywordStrip(keywords) {
  const strip = document.getElementById('keyword-strip');
  const chips = document.getElementById('keyword-chips');
  if (!strip || !chips || keywords.length === 0) return;

  chips.innerHTML = keywords.map(k =>
    `<button class="keyword-chip" data-keyword="${k.keyword}">#${k.keyword}</button>`
  ).join('');

  strip.style.display = 'flex';

  // ランダムな急上昇キーワードをプレースホルダーに表示
  const searchInput = document.getElementById('search-input');
  if (searchInput) {
    const randomKw = keywords[Math.floor(Math.random() * keywords.length)].keyword;
    searchInput.placeholder = `🔍 例：「${randomKw}」で検索...`;
  }

  chips.querySelectorAll('.keyword-chip').forEach(btn => {
    btn.addEventListener('click', () => {
      const kw = btn.dataset.keyword;
      if (searchInput) {
        searchInput.value = kw;
        searchInput.dispatchEvent(new Event('input'));  // trigger search filter
      }
      // Highlight active chip
      chips.querySelectorAll('.keyword-chip').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
    });
  });
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
  // archivedは「すべて」でも非表示（legacyページ送り）
  if (currentStatus === 'all')    list = list.filter(t => t.lifecycleStatus !== 'archived');
  // --- Task 1: favorites-only filter ---
  if (showFavsOnly) list = list.filter(t => userFavorites.has(t.topicId));

  const lmContainer = document.getElementById('load-more-container');

  if (!list.length) {
    grid.innerHTML = showFavsOnly
      ? '<div class="loading">お気に入りのトピックがありません</div>'
      : '<div class="loading">該当するトピックがありません</div>';
    if (lmContainer) lmContainer.innerHTML = '';
    return;
  }

  // --- Task 3: pagination ---
  const totalFiltered = list;
  const pageList = totalFiltered.slice(0, currentPage * PAGE_SIZE);

  grid.innerHTML = pageList.map(t => {
    const primaryGenre = (t.genres||[t.genre||'総合'])[0];
    const thumbHtml = t.imageUrl
      ? `<div class="card-thumb"><img class="card-thumb-img" src="${esc(t.imageUrl)}" alt="" loading="lazy" onerror="this.parentNode.innerHTML='<div class=\\'card-thumb-placeholder ${esc(t.status)}\\'>${genreEmoji(primaryGenre)}</div>'"></div>`
      : `<div class="card-thumb"><div class="card-thumb-placeholder ${esc(t.status)}">${genreEmoji(primaryGenre)}</div></div>`;
    const isFav = userFavorites.has(t.topicId);
    // reading time: ~1min per article, capped at 30min
    const readMins = Math.min(30, Math.max(1, Math.round((t.articleCount || 1) * 0.8)));
    return `
    <div class="topic-card-wrapper" style="position:relative;">
      <a class="topic-card ${esc(t.status)}" href="topic.html?id=${esc(t.topicId)}">
        ${thumbHtml}
        <div class="card-body">
          <div class="topic-status ${esc(t.status)}">${STATUS_LABEL[t.status]||t.status}</div>
          <h3>${esc(t.generatedTitle||t.title)}</h3>
          <div class="topic-meta">
            <span class="article-count">📄 ${t.articleCount}件 · 約${readMins}分</span>
            ${(t.genres||[t.genre||'総合']).map(g=>`<span class="genre-tag">${esc(g)}</span>`).join('')}
            <span>${fmtDate(t.lastUpdated)}</span>
          </div>
        </div>
      </a>
      <button class="fav-btn ${isFav ? 'fav-active' : ''}" data-topic-id="${esc(t.topicId)}" title="${isFav ? 'お気に入りを解除' : 'お気に入りに追加'}" aria-label="お気に入り">♥</button>
    </div>`;
  }).join('');

  // もっと見るボタンの表示制御
  if (lmContainer) {
    if (pageList.length < totalFiltered.length) {
      const remaining = totalFiltered.length - pageList.length;
      lmContainer.innerHTML = `<button class="load-more-btn">もっと見る（残り${remaining}件）</button>`;
      lmContainer.querySelector('.load-more-btn').addEventListener('click', () => {
        currentPage++;
        renderTopics(allTopics);
      });
    } else {
      lmContainer.innerHTML = '';
    }
  }

  // お気に入りボタンのイベント
  grid.querySelectorAll('.fav-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
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
      currentPage = 1;
      renderTopics(allTopics);
    }));
  }
  const gbar = document.getElementById('genre-filter');
  if (gbar) {
    gbar.innerHTML = GENRES.map(g=>`<button class="filter-btn genre-btn ${currentGenre===g?'active':''}" data-genre="${g}">${g}</button>`).join('');
    gbar.querySelectorAll('.genre-btn').forEach(btn => btn.addEventListener('click', () => {
      gbar.querySelectorAll('.genre-btn').forEach(b=>b.classList.remove('active'));
      btn.classList.add('active'); currentGenre = btn.dataset.genre;
      savePrefs({...loadPrefs(), genre: currentGenre});
      currentPage = 1;
      renderTopics(allTopics);
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
  const fetchWeather = async (lat, lon, cityName) => {
    const url = `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current=temperature_2m,weather_code&timezone=Asia%2FTokyo&forecast_days=1`;
    const r = await fetch(url);
    const d = await r.json();
    const temp = Math.round(d.current.temperature_2m);
    const desc = WMO[d.current.weather_code] || '―';
    el.innerHTML = `<span class="weather-city">${cityName}</span><span class="weather-desc">${desc}</span><span class="weather-temp">${temp}°C</span>`;
  };
  try {
    fetchWeather(35.68, 139.69, '東京');
  } catch(e) { el.textContent = ''; }
}

function setupFavsToggle() {
  const btn = document.getElementById('fav-toggle-btn');
  if (!btn) return;
  btn.addEventListener('click', () => {
    if (!currentUser && userFavorites.size === 0) {
      alert('ログインするとお気に入りが保存されます');
      return;
    }
    showFavsOnly = !showFavsOnly;
    btn.classList.toggle('active', showFavsOnly);
    currentPage = 1;
    renderTopics(allTopics);
  });
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

async function refreshTopics() {
  try {
    allTopics = await loadTopics();
    renderTopics(allTopics);
    const el = document.getElementById('last-updated');
    if (el) el.textContent = `最終更新: ${new Date().toLocaleTimeString('ja-JP')}（5分ごとに自動更新）`;
  } catch(e) { console.error(e); }
}
function showTrendingBanner(topics) {
  const grid = document.getElementById('topics-grid');
  if (!grid) return;

  // Remove existing banner
  const existing = document.getElementById('trending-banner');
  if (existing) existing.remove();

  // Filter rising topics with score >= 30, top 3
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
  const topicId = meta.topicId || '';
  const title   = meta.generatedTitle || meta.title || 'Flotopic';
  const rawDesc = meta.generatedSummary || '';
  const desc    = rawDesc.length > 0
    ? rawDesc.slice(0, 100)
    : 'Flotopicでトピックの推移をAIが分析';
  const url     = `https://flotopic.com/topic.html?id=${topicId}`;

  const setMeta = (prop, val) => {
    const el = document.querySelector(`meta[property="${prop}"]`);
    if (el) el.setAttribute('content', val);
  };
  setMeta('og:title',       title);
  setMeta('og:description', desc);
  setMeta('og:url',         url);
}

function renderRelatedTopics(relatedTopics) {
  const card = document.getElementById('related-topics-card');
  const list = document.getElementById('related-topics-list');
  if (!card || !list || !relatedTopics || relatedTopics.length === 0) return;

  list.innerHTML = relatedTopics.map(rt => `
    <a href="topic.html?id=${esc(rt.topicId)}" class="related-topic-item">
      <div class="related-topic-title">${esc(rt.title)}</div>
      <div class="related-topic-tags">${(rt.sharedEntities || []).map(e => `<span class="entity-tag">#${esc(e)}</span>`).join('')}</div>
    </a>
  `).join('');

  card.style.display = 'block';
}

function renderDetail(data) {
  const {meta, timeline, views} = data;
  if (!meta) return;

  // 閲覧履歴に記録
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
      text: meta.generatedSummary || '',
      url: location.href,
    });
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
    const hasAISummary = meta.generatedSummary && !meta.pendingAI;
    const hasExtractive = meta.generatedSummary && meta.pendingAI;
    if (hasAISummary) {
      summaryEl.textContent = meta.generatedSummary;
      summaryEl.className = 'summary-text';
    } else if (hasExtractive) {
      const cnt = meta.articleCount || 1;
      const sources = (meta.sources || []).slice(0, 3).join('・');
      summaryEl.innerHTML =
        `<p style="margin:0 0 8px;line-height:1.7;">${esc(meta.generatedSummary)}</p>` +
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
        const filtered = rangeHours
          ? timeline.filter(s => new Date(s.timestamp).getTime() >= cutoff)
          : timeline;
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
          const pad = Math.max(max * 0.2, 1);
          return { min:0, max: max+pad, ticks:{ precision:0, maxTicksLimit:5 }, grid:{ color:'rgba(0,0,0,.06)' } };
        };
        const makeScaleDelta = (data) => {
          const vals = data.filter(v => v !== null);
          const max = vals.length ? Math.max(...vals) : 1;
          const min = vals.length ? Math.min(...vals) : 0;
          const pad = Math.max(Math.abs(max - min) * 0.2, 1);
          const lo = min < 0 ? min - pad : 0;
          return {
            min: lo, max: max + pad,
            ticks: { precision:0, maxTicksLimit:5 },
            grid: { color: ctx => ctx.tick.value === 0 ? 'rgba(0,0,0,.3)' : 'rgba(0,0,0,.06)', lineWidth: ctx => ctx.tick.value === 0 ? 2 : 1 },
          };
        };

        if (chartInstance) chartInstance.destroy();
        chartInstance = new Chart(canvas.getContext('2d'), {
          type: 'bar',
          data: { labels: vLabels, datasets: [{
            label:'閲覧数増減（昨日比）',
            data: vDelta,
            backgroundColor: vDelta.map(v => v >= 0 ? 'rgba(16,185,129,.85)' : 'rgba(239,68,68,.75)'),
            borderRadius: 4, borderSkipped: false,
          }]},
          options: {
            responsive: true, maintainAspectRatio: false,
            interaction: { mode:'index', intersect:false },
            plugins: {
              legend: { display:true, position:'bottom', labels:{boxWidth:12, font:{size:11}} },
              zoom: zoomOpts,
            },
            scales: { y: makeScaleDelta(vDelta) },
          },
        });

        if (vCanvas) {
          if (viewsChartInstance) viewsChartInstance.destroy();
          viewsChartInstance = new Chart(vCanvas.getContext('2d'), {
            type: 'line',
            data: { labels: vLabels, datasets: [{
              label:'閲覧数',
              data: vAbsolute,
              borderColor:'#10b981',
              backgroundColor: (ctx) => {
                const {ctx:c, chartArea} = ctx.chart;
                if (!chartArea) return 'rgba(16,185,129,.2)';
                const g = c.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
                g.addColorStop(0, 'rgba(16,185,129,.4)');
                g.addColorStop(1, 'rgba(16,185,129,.02)');
                return g;
              },
              borderWidth:2, pointRadius:3, pointHoverRadius:6, tension:0.4, fill:true,
            }]},
            options: {
              responsive: true, maintainAspectRatio: false,
              interaction: { mode:'index', intersect:false },
              plugins: {
                legend: { display:true, position:'bottom', labels:{boxWidth:12, font:{size:11}} },
                zoom: zoomOpts,
              },
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

  // ストーリーマップリンク: 子トピックがある場合に表示
  if (meta.childTopics && meta.childTopics.length > 0) {
    const storymapContainer = document.getElementById('storymap-link-container');
    if (storymapContainer) {
      storymapContainer.innerHTML = `
        <a href="storymap.html?id=${esc(meta.topicId)}" class="storymap-btn">
          🗺 このストーリーの分岐を見る (${meta.childTopics.length}件)
        </a>`;
    }
  }

  const storyEl = document.getElementById('story-timeline');
  if (storyEl && timeline.length) {
    // Collect all unique articles across all snapshots, tagged with snapshot timestamp
    const seenUrls = new Set();
    const allArticles = [];
    [...timeline].reverse().forEach(snap => {
      (snap.articles || []).forEach(a => {
        if (!seenUrls.has(a.url)) {
          seenUrls.add(a.url);
          allArticles.push({ ...a, _snapTs: snap.timestamp });
        }
      });
    });

    // Sort newest first
    allArticles.sort((a, b) => new Date(b._snapTs) - new Date(a._snapTs));

    const totalCount = allArticles.length;
    let timelineOrder = 'desc';

    // Format timestamp for timeline display
    const fmtTl = (ts) => {
      const d = new Date(ts);
      const m = d.getMonth() + 1;
      const day = d.getDate();
      const h = String(d.getHours()).padStart(2, '0');
      const min = String(d.getMinutes()).padStart(2, '0');
      return `${m}月${day}日 ${h}:${min}`;
    };

    const ARTICLES_PER_DAY = 3; // 1日あたり表示する記事数上限
    const DAYS_INITIAL     = 7; // 初期表示する日数上限

    const fmtDay = (ts) => {
      const d = new Date(typeof ts === 'number' && ts < 1e11 ? ts * 1000 : ts);
      return `${d.getFullYear()}/${d.getMonth()+1}/${d.getDate()}`;
    };

    const renderTimeline = () => {
      // 記事を日別にグルーピング（publishedAt → _snapTs の順で使用）
      const dayMap = {};
      allArticles.forEach(a => {
        const ts = a.publishedAt ? a.publishedAt * 1000 : new Date(a._snapTs).getTime();
        const key = fmtDay(new Date(ts));
        if (!dayMap[key]) dayMap[key] = { ts, articles: [] };
        dayMap[key].articles.push({ ...a, _ts: ts });
      });

      // 日付降順 or 昇順に並べ替え
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
                  <div class="timeline-time">${dayKey}</div>
                  <div class="day-articles">
                    ${shown.map(a => {
                      const isNew = a.publishedAt && (Date.now() / 1000 - a.publishedAt) < 6 * 3600;
                      return `<div class="timeline-article">
                        <a href="${esc(a.url)}" class="timeline-article-link" target="_blank" rel="noopener noreferrer">${esc(a.title)}${isNew ? '<span class="new-badge">NEW</span>' : ''}</a>
                        <div class="timeline-source">
                          <img class="source-favicon" src="https://www.google.com/s2/favicons?domain=${esc(a.source)}&sz=16" alt="" width="12" height="12">
                          ${esc(a.source)}
                        </div>
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
        btn.addEventListener('click', () => {
          timelineOrder = btn.dataset.order;
          renderTimeline();
        });
      });

      const showAllBtn = document.getElementById('tl-show-all');
      if (showAllBtn) {
        showAllBtn.addEventListener('click', () => {
          showAll = true;
          storyEl.innerHTML = buildHTML();
          storyEl.querySelectorAll('.sort-btn').forEach(b => b.addEventListener('click', () => { timelineOrder = b.dataset.order; renderTimeline(); }));
        });
      }
    };

    renderTimeline();

    // Related articles section — top 5 articles
    const relatedEl = document.getElementById('related-articles');
    if (relatedEl && allArticles.length) {
      // Pick up to 3 articles: oldest (origin), newest (latest), and one from a different source
      const picked = [];
      const usedSources = new Set();
      const sorted = [...allArticles].sort((a, b) => new Date(a._snapTs) - new Date(b._snapTs));
      // Origin article
      if (sorted.length) { picked.push(sorted[0]); usedSources.add(sorted[0].source); }
      // Latest article (different source preferred)
      const latest = allArticles[0];
      if (latest && latest.url !== (picked[0] && picked[0].url)) { picked.push(latest); usedSources.add(latest.source); }
      // Middle article from a new source
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

    // Related topics — inter-topic navigation
    renderRelatedTopics(meta.relatedTopics);

    // Discovery: 深掘り & 拡張
    renderDiscovery(meta);
  }
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

  section.innerHTML = `
    <div class="discovery-panel">
      <div class="discovery-col" id="disc-deep-col">
        <div class="discovery-col-hd">
          <span class="disc-icon">🔍</span>
          <div><div class="disc-col-title">深掘り</div><div class="disc-col-sub">この話題をさらに詳しく</div></div>
        </div>
        <div class="disc-col-body" id="disc-deep-body"><div class="disc-loading">...</div></div>
      </div>
      <div class="discovery-col" id="disc-expand-col">
        <div class="discovery-col-hd">
          <span class="disc-icon">🌏</span>
          <div><div class="disc-col-title">拡張</div><div class="disc-col-sub" id="disc-expand-sub">今ほかで盛り上がってること</div></div>
        </div>
        <div class="disc-col-body" id="disc-expand-body"><div class="disc-loading">...</div></div>
      </div>
    </div>`;

  fetchAllTopicsOnce().then(allTopics => {
    const curId     = meta.topicId;
    const curGenres = meta.genres || (meta.genre ? [meta.genre] : []);
    const tMap      = {};
    for (const t of allTopics) tMap[t.topicId] = t;

    // --- 深掘り items ---
    const deepItems = [];

    // 1. Parent topic (the bigger story)
    if (meta.parentTopicId) {
      const par = tMap[meta.parentTopicId];
      if (par) deepItems.push({ t: par, badge: { label: '← 大きな流れ', cls: 'parent' } });
    }

    // 2. Child branches (most active first)
    if (meta.childTopics && meta.childTopics.length > 0) {
      const children = meta.childTopics
        .map(ref => tMap[ref.topicId] || ref)
        .filter(c => c && c.topicId !== curId)
        .sort((a, b) => (b.score || 0) - (a.score || 0))
        .slice(0, 2);
      for (const c of children) deepItems.push({ t: c, badge: { label: '↳ 分岐', cls: 'child' } });
    }

    // 3. Same-genre, not already included
    if (deepItems.length < 3 && curGenres.length > 0) {
      const usedIds = new Set(deepItems.map(i => i.t.topicId));
      usedIds.add(curId);
      const sameGenre = allTopics
        .filter(t => {
          if (usedIds.has(t.topicId)) return false;
          const tg = t.genres || (t.genre ? [t.genre] : []);
          return curGenres.some(g => tg.includes(g));
        })
        .sort((a, b) => (b.score || 0) - (a.score || 0))
        .slice(0, 3 - deepItems.length);
      for (const t of sameGenre) deepItems.push({ t, badge: { label: '同ジャンル', cls: 'same' } });
    }

    // Render deep
    const deepBody = document.getElementById('disc-deep-body');
    if (deepBody) {
      const html = deepItems.slice(0, 3).map(({ t, badge }) => discCard(t, badge)).join('');
      const smLink = (meta.childTopics && meta.childTopics.length > 0)
        ? `<a href="storymap.html?id=${esc(meta.topicId)}" class="disc-see-all">🗺 ストーリーマップ (${meta.childTopics.length}件の分岐) →</a>`
        : '';
      deepBody.innerHTML = (html || '<p class="disc-empty">関連トピックを収集中...</p>') + smLink;
    }

    // --- 拡張 items: different genre, high velocity ---
    const expandItems = allTopics
      .filter(t => {
        if (t.topicId === curId) return false;
        if (curGenres.length > 0) {
          const tg = t.genres || (t.genre ? [t.genre] : []);
          if (curGenres.some(g => tg.includes(g))) return false;
        }
        return (t.score || 0) > 0;
      })
      .sort((a, b) => ((b.velocityScore || 0) - (a.velocityScore || 0)) || ((b.score || 0) - (a.score || 0)))
      .slice(0, 3);

    const expandBody = document.getElementById('disc-expand-body');
    if (expandBody) {
      expandBody.innerHTML = expandItems.length > 0
        ? expandItems.map(t => discCard(t, null)).join('')
        : '<p class="disc-empty">トレンドを取得中...</p>';
    }

    // Location layer removed — position prompt was confusing to users
  });
}

// ===== コメント掲示板 =====

function commentsApiUrl(topicId) {
  if (typeof COMMENTS_URL === 'undefined' || !COMMENTS_URL) return null;
  return `${COMMENTS_URL.replace(/\/$/, '')}/comments/${topicId}`;
}

function fmtCommentDate(iso) {
  try {
    const d = new Date(iso);
    const now = new Date();
    const diffMs = now - d;
    const diffMin = Math.floor(diffMs / 60000);
    if (diffMin < 1)  return 'たった今';
    if (diffMin < 60) return `${diffMin}分前`;
    const diffH = Math.floor(diffMin / 60);
    if (diffH < 24)   return `${diffH}時間前`;
    return d.toLocaleDateString('ja-JP', { month: 'numeric', day: 'numeric' });
  } catch { return ''; }
}

function renderComments(comments) {
  const listEl = document.getElementById('comments-list');
  if (!listEl) return;

  if (!comments || !comments.length) {
    listEl.innerHTML = '<div class="comments-empty">まだコメントはありません。最初のコメントを投稿しましょう！</div>';
    return;
  }

  listEl.innerHTML = comments.map(c => `
    <div class="comment-item">
      <div class="comment-header">
        <span class="comment-nick">${esc(c.nickname || '匿名')}</span>
        <span class="comment-time">${fmtCommentDate(c.createdAt)}</span>
      </div>
      <div class="comment-body">${esc(c.body)}</div>
    </div>
  `).join('');
}

async function loadComments(topicId) {
  const url = commentsApiUrl(topicId);
  if (!url) return;
  try {
    const r = await fetch(url);
    const data = await r.json();
    renderComments(data.comments || []);
  } catch (e) {
    const listEl = document.getElementById('comments-list');
    if (listEl) listEl.innerHTML = '<div class="comments-empty">コメントの読み込みに失敗しました。</div>';
  }
}

function setupCommentForm(topicId) {
  const url      = commentsApiUrl(topicId);
  const section  = document.getElementById('comments-section');
  if (!url) { if (section) section.style.display = 'none'; return; }

  const formArea    = document.getElementById('comment-form-area');
  const loginPrompt = document.getElementById('comment-login-prompt');
  const bodyEl      = document.getElementById('comment-body');
  const nickEl      = document.getElementById('comment-nickname');
  const charsEl     = document.getElementById('comment-chars');
  const submitEl    = document.getElementById('comment-submit');
  const errorEl     = document.getElementById('comment-error');

  // ログイン状態に応じてフォームを切り替え
  if (!currentUser) {
    // 未ログイン: ログイン促進メッセージを表示
    if (formArea)    formArea.style.display    = 'none';
    if (loginPrompt) loginPrompt.style.display = 'block';
    return;
  }

  // ログイン済み: フォームを表示
  if (loginPrompt) loginPrompt.style.display = 'none';
  if (formArea)    formArea.style.display    = 'block';

  // ニックネーム: 編集可能、変更するとlocalStorageに保存
  if (nickEl) {
    nickEl.value    = getDisplayName(currentUser);
    nickEl.readOnly = false;
    nickEl.placeholder = '名前（任意）';
    nickEl.style.backgroundColor = '';
    nickEl.style.cursor          = '';
    nickEl.addEventListener('change', () => {
      const v = nickEl.value.trim();
      if (v) saveNickname(v);
    });
  }

  if (!bodyEl || !submitEl) return;

  // 既存のリスナーを避けるためクローンに差し替え
  const newSubmit = submitEl.cloneNode(true);
  submitEl.parentNode.replaceChild(newSubmit, submitEl);

  // 文字数カウンター
  const newBody = bodyEl.cloneNode(true);
  bodyEl.parentNode.replaceChild(newBody, bodyEl);
  newBody.addEventListener('input', () => {
    const len = newBody.value.length;
    if (charsEl) charsEl.textContent = len;
    charsEl && charsEl.parentElement.classList.toggle('comment-char-warn', len > 180);
  });

  // 送信
  newSubmit.addEventListener('click', async () => {
    const body     = newBody.value.trim();
    const nickInput = document.getElementById('comment-nickname');
    const nickname  = (nickInput && nickInput.value.trim()) || getDisplayName(currentUser);

    if (errorEl) errorEl.textContent = '';

    if (!body) {
      if (errorEl) errorEl.textContent = 'コメント本文を入力してください。';
      return;
    }
    if (body.length > 200) {
      if (errorEl) errorEl.textContent = '200文字以内で入力してください。';
      return;
    }

    newSubmit.disabled = true;
    newSubmit.textContent = '送信中...';

    try {
      const r = await fetch(url, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({
          body,
          nickname,
          topicId,
          idToken: currentUser.token,
        }),
      });
      const data = await r.json();

      if (!r.ok) {
        if (errorEl) errorEl.textContent = data.error || '投稿に失敗しました。';
      } else {
        newBody.value = '';
        if (charsEl) charsEl.textContent = '0';
        await loadComments(topicId);
        if (errorEl) {
          errorEl.className = 'comment-success';
          errorEl.textContent = '投稿しました！';
          setTimeout(() => {
            errorEl.textContent = '';
            errorEl.className = 'comment-error';
          }, 3000);
        }
      }
    } catch (e) {
      if (errorEl) errorEl.textContent = 'ネットワークエラーが発生しました。';
    } finally {
      newSubmit.disabled = false;
      newSubmit.textContent = '投稿する';
    }
  });
}

document.addEventListener('DOMContentLoaded', () => {
  // Service Worker 登録（PWAオフライン対応）
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js').catch(err => console.warn('SW registration failed:', err));
  }

  // ===== PWAインストールバナー =====
  (function initPwaBanner() {
    // 過去に「×」で閉じた場合は表示しない
    if (localStorage.getItem('pwa_dismissed') === '1') return;

    let deferredPrompt = null;
    const banner      = document.getElementById('pwa-install-banner');
    const installBtn  = document.getElementById('pwa-install-btn');
    const dismissBtn  = document.getElementById('pwa-dismiss-btn');

    window.addEventListener('beforeinstallprompt', e => {
      e.preventDefault();
      deferredPrompt = e;
      if (banner) banner.style.display = 'flex';
    });

    if (installBtn) {
      installBtn.addEventListener('click', () => {
        if (!deferredPrompt) return;
        deferredPrompt.prompt();
        deferredPrompt.userChoice.then(choice => {
          if (choice.outcome === 'accepted') {
            if (banner) banner.style.display = 'none';
          }
          deferredPrompt = null;
        });
      });
    }

    if (dismissBtn) {
      dismissBtn.addEventListener('click', () => {
        if (banner) banner.style.display = 'none';
        localStorage.setItem('pwa_dismissed', '1');
      });
    }

    // インストール済みなら非表示
    window.addEventListener('appinstalled', () => {
      if (banner) banner.style.display = 'none';
      deferredPrompt = null;
    });
  })();

  // Google 認証の初期化
  initGoogleAuth();

  const topicId = new URLSearchParams(location.search).get('id');
  if (topicId) {
    trackView(topicId);
    const showError = () => {
      const titleEl = document.getElementById('topic-title');
      if (titleEl) titleEl.textContent = '読み込みに失敗しました';
    };
    const refresh = () => fetch(apiUrl(`topic/${topicId}`))
      .then(r => { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(data => { try { renderDetail(data); } catch(e) { console.error('renderDetail error:', e); } })
      .catch(err => { console.error('fetch error:', err); showError(); });
    refresh();
    setInterval(refresh, REFRESH_MS);

    loadComments(topicId);
    setupCommentForm(topicId);
    setInterval(() => loadComments(topicId), 3 * 60 * 1000);
  } else if (document.getElementById('topics-grid')) {
    buildFilters();
    setupSearch();
    setupFavsToggle();
    loadWeather();
    // お気に入り読み込み後にトピック表示
    loadFavorites().finally(() => {
      refreshTopics();
      setInterval(refreshTopics, REFRESH_MS);
    });
  }
});
