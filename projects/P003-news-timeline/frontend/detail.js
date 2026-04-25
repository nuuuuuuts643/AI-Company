// ===== 詳細ページ =====
// app.js が先にロードされていること前提（esc, fmtDate, apiUrl, genreEmoji 等を参照）
let chartInstance = null, viewsChartInstance = null;

function getAnonymousId() {
  let id = localStorage.getItem('flotopic_anon_id');
  if (!id) {
    id = crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).slice(2) + Date.now();
    localStorage.setItem('flotopic_anon_id', id);
  }
  return id;
}

function trackView(topicId) {
  if (typeof ANALYTICS_URL === 'undefined' || !topicId) return;
  fetch(ANALYTICS_URL + 'analytics/event', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ anonymousId: getAnonymousId(), topicId, eventType: 'page_view' }),
  }).catch(() => {});
}

function updateOGP(meta) {
  const title   = meta.generatedTitle || meta.title || 'Flotopic';
  const rawDesc = cleanSummary(meta.generatedSummary) || '';
  const desc    = rawDesc.length > 0 ? rawDesc.slice(0, 100) : 'Flotopicでトピックの推移をAIが分析';
  const url     = `https://flotopic.com/topic.html?id=${meta.topicId || ''}`;
  const setMeta = (prop, val) => {
    const el = document.querySelector(`meta[property="${prop}"]`);
    if (el) el.setAttribute('content', val);
  };
  setMeta('og:title',       title);
  setMeta('og:description', desc);
  setMeta('og:url',         url);

  // canonical URL を動的更新
  const canonical = document.getElementById('canonical-url');
  if (canonical) canonical.setAttribute('href', url);

  // JSON-LD 構造化データ（NewsArticle）を動的更新
  const jsonLdEl = document.getElementById('jsonld-newsarticle');
  if (jsonLdEl && meta.topicId) {
    const iso = (ts) => {
      if (!ts) return new Date().toISOString();
      try { return new Date(ts).toISOString(); } catch { return new Date().toISOString(); }
    };
    const datePublished = iso(meta.firstArticleAt || meta.createdAt);
    const dateModified  = iso(meta.lastArticleAt  || meta.lastUpdated);
    const jsonLd = {
      '@context': 'https://schema.org',
      '@type': 'NewsArticle',
      'headline': title.slice(0, 110),
      'description': desc,
      'url': url,
      'datePublished': datePublished,
      'dateModified':  dateModified,
      'publisher': {
        '@type': 'Organization',
        'name': 'Flotopic',
        'url': 'https://flotopic.com',
        'logo': { '@type': 'ImageObject', 'url': 'https://flotopic.com/icon-192.png' }
      },
      'mainEntityOfPage': { '@type': 'WebPage', '@id': url }
    };
    jsonLdEl.textContent = JSON.stringify(jsonLd);
  }
}


function renderDetail(data) {
  const {meta, timeline, views} = data;
  if (!meta) return;

  recordTopicView(meta);
  document.title = `${meta.generatedTitle||meta.title} | Flotopic`;
  updateOGP(meta);

  const titleEl = document.getElementById('topic-title');
  if (titleEl) titleEl.textContent = meta.generatedTitle || meta.title;

  const shareBtn = document.getElementById('share-btn');
  if (shareBtn && navigator.share) {
    shareBtn.style.display = 'inline-flex';
    shareBtn.onclick = () => navigator.share({
      title: meta.generatedTitle || meta.title,
      text: cleanSummary(meta.generatedSummary) || '',
      url: location.href,
    });
  }

  // X（旧Twitter）シェアボタン
  const xBtn = document.getElementById('x-share-btn');
  if (xBtn) {
    const pageUrl  = `https://flotopic.com/topic.html?id=${encodeURIComponent(meta.topicId || '')}`;
    const xTitle   = encodeURIComponent(meta.generatedTitle || meta.title || 'Flotopic');
    xBtn.href = `https://twitter.com/intent/tweet?text=${xTitle}&url=${encodeURIComponent(pageUrl)}`;
    xBtn.style.display = 'inline-flex';
  }

  // はてなブックマーク シェアボタン
  const hatenaBtn = document.getElementById('hatena-share-btn');
  if (hatenaBtn) {
    const pageUrl   = `https://flotopic.com/topic.html?id=${encodeURIComponent(meta.topicId || '')}`;
    const pageTitle = encodeURIComponent(meta.generatedTitle || meta.title || 'Flotopic');
    hatenaBtn.href = `https://b.hatena.ne.jp/add?mode=confirm&url=${encodeURIComponent(pageUrl)}&title=${pageTitle}`;
    hatenaBtn.style.display = 'inline-flex';
  }

  // Threads シェアボタン
  const threadsBtn = document.getElementById('threads-share-btn');
  if (threadsBtn) {
    const pageUrl    = `https://flotopic.com/topic.html?id=${encodeURIComponent(meta.topicId || '')}`;
    const shareTitle = meta.generatedTitle || meta.title || 'Flotopic';
    const shareText  = encodeURIComponent(`${shareTitle}\n${pageUrl}`);
    threadsBtn.href = `https://www.threads.net/intent/post?text=${shareText}`;
    threadsBtn.style.display = 'inline-flex';
  }

  // <time> タグ（最終更新日時）— toUnixSec で秒/ミリ秒/ISO 混在を正規化
  const timeEl = document.getElementById('topic-last-updated');
  if (timeEl) {
    const rawTs = meta.lastArticleAt || meta.lastUpdated;
    const tsMs = toUnixSec(rawTs) * 1000;
    if (tsMs > 1000000000000) {
      const d = new Date(tsMs);
      timeEl.setAttribute('datetime', d.toISOString());
      timeEl.textContent = d.toLocaleString('ja-JP', { year: 'numeric', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    }
  }

  const badge = document.getElementById('status-badge');
  if (badge) { badge.textContent = STATUS_LABEL[meta.status]||meta.status; badge.className=`status-badge ${meta.status}`; badge.style.display='inline-block'; }
  const genreEl = document.getElementById('genre-badge');
  if (genreEl) {
    const gs = meta.genres || (meta.genre ? [meta.genre] : []);
    if (gs.length) { genreEl.textContent = gs.join(' / '); genreEl.style.display='inline-block'; }
  }

  // ── AI 4セクション分析表示 ───────────────────────────────────
  const aiAnalysisEl = document.getElementById('ai-analysis');
  if (aiAnalysisEl) {
    const summary      = cleanSummary(meta.generatedSummary);
    const spreadReason = meta.spreadReason || '';
    const forecast     = meta.forecast     || '';
    const beats        = Array.isArray(meta.storyTimeline) ? meta.storyTimeline : [];
    const phase        = meta.storyPhase   || '';
    const hasFullAI    = summary && beats.length > 0;
    const hasSummary   = summary && meta.aiGenerated;

    const PHASE_COLOR = { '発端':'#f59e0b','拡散':'#3b82f6','ピーク':'#ef4444','現在地':'#10b981' };
    const PHASE_ICON  = { '発端':'🌱','拡散':'📡','ピーク':'🔥','現在地':'📍' };

    if (hasFullAI || hasSummary) {
      // ① 何が起きたか
      const sect1 = `
        <div class="ai-section">
          <div class="ai-section-label">① 何が起きたか</div>
          <p class="ai-section-body">${esc(summary)}</p>
        </div>`;

      // ② なぜ広がったか
      const sect2 = spreadReason ? `
        <div class="ai-section">
          <div class="ai-section-label">② なぜ広がったか</div>
          <p class="ai-section-body">${esc(spreadReason)}</p>
        </div>` : '';

      // ③ 今どの段階か（フェーズ + タイムライン）
      const phaseChip = phase
        ? `<span class="ai-phase-chip" style="background:${PHASE_COLOR[phase]||'#6366f1'}">${PHASE_ICON[phase]||'📍'} ${esc(phase)}</span>`
        : '';
      const beatsHtml = beats.map(b =>
        `<div class="ai-beat">
           <span class="ai-beat-date">${esc(b.date||'')}</span>
           <span class="ai-beat-event">${esc(b.event||'')}</span>
         </div>`
      ).join('');
      const sect3 = (phaseChip || beatsHtml) ? `
        <div class="ai-section">
          <div class="ai-section-label">③ 今どの段階か</div>
          ${phaseChip}
          ${beatsHtml ? `<div class="ai-beats">${beatsHtml}</div>` : ''}
        </div>` : '';

      // ④ 今後どうなるか
      const sect4 = forecast ? `
        <div class="ai-section ai-section-forecast">
          <div class="ai-section-label">④ 今後どうなるか <span class="ai-hypothesis-badge">仮説</span></div>
          <p class="ai-section-body">${esc(forecast)}</p>
        </div>` : '';

      aiAnalysisEl.innerHTML = `<div class="ai-analysis-inner">${sect1}${sect2}${sect3}${sect4}</div>`;
      aiAnalysisEl.style.display = 'block';
    } else {
      // AI処理待ち
      const cnt = meta.articleCount || 1;
      const sources = (meta.sources || []).slice(0, 3).join('・');
      aiAnalysisEl.innerHTML = `
        <div class="ai-analysis-inner ai-pending">
          <span class="ai-pending-icon">⏳</span>
          <span>AI分析を生成中です（1日4回更新）。${cnt}件の記事を追跡中${sources ? `（${sources} ほか）` : ''}。</span>
        </div>`;
      aiAnalysisEl.style.display = 'block';
    }
  }

  // 後方互換: 旧 ai-story-timeline 要素があれば非表示
  const aiStoryEl = document.getElementById('ai-story-timeline');
  if (aiStoryEl) aiStoryEl.style.display = 'none';

  const canvas = document.getElementById('score-chart');
  const vCanvas = document.getElementById('views-chart');
  const noData = document.getElementById('no-data');
  if (canvas) {
    const chartCard = canvas.closest('.card');
    if (timeline.length < 2) {
      // データ不足時はグラフカードごと非表示（空の暗いブロックを残さない）
      if (chartCard) chartCard.style.display = 'none';
    } else {
      if (chartCard) {
        // プレースホルダー削除 & chart-header 復元
        chartCard.querySelectorAll('.chart-placeholder').forEach(el => el.remove());
        const header = chartCard.querySelector('.chart-header');
        if (header) header.style.display = '';
      }
      canvas.style.display='block'; if(vCanvas) vCanvas.style.display='block'; if(noData) noData.style.display='none';

      const buildCharts = (rangeHours) => {
        const now = Date.now();
        const cutoff = rangeHours ? now - rangeHours * 3600 * 1000 : 0;
        const filtered = rangeHours ? timeline.filter(s => new Date(s.timestamp).getTime() >= cutoff) : timeline;
        const src = filtered.length >= 2 ? filtered : timeline;

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

        const viewsSorted = [...(views||[])].sort((a,b) => a.date.localeCompare(b.date));
        const vLabels   = viewsSorted.map(v => `${parseInt(v.date.slice(4,6))}/${parseInt(v.date.slice(6,8))}`);
        const vAbsolute = viewsSorted.map(v => v.count);
        const vDelta    = viewsSorted.map((v, i) => i === 0 ? 0 : v.count - viewsSorted[i-1].count);

        const zoomOpts = meta.status === 'archived' ? {} : {
          zoom: { wheel:{enabled:true}, pinch:{enabled:true}, mode:'x' },
          pan:  { enabled:true, mode:'x' },
        };
        const makeScaleY0 = (data) => {
          const vals = data.filter(v => v !== null);
          const max = vals.length ? Math.max(...vals) : 10;
          return { min:0, max: max + Math.max(max * 0.2, 1), ticks:{ precision:0, maxTicksLimit:5 }, grid:{ color:'rgba(0,0,0,.06)' } };
        };
        const makeScaleDelta = (data) => {
          const vals = data.filter(v => v !== null);
          const max = vals.length ? Math.max(...vals) : 1;
          const min = vals.length ? Math.min(...vals) : 0;
          const pad = Math.max(Math.abs(max - min) * 0.2, 1);
          return {
            min: min < 0 ? min - pad : 0, max: max + pad,
            ticks: { precision:0, maxTicksLimit:5 },
            grid: { color: ctx => ctx.tick.value === 0 ? 'rgba(0,0,0,.3)' : 'rgba(0,0,0,.06)', lineWidth: ctx => ctx.tick.value === 0 ? 2 : 1 },
          };
        };

        // 記事数の推移（折れ線グラフ）
        const artLabel = aggregate ? '記事数（日次）' : '記事数（30分ごと）';
        if (chartInstance) chartInstance.destroy();
        chartInstance = new Chart(canvas.getContext('2d'), {
          type: 'line',
          data: { labels, datasets: [{ label: artLabel, data: mediaCnts,
            borderColor: '#6366f1',
            backgroundColor: (ctx) => {
              const {ctx: c, chartArea} = ctx.chart;
              if (!chartArea) return 'rgba(99,102,241,.15)';
              const g = c.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
              g.addColorStop(0, 'rgba(99,102,241,.35)'); g.addColorStop(1, 'rgba(99,102,241,.02)');
              return g;
            },
            borderWidth: 2, pointRadius: 3, pointHoverRadius: 6, tension: 0.4, fill: true }]},
          options: {
            responsive: true, maintainAspectRatio: false,
            interaction: { mode:'index', intersect:false },
            plugins: { legend: { display:true, position:'bottom', labels:{boxWidth:12, font:{size:11}} }, zoom: zoomOpts },
            scales: { y: makeScaleY0(mediaCnts) },
          },
        });

        if (vCanvas) {
          // スコアの推移（トピックの「熱量」が上がって落ち着く様子を可視化）
          const scoreLabel = aggregate ? '注目スコア（日次最大）' : '注目スコア';
          if (viewsChartInstance) viewsChartInstance.destroy();
          viewsChartInstance = new Chart(vCanvas.getContext('2d'), {
            type: 'line',
            data: { labels, datasets: [{ label: scoreLabel, data: scores,
              borderColor:'#f59e0b',
              backgroundColor: (ctx) => {
                const {ctx:c, chartArea} = ctx.chart;
                if (!chartArea) return 'rgba(245,158,11,.15)';
                const g = c.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
                g.addColorStop(0, 'rgba(245,158,11,.4)'); g.addColorStop(1, 'rgba(245,158,11,.02)');
                return g;
              },
              borderWidth:2, pointRadius:3, pointHoverRadius:6, tension:0.4, fill:true }]},
            options: {
              responsive: true, maintainAspectRatio: false,
              interaction: { mode:'index', intersect:false },
              plugins: { legend: { display:true, position:'bottom', labels:{boxWidth:12, font:{size:11}} }, zoom: zoomOpts },
              scales: { y: makeScaleY0(scores) },
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
          buildCharts(r==='1d'?24 : r==='3d'?72 : r==='7d'?168 : r==='1m'?720 : r==='3m'?2160 : r==='6m'?4320 : r==='1y'?8760 : null);
        });
      });
    }
  }

  if (meta.childTopics && meta.childTopics.length > 0) {
    const storymapContainer = document.getElementById('storymap-link-container');
    if (storymapContainer) {
      storymapContainer.innerHTML = `<a href="storymap.html?id=${esc(meta.topicId)}" class="storymap-btn">🗺 このストーリーの分岐を見る (${meta.childTopics.length}件)</a>`;
    }
  }

  const storyEl = document.getElementById('story-timeline');
  if (storyEl && !timeline.length) {
    storyEl.innerHTML = '<p style="color:var(--text-muted);font-size:.85rem;padding:8px 0;">記事データを収集中です。ストーリーはデータが蓄積されると表示されます。</p>';
  }
  if (storyEl && timeline.length) {
    const seenUrls = new Set();
    const allArticles = [];
    [...timeline].reverse().forEach(snap => {
      (snap.articles || []).forEach(a => {
        if (!seenUrls.has(a.url)) { seenUrls.add(a.url); allArticles.push({ ...a, _snapTs: snap.timestamp }); }
      });
    });
    allArticles.sort((a, b) => new Date(b._snapTs) - new Date(a._snapTs));

    const totalCount = allArticles.length;
    let timelineOrder = 'desc';
    const fmtTl = (ts) => {
      const d = new Date(ts);
      return `${d.getMonth()+1}月${d.getDate()}日 ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`;
    };
    const ARTICLES_PER_DAY = 3;
    const DAYS_INITIAL     = 7;
    const WDAY = ['日','月','火','水','木','金','土'];
    const fmtDay = (ts) => {
      const d = new Date(typeof ts === 'number' && ts < 1e11 ? ts * 1000 : ts);
      return `${d.getMonth()+1}月${d.getDate()}日（${WDAY[d.getDay()]}）`;
    };

    const renderTimeline = () => {
      const dayMap = {};
      allArticles.forEach(a => {
        const _pubMs = a.publishedAt ? a.publishedAt * 1000 : (a.pubDate ? new Date(a.pubDate).getTime() : 0);
        const ts  = _pubMs || new Date(a._snapTs).getTime();
        const key = fmtDay(new Date(ts));
        if (!dayMap[key]) dayMap[key] = { ts, articles: [] };
        dayMap[key].articles.push({ ...a, _ts: ts });
      });
      let days = Object.entries(dayMap).sort((a, b) =>
        timelineOrder === 'asc' ? a[1].ts - b[1].ts : b[1].ts - a[1].ts
      );
      const totalDays = days.length;
      let showAll = false;

      const buildHTML = () => {
        const visibleDays = showAll ? days : days.slice(0, DAYS_INITIAL);
        return `
          <div class="sort-toggle">
            <span class="sort-label">並び順:</span>
            <button class="sort-btn ${timelineOrder === 'desc' ? 'active' : ''}" data-order="desc">新しい順 ▾</button>
            <button class="sort-btn ${timelineOrder === 'asc' ? 'active' : ''}" data-order="asc">古い順</button>
          </div>
          <div class="article-total-count">全${totalCount}件の記事 · ${totalDays}日間</div>
          <div class="story-timeline-wrap">
            ${visibleDays.map(([dayKey, g]) => {
              const sorted = [...g.articles].sort((a, b) => b._ts - a._ts);
              const shown  = sorted.slice(0, ARTICLES_PER_DAY);
              const rest   = sorted.slice(ARTICLES_PER_DAY);
              return `<div class="timeline-item">
                <div class="timeline-dot"></div>
                <div class="timeline-content">
                  <div class="timeline-time">${dayKey}<span class="day-article-count"> · ${g.articles.length}件</span></div>
                  <div class="day-articles">
                    ${shown.map(a => {
                      const _artMs = a.publishedAt ? a.publishedAt * 1000 : (a.pubDate ? new Date(a.pubDate).getTime() : 0);
                      const isNew = _artMs && (Date.now() - _artMs) < 6 * 3600 * 1000;
                      return `<div class="timeline-article">
                        <a href="${esc(a.url)}" class="timeline-article-link" target="_blank" rel="noopener noreferrer">${esc(a.title)}${isNew ? '<span class="new-badge">NEW</span>' : ''}</a>
                        <div class="timeline-source">${srcFaviconImg(a.source)}${esc(a.source)}</div>
                      </div>`;
                    }).join('')}
                    ${rest.length ? `<details class="day-more-details"><summary class="day-more-btn">他${rest.length}件を表示</summary>${rest.map(a => `<div class="timeline-article">
                        <a href="${esc(a.url)}" class="timeline-article-link" target="_blank" rel="noopener noreferrer">${esc(a.title)}</a>
                        <div class="timeline-source">${srcFaviconImg(a.source)}${esc(a.source)}</div>
                      </div>`).join('')}</details>` : ''}
                  </div>
                </div>
              </div>`;
            }).join('')}
          </div>
          ${!showAll && totalDays > DAYS_INITIAL ? `<button class="timeline-show-all-btn" id="tl-show-all">📅 全${totalDays}日間を表示</button>` : ''}
        `;
      };

      storyEl.innerHTML = buildHTML();
      storyEl.querySelectorAll('.sort-btn').forEach(btn => {
        btn.addEventListener('click', () => { timelineOrder = btn.dataset.order; renderTimeline(); });
      });
      const showAllBtn = document.getElementById('tl-show-all');
      if (showAllBtn) {
        showAllBtn.addEventListener('click', () => { showAll = true; storyEl.innerHTML = buildHTML(); storyEl.querySelectorAll('.sort-btn').forEach(b => b.addEventListener('click', () => { timelineOrder = b.dataset.order; renderTimeline(); })); });
      }
    };

    renderTimeline();

    // タイムラインに既出のURLを収集（表示済み記事を関連記事から除外するため）
    const shownInTimeline = new Set();
    {
      const _dm = {};
      allArticles.forEach(a => {
        const _ms = a.publishedAt ? a.publishedAt * 1000 : (a.pubDate ? new Date(a.pubDate).getTime() : 0);
        const _ts = _ms || new Date(a._snapTs).getTime();
        const key = fmtDay(new Date(_ts));
        if (!_dm[key]) _dm[key] = [];
        _dm[key].push({ url: a.url, _ts });
      });
      Object.values(_dm).forEach(g => {
        g.sort((a, b) => b._ts - a._ts).slice(0, ARTICLES_PER_DAY).forEach(a => shownInTimeline.add(a.url));
      });
    }

    const relatedEl = document.getElementById('related-articles');
    if (relatedEl) {
      const relatedCard = relatedEl.closest('.card');
      // タイムライン未掲載の記事を候補に
      let candidates = allArticles.filter(a => !shownInTimeline.has(a.url));
      // 候補が少ない場合は全記事から補完（ソースを変えて重複感を減らす）
      if (candidates.length < 3 && allArticles.length > 3) {
        const usedInTimeline = allArticles.filter(a => shownInTimeline.has(a.url));
        const extraSources = new Set(candidates.map(a => a.source));
        for (const a of usedInTimeline) {
          if (candidates.length >= 5) break;
          if (!extraSources.has(a.source)) { candidates.push(a); extraSources.add(a.source); }
        }
      }
      if (!candidates.length) {
        if (relatedCard) relatedCard.style.display = 'none';
      } else {
        // ソース多様性を優先してピック（最大3件）
        const picked = [];
        const usedSources = new Set();
        // 最新順でソート
        const sorted = [...candidates].sort((a, b) => {
          const ta = a.publishedAt ? a.publishedAt * 1000 : new Date(a._snapTs).getTime();
          const tb = b.publishedAt ? b.publishedAt * 1000 : new Date(b._snapTs).getTime();
          return tb - ta;
        });
        for (const a of sorted) {
          if (picked.length >= 3) break;
          if (!usedSources.has(a.source)) { picked.push(a); usedSources.add(a.source); }
        }
        // ソース重複でも3件に満たなければ追加
        for (const a of sorted) {
          if (picked.length >= 3) break;
          if (!picked.some(p => p.url === a.url)) picked.push(a);
        }
        relatedEl.innerHTML = picked.map(a => `
          <div class="article-item">
            <a href="${esc(a.url)}" target="_blank" rel="noopener noreferrer">${esc(a.title)}</a>
            <div class="article-meta">
              ${srcFaviconImg(a.source)}
              ${esc(a.source)} · ${fmtTl(a._snapTs)}
            </div>
          </div>
        `).join('');
      }
    }

  }

  // timeline=0 の場合は関連記事枠ごと非表示
  if (!timeline.length) {
    const relatedFallback = document.getElementById('related-articles');
    if (relatedFallback) {
      const card = relatedFallback.closest('.card');
      if (card) card.style.display = 'none';
    }
  }

  renderDiscovery(meta);
}

// ===== Discovery: 深掘り & 拡張 =====
let _allTopicsCache = null;
async function fetchAllTopicsOnce() {
  if (_allTopicsCache) return _allTopicsCache;
  try {
    const r = await fetch(apiUrl('topics'));
    const d = await r.json();
    _allTopicsCache = d.topics || [];
    return _allTopicsCache;
  } catch { return []; }
}

function fmtElapsed(isoOrTs) {
  try {
    const d = typeof isoOrTs === 'number' ? new Date(isoOrTs * 1000) : new Date(isoOrTs);
    if (isNaN(d)) return '';
    const diff = (Date.now() - d.getTime()) / 1000;
    if (diff < 3600)   return `${Math.floor(diff / 60)}分前`;
    if (diff < 86400)  return `${Math.floor(diff / 3600)}時間前`;
    if (diff < 604800) return `${Math.floor(diff / 86400)}日前`;
    return `${d.getMonth()+1}/${d.getDate()}`;
  } catch { return ''; }
}

function discCard(topic, badge) {
  const title = topic.generatedTitle || topic.title || '';
  const ago   = fmtElapsed(topic.lastArticleAt || topic.lastUpdated || 0);
  const cnt   = topic.articleCount || 0;
  const dot   = topic.lifecycleStatus === 'active' ? '🔴' : topic.lifecycleStatus === 'cooling' ? '🟡' : '⚪';
  const badgeHtml = badge ? `<span class="disc-badge disc-badge-${badge.cls}">${esc(badge.label)}</span>` : '';
  return `
    <a href="topic.html?id=${esc(topic.topicId)}" class="disc-card">
      ${badgeHtml}
      <div class="disc-card-title">${esc(title)}</div>
      <div class="disc-card-meta">${dot} ${cnt}件${ago ? ` · ${esc(ago)}` : ''}</div>
    </a>`;
}

function coordsToRegion(lat, lon) {
  if (lat > 41.5)                       return { name: '北海道', kw: '北海道' };
  if (lat > 38.5)                       return { name: '東北',   kw: '東北' };
  if (lat > 36.5 && lon >= 140.5)       return { name: '関東北部', kw: '栃木' };
  if (lat > 35.4 && lon >= 138.5)       return { name: '関東',   kw: '東京' };
  if (lat > 35.0 && lon < 137.0)        return { name: '関西',   kw: '大阪' };
  if (lat > 35.0 && lon >= 137.0)       return { name: '東海',   kw: '名古屋' };
  if (lat > 33.5 && lon < 132.0)        return { name: '中国',   kw: '広島' };
  if (lat > 33.5)                        return { name: '四国',   kw: '愛媛' };
  return { name: '九州', kw: '福岡' };
}

function renderDiscovery(meta) {
  const section = document.getElementById('discovery-section');
  if (!section) return;

  fetchAllTopicsOnce().then(allTopics => {
    const curId = meta.topicId;
    const tMap  = {};
    for (const t of allTopics) tMap[t.topicId] = t;

    const items = [];
    const usedIds = new Set([curId]);

    // 1. 親トピック（上位の流れ）
    if (meta.parentTopicId && tMap[meta.parentTopicId]) {
      items.push({ t: tMap[meta.parentTopicId], badge: { label: '← 大きな流れ', cls: 'parent' } });
      usedIds.add(meta.parentTopicId);
    }

    // 2. エンティティ類似トピック（relatedTopics・最も確実な関連性）
    for (const rt of (meta.relatedTopics || [])) {
      if (items.length >= 5) break;
      if (usedIds.has(rt.topicId)) continue;
      const t = tMap[rt.topicId];
      if (!t) continue;
      const tags = (rt.sharedEntities || []).slice(0, 2).map(e => `<span class="entity-tag">#${esc(e)}</span>`).join('');
      items.push({ t, badge: null, extraHtml: tags });
      usedIds.add(rt.topicId);
    }

    // 3. 子トピック（この話題から派生した流れ）
    for (const ref of (meta.childTopics || [])) {
      if (items.length >= 5) break;
      if (usedIds.has(ref.topicId)) continue;
      const t = tMap[ref.topicId] || ref;
      if (!t) continue;
      items.push({ t, badge: { label: '↳ 分岐', cls: 'child' } });
      usedIds.add(ref.topicId);
    }

    if (items.length === 0) {
      section.innerHTML = '';
      return;
    }

    const smLink = (meta.childTopics && meta.childTopics.length > 0)
      ? `<a href="storymap.html?id=${esc(meta.topicId)}" class="disc-see-all">🗺 ストーリーマップ（${meta.childTopics.length}件の分岐）→</a>`
      : '';

    section.innerHTML = `
      <div class="card disc-card-wrapper">
        <h2>関連する話題</h2>
        <p class="disc-header-sub">エンティティの重複・親子関係から検出</p>
        <div class="disc-col-body">
          ${items.map(({ t, badge, extraHtml }) => {
            const title = t.generatedTitle || t.title || '';
            const ago   = fmtElapsed(t.lastArticleAt || t.lastUpdated || 0);
            const cnt   = t.articleCount || 0;
            const dot   = t.lifecycleStatus === 'active' ? '🔴' : t.lifecycleStatus === 'cooling' ? '🟡' : '⚪';
            const badgeHtml = badge ? `<span class="disc-badge disc-badge-${badge.cls}">${esc(badge.label)}</span>` : '';
            return `
              <a href="topic.html?id=${esc(t.topicId)}" class="disc-card">
                ${badgeHtml}
                <div class="disc-card-title">${esc(title)}</div>
                <div class="disc-card-footer">
                  <span class="disc-card-meta">${dot} ${cnt}件${ago ? ` · ${esc(ago)}` : ''}</span>
                  ${extraHtml || ''}
                </div>
              </a>`;
          }).join('')}
        </div>
        ${smLink}
      </div>`;
  });
}
