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

// ── ハンドルをサーバーに同期 ──────────────────────────────────
async function syncHandleToServer(handle) {
  if (!currentUser || !handle || typeof AUTH_URL === 'undefined') return;
  try {
    await fetch(AUTH_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ idToken: currentUser.token, handle }),
    });
    currentUser.handle = handle;
    saveUser(currentUser);
  } catch {}
}

// ── ログイン後にサーバーから返ったハンドルをローカルにマージ ──
function mergeServerHandle(serverHandle) {
  if (!serverHandle) return;
  try {
    const prof = JSON.parse(localStorage.getItem('flotopic_profile') || '{}');
    if (!prof.handle) {
      prof.handle = serverHandle;
      localStorage.setItem('flotopic_profile', JSON.stringify(prof));
    }
  } catch {}
}

// ── 認証UI更新 ────────────────────────────────────────────────
function updateAuthUI() {
  const signInBtn  = document.getElementById('auth-signin-btn');
  const signOutBtn = document.getElementById('auth-signout-btn');
  const userAvatar = document.getElementById('auth-user-avatar');
  const userName   = document.getElementById('auth-user-name');
  const mypageLink = document.getElementById('mypage-link');
  const modal      = document.getElementById('auth-modal');

  if (mypageLink) mypageLink.style.display = 'inline-flex';

  if (currentUser) {
    if (signInBtn)  signInBtn.style.display  = 'none';
    if (signOutBtn) signOutBtn.style.display = 'inline-flex';
    if (userAvatar) {
      userAvatar.src          = currentUser.picture || '';
      userAvatar.style.display = currentUser.picture ? 'inline-block' : 'none';
    }
    if (userName) userName.textContent = getDisplayName(currentUser);
    if (modal)    modal.style.display  = 'none';
  } else {
    if (signInBtn)  signInBtn.style.display  = 'inline-flex';
    if (signOutBtn) signOutBtn.style.display = 'none';
    if (userAvatar) userAvatar.style.display = 'none';
    if (userName)   userName.textContent     = '';
  }
}

// ── 認証モーダル ──────────────────────────────────────────────
function openAuthModal() {
  const modal = document.getElementById('auth-modal');
  if (!modal) return;
  modal.style.display = 'flex';
  // Googleボタンをモーダルのコンテナにレンダリングする
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

// ── Google認証コールバック ─────────────────────────────────────
async function handleGoogleCredentialResponse(response) {
  const idToken = response.credential;
  if (!idToken) return;
  closeAuthModal();

  function localLogin(token) {
    try {
      const p = JSON.parse(atob(token.split('.')[1]));
      currentUser = { userId: p.sub, name: p.name || '', picture: p.picture || '', handle: '', token };
      saveUser(currentUser);
      updateAuthUI();
      if (typeof showToast === 'function') showToast(`${getDisplayName(currentUser)} でログインしました`);
      const tid = new URLSearchParams(location.search).get('id');
      if (tid && typeof setupCommentForm === 'function') setupCommentForm(tid);
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
      mergeServerHandle(data.handle);  // サーバー上のhandleをローカルにマージ
      updateAuthUI();
      if (typeof showToast === 'function') showToast(`${getDisplayName(currentUser)} でログインしました`);
      const tid = new URLSearchParams(location.search).get('id');
      if (tid && typeof setupCommentForm === 'function') setupCommentForm(tid);
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

// ── 初期化 ────────────────────────────────────────────────────
function initGoogleAuth() {
  currentUser = loadUser();
  updateAuthUI();

  const clientId = (typeof GOOGLE_CLIENT_ID !== 'undefined') ? GOOGLE_CLIENT_ID : '';
  if (!clientId) return;

  const signInBtn  = document.getElementById('auth-signin-btn');
  const signOutBtn = document.getElementById('auth-signout-btn');
  const closeBtn   = document.getElementById('auth-modal-close');

  if (signInBtn)  signInBtn.addEventListener('click', openAuthModal);
  if (signOutBtn) signOutBtn.addEventListener('click', signOut);
  if (closeBtn)   closeBtn.addEventListener('click', closeAuthModal);

  // モーダル外クリックで閉じる
  const modal = document.getElementById('auth-modal');
  if (modal) modal.addEventListener('click', e => { if (e.target === modal) closeAuthModal(); });

  function setupGIS() {
    if (!window.google || !google.accounts || !google.accounts.id) return;
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
