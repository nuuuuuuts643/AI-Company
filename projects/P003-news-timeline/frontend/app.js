const REFRESH_MS = 5 * 60 * 1000;
const STATUS_LABEL = { rising:'🔺 上昇中', peak:'🔷 ピーク', declining:'🔻 減衰中' };
const GENRES = ['すべて','総合','政治','ビジネス','テクノロジー','スポーツ','エンタメ','科学','健康','国際'];

let allTopics = [], currentStatus = 'all', currentGenre = 'すべて', currentLang = 'all';

function esc(s) {
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function fmtDate(s) {
  if (!s) return '';
  try { return new Date(s).toLocaleString('ja-JP',{month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit'}); }
  catch { return s; }
}
function apiUrl(path) { return API_BASE + path + '.json'; }

// ===== 一覧ページ =====
async function loadTopics() {
  const r = await fetch(apiUrl('topics'));
  return (await r.json()).topics || [];
}

function renderTopics(topics) {
  const grid = document.getElementById('topics-grid');
  if (!grid) return;
  let list = topics;
  if (currentLang   !== 'all')    list = list.filter(t => (t.lang||'ja') === currentLang);
  if (currentStatus !== 'all')    list = list.filter(t => t.status === currentStatus);
  if (currentGenre  !== 'すべて') list = list.filter(t => t.genre  === currentGenre);
  if (!list.length) { grid.innerHTML = '<div class="loading">該当するトピックがありません</div>'; return; }

  grid.innerHTML = list.map(t => `
    <a class="topic-card ${esc(t.status)}" href="topic.html?id=${esc(t.topicId)}">
      <div class="topic-status ${esc(t.status)}">${STATUS_LABEL[t.status]||t.status}</div>
      <h3>${esc(t.title)}</h3>
      <div class="topic-meta">
        <span class="article-count">${t.articleCount}</span>
        <span class="genre-tag">${esc(t.genre||'総合')}</span>
        <span>${fmtDate(t.lastUpdated)}</span>
      </div>
    </a>`).join('');
}

function buildFilters() {
  const lbar = document.getElementById('lang-filter');
  if (lbar) {
    const btns = [{k:'all',l:'🌐 すべて'},{k:'ja',l:'🇯🇵 日本語'},{k:'en',l:'🇬🇧 English'}];
    lbar.innerHTML = btns.map(b=>`<button class="filter-btn ${currentLang===b.k?'active':''}" data-lang="${b.k}">${b.l}</button>`).join('');
    lbar.querySelectorAll('.filter-btn').forEach(btn => btn.addEventListener('click', () => {
      lbar.querySelectorAll('.filter-btn').forEach(b=>b.classList.remove('active'));
      btn.classList.add('active'); currentLang = btn.dataset.lang; renderTopics(allTopics);
    }));
  }
  const sbar = document.getElementById('status-filter');
  if (sbar) {
    const btns = [{k:'all',l:'すべて'},{k:'rising',l:'🔺 上昇中'},{k:'peak',l:'🔷 ピーク'},{k:'declining',l:'🔻 減衰中'}];
    sbar.innerHTML = btns.map(b=>`<button class="filter-btn ${currentStatus===b.k?'active':''}" data-status="${b.k}">${b.l}</button>`).join('');
    sbar.querySelectorAll('.filter-btn').forEach(btn => btn.addEventListener('click', () => {
      sbar.querySelectorAll('.filter-btn').forEach(b=>b.classList.remove('active'));
      btn.classList.add('active'); currentStatus = btn.dataset.status; renderTopics(allTopics);
    }));
  }
  const gbar = document.getElementById('genre-filter');
  if (gbar) {
    gbar.innerHTML = GENRES.map(g=>`<button class="filter-btn genre-btn ${currentGenre===g?'active':''}" data-genre="${g}">${g}</button>`).join('');
    gbar.querySelectorAll('.genre-btn').forEach(btn => btn.addEventListener('click', () => {
      gbar.querySelectorAll('.genre-btn').forEach(b=>b.classList.remove('active'));
      btn.classList.add('active'); currentGenre = btn.dataset.genre; renderTopics(allTopics);
    }));
  }
}

async function refreshTopics() {
  try {
    allTopics = await loadTopics();
    renderTopics(allTopics);
    const el = document.getElementById('last-updated');
    if (el) el.textContent = `最終更新: ${new Date().toLocaleTimeString('ja-JP')}（5分ごとに自動更新）`;
  } catch(e) { console.error(e); }
}

// ===== 詳細ページ =====
let chartInstance = null, hatenaChartInstance = null;

function renderDetail(data) {
  const {meta, timeline} = data;
  if (!meta) return;

  document.title = `${meta.title} | ニュースタイムライン`;
  const titleEl = document.getElementById('topic-title');
  if (titleEl) titleEl.textContent = meta.title;

  const badge = document.getElementById('status-badge');
  if (badge) { badge.textContent = STATUS_LABEL[meta.status]||meta.status; badge.className=`status-badge ${meta.status}`; badge.style.display='inline-block'; }
  const genreEl = document.getElementById('genre-badge');
  if (genreEl && meta.genre) { genreEl.textContent = meta.genre; genreEl.style.display='inline-block'; }

  // バズスコアグラフ
  const canvas = document.getElementById('score-chart');
  const noData = document.getElementById('no-data');
  if (canvas) {
    if (timeline.length < 2) {
      canvas.style.display='none'; if(noData) noData.style.display='block';
    } else {
      canvas.style.display='block'; if(noData) noData.style.display='none';
      const labels = timeline.map(s=>fmtDate(s.timestamp));
      const scores = timeline.map(s=>Number(s.score||s.articleCount||0));
      if (chartInstance) chartInstance.destroy();
      chartInstance = new Chart(canvas.getContext('2d'), {
        type: 'line',
        data: { labels, datasets: [{
          label:'バズスコア', data:scores,
          borderColor:'#0f172a', backgroundColor:'rgba(15,23,42,.08)',
          borderWidth:2, pointRadius:4, tension:0.35, fill:true,
        }]},
        options: { responsive:true, plugins:{legend:{display:false}},
          scales:{ y:{beginAtZero:true, ticks:{precision:0}} } },
      });
    }
  }

  // はてブ増加量グラフ
  const hatenaData = timeline.map(s => Number(s.hatenaCount || 0));
  const hasHatena  = hatenaData.some(v => v > 0);
  const hatenaCard = document.getElementById('hatena-card');
  if (hatenaCard) hatenaCard.style.display = hasHatena ? 'block' : 'none';
  if (hasHatena && timeline.length >= 2) {
    const labels  = timeline.map(s => fmtDate(s.timestamp));
    const deltas  = hatenaData.map((v, i) => i === 0 ? 0 : Math.max(0, v - hatenaData[i - 1]));
    const hCanvas = document.getElementById('hatena-chart');
    if (hCanvas) {
      if (hatenaChartInstance) hatenaChartInstance.destroy();
      hatenaChartInstance = new Chart(hCanvas.getContext('2d'), {
        type: 'bar',
        data: { labels, datasets: [{
          label: 'はてブ増加数', data: deltas,
          backgroundColor: deltas.map(v => v >= 10 ? '#ef4444' : v >= 3 ? '#f59e0b' : '#93c5fd'),
          borderRadius: 4,
        }]},
        options: {
          responsive: true,
          plugins: { legend: { display: false },
            tooltip: { callbacks: { label: ctx => `+${ctx.parsed.y} ブックマーク` } }
          },
          scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
        },
      });
    }
  }

  // ストーリー時系列
  const storyEl = document.getElementById('story-timeline');
  if (storyEl && timeline.length) {
    // 古い順に処理して、各スナップで初登場のURLだけを抽出
    const seenUrls = new Set();
    const newPerSnap = timeline.map(snap => {
      const all = snap.articles || [];
      const fresh = all.filter(a => !seenUrls.has(a.url));
      all.forEach(a => seenUrls.add(a.url));
      return fresh;
    });

    const reversed = [...timeline].reverse();
    storyEl.innerHTML = reversed.map((snap, idx) => {
      const snapIdx = timeline.length - 1 - idx;
      const isLatest = idx === 0;
      const articles = newPerSnap[snapIdx];
      const headlineHtml = articles.map(a => `
        <div class="headline-item">
          <a href="${esc(a.url)}" target="_blank" rel="noopener noreferrer">${esc(a.title)}</a>
          <div class="headline-source">${esc(a.source)}</div>
        </div>`).join('');

      return `
        <div class="story-item ${isLatest?'latest':''}">
          <div class="story-time">
            ${fmtDate(snap.timestamp)}
            <span class="story-count">${snap.articleCount}件</span>
            ${isLatest ? '<span style="color:#ef4444;font-size:.72rem;font-weight:700;">最新</span>' : ''}
          </div>
          ${articles.length ? `
            <button class="story-toggle" onclick="this.nextElementSibling.classList.toggle('open');this.textContent=this.nextElementSibling.classList.contains('open')?'▲ 閉じる':'▼ 新着記事（${articles.length}件）'">
              ${isLatest ? '▼ 新着記事（' + articles.length + '件）' : '▼ 新着記事（' + articles.length + '件）'}
            </button>
            <div class="story-headlines ${isLatest?'open':''}">${headlineHtml}</div>
          ` : '<span style="color:#9ca3af;font-size:.8rem;">この時点で新しい記事なし</span>'}
        </div>`;
    }).join('');
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const topicId = new URLSearchParams(location.search).get('id');
  if (topicId) {
    const refresh = () => fetch(apiUrl(`topic/${topicId}`)).then(r=>r.json()).then(renderDetail).catch(console.error);
    refresh();
    setInterval(refresh, REFRESH_MS);
  } else {
    buildFilters();
    refreshTopics();
    setInterval(refreshTopics, REFRESH_MS);
  }
});
