// ===== お気に入り管理 =====
// 依存: config.js (FAVORITES_URL), auth.js (currentUser), app.js (renderTopics, allTopics, currentPage)

const FAV_LS_KEY = 'flotopic_favs';
let userFavorites = new Set();
let showFavsOnly = false;

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
  try {
    const r = await fetch(`${base}/favorites`, {
      method: isFav ? 'DELETE' : 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ userId: currentUser.userId, idToken: currentUser.token, topicId }),
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
