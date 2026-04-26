// ===== お気に入り管理 =====
// 依存: config.js (FAVORITES_URL), auth.js (currentUser), app.js (renderTopics, allTopics, currentPage)

const FAV_LS_KEY  = 'flotopic_favs';
const FAV_SEEN_KEY = 'flotopic_fav_seen'; // {topicId: lastUpdated文字列}
let userFavorites = new Set();
let showFavsOnly = false;

// お気に入りトピックの「既読lastUpdated」を管理
function getFavSeenMap() {
  try { return JSON.parse(localStorage.getItem(FAV_SEEN_KEY) || '{}'); } catch { return {}; }
}
function markFavSeen(topicId, lastUpdated) {
  try {
    const m = getFavSeenMap();
    m[topicId] = lastUpdated || '';
    localStorage.setItem(FAV_SEEN_KEY, JSON.stringify(m));
  } catch {}
}
// トピックリスト更新後に呼ぶ: 初回ならseenに記録し、2回目以降は更新検知
function syncFavSeenTimes(topics) {
  const m = getFavSeenMap();
  topics.forEach(t => {
    if (userFavorites.has(t.topicId) && !(t.topicId in m)) {
      m[t.topicId] = t.lastUpdated || '';
    }
  });
  try { localStorage.setItem(FAV_SEEN_KEY, JSON.stringify(m)); } catch {}
}
// お気に入りかつ前回より更新されているか
function isFavUpdated(t) {
  if (!userFavorites.has(t.topicId)) return false;
  const m = getFavSeenMap();
  if (!(t.topicId in m)) return false; // 初回は更新扱いしない
  return (t.lastUpdated || '') > (m[t.topicId] || '');
}

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
    if (typeof openAuthModal === 'function') openAuthModal();
    return;
  }
  const base = favApiUrl();
  if (!base) return;

  const isFav = userFavorites.has(topicId);
  heartBtn.disabled = true;

  // 楽観的UI更新（即反映）
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

  try {
    const r = await fetch(`${base}/favorites`, {
      method: isFav ? 'DELETE' : 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ userId: currentUser.userId, idToken: currentUser.token, topicId }),
    });
    if (!r.ok) {
      if (r.status === 401) {
        // トークン切れ → ローカルは反映済みのまま、次回ログイン時にサーバー同期
        if (typeof showToast === 'function') showToast('セッション切れ。再ログインでサーバー同期されます');
      } else {
        // その他エラー → ロールバック
        if (isFav) { userFavorites.add(topicId); heartBtn.classList.add('fav-active'); heartBtn.title = 'お気に入りを解除'; }
        else        { userFavorites.delete(topicId); heartBtn.classList.remove('fav-active'); heartBtn.title = 'お気に入りに追加'; }
        saveLocalFavs(userFavorites);
        if (typeof showToast === 'function') showToast('エラーが発生しました');
      }
    }
  } catch {
    if (typeof showToast === 'function') showToast('ネットワークエラー。ローカルには保存しました');
  }
  heartBtn.disabled = false;
}

// ジャンル設定クラウド同期
async function syncGenreToCloud(genre) {
  if (!currentUser) return;
  const base = favApiUrl();
  if (!base) return;
  try {
    await fetch(`${base}/prefs`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ userId: currentUser.userId, idToken: currentUser.token, genre }),
    });
  } catch {}
}

async function loadGenreFromCloud() {
  if (!currentUser) return null;
  const base = favApiUrl();
  if (!base) return null;
  try {
    const r = await fetch(`${base}/prefs/${currentUser.userId}`);
    if (r.ok) {
      const data = await r.json();
      return data.genre || null;
    }
  } catch {}
  return null;
}

function setupFavsToggle() {
  const btn = document.getElementById('fav-toggle-btn');
  if (!btn) return;
  btn.addEventListener('click', () => {
    if (!currentUser && userFavorites.size === 0) {
      if (typeof openAuthModal === 'function') openAuthModal();
      return;
    }
    showFavsOnly = !showFavsOnly;
    btn.classList.toggle('active', showFavsOnly);
    currentPage = 1;
    renderTopics(allTopics);
  });
}
