// ===== @mention通知バッジ =====
// 依存: config.js (_APIGW), auth.js (currentUser), js/auth.js で loadUser()

async function loadNotifBadge() {
  const user = typeof currentUser !== 'undefined' ? currentUser : null;
  if (!user) return;
  const handle = (user.handle || getProfile().handle || '').trim();
  if (!handle || typeof _APIGW === 'undefined') return;

  try {
    const r = await fetch(`${_APIGW}/notifications/${encodeURIComponent(handle)}`);
    if (!r.ok) return;
    const data = await r.json();
    const unread = data.unread || 0;
    const badge = document.getElementById('notif-badge');
    if (badge) {
      badge.textContent = unread > 9 ? '9+' : String(unread);
      badge.style.display = unread > 0 ? 'inline-flex' : 'none';
    }
  } catch {}
}

function getProfile() {
  try { return JSON.parse(localStorage.getItem('flotopic_profile') || '{}'); } catch { return {}; }
}

document.addEventListener('DOMContentLoaded', () => {
  // auth が初期化された後に実行
  setTimeout(loadNotifBadge, 800);
});
