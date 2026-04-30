// ===== 閲覧履歴クラウド同期 =====
// 依存: config.js (FAVORITES_URL), auth.js (currentUser)

const HIST_LS_KEY = 'flotopic_history';
const HIST_MAX    = 200;

function histApiUrl() {
  if (typeof FAVORITES_URL === 'undefined' || !FAVORITES_URL) return null;
  return FAVORITES_URL.replace(/\/$/, '');
}

function readLocalHistory() {
  try { return JSON.parse(localStorage.getItem(HIST_LS_KEY) || '[]'); } catch { return []; }
}

function saveLocalHistory(items) {
  try { localStorage.setItem(HIST_LS_KEY, JSON.stringify(items.slice(0, HIST_MAX))); } catch {}
}

// ログイン時: クラウド履歴を取得してlocalStorageとマージ
async function loadCloudHistory() {
  if (!currentUser) return;
  const base = histApiUrl();
  if (!base) return;
  try {
    const r = await fetch(`${base}/history/${currentUser.userId}`);
    if (!r.ok) return;
    const data = await r.json();
    const cloudItems = (data.history || []).map(h => ({
      topicId:  h.topicId,
      title:    h.title || '',
      viewedAt: typeof h.viewedAt === 'string'
        ? new Date(h.viewedAt).getTime()
        : (h.viewedAt || Date.now()),
    }));
    const local = readLocalHistory();
    // マージ: topicIdで重複排除、viewedAt新しい方を優先 (純粋ロジックは ViewedHistory.mergeHistory)
    const merged = (typeof ViewedHistory !== 'undefined' && ViewedHistory.mergeHistory)
      ? ViewedHistory.mergeHistory(cloudItems, local)
      : [...cloudItems, ...local].reduce((acc, item) => {
          const existing = acc.find(a => a.topicId === item.topicId);
          if (!existing) { acc.push(item); }
          else if ((item.viewedAt || 0) > (existing.viewedAt || 0)) {
            Object.assign(existing, item);
          }
          return acc;
        }, []).sort((a, b) => (b.viewedAt || 0) - (a.viewedAt || 0));
    saveLocalHistory(merged);
    // T2026-0501-B: クラウド側 viewedAt を viewedTopics Map に再反映 + 必要なら再描画。
    // これをやらないと、別デバイスで見たトピックが本デバイスでグレーアウトされない (PO 指摘)。
    if (typeof loadViewedTopics === 'function') loadViewedTopics();
    if (typeof allTopics !== 'undefined' && Array.isArray(allTopics) && allTopics.length
        && typeof renderTopics === 'function') {
      try { renderTopics(allTopics); } catch {}
    }
  } catch {}
}

// トピック閲覧時: クラウドに非同期でPOST（失敗しても無視）
function syncHistoryItemToCloud(topic) {
  if (!currentUser) return;
  const base = histApiUrl();
  if (!base || !topic || !topic.topicId) return;
  const viewedAt = new Date().toISOString();
  fetch(`${base}/history`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      userId:   currentUser.userId,
      idToken:  currentUser.token,
      topicId:  topic.topicId,
      title:    topic.generatedTitle || topic.title || '',
      viewedAt: viewedAt,
    }),
  }).catch(() => {});
}

// mypage: 全履歴クラウドから削除
async function clearCloudHistory() {
  if (!currentUser) return;
  const base = histApiUrl();
  if (!base) return;
  try {
    await fetch(`${base}/history`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ userId: currentUser.userId, idToken: currentUser.token }),
    });
  } catch {}
}
