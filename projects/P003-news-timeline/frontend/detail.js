// ===== 詳細ページ =====
// app.js が先にロードされていること前提（esc, fmtDate, apiUrl, genreEmoji 等を参照）
let chartInstance = null, viewsChartInstance = null;

function getNextUpdateTime() {
  const now = new Date();
  const jstNow = new Date(now.getTime() + (9 * 60 + now.getTimezoneOffset()) * 60000);
  const hours = [5, 9, 15, 19, 23];
  const currentHour = jstNow.getHours() * 60 + jstNow.getMinutes();
  for (const h of hours) {
    if (h * 60 > currentHour) return `${h}:00 JST`;
  }
  return '翌 05:00 JST';
}

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

async function fetchAndShowViews30m(topicId) {
  if (!topicId || typeof _GW === 'undefined') return;
  try {
    const r = await fetch(`${_GW}/analytics/views/${topicId}`);
    if (!r.ok) return;
    const data = await r.json();
    const count = data.views30m || 0;
    if (count < 2) return;
    const badge = document.getElementById('views30m-badge');
    if (badge) {
      badge.textContent = `👁 過去30分 ${count}人が閲覧`;
      badge.style.display = '';
    }
  } catch {}
}

function updateOGP(meta) {
  const title   = meta.generatedTitle || meta.title || 'Flotopic';
  const rawDesc = cleanSummary(meta.generatedSummary) || '';
  const PHASE_LABEL_OGP = {'発端':'始まり','拡散':'広まってる','ピーク':'急上昇','現在地':'進行中','収束':'ひと段落'};
  const phaseText = meta.storyPhase ? (PHASE_LABEL_OGP[meta.storyPhase] || meta.storyPhase) : '';
  const phasePrefix = phaseText ? `【${phaseText}】` : '';
  const summaryPart = rawDesc.length > 0 ? rawDesc.slice(0, 90) : '';
  const desc = summaryPart
    ? `${phasePrefix}${summaryPart}`
    : 'AIがニュースの経緯をストーリー化。話の始まりから今日まで時系列で追える。';
  const url     = meta.topicId ? `https://flotopic.com/topics/${meta.topicId}.html` : 'https://flotopic.com/topic.html';
  const ogImage = meta.imageUrl || 'https://flotopic.com/ogp.png';
  const setMeta = (prop, val) => {
    const el = document.querySelector(`meta[property="${prop}"]`);
    if (el) el.setAttribute('content', val);
  };
  const setName = (name, val) => {
    const el = document.querySelector(`meta[name="${name}"]`);
    if (el) el.setAttribute('content', val);
  };
  setMeta('og:title',       title);
  setMeta('og:description', desc);
  setMeta('og:url',         url);
  setMeta('og:image',       ogImage);
  setName('twitter:title',       title);
  setName('twitter:description', desc);
  setName('twitter:image',       ogImage);
  setName('description',         desc);

  // canonical URL を動的更新
  const canonical = document.getElementById('canonical-url');
  if (canonical) canonical.setAttribute('href', url);

  // JSON-LD 構造化データ（NewsArticle）を動的更新
  const jsonLdEl = document.getElementById('jsonld-newsarticle');
  if (jsonLdEl && meta.topicId) {
    const iso = (ts) => {
      if (!ts) return new Date().toISOString();
      try {
        // Unix seconds → milliseconds (integers under 2e10 are seconds, not ms)
        const ms = typeof ts === 'number' && ts < 2e10 ? ts * 1000 : ts;
        return new Date(ms).toISOString();
      } catch { return new Date().toISOString(); }
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
      'image': ogImage !== 'https://flotopic.com/ogp.png'
        ? [{ '@type': 'ImageObject', 'url': ogImage, 'width': 1200, 'height': 630 }]
        : [{ '@type': 'ImageObject', 'url': 'https://flotopic.com/ogp.png', 'width': 1200, 'height': 630 }],
      'author': { '@type': 'Organization', 'name': 'Flotopic', 'url': 'https://flotopic.com' },
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

  // BreadcrumbList 構造化データ
  const breadcrumbEl = document.getElementById('jsonld-breadcrumb');
  if (breadcrumbEl && meta.topicId) {
    breadcrumbEl.textContent = JSON.stringify({
      '@context': 'https://schema.org',
      '@type': 'BreadcrumbList',
      'itemListElement': [
        { '@type': 'ListItem', 'position': 1, 'name': 'Flotopic', 'item': 'https://flotopic.com/' },
        { '@type': 'ListItem', 'position': 2, 'name': title.slice(0, 80), 'item': url }
      ]
    });
  }
}


function renderDetail(data) {
  const {meta, timeline, views} = data;
  if (!meta) return;

  recordTopicView(meta);
  fetchAndShowViews30m(meta.topicId);
  document.title = `${meta.generatedTitle||meta.title} | Flotopic`;
  updateOGP(meta);

  const titleEl = document.getElementById('topic-title');
  if (titleEl) titleEl.textContent = meta.topicTitle || meta.generatedTitle || meta.title;

  // 親トピックリンク (思想: 縦の階層を一目で・冒頭に表示) — 2026-04-27
  const parentLinkEl = document.getElementById('parent-topic-link');
  if (parentLinkEl && meta.parentTopicId) {
    parentLinkEl.innerHTML = `<a href="topic.html?id=${esc(meta.parentTopicId)}" style="color:inherit;text-decoration:none;">この話は${meta.parentTopicTitle ? `「${esc(meta.parentTopicTitle)}」` : '上位テーマ'}の一部です →</a>`;
    parentLinkEl.style.display = 'inline-flex';
  }

  // ヒーロー背景画像（imageUrlがある場合、グラデーション+画像でリッチ表示）
  if (meta.imageUrl) {
    const heroEl = document.querySelector('.topic-hero');
    if (heroEl) {
      const safeUrl = (typeof safeImgUrl === 'function' ? safeImgUrl(meta.imageUrl) : meta.imageUrl.replace(/^http:\/\//i, 'https://')).replace(/'/g, '%27');
      // 暗いオーバーレイ(0.82→0.68)で可読性を保ちつつ画像を見せる
      heroEl.style.backgroundImage = `linear-gradient(rgba(15,23,42,0.82) 0%, rgba(15,23,42,0.68) 60%, rgba(15,23,42,0.82) 100%), url('${safeUrl}')`;
      heroEl.style.backgroundSize = 'cover';
      heroEl.style.backgroundPosition = 'center 30%';  // 画像上部(被写体が多い)を優先
      heroEl.style.minHeight = '150px';  // 短タイトルでも背景画像が見えるよう最低高さ確保
    }
  }

  // お気に入りボタン（トピックページのヒーロー内）
  const topicFavBtn = document.getElementById('topic-fav-btn');
  if (topicFavBtn && meta.topicId) {
    const updateFavBtnUI = () => {
      const isFav = typeof userFavorites !== 'undefined' && userFavorites.has(meta.topicId);
      topicFavBtn.classList.toggle('fav-active', isFav);
      topicFavBtn.title = isFav ? 'お気に入りを解除' : 'お気に入りに追加';
      topicFavBtn.textContent = isFav ? '♥ 登録済み' : '♥ お気に入り';
    };
    updateFavBtnUI();
    topicFavBtn.addEventListener('click', async () => {
      if (typeof toggleFavorite === 'function') {
        await toggleFavorite(meta.topicId, topicFavBtn);
        updateFavBtnUI();
      } else if (typeof openAuthModal === 'function') {
        openAuthModal();
      }
    });
  }

  const shareBtn = document.getElementById('share-btn');
  if (shareBtn && navigator.share) {
    shareBtn.style.display = 'inline-flex';
    shareBtn.onclick = () => navigator.share({
      title: meta.generatedTitle || meta.title,
      text: cleanSummary(meta.generatedSummary) || '',
      url: location.href,
    });
  }

  // シェアボタン共通: canonicalな静的URLを使用（SEO・OGP最適化）
  const sharePageUrl = meta.topicId ? `https://flotopic.com/topics/${meta.topicId}.html` : location.href;

  // X（旧Twitter）シェアボタン
  const xBtn = document.getElementById('x-share-btn');
  if (xBtn) {
    const xTitle = encodeURIComponent(meta.generatedTitle || meta.title || 'Flotopic');
    xBtn.href = `https://twitter.com/intent/tweet?text=${xTitle}&url=${encodeURIComponent(sharePageUrl)}`;
    xBtn.style.display = 'inline-flex';
  }

  // はてなブックマーク シェアボタン
  const hatenaBtn = document.getElementById('hatena-share-btn');
  if (hatenaBtn) {
    const pageTitle = encodeURIComponent(meta.generatedTitle || meta.title || 'Flotopic');
    hatenaBtn.href = `https://b.hatena.ne.jp/add?mode=confirm&url=${encodeURIComponent(sharePageUrl)}&title=${pageTitle}`;
    hatenaBtn.style.display = 'inline-flex';
  }

  // Threads シェアボタン
  const threadsBtn = document.getElementById('threads-share-btn');
  if (threadsBtn) {
    const shareTitle = meta.generatedTitle || meta.title || 'Flotopic';
    const shareText  = encodeURIComponent(`${shareTitle}\n${sharePageUrl}`);
    threadsBtn.href = `https://www.threads.net/intent/post?text=${shareText}`;
    threadsBtn.style.display = 'inline-flex';
  }

  // LINE シェアボタン
  const lineBtn = document.getElementById('line-share-btn');
  if (lineBtn) {
    lineBtn.href = `https://social-plugins.line.me/lineit/share?url=${encodeURIComponent(sharePageUrl)}`;
    lineBtn.style.display = 'inline-flex';
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

  // ── AI 分析表示（記事数に応じた段階レンダリング） ───────────────────────────────────
  const aiAnalysisEl = document.getElementById('ai-analysis');
  if (aiAnalysisEl) {
    const summary           = cleanSummary(meta.generatedSummary);
    const backgroundContext = cleanSummary(meta.backgroundContext || '');
    const spreadReason      = cleanSummary(meta.spreadReason || '');
    const forecast          = cleanSummary(meta.forecast     || '');
    const background        = cleanSummary(meta.background   || '');
    const perspectives      = cleanSummary(meta.perspectives || '');
    const outlook           = cleanSummary(meta.outlook      || '');
    const beats        = Array.isArray(meta.storyTimeline) ? meta.storyTimeline : [];
    const phase        = meta.storyPhase   || '';
    const summaryMode  = meta.summaryMode  || (beats.length > 0 || spreadReason || forecast ? 'full' : 'minimal');
    const hasSummary   = !!summary && !!meta.aiGenerated;
    const isFullAI     = summary && meta.aiGenerated;

    const PHASE_COLOR = { '発端':'rgba(78,201,192,0.55)','拡散':'rgba(78,201,192,0.7)','ピーク':'#4EC9C0','現在地':'#3BB5AC','収束':'#64748b' };
    const PHASE_ICON  = { '発端':'🌱','拡散':'📡','ピーク':'🔥','現在地':'📍','収束':'✅' };
    const PHASE_TEXT  = { '発端':'始まり','拡散':'広まってる','ピーク':'急上昇','現在地':'進行中','収束':'ひと段落' };
    const ALL_PHASES  = ['発端','拡散','ピーク','現在地','収束'];
    const currentIdx  = phase ? ALL_PHASES.indexOf(phase) : -1;
    const phaseBarHtml = phase ? `<div class="ai-phase-bar">${ALL_PHASES.map((p,i)=>{
      const cls = i===currentIdx ? 'active' : i<currentIdx ? 'past' : '';
      return `<div class="ai-phase-step ${cls}" style="background:${PHASE_COLOR[p]||'#4EC9C0'}"><span class="ai-phase-step-icon">${PHASE_ICON[p]||'📍'}</span><span class="ai-phase-step-label">${PHASE_TEXT[p]||p}</span></div>`;
    }).join('')}</div>` : '';
    const originHtml = (beats.length >= 2 && beats[0] && beats[0].event) ? `
      <div class="story-origin-highlight">
        <span class="story-origin-label">📅 この話の始まり${beats[0].date ? '（' + esc(beats[0].date) + '）' : ''}</span>
        <div class="story-origin-event">${esc(beats[0].event)}</div>
      </div>` : '';

    const buildBeatsHtml = (bts) => bts.map((b,i)=>{
      const isLast = i===bts.length-1;
      const dotCls = isLast ? 'ai-beat-dot ai-beat-dot-last' : 'ai-beat-dot';
      const transition = !isLast && b.transition ? `<span class="ai-beat-transition">${esc(b.transition)}</span>` : '';
      return `<div class="ai-beat"><div class="ai-beat-dot-col"><div class="${dotCls}"></div>${!isLast?'<div class="ai-beat-vline"></div>':''}</div><div class="ai-beat-content"><span class="ai-beat-date">${esc(b.date||'')}</span><div class="ai-beat-event">${esc(b.event||'')}</div>${transition}</div></div>`;
    }).join('');

    if (hasSummary) {
      const _artCnt = meta.articleCount || 0;
      const _srcs   = Array.isArray(meta.sources) ? meta.sources : [];
      const trustFooterHtml = _artCnt ? (() => {
        const cntText = `${_artCnt}件の記事を分析`;
        if (!_srcs.length) return `<div class="ai-trust-footer">${cntText}</div>`;
        const srcItems = _srcs.map(s => `<span class="ai-trust-source">${esc(s)}</span>`).join('');
        return `<details class="ai-trust-footer"><summary>${cntText} <span class="ai-trust-toggle">（情報源を見る）</span></summary><div class="ai-trust-sources">${srcItems}</div></details>`;
      })() : '';
      const storyNavHtml = document.getElementById('story-timeline')
        ? `<a class="ai-story-nav" href="#story-timeline">📅 記事の全タイムラインを見る</a>`
        : '';

      // ── minimal: 1〜2件記事 → 思想フレーム順 (背景→なぜ今→現状→今後) で短く
      if (summaryMode === 'minimal') {
        const sectBgM = background ? `<p class="ai-summary-bg">📚 <strong>なぜ今:</strong> ${esc(background)}</p>` : '';
        const sectCurM = `<p class="ai-summary-simple"><strong>📍 現状:</strong> ${esc(summary)}</p>`;
        const sectOlM = outlook ? `<p class="ai-summary-outlook">🔮 <strong>見通し:</strong> ${esc(outlook)}</p>` : '';
        aiAnalysisEl.innerHTML = `
          <div class="ai-analysis-inner ai-analysis-minimal">
            ${sectBgM}
            ${sectCurM}
            ${sectOlM}
            ${trustFooterHtml}
          </div>`;

      // ── standard: 3〜5件記事 → 思想フレーム順 (背景→なぜ今→なぜ広がった→経緯→現状→メディアズレ→今後)
      } else if (summaryMode === 'standard') {
        const sectBg = backgroundContext ? `
          <div class="ai-section">
            <div class="ai-section-label">📐 なぜ起きたか（構造的背景）</div>
            <p class="ai-section-body">${esc(backgroundContext)}</p>
          </div>` : '';
        const sectBgNow = background ? `
          <div class="ai-section">
            <div class="ai-section-label">📚 なぜ今この話題か</div>
            <p class="ai-section-body">${esc(background)}</p>
          </div>` : '';
        const sect2 = spreadReason ? `
          <div class="ai-section">
            <div class="ai-section-label">📡 なぜ広がったか</div>
            <p class="ai-section-body">${esc(spreadReason)}</p>
          </div>` : '';
        const beatsHtml = beats.length ? buildBeatsHtml(beats) : '';
        const sect3 = (phaseBarHtml || beatsHtml) ? `
          <div class="ai-section">
            <div class="ai-section-label">⏱ 経緯と今どの段階か</div>
            ${phaseBarHtml}
            ${originHtml}
            ${beatsHtml ? `<div class="ai-beats">${beatsHtml}</div>` : ''}
          </div>` : '';
        const sect1 = `
          <div class="ai-section">
            <div class="ai-section-label">📍 現状（何が起きているか）</div>
            <p class="ai-section-body">${esc(summary)}</p>
          </div>`;
        const sectPersp = perspectives ? `
          <div class="ai-section">
            <div class="ai-section-label">📰 メディアの見方のズレ</div>
            <p class="ai-section-body">${esc(perspectives)}</p>
          </div>` : '';
        const sectOl = outlook ? `
          <div class="ai-section ai-section-forecast">
            <div class="ai-section-label">🔮 今後どうなるか <span class="ai-hypothesis-badge">仮説</span></div>
            <p class="ai-section-body">${esc(outlook)}</p>
          </div>` : '';
        // 思想フレーム順: 背景 → なぜ今 → なぜ広がった → 経緯 → 現状 → メディアズレ → 今後 (full と同じ)
        aiAnalysisEl.innerHTML = `<div class="ai-analysis-inner">${sectBg}${sectBgNow}${sect2}${sect3}${sect1}${sectPersp}${sectOl}${trustFooterHtml}${storyNavHtml}</div>`;

      // ── full: 6件以上 → フル4セクション（従来通り）
      } else {
        // ① 何が起きたか
        // 思想に沿った順序: 背景 → なぜ今 → 経緯 → 現在 → メディア間ズレ → 今後 (2026-04-27)
        // ① なぜ起きたか (構造的背景)
        const sect2bg = backgroundContext ? `
          <div class="ai-section">
            <div class="ai-section-label">📐 なぜ起きたか（構造的背景）</div>
            <p class="ai-section-body">${esc(backgroundContext)}</p>
          </div>` : '';
        // ② なぜ今この話題か (時事文脈)
        const sectBgNowF = background ? `
          <div class="ai-section">
            <div class="ai-section-label">📚 なぜ今この話題か</div>
            <p class="ai-section-body">${esc(background)}</p>
          </div>` : '';
        // ③ なぜ広がったか
        const sect2 = spreadReason ? `
          <div class="ai-section">
            <div class="ai-section-label">📡 なぜ広がったか</div>
            <p class="ai-section-body">${esc(spreadReason)}</p>
          </div>` : '';
        // ④ 経緯 (タイムライン+フェーズ)
        const beatsHtml = beats.length ? buildBeatsHtml(beats) : '';
        const sect3 = (phaseBarHtml || beatsHtml) ? `
          <div class="ai-section">
            <div class="ai-section-label">⏱ 経緯と今どの段階か</div>
            ${phaseBarHtml}
            ${originHtml}
            ${beatsHtml ? `<div class="ai-beats">${beatsHtml}</div>` : ''}
          </div>` : '';
        // ⑤ 何が起きたか (現状サマリー) — 背景・経緯を踏まえた現在の状態
        const sect1 = `
          <div class="ai-section">
            <div class="ai-section-label">📍 現状（何が起きているか）</div>
            <p class="ai-section-body">${esc(summary)}</p>
          </div>`;
        // ⑥ メディア間のズレ (Flotopic 独自価値)
        const sectPerspF = perspectives ? `
          <div class="ai-section">
            <div class="ai-section-label">📰 メディアの見方のズレ</div>
            <p class="ai-section-body">${esc(perspectives)}</p>
          </div>` : '';
        // ⑦ 今後どうなるか
        const sect4 = forecast ? `
          <div class="ai-section ai-section-forecast">
            <div class="ai-section-label">🔮 今後どうなるか <span class="ai-hypothesis-badge">仮説</span></div>
            <p class="ai-section-body">${esc(forecast)}</p>
          </div>` : '';
        // ⑧ 短い見通し (forecast の代わり)
        const sectOlF = (outlook && !forecast) ? `
          <div class="ai-section ai-section-forecast">
            <div class="ai-section-label">🔮 見通し <span class="ai-hypothesis-badge">仮説</span></div>
            <p class="ai-section-body">${esc(outlook)}</p>
          </div>` : '';
        aiAnalysisEl.innerHTML = `<div class="ai-analysis-inner">${sect2bg}${sectBgNowF}${sect2}${sect3}${sect1}${sectPerspF}${sect4}${sectOlF}${trustFooterHtml}${storyNavHtml}</div>`;
      }

      aiAnalysisEl.style.display = 'block';
    } else {
      // AI処理待ち
      const cnt = meta.articleCount || 1;
      const sources = (meta.sources || []).slice(0, 3).join('・');
      aiAnalysisEl.innerHTML = `
        <div class="ai-analysis-inner ai-pending">
          <span class="ai-pending-icon">⏳</span>
          <span>AI分析を準備中です。次の更新: ${getNextUpdateTime()}。${cnt}件の記事を追跡中${sources ? `（${sources} ほか）` : ''}。</span>
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
      // データ不足時: 隠さず「正直に表示」(2026-04-27 思想に沿った変更)
      if (chartCard) {
        // 既存の chart-header / canvas を非表示にしてプレースホルダーに置換
        chartCard.querySelectorAll('canvas').forEach(c => c.style.display = 'none');
        const header = chartCard.querySelector('.chart-header');
        if (header) header.style.display = 'none';
        if (noData) noData.style.display = 'none';  // 重複防止
        // 既にプレースホルダーがあれば再生成しない
        if (!chartCard.querySelector('.chart-placeholder')) {
          const ph = document.createElement('div');
          ph.className = 'chart-placeholder';
          ph.style.cssText = 'padding:24px 16px;text-align:center;color:var(--text-muted);font-size:.85rem;line-height:1.7;';
          const totalViews = (views || []).reduce((s, v) => s + Number(v.count || 0), 0);
          const viewsLine = totalViews > 0
            ? `📊 直近の閲覧 ${totalViews} 回`
            : '👁 まだ誰も見ていません';
          const dataLine = timeline.length === 0
            ? 'まだスナップショットが取られていません。'
            : 'スナップショットが2件以上たまるとグラフが描画されます (約30分後〜)。';
          ph.innerHTML = `<div style="font-size:1rem;margin-bottom:6px;">推移グラフ</div><div>${viewsLine}</div><div style="margin-top:6px;">${dataLine}</div>`;
          chartCard.appendChild(ph);
        }
      }
    } else {
      if (chartCard) {
        // プレースホルダー削除 & chart-header 復元
        chartCard.querySelectorAll('.chart-placeholder').forEach(el => el.remove());
        const header = chartCard.querySelector('.chart-header');
        if (header) header.style.display = '';
      }
      canvas.style.display='block'; if(vCanvas) vCanvas.style.display='block'; if(noData) noData.style.display='none';

      const getChartColors = () => {
        const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
        return {
          grid:     isDark ? 'rgba(255,255,255,.12)' : 'rgba(0,0,0,.06)',
          gridZero: isDark ? 'rgba(255,255,255,.3)'  : 'rgba(0,0,0,.3)',
          tick:     isDark ? '#9ba3c4' : '#666',
        };
      };
      let _chartRange = 24;

      const buildCharts = (rangeHours) => {
        _chartRange = rangeHours;
        const now = Date.now();
        const cutoff = rangeHours ? now - rangeHours * 3600 * 1000 : 0;
        const filtered = rangeHours ? timeline.filter(s => new Date(s.timestamp).getTime() >= cutoff) : timeline;
        const src = filtered.length >= 2 ? filtered : timeline;

        const aggregate = rangeHours === null || rangeHours >= 72;

        // エンゲージメントスコア計算用: はてブ数(SNAP単位) + 累計閲覧数 + コメント×3 + お気に入り×5
        const viewsByDate = {};
        (views || []).forEach(v => { viewsByDate[v.date] = Number(v.count || 0); });
        const totalViews  = Object.values(viewsByDate).reduce((s, c) => s + c, 0);
        const commentCnt  = Number(meta.commentCount  || 0);
        const favoriteCnt = Number(meta.favoriteCount || 0);

        let labels, scores, mediaCnts, engagements;
        if (aggregate) {
          const byDay = {};
          src.forEach(s => {
            const d = new Date(s.timestamp);
            const day     = d.toLocaleDateString('ja-JP',{month:'numeric',day:'numeric'});
            const dateKey = d.toISOString().slice(0, 10).replace(/-/g, '');
            if (!byDay[day]) byDay[day] = {scores:[], media:[], hatenas:[], dateKey};
            byDay[day].scores.push(Number(s.score||0));
            byDay[day].media.push(Number(s.articleCount||0));
            byDay[day].hatenas.push(Number(s.hatenaCount||0));
          });
          labels      = Object.keys(byDay);
          scores      = labels.map(d => Math.max(...byDay[d].scores));
          mediaCnts   = labels.map(d => Math.max(...byDay[d].media));
          engagements = labels.map(d => {
            const maxHatena  = Math.max(0, ...byDay[d].hatenas);
            const dailyViews = viewsByDate[byDay[d].dateKey] || 0;
            return maxHatena + dailyViews + commentCnt * 3 + favoriteCnt * 5;
          });
        } else {
          labels      = src.map(s => fmtDate(s.timestamp));
          scores      = src.map(s => Number(s.score||0));
          mediaCnts   = src.map(s => Number(s.articleCount||0));
          engagements = src.map(s => Number(s.hatenaCount||0) + totalViews + commentCnt * 3 + favoriteCnt * 5);
        }

        // SNAPのarticleCountはスナップショット値。topics.jsonの値（meta.articleCount）が正。
        // グラフ最終点を現在の記事数で補正して不一致を解消する。
        if (mediaCnts.length && meta.articleCount) {
          mediaCnts[mediaCnts.length - 1] = meta.articleCount;
        }

        const hasEngagement = engagements.some(v => v > 0);

        const viewsSorted = [...(views||[])].sort((a,b) => a.date.localeCompare(b.date));
        const vLabels   = viewsSorted.map(v => `${parseInt(v.date.slice(4,6))}/${parseInt(v.date.slice(6,8))}`);
        const vAbsolute = viewsSorted.map(v => v.count);
        const vDelta    = viewsSorted.map((v, i) => i === 0 ? 0 : v.count - viewsSorted[i-1].count);

        const cc = getChartColors();
        const zoomOpts = meta.status === 'archived' ? {} : {
          zoom: { wheel:{enabled:true}, pinch:{enabled:true}, mode:'x' },
          pan:  { enabled:true, mode:'x' },
        };
        const makeScaleY0 = (data) => {
          const vals = data.filter(v => v !== null);
          const max = vals.length ? Math.max(...vals) : 10;
          return { min:0, max: max + Math.max(max * 0.2, 1), ticks:{ precision:0, maxTicksLimit:5, color: cc.tick }, grid:{ color: cc.grid } };
        };
        const makeScaleY0Right = (data) => {
          const vals = data.filter(v => v !== null);
          const max = vals.length ? Math.max(...vals) : 10;
          return {
            min: 0, max: max + Math.max(max * 0.2, 1),
            position: 'right',
            grid: { drawOnChartArea: false },
            title: { display: true, text: '関心度', color: cc.tick, font: { size: 10 } },
            ticks: { precision: 0, maxTicksLimit: 5, color: cc.tick },
          };
        };
        const makeScaleDelta = (data) => {
          const vals = data.filter(v => v !== null);
          const max = vals.length ? Math.max(...vals) : 1;
          const min = vals.length ? Math.min(...vals) : 0;
          const pad = Math.max(Math.abs(max - min) * 0.2, 1);
          return {
            min: min < 0 ? min - pad : 0, max: max + pad,
            ticks: { precision:0, maxTicksLimit:5, color: cc.tick },
            grid: { color: ctx => ctx.tick.value === 0 ? cc.gridZero : cc.grid, lineWidth: ctx => ctx.tick.value === 0 ? 2 : 1 },
          };
        };

        // 記事数の推移（折れ線グラフ）+ 右軸: 関心度（エンゲージメントスコア）
        const artLabel = aggregate ? '記事数（日次）' : '記事数（30分ごと）';

        // Google Trends オーバーレイ（日次集計モードのみ・データあり時）— 1811e4b の 16b688e 統合
        let trendsValues = null;
        if (aggregate && meta.trendsData && typeof meta.trendsData === 'object') {
          const trendsByLabel = {};
          for (const [dateStr, val] of Object.entries(meta.trendsData)) {
            const d = new Date(dateStr + 'T00:00:00Z');
            const lbl = d.toLocaleDateString('ja-JP', { month: 'numeric', day: 'numeric' });
            trendsByLabel[lbl] = val;
          }
          const mapped = labels.map(l => (trendsByLabel[l] !== undefined ? trendsByLabel[l] : null));
          if (mapped.some(v => v !== null)) trendsValues = mapped;
        }

        if (chartInstance) chartInstance.destroy();
        const engagementDataset = hasEngagement ? {
          label: '関心度',
          data: engagements,
          yAxisID: 'y2',
          borderColor: '#f59e0b',
          backgroundColor: (ctx) => {
            const {ctx: c, chartArea} = ctx.chart;
            if (!chartArea) return 'rgba(245,158,11,0.06)';
            const g = c.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
            g.addColorStop(0, 'rgba(245,158,11,0.18)'); g.addColorStop(1, 'rgba(245,158,11,0.01)');
            return g;
          },
          borderWidth: 2, pointRadius: 2, pointHoverRadius: 5, tension: 0.4, fill: true,
        } : null;
        const trendsDataset = trendsValues ? {
          label: '検索関心度',
          data: trendsValues,
          yAxisID: 'yTrends',
          borderColor: '#f87171',
          backgroundColor: 'rgba(248,113,113,0)',
          borderWidth: 2,
          borderDash: [5, 4],
          pointRadius: 2,
          pointHoverRadius: 5,
          tension: 0.4,
          fill: false,
          spanGaps: true,
        } : null;
        const _datasets = [
          { label: artLabel, data: mediaCnts,
            yAxisID: 'y',
            borderColor: '#4EC9C0',
            backgroundColor: (ctx) => {
              const {ctx: c, chartArea} = ctx.chart;
              if (!chartArea) return 'rgba(78,201,192,.15)';
              const g = c.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
              g.addColorStop(0, 'rgba(78,201,192,.35)'); g.addColorStop(1, 'rgba(78,201,192,.02)');
              return g;
            },
            borderWidth: 2, pointRadius: 3, pointHoverRadius: 6, tension: 0.4, fill: true },
          ...(engagementDataset ? [engagementDataset] : []),
          ...(trendsDataset ? [trendsDataset] : []),
        ];
        chartInstance = new Chart(canvas.getContext('2d'), {
          type: 'line',
          data: { labels, datasets: _datasets },
          options: {
            responsive: true, maintainAspectRatio: false,
            interaction: { mode:'index', intersect:false },
            plugins: { legend: { display:true, position:'bottom', labels:{boxWidth:12, font:{size:11}, color: cc.tick} }, zoom: zoomOpts },
            scales: {
              y: { ...makeScaleY0(mediaCnts), position: 'left' },
              ...(hasEngagement ? { y2: makeScaleY0Right(engagements) } : {}),
              ...(trendsValues ? { yTrends: {
                position: 'right', min: 0, max: 100,
                ticks: { precision: 0, maxTicksLimit: 5, color: cc.tick },
                grid: { drawOnChartArea: false },
              } } : {}),
            },
          },
        });

        if (vCanvas) {
          // スコアの推移（トピックの「熱量」が上がって落ち着く様子を可視化）
          const scoreLabel = aggregate ? '注目スコア（日次最大）' : '注目スコア';
          if (viewsChartInstance) viewsChartInstance.destroy();
          viewsChartInstance = new Chart(vCanvas.getContext('2d'), {
            type: 'line',
            data: { labels, datasets: [{ label: scoreLabel, data: scores,
              borderColor:'#3BB5AC',
              backgroundColor: (ctx) => {
                const {ctx:c, chartArea} = ctx.chart;
                if (!chartArea) return 'rgba(59,181,172,.15)';
                const g = c.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
                g.addColorStop(0, 'rgba(59,181,172,.4)'); g.addColorStop(1, 'rgba(59,181,172,.02)');
                return g;
              },
              borderWidth:2, pointRadius:3, pointHoverRadius:6, tension:0.4, fill:true }]},
            options: {
              responsive: true, maintainAspectRatio: false,
              interaction: { mode:'index', intersect:false },
              plugins: { legend: { display:true, position:'bottom', labels:{boxWidth:12, font:{size:11}, color: cc.tick} }, zoom: zoomOpts },
              scales: { y: makeScaleY0(scores) },
            },
          });
        }
      };

      const _initCharts = () => {
        if (typeof Chart === 'undefined') {
          // Chart.js未ロード: window.loadで再試行（CDN遅延対策）
          window.addEventListener('load', () => { try { _initCharts(); } catch {} }, { once: true });
          return;
        }
        try {
          buildCharts(24);
          new MutationObserver(() => { try { buildCharts(_chartRange); } catch {} }).observe(
            document.documentElement, { attributes: true, attributeFilter: ['data-theme'] }
          );
          // Grayout buttons for ranges that exceed available data
          const _firstSeenMs = meta.firstArticleAt
            ? meta.firstArticleAt * 1000
            : (timeline.length > 0 ? Math.min(...timeline.map(s => new Date(s.timestamp).getTime())) : Date.now());
          const _elapsedH = (Date.now() - _firstSeenMs) / 3600000;
          const _RANGE_H = { '1d': 24, '3d': 72, '7d': 168, '1m': 720, '3m': 2160, '6m': 4320, '1y': 8760 };
          document.querySelectorAll('.tr-btn[data-range]').forEach(btn => {
            const rh = _RANGE_H[btn.dataset.range];
            if (rh && rh > _elapsedH) {
              btn.disabled = true;
              btn.title = 'データ蓄積中';
            }
          });
          document.querySelectorAll('.tr-btn').forEach(btn => {
            btn.addEventListener('click', () => {
              document.querySelectorAll('.tr-btn').forEach(b => b.classList.remove('active'));
              btn.classList.add('active');
              const r = btn.dataset.range;
              try { buildCharts(r==='1d'?24 : r==='3d'?72 : r==='7d'?168 : r==='1m'?720 : r==='3m'?2160 : r==='6m'?4320 : r==='1y'?8760 : null); } catch {}
            });
          });
        } catch(e) {
          if (chartCard) chartCard.style.display = 'none';
        }
      };
      _initCharts();
    }
  }

  const storymapContainer = document.getElementById('storymap-link-container');
  if (storymapContainer) {
    if (meta.childTopics && meta.childTopics.length > 0) {
      storymapContainer.innerHTML = `<a href="storymap.html?id=${esc(meta.topicId)}" class="storymap-btn">🗺 このストーリーの分岐を見る (${meta.childTopics.length}件)</a>`;
    } else if (meta.storyPhase || (Array.isArray(meta.storyTimeline) && meta.storyTimeline.length > 0)) {
      storymapContainer.innerHTML = `<a href="storymap.html?id=${esc(meta.topicId)}" class="storymap-banner">📖 このストーリーを始まりから追う →</a>`;
    }
  }

  const storyEl = document.getElementById('story-timeline');
  try {
  if (!timeline.length) {
    const storyCard = storyEl && storyEl.closest('.card');
    if (storyCard) storyCard.style.display = 'none';
  }
  if (storyEl && timeline.length) {
    const seenUrls = new Set();
    const seenSourceTitle = new Set();
    const allArticles = [];
    [...timeline].reverse().forEach(snap => {
      (snap.articles || []).forEach(a => {
        const stKey = `${a.source}::${a.title}`;
        if (!seenUrls.has(a.url) && !seenSourceTitle.has(stKey)) {
          seenUrls.add(a.url);
          seenSourceTitle.add(stKey);
          allArticles.push({ ...a, _snapTs: snap.timestamp });
        }
      });
    });
    allArticles.sort((a, b) => new Date(b._snapTs) - new Date(a._snapTs));

    // 全スナップのarticlesが空の場合（旧形式SNAPまたはSNAP期限切れ）はタイムラインカードを非表示
    if (!allArticles.length) {
      const storyCard = storyEl && storyEl.closest('.card');
      if (storyCard) storyCard.style.display = 'none';
      // related-articlesは後続ロジック(candidates=[])で自動的に非表示になる
    }

    const totalCount = allArticles.length;
    let timelineOrder = 'desc';
    const fmtTl = (ts) => {
      const d = new Date(ts);
      return `${d.getMonth()+1}月${d.getDate()}日 ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`;
    };
    const ARTICLES_PER_DAY = 5;
    const DAYS_INITIAL     = 14;
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
                      const wayback = `https://web.archive.org/web/*/${encodeURIComponent(a.url || '')}`;
                      return `<div class="timeline-article">
                        <a href="${esc(a.url)}" class="timeline-article-link" target="_blank" rel="noopener noreferrer">${esc(a.title)}${isNew ? '<span class="new-badge">NEW</span>' : ''}</a>
                        <div class="timeline-source">${srcFaviconImg(a.source)}${esc(a.source)}<a href="${esc(wayback)}" class="article-archive-link" target="_blank" rel="noopener noreferrer" title="リンク切れ時は Internet Archive で記事を遡れます">📦 アーカイブ</a></div>
                      </div>`;
                    }).join('')}
                    ${rest.length ? `<details class="day-more-details"><summary class="day-more-btn">他${rest.length}件を表示</summary>${rest.map(a => {
                      const wayback = `https://web.archive.org/web/*/${encodeURIComponent(a.url || '')}`;
                      return `<div class="timeline-article">
                        <a href="${esc(a.url)}" class="timeline-article-link" target="_blank" rel="noopener noreferrer">${esc(a.title)}</a>
                        <div class="timeline-source">${srcFaviconImg(a.source)}${esc(a.source)}<a href="${esc(wayback)}" class="article-archive-link" target="_blank" rel="noopener noreferrer" title="リンク切れ時は Internet Archive で記事を遡れます">📦</a></div>
                      </div>`;
                    }).join('')}</details>` : ''}
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
  } catch(e) { console.error('storyEl/related rendering error:', e); }

  renderDiscovery(meta);
}

// ===== Discovery: 深掘り & 拡張 =====
let _allTopicsCache = null;
async function fetchAllTopicsOnce() {
  if (_allTopicsCache) return _allTopicsCache;
  try {
    const r = await fetch(apiUrl('topics'));
    if (!r.ok) return [];
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
      if (items.length >= 6) break;
      if (usedIds.has(rt.topicId)) continue;
      const t = tMap[rt.topicId];
      if (!t) continue;
      const tags = (rt.sharedEntities || []).slice(0, 2).map(e => `<span class="entity-tag">#${esc(e)}</span>`).join('');
      items.push({ t, badge: null, extraHtml: tags });
      usedIds.add(rt.topicId);
    }

    // 3. 子トピック（この話題から派生した流れ）
    for (const ref of (meta.childTopics || [])) {
      if (items.length >= 6) break;
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
            const safeThumb = t.imageUrl ? esc(typeof safeImgUrl === 'function' ? safeImgUrl(t.imageUrl) : t.imageUrl.replace(/['"<>]/g, '')) : '';
            const thumbHtml = safeThumb
              ? `<img class="disc-card-thumb" src="${safeThumb}" alt="" loading="lazy" referrerpolicy="origin-when-cross-origin" onerror="this.style.display='none'">`
              : '';
            return `
              <a href="topic.html?id=${esc(t.topicId)}" class="disc-card">
                ${thumbHtml}
                <div class="disc-card-body">
                  ${badgeHtml}
                  <div class="disc-card-title">${esc(title)}</div>
                  <div class="disc-card-footer">
                    <span class="disc-card-meta">${dot} ${cnt}件${ago ? ` · ${esc(ago)}` : ''}</span>
                    ${extraHtml || ''}
                  </div>
                </div>
              </a>`;
          }).join('')}
        </div>
        ${smLink}
      </div>`;
  });
}

// ── スティッキーCTAバー（モバイル） ──────────────────────────────────────
(function initStickyCta() {
  const bar        = document.getElementById('sticky-cta-bar');
  const favBtn     = document.getElementById('scb-fav-btn');
  const commentBtn = document.getElementById('scb-comment-btn');
  const commSec    = document.getElementById('comments-section');
  if (!bar || !commSec) return;

  // コメントセクションが見えたら非表示
  const observer = new IntersectionObserver(
    entries => { bar.classList.toggle('visible', !entries[0].isIntersecting); },
    { threshold: 0.1 }
  );
  observer.observe(commSec);

  // お気に入りボタン：topic-fav-btn と連動
  function syncFav() {
    const srcBtn = document.getElementById('topic-fav-btn');
    if (favBtn && srcBtn) {
      favBtn.classList.toggle('fav-active', srcBtn.classList.contains('fav-active'));
      favBtn.textContent = srcBtn.textContent;
    }
  }
  new MutationObserver(syncFav).observe(document.getElementById('topic-fav-btn') || document.body, { attributes: true, childList: true, subtree: true });
  if (favBtn) favBtn.addEventListener('click', () => document.getElementById('topic-fav-btn')?.click());

  // コメントボタン
  if (commentBtn) {
    commentBtn.addEventListener('click', () => {
      commSec.scrollIntoView({ behavior: 'smooth', block: 'start' });
      setTimeout(() => {
        const textarea = document.getElementById('comment-body');
        if (textarea && getComputedStyle(textarea.closest('#comment-form-area') || document.body).display !== 'none') {
          textarea.focus();
        } else {
          document.getElementById('auth-signin-btn')?.click();
        }
      }, 400);
    });
  }
})();
