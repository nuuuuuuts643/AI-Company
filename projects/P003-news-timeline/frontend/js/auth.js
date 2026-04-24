// ===== Google Auth =====
// 依存: config.js (AUTH_URL, GOOGLE_CLIENT_ID), app.js (showToast, setupCommentForm)

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
      userAvatar.src           = currentUser.picture || '';
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

  if (typeof AUTH_URL === 'undefined' || !AUTH_URL) {
    try {
      const payload = JSON.parse(atob(idToken.split('.')[1]));
      currentUser = { userId: payload.sub, name: payload.name || '', picture: payload.picture || '', token: idToken };
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
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ idToken }),
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
  } catch {
    localLoginFromToken(idToken);
  }
}

function signOut() {
  currentUser = null;
  saveUser(null);
  updateAuthUI();
  if (window.google && google.accounts && google.accounts.id) {
    google.accounts.id.disableAutoSelect();
  }
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
      const btnWrap = document.createElement('div');
      btnWrap.id = 'google-btn-wrap';
      btnWrap.style.display = 'inline-block';
      signInBtn.parentNode.insertBefore(btnWrap, signInBtn);
      signInBtn.style.display = 'none';
      google.accounts.id.renderButton(btnWrap, {
        type: 'standard', theme: 'outline', size: 'medium',
        text: 'signin_with', locale: 'ja',
      });
      if (currentUser) btnWrap.style.display = 'none';
    }
  }

  if (window.google && google.accounts && google.accounts.id) {
    setupGIS();
  } else {
    window.__gsiReady = setupGIS;
  }
}
