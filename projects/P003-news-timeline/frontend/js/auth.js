// ===== 認証管理 (Google Sign-In / 将来: Apple Sign-In) =====
// 依存: config.js (AUTH_URL, GOOGLE_CLIENT_ID)

let currentUser = null;

// ── ストレージヘルパー ─────────────────────────────────────────
function loadUser()  { try { return JSON.parse(localStorage.getItem('flotopic_user') || 'null'); } catch { return null; } }
function saveUser(u) { try { if (u) localStorage.setItem('flotopic_user', JSON.stringify(u)); else localStorage.removeItem('flotopic_user'); } catch {} }
function getDisplayName(user) {
  if (!user) return '';
  if (user.nickname) return user.nickname;
  const full = user.name || '';
  return full.split(/\s+/)[0] || full || 'ユーザー';
}
function saveNickname(nickname) {
  try { const u = loadUser(); if (u) { u.nickname = nickname; saveUser(u); if (currentUser) currentUser.nickname = nickname; } } catch {}
}

// ── プロフィールをサーバーに同期 ─────────────────────────────
async function syncProfileToServer(profileData) {
  if (!currentUser || typeof AUTH_URL === 'undefined') return;
  try {
    // IDトークンの有効期限チェック（1時間で失効）
    try {
      const p = JSON.parse(atob(currentUser.token.split('.')[1]));
      if (p.exp * 1000 < Date.now()) return;
    } catch {}
    const body = { idToken: currentUser.token };
    if (profileData.handle)    body.handle    = profileData.handle;
    if (profileData.ageGroup)  body.ageGroup  = profileData.ageGroup;
    if (profileData.gender)    body.gender    = profileData.gender;
    if (profileData.nickname)  body.nickname  = profileData.nickname;
    if (profileData.interests) body.interests = profileData.interests;
    if (profileData.avatarUrl) body.avatarUrl = profileData.avatarUrl;
    await fetch(AUTH_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (profileData.handle)    { currentUser.handle    = profileData.handle;    saveUser(currentUser); }
    if (profileData.nickname)  { currentUser.nickname  = profileData.nickname;  saveUser(currentUser); }
    if (profileData.interests) { currentUser.interests = profileData.interests; saveUser(currentUser); }
    if (profileData.avatarUrl) { currentUser.avatarUrl = profileData.avatarUrl; saveUser(currentUser); }
  } catch {}
}

// 後方互換エイリアス
async function syncHandleToServer(handle) {
  return syncProfileToServer({ handle });
}

// ── ログイン後にサーバーのプロフィールをローカルにマージ ────
function mergeServerProfile(data) {
  try {
    const prof = JSON.parse(localStorage.getItem('flotopic_profile') || '{}');
    let changed = false;
    // サーバー値で常に上書き（同一Googleアカウントなのでサーバーが正）
    if (data.handle   !== undefined) { prof.handle   = data.handle   || prof.handle   || ''; changed = true; }
    if (data.ageGroup !== undefined) { prof.ageGroup = data.ageGroup || prof.ageGroup || ''; changed = true; }
    if (data.gender   !== undefined) { prof.gender   = data.gender   || prof.gender   || ''; changed = true; }
    if (data.nickname !== undefined) { prof.nickname = data.nickname || prof.nickname || ''; changed = true; }
    if (Array.isArray(data.interests) && data.interests.length) {
      prof.interests = data.interests;
      changed = true;
    }
    if (changed) localStorage.setItem('flotopic_profile', JSON.stringify(prof));

    // アバターURL: サーバーにカスタム画像があればlocalStorageに反映（デバイス間同期）
    if (data.avatarUrl) {
      try { localStorage.setItem('flotopic_avatar', data.avatarUrl); } catch {}
    }
  } catch {}
}

// ── 認証UI更新 ────────────────────────────────────────────────
function updateAuthUI() {
  const signInBtn    = document.getElementById('auth-signin-btn');
  const userMenuWrap = document.getElementById('user-menu-wrap');
  const userAvatar   = document.getElementById('auth-user-avatar');
  const userInit     = document.getElementById('auth-user-init');
  const userName     = document.getElementById('auth-user-name');
  const modal        = document.getElementById('auth-modal');

  // 後方互換: 旧要素は常に非表示
  const legacyLink   = document.getElementById('auth-user-link');
  const legacySignout = document.getElementById('auth-signout-btn');
  const mypageLink   = document.getElementById('mypage-link');
  if (legacyLink)    legacyLink.style.display    = 'none';
  if (legacySignout) legacySignout.style.display = 'none';
  if (mypageLink)    mypageLink.style.display    = 'none';

  if (currentUser) {
    if (signInBtn)    signInBtn.style.display    = 'none';
    if (userMenuWrap) userMenuWrap.style.display = 'inline-flex';
    if (modal)        modal.style.display        = 'none';

    // アバター画像 or イニシャル
    const savedAvatar = (() => { try { return localStorage.getItem('flotopic_avatar') || ''; } catch { return ''; } })();
    const pic = savedAvatar || currentUser.picture || '';
    if (userAvatar) {
      if (pic) {
        userAvatar.src = pic;
        userAvatar.style.display = 'inline-block';
        if (userInit) userInit.style.display = 'none';
      } else {
        userAvatar.style.display = 'none';
        if (userInit) {
          const initial = getDisplayName(currentUser).charAt(0).toUpperCase() || '?';
          userInit.textContent = initial;
          userInit.style.display = 'inline-flex';
        }
      }
    }
    if (userName) userName.textContent = getDisplayName(currentUser);
  } else {
    if (signInBtn)    signInBtn.style.display    = 'inline-flex';
    if (userMenuWrap) userMenuWrap.style.display = 'none';
    if (userName)     userName.textContent       = '';
  }
}

// ── 認証モーダル ──────────────────────────────────────────────
function openAuthModal() {
  const modal = document.getElementById('auth-modal');
  if (!modal) return;
  modal.style.display = 'flex';

  // 特典を明示（初回のみ書き換え）
  const desc = modal.querySelector('.auth-modal-desc');
  if (desc && !desc.dataset.enhanced) {
    desc.innerHTML =
      '<ul style="list-style:none;padding:0;margin:0;text-align:left;font-size:.82rem;color:inherit;">' +
      '<li style="padding:3px 0;">⭐ お気に入りトピックを保存</li>' +
      '<li style="padding:3px 0;">📱 閲覧履歴をどのデバイスでも同期</li>' +
      '<li style="padding:3px 0;">🎯 ジャンル設定をどのデバイスでも引き継ぎ</li>' +
      '</ul>';
    desc.dataset.enhanced = '1';
  }

  const wrap = document.getElementById('auth-modal-google-wrap');
  if (wrap && !wrap.hasChildNodes() && window.google && google.accounts && google.accounts.id) {
    google.accounts.id.renderButton(wrap, {
      type: 'standard', theme: 'outline', size: 'large', text: 'signin_with', locale: 'ja', width: 280,
    });
  }
}
function closeAuthModal() {
  const modal = document.getElementById('auth-modal');
  if (modal) modal.style.display = 'none';
}

// ── ドロップダウン制御 ─────────────────────────────────────────
function setupUserDropdown() {
  const trigger = document.getElementById('user-menu-trigger');
  const wrap    = document.getElementById('user-menu-wrap');
  if (!trigger || !wrap) return;

  trigger.addEventListener('click', () => {
    const isOpen = wrap.classList.toggle('open');
    trigger.setAttribute('aria-expanded', String(isOpen));
  });

  // wrap の外をクリックしたら閉じる（contains でチェック）
  document.addEventListener('click', e => {
    if (!wrap.contains(e.target)) {
      wrap.classList.remove('open');
      trigger.setAttribute('aria-expanded', 'false');
    }
  });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') { wrap.classList.remove('open'); trigger.setAttribute('aria-expanded', 'false'); }
  });
}

// ── Google認証コールバック ─────────────────────────────────────
async function handleGoogleCredentialResponse(response) {
  const idToken = response.credential;
  if (!idToken) return;
  closeAuthModal();

  function _retryPendingDelete() {
    const pending = window._pendingCommentDelete;
    if (pending && typeof deleteComment === 'function') {
      window._pendingCommentDelete = null;
      deleteComment(pending.topicId, pending.commentId);
    }
  }

  function localLogin(token) {
    try {
      const p = JSON.parse(atob(token.split('.')[1]));
      currentUser = { userId: p.sub, name: p.name || '', picture: p.picture || '', handle: '', token };
      saveUser(currentUser);
      updateAuthUI();
      if (typeof showToast === 'function') showToast(`${getDisplayName(currentUser)} でログインしました`);
      const tid = new URLSearchParams(location.search).get('id');
      if (tid && typeof setupCommentForm === 'function') setupCommentForm(tid);
      _retryPendingDelete();
    } catch {}
  }

  if (typeof AUTH_URL === 'undefined' || !AUTH_URL) { localLogin(idToken); return; }

  try {
    const r = await fetch(AUTH_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ idToken }),
    });
    if (r.ok) {
      const data = await r.json();
      currentUser = { ...data, token: idToken };
      saveUser(currentUser);
      mergeServerProfile(data);
      updateAuthUI();
      if (typeof loadFavorites === 'function') loadFavorites();
      if (typeof showToast === 'function') showToast(`${getDisplayName(currentUser)} でログインしました`);
      const tid = new URLSearchParams(location.search).get('id');
      if (tid && typeof setupCommentForm === 'function') setupCommentForm(tid);
      _retryPendingDelete();
      // interests があればデフォルトジャンルに反映（index.html のみ）
      _applyInterestsAsGenre(data.interests);
      // 初回ログイン時のみ興味ジャンル選択を表示（index.html のみ）
      _maybeShowGenreOnboarding();
    } else {
      localLogin(idToken);
    }
  } catch {
    localLogin(idToken);
  }
}

function signOut() {
  currentUser = null;
  saveUser(null);
  updateAuthUI();
  if (window.google && google.accounts && google.accounts.id) google.accounts.id.disableAutoSelect();
  const tid = new URLSearchParams(location.search).get('id');
  if (tid && typeof setupCommentForm === 'function') setupCommentForm(tid);
}

// ── ログイン後ヘルパー ─────────────────────────────────────────

// interests[0] をデフォルトジャンルに適用（index.html でのみ有効）
function _applyInterestsAsGenre(interests) {
  if (!Array.isArray(interests) || !interests.length) return;
  // app.js の currentGenre / savePrefs が存在する場合のみ適用
  if (typeof currentGenre === 'undefined' || typeof savePrefs !== 'function') return;
  // すでにジャンルが選択済み（総合以外）なら上書きしない
  if (currentGenre && currentGenre !== '総合') return;
  const genre = interests[0];
  if (!genre) return;
  currentGenre = genre;
  try { savePrefs({ ...loadPrefs(), genre }); } catch {}
  // フィルターボタンUIを更新
  document.querySelectorAll('.genre-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.genre === genre);
  });
  if (typeof renderTopics === 'function' && typeof allTopics !== 'undefined') {
    renderTopics(allTopics);
  }
}

// ログイン後、まだジャンル未選択ならオンボーディングを表示（index.html のみ）
function _maybeShowGenreOnboarding() {
  if (localStorage.getItem('flotopic_genre_selected')) return;
  if (typeof showGenreOnboarding === 'function') showGenreOnboarding();
}

// アバター画像URLをサーバーに保存（S3アップロード完了後に呼ぶ）
async function syncAvatarToServer(avatarUrl) {
  return syncProfileToServer({ avatarUrl });
}

// ── 初期化 ────────────────────────────────────────────────────
function initGoogleAuth() {
  if (window.__authInitialized) return;
  window.__authInitialized = true;
  currentUser = loadUser();
  updateAuthUI();
  setupUserDropdown();

  const clientId = (typeof GOOGLE_CLIENT_ID !== 'undefined') ? GOOGLE_CLIENT_ID : '';
  if (!clientId) return;

  const signInBtn  = document.getElementById('auth-signin-btn');
  const ddSignout  = document.getElementById('dd-signout-btn');
  const closeBtn   = document.getElementById('auth-modal-close');

  if (signInBtn) signInBtn.addEventListener('click', openAuthModal);
  if (ddSignout) ddSignout.addEventListener('click', signOut);
  if (closeBtn)  closeBtn.addEventListener('click', closeAuthModal);

  const modal = document.getElementById('auth-modal');
  if (modal) modal.addEventListener('click', e => { if (e.target === modal) closeAuthModal(); });

  function setupGIS() {
    if (window.__gsiInitialized) return;
    if (!window.google || !google.accounts || !google.accounts.id) return;
    window.__gsiInitialized = true;
    google.accounts.id.initialize({
      client_id:   clientId,
      callback:    handleGoogleCredentialResponse,
      auto_select: false,
      ux_mode:     'popup',
    });
  }

  if (window.google && google.accounts && google.accounts.id) setupGIS();
  else window.__gsiReady = setupGIS;
}

document.addEventListener('DOMContentLoaded', initGoogleAuth);
