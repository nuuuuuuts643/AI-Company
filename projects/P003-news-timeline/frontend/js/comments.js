// ===== X風コメント掲示板 =====
// 依存: config.js (COMMENTS_URL), auth.js (currentUser, getDisplayName, saveNickname), app.js (esc, showToast)

// ── localStorageキー ──────────────────────────────────────────────
const LIKES_KEY    = 'flotopic_likes';           // { commentId: true }
const DISLIKES_KEY = 'flotopic_dislikes';        // { commentId: true }
const SAVES_KEY    = 'flotopic_saved_comments';  // { commentId: true }
const PROFILE_KEY  = 'flotopic_profile';         // { handle, ageGroup, gender }

// ── localStorage ヘルパー ─────────────────────────────────────────
function getLikedSet()    { try { return JSON.parse(localStorage.getItem(LIKES_KEY)    || '{}'); } catch { return {}; } }
function getDislikedSet() { try { return JSON.parse(localStorage.getItem(DISLIKES_KEY) || '{}'); } catch { return {}; } }
function getSavedSet()    { try { return JSON.parse(localStorage.getItem(SAVES_KEY)    || '{}'); } catch { return {}; } }
function getProfile()     { try { return JSON.parse(localStorage.getItem(PROFILE_KEY)  || '{}'); } catch { return {}; } }

// ── URL ヘルパー ──────────────────────────────────────────────────
function commentsApiUrl(topicId) {
  if (typeof COMMENTS_URL === 'undefined' || !COMMENTS_URL) return null;
  return `${COMMENTS_URL.replace(/\/$/, '')}/comments/${topicId}`;
}

function commentsLikeUrl(topicId, commentId, userHash) {
  if (typeof COMMENTS_URL === 'undefined' || !COMMENTS_URL) return null;
  const base = COMMENTS_URL.replace(/\/$/, '');
  return `${base}/comments/like?topicId=${encodeURIComponent(topicId)}&commentId=${encodeURIComponent(commentId)}&userHash=${encodeURIComponent(userHash)}`;
}

// ── 時刻フォーマット ──────────────────────────────────────────────
function fmtCommentDate(iso) {
  try {
    const d = new Date(iso);
    const diffMin = Math.floor((new Date() - d) / 60000);
    if (diffMin < 1)  return 'たった今';
    if (diffMin < 60) return `${diffMin}分前`;
    const diffH = Math.floor(diffMin / 60);
    if (diffH < 24)   return `${diffH}時間前`;
    return d.toLocaleDateString('ja-JP', { year: 'numeric', month: 'numeric', day: 'numeric' });
  } catch { return ''; }
}

// ── ユーザーIDハッシュ（本人判定用） ─────────────────────────────
let _myCommentHash = null;

async function getMyCommentHash() {
  if (!currentUser) return null;
  if (_myCommentHash) return _myCommentHash;
  try {
    const enc = new TextEncoder().encode(currentUser.userId);
    const buf = await crypto.subtle.digest('SHA-256', enc);
    _myCommentHash = Array.from(new Uint8Array(buf))
      .map(b => b.toString(16).padStart(2, '0')).join('').slice(0, 16);
    return _myCommentHash;
  } catch { return null; }
}

// ── アバター HTML ─────────────────────────────────────────────────
function initials(name) {
  if (!name) return '?';
  const s = name.trim();
  return s[0].toUpperCase();
}

function avatarHtml(comment, isOwn) {
  const name = comment.nickname || '匿名';
  let pic = '';
  if (isOwn) {
    // 優先順位: Flotopicアバター（localStorage）> Googleアバター > なし
    try { pic = localStorage.getItem('flotopic_avatar') || ''; } catch {}
    if (!pic && currentUser && currentUser.picture) pic = currentUser.picture;
  } else {
    // 他ユーザー: DBに保存されたアバターURL（Google CDN or Flotopic CloudFront）
    pic = comment.avatarUrl || '';
  }
  if (pic) {
    return `<img class="cx-avatar" src="${esc(pic)}" alt=""
      onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">` +
      `<div class="cx-avatar cx-avatar-init" style="display:none">${esc(initials(name))}</div>`;
  }
  return `<div class="cx-avatar-init">${esc(initials(name))}</div>`;
}

// ── @メンションをリンクに変換 ────────────────────────────────────
function mentionBody(text) {
  return esc(text).replace(/@([A-Za-z0-9_]{1,20})/g,
    '<a class="cx-mention" href="profile.html?handle=$1">@$1</a>');
}

// ── コメントリストからハンドルを収集（@サジェスト用） ──────────
let _topicHandles = [];

function collectHandles(comments) {
  _topicHandles = [...new Set(
    comments.filter(c => c.handle && c.handle.trim()).map(c => c.handle.trim())
  )];
}

// ── コメント描画（X風） ───────────────────────────────────────────
function renderComments(comments, topicId, myHash) {
  const listEl = document.getElementById('comments-list');
  if (!listEl) return;

  if (!comments || !comments.length) {
    const loggedIn = !!currentUser;
    const ctaHtml = loggedIn
      ? `<button class="ces-cta-btn" onclick="document.getElementById('comment-body')?.focus();document.getElementById('comment-form-area')?.scrollIntoView({behavior:'smooth',block:'center'})">コメントを書く</button>`
      : `<button class="ces-cta-btn" onclick="document.getElementById('auth-signin-btn')?.click()">Googleでログインして投稿</button>`;
    listEl.innerHTML = `<div class="comments-empty-state"><div class="ces-icon">💬</div><p class="ces-title">まだコメントがありません</p><p class="ces-sub">このトピックについて、あなたの考えを最初に投稿しませんか？</p>${ctaHtml}</div>`;
    return;
  }

  collectHandles(comments);

  const likedSet    = getLikedSet();
  const dislikedSet = getDislikedSet();
  const savedSet    = getSavedSet();

  listEl.innerHTML = comments.map(c => {
    const cid      = c.commentId || c.SK || '';
    const isOwn    = myHash && c.userIdHash === myHash;
    const handle   = c.handle || '';
    const liked    = !!likedSet[cid];
    const disliked = !!dislikedSet[cid];
    const saved    = !!savedSet[cid];
    const lc       = Number(c.likeCount)    || 0;
    const dc       = Number(c.dislikeCount) || 0;
    const handleLink = handle
      ? `<a class="cx-handle" href="${isOwn ? 'mypage.html' : 'profile.html?handle=' + esc(handle)}">@${esc(handle)}</a>`
      : '';
    const quotedBlock = c.quotedHandle ? `
      <div class="cx-quoted-block">
        <a class="cx-quoted-handle" href="profile.html?handle=${esc(c.quotedHandle)}">@${esc(c.quotedHandle)}</a>
        ${esc(c.quotedText || '')}
      </div>` : '';

    return `
      <div class="cx-comment" data-cid="${esc(cid)}" data-topic="${esc(topicId || '')}">
        <div class="cx-avatar-col">${avatarHtml(c, isOwn)}</div>
        <div class="cx-content">
          <div class="cx-header">
            <span class="cx-name">${esc(c.nickname || '匿名')}</span>
            ${handleLink}
            <span class="cx-dot">·</span>
            <span class="cx-time">${fmtCommentDate(c.createdAt)}</span>
            ${isOwn ? `<button class="cx-delete-btn" data-cid="${esc(cid)}" aria-label="削除">🗑</button>` : ''}
          </div>
          ${quotedBlock}
          <div class="cx-body">${mentionBody(c.body)}</div>
          <div class="cx-actions">
            <button class="cx-action-btn cx-like-btn${liked ? ' liked' : ''}"
              data-cid="${esc(cid)}" aria-label="いいね">
              <span class="cx-like-icon">${liked ? '♥' : '♡'}</span>
              <span class="cx-like-count">${lc > 0 ? lc : ''}</span>
            </button>
            <button class="cx-action-btn cx-action-dislike${disliked ? ' cx-bad-active' : ''}"
              data-cid="${esc(cid)}" aria-label="よくない">
              👎<span class="cx-like-count">${dc > 0 ? dc : ''}</span>
            </button>
            <button class="cx-action-btn cx-quote-btn"
              data-cid="${esc(cid)}" data-handle="${esc(handle)}"
              data-body="${esc((c.body || '').slice(0, 60))}" aria-label="引用">
              🔁
            </button>
            <button class="cx-action-btn cx-save-btn${saved ? ' saved' : ''}"
              data-cid="${esc(cid)}" aria-label="${saved ? '保存済み' : '保存'}">
              🔖${saved ? '<span style="font-size:.7rem;font-weight:700;margin-left:2px">済</span>' : ''}
            </button>
            <button class="cx-action-btn cx-reply-btn"
              data-handle="${esc(handle || c.nickname || '')}" aria-label="返信">
              ↩️
            </button>
          </div>
        </div>
      </div>`;
  }).join('');

  // イベントリスナーを一括設定
  listEl.querySelectorAll('.cx-like-btn').forEach(btn => {
    btn.addEventListener('click', () => toggleLike(btn, topicId));
  });
  listEl.querySelectorAll('.cx-action-dislike').forEach(btn => {
    btn.addEventListener('click', () => toggleDislike(btn, topicId));
  });
  listEl.querySelectorAll('.cx-quote-btn').forEach(btn => {
    btn.addEventListener('click', () => triggerQuote(btn.dataset));
  });
  listEl.querySelectorAll('.cx-save-btn').forEach(btn => {
    btn.addEventListener('click', () => toggleSave(btn, topicId, comments));
  });
  listEl.querySelectorAll('.cx-reply-btn').forEach(btn => {
    btn.addEventListener('click', () => triggerReply(btn.dataset.handle));
  });
  listEl.querySelectorAll('.cx-delete-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const cid = btn.dataset.cid;
      if (!cid || !confirm('このコメントを削除しますか？')) return;
      btn.disabled = true;
      await deleteComment(topicId, cid);
    });
  });
}

// ── いいねトグル（楽観的UI + DynamoDB更新） ──────────────────────
async function toggleLike(btn, topicId) {
  const cid       = btn.dataset.cid;
  const likedSet  = getLikedSet();
  const isLiked   = !!likedSet[cid];
  const iconEl    = btn.querySelector('.cx-like-icon');
  const countEl   = btn.querySelector('.cx-like-count');
  const curCount  = parseInt(countEl.textContent) || 0;

  // 楽観的UI更新
  if (!isLiked) {
    likedSet[cid] = true;
    btn.classList.add('liked');
    iconEl.textContent = '♥';
    countEl.textContent = curCount + 1;
  } else {
    likedSet[cid] = false;
    btn.classList.remove('liked');
    iconEl.textContent = '♡';
    countEl.textContent = curCount > 1 ? curCount - 1 : '';
  }
  localStorage.setItem(LIKES_KEY, JSON.stringify(likedSet));

  const myHash = await getMyCommentHash();
  if (!myHash) return;
  const baseUrl = commentsLikeUrl(topicId, cid, myHash);
  if (!baseUrl) return;
  const url = isLiked ? baseUrl + '&type=unlike' : baseUrl;
  try {
    const r = await fetch(url, { method: 'PUT' });
    if (r.ok) {
      const data = await r.json();
      if (typeof data.likeCount === 'number') {
        countEl.textContent = data.likeCount > 0 ? data.likeCount : '';
      }
    }
  } catch (e) {
    console.warn('like fetch error', e);
  }
}

// ── バッドトグル（楽観的UI + DynamoDB更新） ─────────────────────
async function toggleDislike(btn, topicId) {
  const cid         = btn.dataset.cid;
  const dislikedSet = getDislikedSet();
  const isDisliked  = !!dislikedSet[cid];
  const countEl     = btn.querySelector('.cx-like-count');
  const curCount    = parseInt(countEl ? countEl.textContent : 0) || 0;

  if (!isDisliked) {
    dislikedSet[cid] = true;
    btn.classList.add('cx-bad-active');
    if (countEl) countEl.textContent = curCount + 1;
  } else {
    dislikedSet[cid] = false;
    btn.classList.remove('cx-bad-active');
    if (countEl) countEl.textContent = curCount > 1 ? curCount - 1 : '';
  }
  localStorage.setItem(DISLIKES_KEY, JSON.stringify(dislikedSet));

  const myHash = await getMyCommentHash();
  if (!myHash) return;
  const base = typeof COMMENTS_URL !== 'undefined' ? COMMENTS_URL.replace(/\/$/, '') : null;
  if (!base) return;
  const type = isDisliked ? 'undislike' : 'dislike';
  const url = `${base}/comments/like?topicId=${encodeURIComponent(topicId)}&commentId=${encodeURIComponent(cid)}&userHash=${encodeURIComponent(myHash)}&type=${type}`;
  try {
    const r = await fetch(url, { method: 'PUT' });
    if (r.ok) {
      const data = await r.json();
      if (countEl && typeof data.dislikeCount === 'number') {
        countEl.textContent = data.dislikeCount > 0 ? data.dislikeCount : '';
      }
    }
  } catch (e) { console.warn('dislike fetch error', e); }
}

// ── 引用コメント状態 ──────────────────────────────────────────────
let _quoteData = null;

function triggerQuote(dataset) {
  const { cid, handle, body } = dataset;
  if (!cid) return;
  _quoteData = { cid, handle, body: body || '' };

  const bodyEl = document.getElementById('comment-body');
  const preview = document.getElementById('quote-preview');
  if (preview) {
    preview.innerHTML = `
      <div class="cx-quoted-block cx-quote-preview-block">
        <a class="cx-quoted-handle">@${esc(handle)}</a>
        <span>${esc((body || '').slice(0, 80))}</span>
        <button class="cx-quote-cancel-btn" aria-label="引用を取消">×</button>
      </div>`;
    preview.style.display = 'block';
    const cancelBtn = preview.querySelector('.cx-quote-cancel-btn');
    if (cancelBtn) cancelBtn.addEventListener('click', cancelQuote);
  }
  if (bodyEl) {
    bodyEl.focus();
    bodyEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
}

function cancelQuote() {
  _quoteData = null;
  const preview = document.getElementById('quote-preview');
  if (preview) { preview.innerHTML = ''; preview.style.display = 'none'; }
}

// ── 保存トグル（localStorageのみ） ───────────────────────────────
function toggleSave(btn, topicId, comments) {
  const cid      = btn.dataset.cid;
  const savedSet = getSavedSet();
  const isSaved  = !!savedSet[cid];

  if (!isSaved) {
    const c = comments.find(x => (x.commentId || x.SK) === cid) || {};
    savedSet[cid] = {
      topicId: topicId || '',
      body:      c.body      || '',
      nickname:  c.nickname  || '匿名',
      handle:    c.handle    || '',
      createdAt: c.createdAt || '',
      likeCount: Number(c.likeCount) || 0,
    };
    btn.classList.add('saved');
    btn.innerHTML = '🔖<span style="font-size:.7rem;font-weight:700;margin-left:2px">済</span>';
    btn.setAttribute('aria-label', '保存済み');
    if (typeof showToast === 'function') showToast('コメントを保存しました');
  } else {
    delete savedSet[cid];
    btn.classList.remove('saved');
    btn.innerHTML = '🔖';
    btn.setAttribute('aria-label', '保存');
    if (typeof showToast === 'function') showToast('保存を解除しました');
  }
  localStorage.setItem(SAVES_KEY, JSON.stringify(savedSet));
}

// ── 返信: テキストエリアに @handle を挿入 ────────────────────────
function triggerReply(handle) {
  if (!handle) return;
  const bodyEl = document.getElementById('comment-body');
  if (!bodyEl) return;
  const prefix = `@${handle} `;
  if (!bodyEl.value.includes(prefix)) {
    bodyEl.value = prefix + bodyEl.value;
  }
  bodyEl.focus();
  bodyEl.selectionStart = bodyEl.selectionEnd = bodyEl.value.length;
  // 文字数カウント更新
  const charsEl = document.getElementById('comment-chars');
  if (charsEl) charsEl.textContent = bodyEl.value.length;
}

// ── @メンションサジェスト ─────────────────────────────────────────
function setupMentionSuggest(textareaEl) {
  const suggestEl = document.getElementById('mention-suggest');
  if (!textareaEl || !suggestEl) return;

  textareaEl.addEventListener('input', () => {
    const val   = textareaEl.value;
    const caret = textareaEl.selectionStart;
    const before = val.slice(0, caret);
    const match  = before.match(/@([A-Za-z0-9_]*)$/);

    if (!match || !_topicHandles.length) {
      suggestEl.style.display = 'none';
      return;
    }

    const query    = match[1].toLowerCase();
    const filtered = _topicHandles.filter(h => h.toLowerCase().startsWith(query));

    if (!filtered.length) {
      suggestEl.style.display = 'none';
      return;
    }

    suggestEl.innerHTML = filtered.slice(0, 6).map(h =>
      `<div class="mention-item" data-handle="${esc(h)}">@${esc(h)}</div>`
    ).join('');
    suggestEl.style.display = 'block';

    suggestEl.querySelectorAll('.mention-item').forEach(item => {
      item.addEventListener('mousedown', e => {
        e.preventDefault(); // blur を防ぐ
        const h      = item.dataset.handle;
        const newVal = val.slice(0, caret).replace(/@[A-Za-z0-9_]*$/, `@${h} `)
                     + val.slice(caret);
        textareaEl.value = newVal;
        textareaEl.focus();
        suggestEl.style.display = 'none';
        const charsEl = document.getElementById('comment-chars');
        if (charsEl) charsEl.textContent = newVal.length;
      });
    });
  });

  document.addEventListener('click', e => {
    if (!suggestEl.contains(e.target) && e.target !== textareaEl) {
      suggestEl.style.display = 'none';
    }
  });
}

// ── コメント削除 ─────────────────────────────────────────────────
async function deleteComment(topicId, commentId) {
  const base = commentsApiUrl(topicId);
  if (!base || !currentUser) return;
  try {
    const r = await fetch(`${base}/${encodeURIComponent(commentId)}`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ idToken: currentUser.token }),
    });
    if (r.status === 401) {
      // トークン期限切れ: 再認証後に自動リトライするためペンディング情報を保存
      window._pendingCommentDelete = { topicId, commentId };
      if (typeof showToast === 'function') showToast('セッションが切れました。再ログイン後に削除を自動実行します', 5000);
      if (typeof openAuthModal === 'function') openAuthModal();
      return;
    }
    if (r.status === 403) {
      if (typeof showToast === 'function') showToast('このコメントは削除できません');
      return;
    }
    if (r.ok) {
      if (typeof showToast === 'function') showToast('コメントを削除しました');
      await loadComments(topicId);
    }
  } catch {
    if (typeof showToast === 'function') showToast('削除に失敗しました。ネットワークを確認してください');
  }
}

// ── コメント読み込み ──────────────────────────────────────────────
async function loadComments(topicId) {
  const url = commentsApiUrl(topicId);
  if (!url) return;
  try {
    const r    = await fetch(url);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();
    const myHash = await getMyCommentHash();
    renderComments(data.comments || [], topicId, myHash);
  } catch {
    const listEl = document.getElementById('comments-list');
    if (listEl) listEl.innerHTML = '<div class="comments-empty">コメントの読み込みに失敗しました。</div>';
  }
}

// ── 投稿フォームのアバター更新 ────────────────────────────────────
function updatePostAvatar() {
  const col = document.getElementById('post-avatar-col');
  if (!col || !currentUser) return;
  // flotopic_avatar（localStorage）> Googleプロフィール画像 の優先順位
  let pic = '';
  try { pic = localStorage.getItem('flotopic_avatar') || ''; } catch {}
  if (!pic) pic = currentUser.picture || '';
  const init = initials(currentUser.name || '?');
  if (pic) {
    col.innerHTML = `<img class="cx-post-avatar" src="${esc(pic)}" alt=""
      onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">` +
      `<div class="cx-post-avatar-init" style="display:none">${esc(init)}</div>`;
  } else {
    col.innerHTML = `<div class="cx-post-avatar-init">${esc(init)}</div>`;
  }
}

// ── 投稿フォームセットアップ ─────────────────────────────────────
function setupCommentForm(topicId) {
  const url     = commentsApiUrl(topicId);
  const section = document.getElementById('comments-section');
  if (!url) { if (section) section.style.display = 'none'; return; }

  const formArea    = document.getElementById('comment-form-area');
  const loginPrompt = document.getElementById('comment-login-prompt');
  const bodyEl      = document.getElementById('comment-body');
  const charsEl     = document.getElementById('comment-chars');
  const submitEl    = document.getElementById('comment-submit');
  const errorEl     = document.getElementById('comment-error');

  if (!currentUser) {
    if (formArea)    formArea.style.display    = 'none';
    if (loginPrompt) loginPrompt.style.display = 'block';
    return;
  }
  if (loginPrompt) loginPrompt.style.display = 'none';
  if (formArea)    formArea.style.display    = 'flex';

  // アバター表示
  updatePostAvatar();

  // ハンドル表示（ハンドルがあれば @handle のみ、なければ表示名）
  const handleDisplayEl = document.getElementById('post-handle-display');
  if (handleDisplayEl) {
    const profile = getProfile();
    const handle  = profile.handle || '';
    handleDisplayEl.textContent = handle ? `@${handle}` : getDisplayName(currentUser);
  }

  // @メンションサジェスト
  if (bodyEl) setupMentionSuggest(bodyEl);

  if (!bodyEl || !submitEl) return;

  const newSubmit = submitEl.cloneNode(true);
  submitEl.parentNode.replaceChild(newSubmit, submitEl);
  const newBody = bodyEl.cloneNode(true);
  bodyEl.parentNode.replaceChild(newBody, bodyEl);

  // 文字数カウント
  newBody.addEventListener('input', () => {
    const len = newBody.value.length;
    if (charsEl) charsEl.textContent = len;
    if (charsEl) charsEl.parentElement.classList.toggle('comment-char-warn', len > 180);
  });

  // @メンションサジェストを再接続（cloneNode後）
  setupMentionSuggest(newBody);

  // 投稿ボタン
  newSubmit.addEventListener('click', async () => {
    const body     = newBody.value.trim();
    const profile  = getProfile();
    const nickname = getDisplayName(currentUser);
    const handle   = profile.handle || '';

    if (errorEl) errorEl.textContent = '';
    if (!body) { if (errorEl) errorEl.textContent = 'コメント本文を入力してください。'; return; }
    if (body.length > 200) { if (errorEl) errorEl.textContent = '200文字以内で入力してください。'; return; }

    newSubmit.disabled = true;
    newSubmit.textContent = '送信中...';
    try {
      const payload = {
        body,
        nickname,
        topicId,
        idToken: currentUser.token,
      };
      if (handle)                             payload.handle    = handle;
      if (currentUser && currentUser.picture) payload.avatarUrl = currentUser.picture;
      if (_quoteData) {
        payload.quotedCommentId = _quoteData.cid;
        payload.quotedHandle    = _quoteData.handle;
        payload.quotedText      = _quoteData.body;
      }

      const r = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await r.json();
      if (!r.ok) {
        if (r.status === 401) {
          if (errorEl) errorEl.textContent = 'ログインセッションが切れました。再ログインしてください。';
          if (typeof openAuthModal === 'function') openAuthModal();
          return;
        }
        if (errorEl) errorEl.textContent = data.error || '投稿に失敗しました。';
      } else {
        newBody.value = '';
        if (charsEl) charsEl.textContent = '0';
        cancelQuote();
        await loadComments(topicId);
        if (errorEl) {
          errorEl.className = 'comment-success';
          errorEl.textContent = '投稿しました！';
          setTimeout(() => { errorEl.textContent = ''; errorEl.className = 'comment-error'; }, 3000);
        }
      }
    } catch {
      if (errorEl) errorEl.textContent = 'ネットワークエラーが発生しました。';
    } finally {
      newSubmit.disabled = false;
      newSubmit.textContent = '投稿する';
    }
  });
}
