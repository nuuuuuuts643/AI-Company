const REFRESH_MS = 5 * 60 * 1000;
const STATUS_LABEL = { rising:'🔺 上昇中', peak:'🔷 ピーク', declining:'🔻 減衰中' };
const GENRES = ['すべて','総合','政治','ビジネス','株・金融','テクノロジー','スポーツ','エンタメ','科学','健康','国際'];
const GENRE_EMOJI = {'政治':'🏛️','ビジネス':'💼','株・金融':'📈','テクノロジー':'💻','スポーツ':'⚽','エンタメ':'🎬','科学':'🔬','健康':'💊','国際':'🌏','総合':'📰'};

let allTopics = [], currentStatus = 'all', currentGenre = 'すべて', currentSearch = '';

function esc(s) {
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function genreEmoji(genre) { return GENRE_EMOJI[genre] || '📰'; }
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
  if (currentSearch) {
    const q = currentSearch.toLowerCase();
    list = list.filter(t => (t.generatedTitle||t.title||'').toLowerCase().includes(q));
  }
  if (currentStatus !== 'all')    list = list.filter(t => t.status === currentStatus);
  if (currentGenre  !== 'すべて') list = list.filter(t => (t.genres||[t.genre]).includes(currentGenre));
  if (!list.length) { grid.innerHTML = '<div class="loading">該当するトピックがありません</div>'; return; }

  grid.innerHTML = list.map(t => {
    const primaryGenre = (t.genres||[t.genre||'総合'])[0];
    const thumbHtml = t.imageUrl
      ? `<div class="card-thumb"><img class="card-thumb-img" src="${esc(t.imageUrl)}" alt="" loading="lazy" onerror="this.parentNode.innerHTML='<div class=\\'card-thumb-placeholder ${esc(t.status)}\\'>${genreEmoji(primaryGenre)}</div>'"></div>`
      : `<div class="card-thumb"><div class="card-thumb-placeholder ${esc(t.status)}">${genreEmoji(primaryGenre)}</div></div>`;
    return `
    <a class="topic-card ${esc(t.status)}" href="topic.html?id=${esc(t.topicId)}">
      ${thumbHtml}
      <div class="card-body">
        <div class="topic-status ${esc(t.status)}">${STATUS_LABEL[t.status]||t.status}</div>
        <h3>${esc(t.generatedTitle||t.title)}</h3>
        <div class="topic-meta">
          <span class="article-count">${t.articleCount}</span>
          ${(t.genres||[t.genre||'総合']).map(g=>`<span class="genre-tag">${esc(g)}</span>`).join('')}
          <span>${fmtDate(t.lastUpdated)}</span>
        </div>
      </div>
    </a>`;
  }).join('');
}

function buildFilters() {
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

const WMO = {
  0:'☀️ 快晴',1:'🌤 晴れ',2:'⛅ 曇り時々晴れ',3:'☁️ 曇り',
  45:'🌫 霧',48:'🌫 霧',
  51:'🌦 小雨',53:'🌧 雨',55:'🌧 強雨',
  61:'🌦 小雨',63:'🌧 雨',65:'🌧 強雨',
  71:'🌨 小雪',73:'❄️ 雪',75:'❄️ 大雪',
  80:'🌦 にわか雨',81:'🌧 にわか雨',82:'⛈ 激しいにわか雨',
  95:'⛈ 雷雨',96:'⛈ 雷雨',99:'⛈ 激しい雷雨',
};

async function loadWeather() {
  const el = document.getElementById('weather-widget');
  if (!el) return;
  const fetchWeather = async (lat, lon, cityName) => {
    const url = `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current=temperature_2m,weather_code&timezone=Asia%2FTokyo&forecast_days=1`;
    const r = await fetch(url);
    const d = await r.json();
    const temp = Math.round(d.current.temperature_2m);
    const desc = WMO[d.current.weather_code] || '―';
    el.innerHTML = `<span class="weather-city">${cityName}</span><span class="weather-desc">${desc}</span><span class="weather-temp">${temp}°C</span>`;
  };
  const getCity = async (lat, lon) => {
    try {
      const r = await fetch(`https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lon}&format=json&zoom=10`, {headers:{'Accept-Language':'ja'}});
      const d = await r.json();
      return d.address?.city || d.address?.town || d.address?.county || '現在地';
    } catch { return '現在地'; }
  };
  try {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        async p => {
          const city = await getCity(p.coords.latitude, p.coords.longitude);
          fetchWeather(p.coords.latitude, p.coords.longitude, city);
        },
        () => fetchWeather(35.68, 139.69, '東京'),
      );
    } else {
      fetchWeather(35.68, 139.69, '東京');
    }
  } catch(e) { el.textContent = ''; }
}

function setupSearch() {
  const input = document.getElementById('search-input');
  if (!input) return;
  input.addEventListener('input', () => {
    currentSearch = input.value.trim();
    renderTopics(allTopics);
  });
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
let chartInstance = null, viewsChartInstance = null;

function trackView(topicId) {
  if (typeof TRACKER_URL === 'undefined') return;
  fetch(TRACKER_URL, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({topicId}),
  }).catch(() => {});
}

function renderDetail(data) {
  const {meta, timeline, views} = data;
  if (!meta) return;

  document.title = `${meta.generatedTitle||meta.title} | ニュースタイムライン`;
  const titleEl = document.getElementById('topic-title');
  if (titleEl) titleEl.textContent = meta.generatedTitle || meta.title;

  const badge = document.getElementById('status-badge');
  if (badge) { badge.textContent = STATUS_LABEL[meta.status]||meta.status; badge.className=`status-badge ${meta.status}`; badge.style.display='inline-block'; }
  const genreEl = document.getElementById('genre-badge');
  if (genreEl) {
    const gs = meta.genres || (meta.genre ? [meta.genre] : []);
    if (gs.length) { genreEl.textContent = gs.join(' / '); genreEl.style.display='inline-block'; }
  }

  // AI要約を表示
  const summaryEl = document.querySelector('.summary-placeholder');
  if (summaryEl) {
    if (meta.generatedSummary) {
      summaryEl.textContent = meta.generatedSummary;
      summaryEl.className = 'summary-text';
    } else {
      summaryEl.textContent = 'AI要約は次回の自動更新時に生成されます（30分ごと）。';
    }
  }

  // グラフ（時間軸切替付き）
  const canvas = document.getElementById('score-chart');
  const vCanvas = document.getElementById('views-chart');
  const noData = document.getElementById('no-data');
  if (canvas) {
    if (timeline.length < 2) {
      canvas.style.display='none'; if(vCanvas) vCanvas.style.display='none'; if(noData) noData.style.display='block';
    } else {
      canvas.style.display='block'; if(vCanvas) vCanvas.style.display='block'; if(noData) noData.style.display='none';

      const buildCharts = (rangeHours) => {
        const now = Date.now();
        const cutoff = rangeHours ? now - rangeHours * 3600 * 1000 : 0;
        const filtered = rangeHours
          ? timeline.filter(s => new Date(s.timestamp).getTime() >= cutoff)
          : timeline;
        const src = filtered.length >= 2 ? filtered : timeline;

        // 週足・全期間は日次集計
        const aggregate = rangeHours === null || rangeHours >= 72;
        let labels, scores, mediaCnts;
        if (aggregate) {
          const byDay = {};
          src.forEach(s => {
            const day = new Date(s.timestamp).toLocaleDateString('ja-JP',{month:'numeric',day:'numeric'});
            if (!byDay[day]) byDay[day] = {scores:[], media:[]};
            byDay[day].scores.push(Number(s.score||0));
            byDay[day].media.push(Number(s.articleCount||0));
          });
          labels    = Object.keys(byDay);
          scores    = labels.map(d => Math.max(...byDay[d].scores));
          mediaCnts = labels.map(d => Math.max(...byDay[d].media));
        } else {
          labels    = src.map(s => fmtDate(s.timestamp));
          scores    = src.map(s => Number(s.score||0));
          mediaCnts = src.map(s => Number(s.articleCount||0));
        }

        // 閲覧数：日次データを日付順にソート
        const viewsSorted = [...(views||[])].sort((a,b) => a.date.localeCompare(b.date));
        const vLabels   = viewsSorted.map(v => `${parseInt(v.date.slice(4,6))}/${parseInt(v.date.slice(6,8))}`);
        const vAbsolute = viewsSorted.map(v => v.count);
        const vDelta    = viewsSorted.map((v, i) => i === 0 ? 0 : v.count - viewsSorted[i-1].count);

        const zoomOpts = meta.status === 'archived' ? {} : {
          zoom: { wheel:{enabled:true}, pinch:{enabled:true}, mode:'x' },
          pan:  { enabled:true, mode:'x' },
        };

        // Y軸：最大値から余白を取り、目盛りを粗く
        const makeScaleY0 = (data) => {
          const vals = data.filter(v => v !== null);
          const max = vals.length ? Math.max(...vals) : 10;
          const pad = Math.max(max * 0.2, 1);
          return { min:0, max: max+pad, ticks:{ precision:0, maxTicksLimit:5 }, grid:{ color:'rgba(0,0,0,.06)' } };
        };
        const makeScaleDelta = (data) => {
          const vals = data.filter(v => v !== null);
          const max = vals.length ? Math.max(...vals) : 1;
          const min = vals.length ? Math.min(...vals) : 0;
          const pad = Math.max(Math.abs(max - min) * 0.2, 1);
          const lo = min < 0 ? min - pad : 0;
          return {
            min: lo, max: max + pad,
            ticks: { precision:0, maxTicksLimit:5 },
            grid: { color: ctx => ctx.tick.value === 0 ? 'rgba(0,0,0,.3)' : 'rgba(0,0,0,.06)', lineWidth: ctx => ctx.tick.value === 0 ? 2 : 1 },
          };
        };

        // 左グラフ：閲覧数増減（昨日比、バー）
        if (chartInstance) chartInstance.destroy();
        chartInstance = new Chart(canvas.getContext('2d'), {
          type: 'bar',
          data: { labels: vLabels, datasets: [{
            label:'閲覧数増減（昨日比）',
            data: vDelta,
            backgroundColor: vDelta.map(v => v >= 0 ? 'rgba(16,185,129,.85)' : 'rgba(239,68,68,.75)'),
            borderRadius: 4, borderSkipped: false,
          }]},
          options: {
            responsive: true, maintainAspectRatio: false,
            interaction: { mode:'index', intersect:false },
            plugins: {
              legend: { display:true, position:'bottom', labels:{boxWidth:12, font:{size:11}} },
              zoom: zoomOpts,
            },
            scales: { y: makeScaleDelta(vDelta) },
          },
        });

        // 右グラフ：閲覧数累計（面グラフ）
        if (vCanvas) {
          if (viewsChartInstance) viewsChartInstance.destroy();
          viewsChartInstance = new Chart(vCanvas.getContext('2d'), {
            type: 'line',
            data: { labels: vLabels, datasets: [{
              label:'閲覧数',
              data: vAbsolute,
              borderColor:'#10b981',
              backgroundColor: (ctx) => {
                const {ctx:c, chartArea} = ctx.chart;
                if (!chartArea) return 'rgba(16,185,129,.2)';
                const g = c.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
                g.addColorStop(0, 'rgba(16,185,129,.4)');
                g.addColorStop(1, 'rgba(16,185,129,.02)');
                return g;
              },
              borderWidth:2, pointRadius:3, pointHoverRadius:6, tension:0.4, fill:true,
            }]},
            options: {
              responsive: true, maintainAspectRatio: false,
              interaction: { mode:'index', intersect:false },
              plugins: {
                legend: { display:true, position:'bottom', labels:{boxWidth:12, font:{size:11}} },
                zoom: zoomOpts,
              },
              scales: { y: makeScaleY0(vAbsolute) },
            },
          });
        }
      };

      buildCharts(24);

      document.querySelectorAll('.tr-btn').forEach(btn => {
        btn.addEventListener('click', () => {
          document.querySelectorAll('.tr-btn').forEach(b => b.classList.remove('active'));
          btn.classList.add('active');
          const r = btn.dataset.range;
          buildCharts(r==='1d'?24 : r==='3d'?72 : r==='7d'?168 : null);
        });
      });
    }
  }

  // ストーリー時系列
  const storyEl = document.getElementById('story-timeline');
  if (storyEl && timeline.length) {
    // 古い順に処理して、各スナップで初登場のURLだけを抽出（Yahoo直リンクは除外）
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
      if (!articles.length) return '';  // 新記事なしは非表示
      const headlineHtml = articles.map(a => `
        <div class="headline-item">
          <span class="headline-source-badge">
            <img class="source-favicon" src="https://www.google.com/s2/favicons?domain=${esc(a.source)}&sz=16" alt="" width="12" height="12">
            ${esc(a.source)}
          </span>
          <a href="${esc(a.url)}" target="_blank" rel="noopener noreferrer">${esc(a.title)}</a>
        </div>`).join('');

      return `
        <div class="story-item ${isLatest?'latest':''}">
          <div class="story-left">
            <div class="story-time">${fmtDate(snap.timestamp)}</div>
            <div class="story-badges">
              <span class="story-count">${articles.length}件</span>
            </div>
          </div>
          <div class="story-right">
            ${headlineHtml || '<span class="story-empty">―</span>'}
          </div>
        </div>`;
    }).join('');
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const topicId = new URLSearchParams(location.search).get('id');
  if (topicId) {
    trackView(topicId);
    const refresh = () => fetch(apiUrl(`topic/${topicId}`)).then(r=>r.json()).then(renderDetail).catch(console.error);
    refresh();
    setInterval(refresh, REFRESH_MS);
  } else {
    buildFilters();
    setupSearch();
    loadWeather();
    refreshTopics();
    setInterval(refreshTopics, REFRESH_MS);
  }
});
