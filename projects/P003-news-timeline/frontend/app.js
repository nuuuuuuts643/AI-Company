// ===== 定数 =====
const REFRESH_MS = 5 * 60 * 1000; // 5分ごとに自動更新

const STATUS_LABEL = {
  rising:    '🔺 上昇中',
  peak:      '🔷 ピーク',
  declining: '🔻 減衰中',
};

// ===== ユーティリティ =====
function esc(str) {
  return String(str || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function fmtDate(str) {
  if (!str) return '';
  try {
    return new Date(str).toLocaleString('ja-JP', {
      month: 'numeric', day: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  } catch { return str; }
}

function apiUrl(path) {
  // API_BASE は config.js で定義（末尾スラッシュあり）
  return API_BASE + path;
}

// ===== 一覧ページ =====
let allTopics    = [];
let currentFilter = 'all';

async function loadTopics() {
  const res  = await fetch(apiUrl('topics'));
  const data = await res.json();
  return data.topics || [];
}

function renderTopics(topics) {
  const grid = document.getElementById('topics-grid');
  if (!grid) return;

  const list = currentFilter === 'all'
    ? topics
    : topics.filter(t => t.status === currentFilter);

  if (list.length === 0) {
    grid.innerHTML = '<div class="loading">該当するトピックがありません</div>';
    return;
  }

  grid.innerHTML = list.map(t => `
    <a class="topic-card ${esc(t.status)}" href="topic.html?id=${esc(t.topicId)}">
      <div class="topic-status ${esc(t.status)}">${STATUS_LABEL[t.status] || t.status}</div>
      <h3>${esc(t.title)}</h3>
      <div class="topic-meta">
        <span class="article-count">${t.articleCount}</span>
        <span>${fmtDate(t.lastUpdated)}</span>
      </div>
    </a>
  `).join('');
}

function setLastUpdated() {
  const el = document.getElementById('last-updated');
  if (el) el.textContent = `最終更新: ${new Date().toLocaleTimeString('ja-JP')}（5分ごとに自動更新）`;
}

async function refreshTopics() {
  try {
    allTopics = await loadTopics();
    renderTopics(allTopics);
    setLastUpdated();
  } catch (e) {
    console.error('トピック取得エラー:', e);
  }
}

// ===== 詳細ページ =====
let chartInstance = null;

async function loadDetail(topicId) {
  const res  = await fetch(apiUrl(`topic/${topicId}`));
  return await res.json();
}

function renderDetail(data) {
  const { meta, timeline } = data;
  if (!meta) return;

  // タイトル
  document.title = `${meta.title} | ニュースタイムライン`;
  const titleEl = document.getElementById('topic-title');
  if (titleEl) titleEl.textContent = meta.title;

  // ステータスバッジ
  const badge = document.getElementById('status-badge');
  if (badge) {
    badge.textContent  = STATUS_LABEL[meta.status] || meta.status;
    badge.className    = `status-badge ${meta.status}`;
    badge.style.display = 'inline-block';
  }

  // グラフ
  const canvas = document.getElementById('timeline-chart');
  const noData = document.getElementById('no-data');
  if (canvas) {
    if (timeline.length < 2) {
      canvas.style.display = 'none';
      if (noData) noData.style.display = 'block';
    } else {
      canvas.style.display = 'block';
      if (noData) noData.style.display = 'none';

      const labels = timeline.map(s => fmtDate(s.timestamp));
      const counts = timeline.map(s => Number(s.articleCount));

      if (chartInstance) chartInstance.destroy();
      chartInstance = new Chart(canvas.getContext('2d'), {
        type: 'line',
        data: {
          labels,
          datasets: [{
            label:           '記事数',
            data:            counts,
            borderColor:     '#0f172a',
            backgroundColor: 'rgba(15,23,42,.08)',
            borderWidth:     2,
            pointRadius:     4,
            tension:         0.35,
            fill:            true,
          }],
        },
        options: {
          responsive: true,
          plugins: { legend: { display: false } },
          scales: {
            y: { beginAtZero: true, ticks: { stepSize: 1, precision: 0 } },
          },
        },
      });
    }
  }

  // 最新記事リスト
  const latest   = timeline[timeline.length - 1];
  const articles = latest ? (latest.articles || []) : [];
  const list     = document.getElementById('articles-list');
  if (list) {
    if (articles.length === 0) {
      list.innerHTML = '<p style="color:#9ca3af;font-size:.85rem;">記事情報がありません</p>';
    } else {
      list.innerHTML = articles.map(a => `
        <div class="article-item">
          <a href="${esc(a.url)}" target="_blank" rel="noopener noreferrer">${esc(a.title)}</a>
          <div class="article-meta">${esc(a.source)} · ${fmtDate(a.pubDate)}</div>
        </div>
      `).join('');
    }
  }
}

// ===== 初期化 =====
document.addEventListener('DOMContentLoaded', () => {
  const params  = new URLSearchParams(location.search);
  const topicId = params.get('id');

  if (topicId) {
    // 詳細ページ
    const refresh = () => loadDetail(topicId).then(renderDetail).catch(console.error);
    refresh();
    setInterval(refresh, REFRESH_MS);
  } else {
    // 一覧ページ
    refreshTopics();
    setInterval(refreshTopics, REFRESH_MS);

    document.querySelectorAll('.filter-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentFilter = btn.dataset.status;
        renderTopics(allTopics);
      });
    });
  }
});
