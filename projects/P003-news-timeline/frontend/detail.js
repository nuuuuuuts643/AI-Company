// ===== 詳細ページ =====
// app.js が先にロードされていること前提（esc, fmtDate, apiUrl, genreEmoji 等を参照）
// js/timestamp.js が先にロードされていること前提（toMs / _warnBadTs を window から参照）。
//   timestamp.js が無い環境（古い HTML キャッシュ等）でも detail.js が落ちないよう
//   minimal フォールバックを置く。
let chartInstance = null, viewsChartInstance = null;
const _toMs = (typeof toMs === 'function') ? toMs : function (v) {
  if (v == null || v === '') return 0;
  if (v instanceof Date) { const t = v.getTime(); return isNaN(t) ? 0 : t; }
  if (typeof v === 'number') {
    if (!isFinite(v) || v <= 0) return 0;
    if (v > 1e9 && v < 1e12) return v * 1000;
    if (v >= 1e12) return v;
    return 0;
  }
  const s = String(v).trim();
  if (!s) return 0;
  if (/^-?\d+(\.\d+)?$/.test(s)) {
    const n = Number(s);
    if (n > 1e9 && n < 1e12) return n * 1000;
    if (n >= 1e12) return n;
    return 0;
  }
  const t = new Date(s).getTime();
  return isNaN(t) ? 0 : t;
};
const _warnBadTsLocal = (typeof _warnBadTs === 'function') ? _warnBadTs : function () { return false; };

function getNextUpdateTime() {
  // 実機 EventBridge cron: cron(30 20,8 * * ? *) UTC = JST 05:30 / 17:30 (2x/day 朝刊・夕刊)
  // 「N時間後」「N分後」の相対表示も付与してユーザーが待ち時間を直感的に分かるように(2026-04-27)
  const now = new Date();
  const jstNow = new Date(now.getTime() + (9 * 60 + now.getTimezoneOffset()) * 60000);
  const hours = [{ h: 5, m: 30 }, { h: 17, m: 30 }];
  const currentMin = jstNow.getHours() * 60 + jstNow.getMinutes();
  const fmt = (h, m) => `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
  const next = hours.find(({ h, m }) => h * 60 + m > currentMin);
  let absStr;
  let waitMin;
  if (next) {
    waitMin = next.h * 60 + next.m - currentMin;
    absStr = `${fmt(next.h, next.m)} JST`;
  } else {
    waitMin = (24 + hours[0].h) * 60 + hours[0].m - currentMin;
    absStr = `翌 ${fmt(hours[0].h, hours[0].m)} JST`;
  }
  const relStr = waitMin < 60
    ? `${waitMin}分後`
    : `約${Math.round(waitMin / 60)}時間後`;
  return `${absStr} (${relStr})`;
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
  const PHASE_LABEL_OGP = {'発端':'始まり','拡散':'広まってる','ピーク':'急上昇','現在地':'今ここ','収束':'ひと段落'};
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
        const ms = _toMs(ts);
        _warnBadTsLocal('jsonld.iso', ts, ms);
        if (!ms) return new Date().toISOString();
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
  // T2026-0428-AM: 単一 SNAP しかないトピックでも記事 publishedAt から
  // 疑似 timeline を生成してグラフを描けるようにする。
  // fetcher は new_urls に1件も該当しない group は SNAP を追加しない
  // (lambda/fetcher/handler.py:328) ため、初回クラスタリング以後 RSS から
  // 記事が消えたトピックは timeline.length=1 で固定され、いつまでもグラフが
  // 出なかった (例: 87cf1e16705c39e0、~12% のトピックが該当)。
  if (Array.isArray(data.timeline) && data.timeline.length === 1) {
    const tl0 = data.timeline[0];
    const arts = (tl0.articles || [])
      .filter(a => Number(a.publishedAt) > 0)
      .map(a => ({...a, _ts: Number(a.publishedAt) * 1000}))
      .sort((a, b) => a._ts - b._ts);
    if (arts.length >= 2 && arts[arts.length - 1]._ts > arts[0]._ts) {
      const finalScore = Number(tl0.score || 0);
      const finalHb    = Number(tl0.hatenaCount || 0);
      data.timeline = arts.map((a, i) => {
        const slice = arts.slice(0, i + 1);
        const isLast = i === arts.length - 1;
        return {
          timestamp: new Date(a._ts).toISOString(),
          articleCount: i + 1,
          score: isLast ? finalScore : Math.round(finalScore * (i + 1) / arts.length),
          hatenaCount: isLast ? finalHb : 0,
          mediaCount: new Set(slice.map(x => x.source)).size,
          articles: slice.map(({_ts, ...rest}) => rest),
        };
      });
    }
  }
  const {meta, timeline, views} = data;
  if (!meta) return;

  // T2026-0428-AI: meta.articleCount は fetcher 側で URL 重複未 dedup な水増し値の場合がある。
  // 表示記事数（timeline / story-timeline で実際にユーザーが見る件数）と一致させるため
  // SNAP[*].articles を URL + source::title で dedup したカウントを真とする。
  // 旧データ（articleCount=20 だが実 unique URL は 7）でも整合表示できるようにする。
  const computeUniqueArticleCount = () => {
    if (!Array.isArray(timeline) || !timeline.length) return 0;
    const seenUrls = new Set();
    const seenST   = new Set();
    let n = 0;
    for (const snap of [...timeline].reverse()) {
      for (const a of (snap.articles || [])) {
        const st = `${a.source}::${a.title}`;
        if (a.url && !seenUrls.has(a.url) && !seenST.has(st)) {
          seenUrls.add(a.url); seenST.add(st); n++;
        }
      }
    }
    return n;
  };
  const uniqueArtCount = computeUniqueArticleCount();
  // SNAP.articles は URL+source::title で dedup された「実際にユーザーが見る記事数」。
  // ここを表示の真とすることで、グラフ・フッター・タイムラインヘッダーが全て一致する。
  // articles 配列が空の旧 SNAP のみの場合は uniqueArtCount=0 → 既存値にフォールバック。
  const displayArticleCount = uniqueArtCount > 0 ? uniqueArtCount : Number(meta.articleCount || 0);

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
  // T236 (2026-04-28): proc_ai.py が outlook/forecast 末尾に [確信度:高/中/低] を付ける仕様。
  // 文字列のまま表示すると視認性低い → バッジ装飾して「予測の不確実性が一瞬で読み取れる」UX に。
  // 旧データ (確信度ラベル無し) は match しないので素通し (副作用ゼロ)。
  function decorateConfidence(text) {
    if (!text) return '';
    const m = text.match(/^([\s\S]*?)\s*[\[［]\s*確信度[:：]\s*(高|中|低)\s*[\]］]\s*$/);
    if (!m) return esc(text);
    const [, body, level] = m;
    const levelClass = level === '高' ? 'cf-high' : level === '中' ? 'cf-mid' : 'cf-low';
    const dot = level === '高' ? '🟢' : level === '中' ? '🟡' : '⚪';
    return `${esc(body.trim())} <span class="confidence-badge ${levelClass}" title="記事内に明示根拠あり=高 / 複数の状況証拠=中 / 推測ベース=低">${dot} 確信度: ${esc(level)}</span>`;
  }
  const aiAnalysisEl = document.getElementById('ai-analysis');
  if (aiAnalysisEl) {
    const summary           = cleanSummary(meta.generatedSummary);
    const keyPoint          = cleanSummary(meta.keyPoint || '');
    const forecast          = cleanSummary(meta.forecast     || '');
    const perspectives      = cleanSummary(meta.perspectives || '');
    const outlook           = cleanSummary(meta.outlook      || '');
    // T2026-0428-J/E: 新フィールド (statusLabel / watchPoints / predictionResult)
    const watchPoints       = cleanSummary(meta.watchPoints  || '');
    const statusLabelRaw    = (meta.statusLabel || '').trim();
    const predictionResult  = (meta.predictionResult || '').trim();
    const predictionMadeAt  = meta.predictionMadeAt || '';
    const beats        = Array.isArray(meta.storyTimeline) ? meta.storyTimeline : [];
    const phase        = meta.storyPhase   || '';
    const summaryMode  = meta.summaryMode  || (beats.length > 0 || forecast || watchPoints ? 'full' : 'minimal');
    const hasSummary   = !!summary && !!meta.aiGenerated;
    const isFullAI     = summary && meta.aiGenerated;
    // T2026-0428-J/E: statusLabel が AI から来てない旧 topic 用に storyPhase からの fallback マッピング。
    // 発端→発端 / 拡散・ピーク→進行中 / 現在地→進行中 / 収束→決着 (沈静化はAI判定でのみ得られる)。
    const STATUS_FALLBACK = { '発端':'発端','拡散':'進行中','ピーク':'進行中','現在地':'進行中','収束':'決着' };
    const statusLabel = statusLabelRaw || STATUS_FALLBACK[phase] || '';
    // T2026-0428-AU: 表示ラベル(label)と AI 内部値(キー)を分離。
    // 「進行中」だけだと"何が進行中か"が伝わらないため、読者向けに具体的な動詞句に置換。
    const STATUS_BADGE = {
      '発端':   { icon:'🌱', cls:'sl-onset',     label:'起き始め',     hint:'注目され始めた直後' },
      '進行中': { icon:'🔥', cls:'sl-active',    label:'報道継続中',   hint:'報道が続き熱量がある' },
      '沈静化': { icon:'📉', cls:'sl-cooling',   label:'落ち着いてきた', hint:'報道頻度が落ちてきた' },
      '決着':   { icon:'✅', cls:'sl-resolved',  label:'ひと段落',     hint:'結論や合意が出て話題が閉じた' },
    };

    const PHASE_COLOR = { '発端':'rgba(78,201,192,0.55)','拡散':'rgba(78,201,192,0.7)','ピーク':'#4EC9C0','現在地':'#3BB5AC','収束':'#64748b' };
    const PHASE_ICON  = { '発端':'🌱','拡散':'📡','ピーク':'🔥','現在地':'📍','収束':'✅' };
    const PHASE_TEXT  = { '発端':'始まり','拡散':'広まってる','ピーク':'急上昇','現在地':'今ここ','収束':'ひと段落' };
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
      const _artCnt = displayArticleCount;
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

      // ─── T2026-0428-J/E: 2 ゾーン設計に再編成 ────────────────────────────
      // 注目度ゾーン: グラフ・記事数スパイクは別 DOM (#score-chart) に既存。
      //   ここでは statusLabel バッジのみを「現在の状況」として可視化する。
      // コンテンツゾーン: keyPoint (時系列ストーリー) → perspectives (各メディアの見解)
      //   → watchPoints (注目ポイント) → outlook (AI予想 + 判定バッジ)。
      // 「両軸が同一ページで満たされる」設計目標を満たすため、ゾーン間に区切り線を入れる。

      // ─── 注目度ゾーン: statusLabel バッジ ───
      // T2026-0428-AU: バッジ表示は b.label (読者向け) を使い、AI 内部値 (statusLabel) は使わない。
      const statusBadgeHtml = (statusLabel && STATUS_BADGE[statusLabel]) ? (() => {
        const b = STATUS_BADGE[statusLabel];
        const display = b.label || statusLabel;
        return `<div class="ai-status-zone">
          <span class="ai-status-badge ${b.cls}" title="${esc(b.hint)}">${b.icon} ${esc(display)}</span>
          <span class="ai-status-hint">${esc(b.hint)}</span>
        </div>`;
      })() : '';

      // ─── コンテンツゾーン: 状況解説 (keyPoint, 200-300 字の時系列ストーリー) ───
      // 旧「💡 ひとことで言うと」hero box は廃止。状況解説をメイン本文として扱う。
      const sectKeyPoint = keyPoint ? `
        <div class="ai-section ai-section-story">
          <div class="ai-section-label">📰 状況解説</div>
          <p class="ai-section-body ai-section-story-body">${esc(keyPoint)}</p>
        </div>` : (summary ? `
        <div class="ai-section">
          <div class="ai-section-label">📍 現状（要約）</div>
          <p class="ai-section-body">${esc(summary)}</p>
        </div>` : '');

      // ─── コンテンツゾーン: 各メディアの見解 ───
      const sectPersp = perspectives ? `
        <div class="ai-section">
          <div class="ai-section-label">🗞️ 各メディアの見解</div>
          <p class="ai-section-body">${esc(perspectives)}</p>
        </div>` : '';

      // ─── コンテンツゾーン: これからの注目ポイント ───
      // outlook (AI予想) とは役割が異なる「観察視点」のガイド。
      const sectWatch = watchPoints ? `
        <div class="ai-section">
          <div class="ai-section-label">👁️ これからの注目ポイント</div>
          <p class="ai-section-body">${esc(watchPoints)}</p>
        </div>` : '';

      // ─── コンテンツゾーン: AI予想 + 判定バッジ ───
      // T2026-0428-PRED で predictionResult を後付けで判定する想定。今は pending のみ表示。
      const PREDICTION_BADGE = {
        matched: { cls:'pr-matched', icon:'🎯', text:'当たった' },
        partial: { cls:'pr-partial', icon:'🟡', text:'一部当たり' },
        missed:  { cls:'pr-missed',  icon:'❌', text:'外れた' },
        pending: { cls:'pr-pending', icon:'⏳', text:'判定待ち' },
      };
      const predBadge = predictionResult && PREDICTION_BADGE[predictionResult]
        ? `<span class="ai-prediction-badge ${PREDICTION_BADGE[predictionResult].cls}">${PREDICTION_BADGE[predictionResult].icon} ${PREDICTION_BADGE[predictionResult].text}</span>`
        : '';
      const _predMs = _toMs(predictionMadeAt);
      _warnBadTsLocal('predictionMadeAt', predictionMadeAt, _predMs);
      const predTimeHint = (predictionMadeAt && _predMs > 0) ? `<span class="ai-prediction-time">${esc(new Date(_predMs).toLocaleString('ja-JP', {year:'numeric',month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit'}))} 時点</span>` : '';
      // forecast (full mode 2文) があればそれを優先、無ければ outlook (1文)
      const predictionText = forecast || outlook;
      const sectOl = predictionText ? `
        <div class="ai-section ai-section-forecast">
          <div class="ai-section-label">🔮 AI予想 <span class="ai-hypothesis-badge">仮説</span> ${predBadge} ${predTimeHint}</div>
          <p class="ai-section-body">${decorateConfidence(predictionText)}</p>
        </div>` : '';

      // ─── 経緯セクション (storyTimeline beats) ───
      // 注目度の細粒度フェーズ表示は phase バー + beats で残す。
      // (storyPhase は AI 内部判定の 5 値、statusLabel は読者向け 4 値で別軸)
      const beatsHtml = beats.length ? buildBeatsHtml(beats) : '';
      const sectTimeline = (phaseBarHtml || beatsHtml) ? `
        <div class="ai-section ai-section-timeline">
          <div class="ai-section-label">⏱ 経緯</div>
          ${phaseBarHtml}
          ${originHtml}
          ${beatsHtml ? `<div class="ai-beats">${beatsHtml}</div>` : ''}
        </div>` : '';

      // ─── 最終レイアウト ───
      // [注目度ゾーン: statusLabel] (グラフは別 DOM)
      //   ─── divider ───
      // [コンテンツゾーン: keyPoint → perspectives → watchPoints → outlook]
      //   ─── divider ───
      // [経緯 (timeline)]
      // [trust footer]
      const dividerHtml = '<hr class="ai-zone-divider" aria-hidden="true">';
      if (summaryMode === 'minimal') {
        // minimal は perspectives/watchPoints が無いため簡略
        aiAnalysisEl.innerHTML = `<div class="ai-analysis-inner ai-analysis-minimal">
          ${statusBadgeHtml}
          ${statusBadgeHtml ? dividerHtml : ''}
          ${sectKeyPoint}
          ${sectOl}
          ${trustFooterHtml}
        </div>`;
      } else {
        aiAnalysisEl.innerHTML = `<div class="ai-analysis-inner">
          ${statusBadgeHtml}
          ${statusBadgeHtml ? dividerHtml : ''}
          ${sectKeyPoint}
          ${sectPersp}
          ${sectWatch}
          ${sectOl}
          ${sectTimeline ? dividerHtml : ''}
          ${sectTimeline}
          ${trustFooterHtml}
          ${storyNavHtml}
        </div>`;
      }

      aiAnalysisEl.style.display = 'block';
    } else {
      // T2026-0428-AJ: AI 未処理 / 初回トピックでも「要約セクションの形」を必ず見せる。
      // 要約エリア自体を消さず、要点プレースホルダー＋次回更新時刻＋追跡中ソース。
      const cnt = displayArticleCount || (Number(meta.articleCount) || 1);
      const sources = (meta.sources || []).slice(0, 3).join('・');
      const titleFallback = esc(meta.topicTitle || meta.generatedTitle || meta.title || '');
      aiAnalysisEl.innerHTML = `
        <div class="ai-analysis-inner ai-pending">
          <div class="ai-section ai-section-keypoint">
            <div class="ai-section-label">📌 要点</div>
            <div class="ai-section-body" style="color:var(--text-muted);font-style:italic;line-height:1.7;">
              ${titleFallback ? `「${titleFallback}」について` : ''}AIが要点を分析中です。
              <br>初回スナップショット完了後、次の更新（${getNextUpdateTime()}）で要約が生成されます。
            </div>
          </div>
          <hr class="ai-zone-divider" aria-hidden="true">
          <div class="ai-section">
            <div class="ai-section-label">📊 追跡状況</div>
            <div class="ai-section-body" style="font-size:.85rem;color:var(--text-muted);">
              <span class="ai-pending-icon">⏳</span> ${cnt}件の記事を追跡中${sources ? `（${sources} ほか）` : ''}。
            </div>
          </div>
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
    // T2026-0428-AJ: グラフは「必ず表示」する。データが 0 件の場合のみ
    // プレースホルダー、それ以外（1 点でも）は描画して点を出す。
    if (timeline.length === 0) {
      if (chartCard) {
        chartCard.querySelectorAll('canvas').forEach(c => c.style.display = 'none');
        const header = chartCard.querySelector('.chart-header');
        if (header) header.style.display = 'none';
        if (noData) noData.style.display = 'none';
        if (!chartCard.querySelector('.chart-placeholder')) {
          const ph = document.createElement('div');
          ph.className = 'chart-placeholder';
          ph.style.cssText = 'padding:24px 16px;text-align:center;color:var(--text-muted);font-size:.85rem;line-height:1.7;';
          ph.innerHTML = `<div style="font-size:1rem;margin-bottom:6px;">推移グラフ</div><div>📊 データ蓄積中（初回）</div><div style="margin-top:6px;">最初のスナップショットが取られるとグラフが描画されます（約30分後〜）。</div>`;
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
        const filtered = rangeHours ? timeline.filter(s => {
          const ms = _toMs(s.timestamp);
          _warnBadTsLocal('snap.timestamp(filter)', s.timestamp, ms);
          return ms >= cutoff;
        }) : timeline;
        // T2026-0428-AJ: 1 点でも描画する。range フィルタで 0 件になったら全期間にフォールバック。
        const src = filtered.length >= 1 ? filtered : timeline;

        const aggregate = rangeHours === null || rangeHours >= 72;

        // エンゲージメントスコア計算用: はてブ数(SNAP単位) + 累計閲覧数 + コメント×3 + お気に入り×5
        const viewsByDate = {};
        (views || []).forEach(v => { viewsByDate[v.date] = Number(v.count || 0); });
        const totalViews  = Object.values(viewsByDate).reduce((s, c) => s + c, 0);
        const commentCnt  = Number(meta.commentCount  || 0);
        const favoriteCnt = Number(meta.favoriteCount || 0);

        // T2026-0428-AI: SNAP.articleCount は fetcher の cnt = len(g) で URL 重複未 dedup な
        // 水増し値。一方 SNAP.articles は URL で dedup された実体。フロント表示「全 X 件」と
        // 整合させるため、articles.length が取れる SNAP では articles.length を使う。
        // (旧バグ: cnt=20 だが unique URL は 7 で「グラフ 20 件 vs 表示 7 件」乖離)
        const snapArtCount = (s) => {
          const arts = s.articles;
          if (Array.isArray(arts) && arts.length) return arts.length;
          return Number(s.articleCount || 0);
        };

        // T2026-0428-GRAPH: スパイク（前ポイント比 +3以上 or +50%以上）を検出して
        // 各ポイントの「きっかけ記事」タイトル候補を保持する（aggregate/non-aggregate 両対応）
        const firstArticleTitle = (snap) => {
          const arts = snap && snap.articles;
          if (Array.isArray(arts) && arts.length) {
            const t = (arts[0].title || '').toString().trim();
            return t || null;
          }
          return null;
        };

        let labels, scores, mediaCnts, engagements, triggerTitles;
        if (aggregate) {
          const byDay = {};
          src.forEach(s => {
            const _ms = _toMs(s.timestamp);
            _warnBadTsLocal('snap.timestamp(aggregate)', s.timestamp, _ms);
            if (!_ms) return;
            const d = new Date(_ms);
            const day     = `${String(d.getFullYear()).slice(2)}/${d.getMonth()+1}/${d.getDate()}`;
            const dateKey = d.toISOString().slice(0, 10).replace(/-/g, '');
            if (!byDay[day]) byDay[day] = {scores:[], media:[], hatenas:[], dateKey, snaps:[]};
            byDay[day].scores.push(Number(s.score||0));
            byDay[day].media.push(snapArtCount(s));
            byDay[day].hatenas.push(Number(s.hatenaCount||0));
            byDay[day].snaps.push(s);
          });
          labels      = Object.keys(byDay);
          scores      = labels.map(d => Math.max(...byDay[d].scores));
          mediaCnts   = labels.map(d => Math.max(...byDay[d].media));
          engagements = labels.map(d => {
            const maxHatena  = Math.max(0, ...byDay[d].hatenas);
            const dailyViews = viewsByDate[byDay[d].dateKey] || 0;
            return maxHatena + dailyViews + commentCnt * 3 + favoriteCnt * 5;
          });
          // 各日について articleCount が最大の SNAP の articles[0].title を候補に
          triggerTitles = labels.map(d => {
            const snaps = byDay[d].snaps || [];
            let best = null, bestN = -1;
            for (const s of snaps) {
              const n = snapArtCount(s);
              if (n > bestN) { bestN = n; best = s; }
            }
            return firstArticleTitle(best);
          });
        } else {
          labels      = src.map(s => fmtDate(s.timestamp));
          scores      = src.map(s => Number(s.score||0));
          mediaCnts   = src.map(s => snapArtCount(s));
          engagements = src.map(s => Number(s.hatenaCount||0) + totalViews + commentCnt * 3 + favoriteCnt * 5);
          triggerTitles = src.map(s => firstArticleTitle(s));
        }

        // スパイク判定: 前ポイント比 diff >= 3 or 50% 以上の増加
        const spikeFlags = mediaCnts.map((cur, i) => {
          if (i === 0) return false;
          const prev = mediaCnts[i - 1];
          const diff = cur - prev;
          if (diff >= 3) return true;
          if (prev > 0 && diff / prev >= 0.5 && diff >= 1) return true;
          return false;
        });
        // スパイクでないポイントの triggerTitle は表示しない
        const spikeTitles = triggerTitles.map((t, i) => spikeFlags[i] ? t : null);

        const hasEngagement = engagements.some(v => v > 0);

        const viewsSorted = [...(views||[])].sort((a,b) => a.date.localeCompare(b.date));
        const vLabels   = viewsSorted.map(v => `${v.date.slice(2,4)}/${parseInt(v.date.slice(4,6))}/${parseInt(v.date.slice(6,8))}`);
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
            const lbl = `${String(d.getFullYear()).slice(2)}/${d.getMonth()+1}/${d.getDate()}`;
            trendsByLabel[lbl] = val;
          }
          const mapped = labels.map(l => (trendsByLabel[l] !== undefined ? trendsByLabel[l] : null));
          if (mapped.some(v => v !== null)) trendsValues = mapped;
        }

        // T2026-0428-AJ: 「記事数の推移」は単軸（関心度の右Y軸 y2 を廃止）。
        // 関心度は別スコアと混乱させないため Google Trends overlay のみ残す。
        // 1 点しかないとき折れ線が引けないので pointRadius を太く。
        const onePoint = src.length <= 1;
        if (chartInstance) chartInstance.destroy();
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
        // T2026-0428-GRAPH: スパイク点はオレンジで大きく表示
        const SPIKE_COLOR = '#f59e0b';
        const pointBgColors  = spikeFlags.map(f => f ? SPIKE_COLOR : '#4EC9C0');
        const pointRadii     = spikeFlags.map(f => f ? 6 : (onePoint ? 6 : 3));
        const pointHoverRadii= spikeFlags.map(f => f ? 9 : 7);

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
            borderWidth: 2,
            pointBackgroundColor: pointBgColors,
            pointBorderColor: pointBgColors,
            pointRadius: pointRadii,
            pointHoverRadius: pointHoverRadii,
            tension: 0.4, fill: true },
          ...(trendsDataset ? [trendsDataset] : []),
        ];
        chartInstance = new Chart(canvas.getContext('2d'), {
          type: 'line',
          data: { labels, datasets: _datasets },
          options: {
            responsive: true, maintainAspectRatio: false,
            interaction: { mode:'index', intersect:false },
            plugins: {
              legend: { display:true, position:'bottom', labels:{boxWidth:12, font:{size:11}, color: cc.tick} },
              zoom: zoomOpts,
              tooltip: {
                callbacks: {
                  // T2026-0428-GRAPH: スパイクポイントに「📌 きっかけ記事タイトル」を追記
                  afterBody: (items) => {
                    if (!items || !items.length) return '';
                    const idx = items[0].dataIndex;
                    const title = spikeTitles[idx];
                    if (!title) return '';
                    const t = title.length > 40 ? title.slice(0, 40) + '…' : title;
                    return `📌 きっかけ: ${t}`;
                  },
                },
              },
            },
            scales: {
              y: { ...makeScaleY0(mediaCnts), position: 'left' },
              ...(trendsValues ? { yTrends: {
                position: 'right', min: 0, max: 100,
                ticks: { precision: 0, maxTicksLimit: 5, color: cc.tick },
                grid: { drawOnChartArea: false },
              } } : {}),
            },
          },
        });

        if (vCanvas) {
          // T2026-0428-AJ: 注目スコア = velocityScore ベース。1 点しかない場合も
          // 点は出す（pointRadius 大）。データ蓄積中の注記を canvas 親要素に追加。
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
              borderWidth:2, pointRadius: onePoint ? 6 : 3, pointHoverRadius:7, tension:0.4, fill:true }]},
            options: {
              responsive: true, maintainAspectRatio: false,
              interaction: { mode:'index', intersect:false },
              plugins: { legend: { display:true, position:'bottom', labels:{boxWidth:12, font:{size:11}, color: cc.tick} }, zoom: zoomOpts },
              scales: { y: makeScaleY0(scores) },
            },
          });

          // 1 点しかない場合「データ蓄積中」の注記をグラフ下に追加（重複生成しない）
          const vCol = vCanvas.closest('.chart-col');
          if (vCol) {
            const NOTE_CLS = 'chart-data-note';
            vCol.querySelectorAll('.' + NOTE_CLS).forEach(el => el.remove());
            if (onePoint) {
              const note = document.createElement('p');
              note.className = NOTE_CLS;
              note.style.cssText = 'margin:6px 0 0;font-size:.72rem;color:var(--text-muted);text-align:center;';
              note.textContent = '📊 データ蓄積中（30分ごとに更新）';
              vCol.appendChild(note);
            }
          }
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
            ? _toMs(meta.firstArticleAt)
            : (timeline.length > 0 ? Math.min(...timeline.map(s => _toMs(s.timestamp)).filter(t => t > 0)) : Date.now());
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
  // T2026-0428-AJ: timeline=0 でも「記事の流れ」カードは消さない。
  // 取得中プレースホルダーで利用者に状態を見せる。
  if (!timeline.length && storyEl) {
    storyEl.innerHTML = `
      <div class="topic-empty-placeholder" style="padding:18px 12px;text-align:center;color:var(--text-muted);font-size:.85rem;line-height:1.6;">
        📥 記事データを取得中です。<br>
        最新のスナップショットがまだ届いていません（30分ごとに更新）。
      </div>`;
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
    allArticles.sort((a, b) => _toMs(b._snapTs) - _toMs(a._snapTs));

    // 全スナップのarticlesが空の場合（旧形式SNAPまたはSNAP期限切れ）はプレースホルダー表示
    // T2026-0428-AJ: カード自体は消さない（「常にグラフ／要約／流れを見せる」要件）
    if (!allArticles.length) {
      storyEl.innerHTML = `
        <div class="topic-empty-placeholder" style="padding:18px 12px;text-align:center;color:var(--text-muted);font-size:.85rem;line-height:1.6;">
          🗂 記事の中身を再取得中です。<br>
          スナップショットの再構築をお待ちください。
        </div>`;
    }

    const totalCount = allArticles.length;
    let timelineOrder = 'desc';
    const fmtTl = (ts) => {
      const ms = _toMs(ts);
      _warnBadTsLocal('fmtTl', ts, ms);
      if (!ms) return '';
      const d = new Date(ms);
      return `${d.getFullYear()}年${d.getMonth()+1}月${d.getDate()}日 ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`;
    };
    const ARTICLES_PER_DAY = 5;
    const DAYS_INITIAL     = 14;
    const WDAY = ['日','月','火','水','木','金','土'];
    const fmtDay = (ts) => {
      const ms = _toMs(ts);
      _warnBadTsLocal('fmtDay', ts, ms);
      if (!ms) return '';
      const d = new Date(ms);
      return `${d.getFullYear()}年${d.getMonth()+1}月${d.getDate()}日（${WDAY[d.getDay()]}）`;
    };

    const renderTimeline = () => {
      const dayMap = {};
      allArticles.forEach(a => {
        const _pubMs = _toMs(a.publishedAt) || _toMs(a.pubDate);
        _warnBadTsLocal('article.publishedAt', a.publishedAt, _pubMs);
        const _snapMs = _toMs(a._snapTs);
        const ts = _pubMs || _snapMs;
        if (!ts) return;
        const key = fmtDay(ts);
        if (!key) return;
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
                      const _artMs = _toMs(a.publishedAt) || _toMs(a.pubDate);
                      const isNew = _artMs && (Date.now() - _artMs) < 6 * 3600 * 1000;
                      // T2026-0428-AN: 一次情報バッジ（バックエンドの isPrimary フラグを信頼）
                      // 著作権法32条「引用」として利用、出典明示必須（source 名+リンクで遵守）
                      const primaryBadge = a.isPrimary
                        ? '<span class="primary-source-badge" title="この記事は一次情報源（公式機関・主要通信社）からの報道です">🔵 一次情報</span>'
                        : '';
                      return `<div class="timeline-article${a.isPrimary ? ' is-primary' : ''}">
                        ${primaryBadge}<a href="${esc(a.url)}" class="timeline-article-link" target="_blank" rel="noopener noreferrer">${esc(a.title)}${isNew ? '<span class="new-badge">NEW</span>' : ''}</a>
                        <div class="timeline-source">${srcFaviconImg(a.source)}${esc(a.source)}${a.isPrimary ? ' より引用' : ''}</div>
                      </div>`;
                    }).join('')}
                    ${rest.length ? `<details class="day-more-details"><summary class="day-more-btn">他${rest.length}件を表示</summary>${rest.map(a => {
                      const primaryBadge = a.isPrimary
                        ? '<span class="primary-source-badge" title="この記事は一次情報源（公式機関・主要通信社）からの報道です">🔵 一次情報</span>'
                        : '';
                      return `<div class="timeline-article${a.isPrimary ? ' is-primary' : ''}">
                        ${primaryBadge}<a href="${esc(a.url)}" class="timeline-article-link" target="_blank" rel="noopener noreferrer">${esc(a.title)}</a>
                        <div class="timeline-source">${srcFaviconImg(a.source)}${esc(a.source)}${a.isPrimary ? ' より引用' : ''}</div>
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
        const _ms = _toMs(a.publishedAt) || _toMs(a.pubDate);
        const _snapMs = _toMs(a._snapTs);
        const _ts = _ms || _snapMs;
        if (!_ts) return;
        const key = fmtDay(_ts);
        if (!key) return;
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
        // T2026-0428-AJ: 関連記事カードも消さずに状態を見せる
        relatedEl.innerHTML = `
          <div class="topic-empty-placeholder" style="padding:14px 12px;text-align:center;color:var(--text-muted);font-size:.82rem;">
            関連記事は記事の流れに統合表示しています。
          </div>`;
      } else {
        // ソース多様性を優先してピック（最大3件）
        const picked = [];
        const usedSources = new Set();
        // 最新順でソート
        const sorted = [...candidates].sort((a, b) => {
          const ta = _toMs(a.publishedAt) || _toMs(a._snapTs);
          const tb = _toMs(b.publishedAt) || _toMs(b._snapTs);
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
        relatedEl.innerHTML = picked.map(a => {
          // T2026-0428-AN: 一次情報バッジ（バックエンドの isPrimary フラグを信頼）
          const primaryBadge = a.isPrimary
            ? '<span class="primary-source-badge" title="この記事は一次情報源（公式機関・主要通信社）からの報道です">🔵 一次情報</span>'
            : '';
          return `
          <div class="article-item${a.isPrimary ? ' is-primary' : ''}">
            ${primaryBadge}<a href="${esc(a.url)}" target="_blank" rel="noopener noreferrer">${esc(a.title)}</a>
            <div class="article-meta">
              ${srcFaviconImg(a.source)}
              ${esc(a.source)}${a.isPrimary ? ' より引用' : ''} · ${fmtTl(a._snapTs)}
            </div>
          </div>
        `;
        }).join('');
      }
    }

  }

  // T2026-0428-AJ: timeline=0 でも関連記事カードは残し、プレースホルダー表示。
  if (!timeline.length) {
    const relatedFallback = document.getElementById('related-articles');
    if (relatedFallback && !relatedFallback.innerHTML.trim()) {
      relatedFallback.innerHTML = `
        <div class="topic-empty-placeholder" style="padding:14px 12px;text-align:center;color:var(--text-muted);font-size:.82rem;">
          関連記事は記事データ取得後に表示されます。
        </div>`;
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
  // 0 / null / undefined / 空文字 は無効として空を返す。
  // (旧バグ: fmtElapsed(0) が new Date(0*1000)=1970-01-01 から '1/1' を返し、
  //  childTopics ref が allTopics に無い (archived 等) 場合に "0件 · 1/1" として出ていた)
  if (!isoOrTs && isoOrTs !== 0) return '';
  if (isoOrTs === 0 || isoOrTs === '0') return '';
  try {
    const ms = _toMs(isoOrTs);
    if (!ms) return '';
    _warnBadTsLocal('fmtElapsed', isoOrTs, ms);
    const d = new Date(ms);
    if (isNaN(d)) return '';
    // 1970-01-01 近辺の epoch値ガード (1990年以前は誤った値とみなす)
    if (d.getFullYear() < 1990) return '';
    const diff = (Date.now() - ms) / 1000;
    if (diff < 0) return '';   // 未来日付は無効扱い
    if (diff < 3600)   return `${Math.floor(diff / 60)}分前`;
    if (diff < 86400)  return `${Math.floor(diff / 3600)}時間前`;
    if (diff < 604800) return `${Math.floor(diff / 86400)}日前`;
    return `${d.getFullYear()}/${d.getMonth()+1}/${d.getDate()}`;
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

    // 4. AI 関連テーマ (relatedTopicTitles) — タイトル文字列から allTopics を逆引きし、
    //    一致するトピックがあればカードに追加。CLAUDE.md vision-roadmap フェーズ2「関連する動きリンク」。
    //    一致しないタイトルは握りつぶす（ユーザーが進めないリンクは出さない）。
    if (Array.isArray(meta.relatedTopicTitles) && meta.relatedTopicTitles.length > 0) {
      const norm = (s) => String(s || '').trim().toLowerCase().replace(/\s+/g, '');
      const titleIndex = allTopics.map(t => ({
        t,
        keys: [t.topicTitle, t.generatedTitle, t.title].map(norm).filter(Boolean),
      }));
      for (const rawTitle of meta.relatedTopicTitles) {
        if (items.length >= 6) break;
        const wanted = norm(rawTitle);
        if (!wanted) continue;
        // 厳密一致 → 部分一致 (双方向 includes) の順でヒット判定
        let hit = titleIndex.find(({ keys }) => keys.some(k => k === wanted));
        if (!hit) {
          hit = titleIndex.find(({ keys }) => keys.some(k => k && (k.includes(wanted) || wanted.includes(k))));
        }
        if (!hit) continue;
        if (usedIds.has(hit.t.topicId)) continue;
        items.push({ t: hit.t, badge: { label: '📡 関連する動き', cls: 'related' } });
        usedIds.add(hit.t.topicId);
      }
    }

    // 5. T2026-0501-D: ジャンル + タイトル char-bigram 類似度フォールバック
    //    フェーズ3「情報の地図」リンク密度強化。allTopics は既にキャッシュ済なので追加 fetch なし。
    //    server 側で relatedTopics が空 (~88%) のトピックでも、最低 3 件は地図上の隣接ノードを保証する。
    //    ステップ 1〜4 の高信頼リンクを優先し、不足分のみ同ジャンル・タイトル類似で補完。
    const MIN_DENSITY = 3;
    const MAX_ITEMS = 6;
    if (items.length < MIN_DENSITY) {
      const _bigrams = (s) => {
        const t = String(s || '').replace(/\s+/g, '').toLowerCase();
        const out = new Set();
        for (let i = 0; i < t.length - 1; i++) out.add(t.slice(i, i + 2));
        return out;
      };
      const _jac = (a, b) => {
        if (!a.size || !b.size) return 0;
        let inter = 0;
        for (const x of a) if (b.has(x)) inter++;
        return inter / (a.size + b.size - inter);
      };
      const myGenre = (meta.genre || '').toString();
      const myGenres = Array.isArray(meta.genres) ? meta.genres : (myGenre ? [myGenre] : []);
      const myBg = _bigrams(meta.generatedTitle || meta.title || '');

      const candidates = [];
      for (const t of allTopics) {
        if (!t || t.topicId === curId || usedIds.has(t.topicId)) continue;
        const status = t.lifecycleStatus || 'active';
        if (status !== 'active' && status !== 'cooling') continue;
        const otherTitle = t.generatedTitle || t.title || '';
        if (!otherTitle) continue;
        const otherGenres = Array.isArray(t.genres) ? t.genres : (t.genre ? [t.genre] : []);
        const sameGenre = myGenres.some(g => g && otherGenres.includes(g));
        const jac = _jac(myBg, _bigrams(otherTitle));
        let score = jac * 10;
        if (sameGenre) score += 2;
        if (score < 1) continue;
        candidates.push({ t, score });
      }
      candidates.sort((a, b) => {
        if (b.score !== a.score) return b.score - a.score;
        const at = _toMs(a.t.lastArticleAt || a.t.lastUpdated || 0);
        const bt = _toMs(b.t.lastArticleAt || b.t.lastUpdated || 0);
        return bt - at;
      });
      for (const { t } of candidates) {
        if (items.length >= MAX_ITEMS) break;
        items.push({ t, badge: { label: '📂 同じ動き', cls: 'related' } });
        usedIds.add(t.topicId);
      }
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
        <h2>🔗 この話に繋がる別の話</h2>
        <p class="disc-header-sub">同じ人物・組織・場所が登場するトピック、または上位/派生のテーマ</p>
        <div class="disc-col-body">
          ${items.map(({ t, badge, extraHtml }) => {
            const title = t.generatedTitle || t.title || '';
            const ago   = fmtElapsed(t.lastArticleAt || t.lastUpdated || 0);
            // childTopics ref は {topicId,title} だけのこともあるので articleCount が無い場合は表示しない
            const rawCnt = parseInt(t.articleCount, 10);
            const cnt   = (Number.isFinite(rawCnt) && rawCnt > 0) ? rawCnt : null;
            const dot   = t.lifecycleStatus === 'active' ? '🔴' : t.lifecycleStatus === 'cooling' ? '🟡' : t.lifecycleStatus ? '⚪' : '';
            const badgeHtml = badge ? `<span class="disc-badge disc-badge-${badge.cls}">${esc(badge.label)}</span>` : '';
            const safeThumb = t.imageUrl ? esc(typeof safeImgUrl === 'function' ? safeImgUrl(t.imageUrl) : t.imageUrl.replace(/['"<>]/g, '')) : '';
            const thumbHtml = safeThumb
              ? `<img class="disc-card-thumb" src="${safeThumb}" alt="" loading="lazy" referrerpolicy="origin-when-cross-origin" onerror="this.style.display='none'">`
              : '';
            // フッター: 無効値（0件/1970-1-1由来）を一切表示しないため空欄なら meta 行ごと省略
            const metaParts = [];
            if (dot) metaParts.push(dot);
            if (cnt) metaParts.push(`${cnt}件`);
            if (ago) metaParts.push(esc(ago));
            const metaText = metaParts.join(' · ');
            const metaHtml = metaText
              ? `<span class="disc-card-meta">${metaText}</span>`
              : '<span class="disc-card-meta disc-card-meta-muted">続き読む →</span>';
            return `
              <a href="topic.html?id=${esc(t.topicId)}" class="disc-card">
                ${thumbHtml}
                <div class="disc-card-body">
                  ${badgeHtml}
                  <div class="disc-card-title">${esc(title)}</div>
                  <div class="disc-card-footer">
                    ${metaHtml}
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

// ── スティッキーCTAバー（モバイル） ─────────────────────────────────
// #2: 表示制御を再設計
//   - hero がビューポートに見えている間: 非表示（hero の CTA で十分）
//   - hero を抜けて記事を読み始めたら: 表示（コメント誘導）
//   - コメントセクションに到達したら: 非表示（直接コメントできるので不要）
(function initStickyCta() {
  const bar        = document.getElementById('sticky-cta-bar');
  const commentBtn = document.getElementById('scb-comment-btn');
  const commSec    = document.getElementById('comments-section');
  const hero       = document.querySelector('.topic-hero');
  if (!bar || !commSec) return;

  let heroVisible = !!hero;          // 初期は hero が見えているはず
  let commentsVisible = false;
  function update() {
    bar.classList.toggle('visible', !heroVisible && !commentsVisible);
  }

  if (hero) {
    new IntersectionObserver(entries => {
      heroVisible = entries[0].isIntersecting;
      update();
    }, { threshold: 0.1 }).observe(hero);
  }
  new IntersectionObserver(entries => {
    commentsVisible = entries[0].isIntersecting;
    update();
  }, { threshold: 0.05 }).observe(commSec);

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
