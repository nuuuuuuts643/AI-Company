// app.js — メイン。auth.js / favorites.js / comments.js を先に読み込むこと。
// 読み込み順: config.js → js/formatters.js → js/auth.js → js/favorites.js → js/comments.js → app.js
//
// ─── 構造マップ（行番号は概算。再編した際は更新する） ───
//  §1  設定定数 / LSキー / トースト・エラーバナー       (約 1-60)
//  §2  ステータス・フェーズラベル / cleanSummary         (約 60-90)
//  §3  ジャンル定義 / パーソナライズ履歴                  (約 90-105)
//  §4  純粋整形（esc / fmtDate / safeImgUrl 等）          (約 105-170)
//        → ※テスト容易な版は frontend/js/formatters.js に分離。
//          window.Formatters.{esc,formatDate,cleanSummary,...} で参照可能。
//  §5  loadTopics / キーワードチップ                      (約 170-235)
//  §6  バッジ / カードメタ / 信頼度                        (約 235-360)
//  §7  カード描画 / ヒーロー / トピック一覧                (約 360-680)
//  §8  フィルター / トレンドジャンル / 検索               (約 680-775)
//  §9  refreshTopics / 鮮度・オンボーディング              (約 775-930)
//  §10 戻る・お気に入り・クイックニュースのストリップ      (約 930-1060)
//  §11 既読管理 / Back-to-top / スクロール復元 / Reading    (約 1060-1185)
//  §12 ボトムナビ / スケルトン                              (約 1185-1235)
//  §13 DOMContentLoaded ハンドラ                            (約 1235-end)

// ── 広告タイマー（stale timeout防止） ────────────────────────
let adHideTimer = null;

// ── 設定定数 ──────────────────────────────────────────────────
const CONFIG = {
  HOT_STRIP_HOURS: 6,                   // 今急上昇中セクションの対象時間（時間）
  HOT_STRIP_MIN_VELOCITY: 3,            // 急上昇と判定するvelocityScoreの最低値
  NEW_BADGE_HOURS: 1,                   // NEWバッジを表示する最大経過時間（時間）
  AD_CARD_INTERVAL: 5,                  // 広告を挿入する間隔
  FRESHNESS_INTERVAL_MS: 60000,         // 鮮度表示テキストの更新間隔（ミリ秒）
  TOPICS_PER_PAGE: 20,                  // 1ページに表示するトピック数
  REFRESH_INTERVAL_MS: 5 * 60 * 1000,  // トピック一覧の自動更新間隔（ミリ秒）
  MAX_GENRE_RATIO: 0.4,                 // 1ジャンルが全体に占める最大割合（多様性制御）
};

// ── ローカルストレージ キー定数 ──────────────────────────────
const LS_KEYS = {
  FAVORITES:     'flotopic_favorites',
  HISTORY:       'flotopic_history',
  AVATAR:        'flotopic_avatar',
  PROFILE_SET:   'flotopic_profile_set',
  DARK_MODE:     'flotopic_dark',
  PREFS:         'flotopic_prefs',
  PWA_DISMISSED: 'pwa_dismissed',
};

function showToast(msg, duration = 3000) {
  let el = document.getElementById('flotopic-toast');
  if (!el) {
    el = document.createElement('div');
    el.id = 'flotopic-toast';
    el.style.cssText = 'position:fixed;bottom:24px;left:50%;transform:translateX(-50%) translateY(60px);background:#1a1a1a;color:#fff;padding:10px 20px;border-radius:24px;font-size:.88rem;font-weight:600;z-index:9999;opacity:0;transition:all .3s ease;pointer-events:none;white-space:nowrap;';
    document.body.appendChild(el);
  }
  el.textContent = msg;
  el.style.opacity = '1';
  el.style.transform = 'translateX(-50%) translateY(0)';
  clearTimeout(el._tid);
  el._tid = setTimeout(() => {
    el.style.opacity = '0';
    el.style.transform = 'translateX(-50%) translateY(60px)';
  }, duration);
}

/**
 * エラーバナーを5秒間表示する
 * @param {string} message - 表示するエラーメッセージ
 */
function showErrorBanner(message) {
  const banner = document.getElementById('error-banner');
  if (banner) {
    banner.textContent = message;
    banner.style.display = 'block';
    setTimeout(() => { banner.style.display = 'none'; }, 5000);
  }
}

const STATUS_LABEL = { rising:'🔥 注目度急上昇', peak:'⚡ いま注目度ピーク', declining:'📉 落ち着き始め', cooling:'📉 沈静化中' };
const PHASE_BADGE  = { '発端':'🌱 始まり', '拡散':'📡 広まってる', 'ピーク':'🔥 急上昇', '現在地':'📍 今ここ', '収束':'✅ ひと段落' };
const PHASE_CLASS  = { '発端':'phase-start', '拡散':'phase-spread', 'ピーク':'phase-peak', '現在地':'phase-now', '収束':'phase-end' };

function cleanSummary(s) {
  if (!s) return s;
  return s
    .replace(/^#{1,3}\s+.+?\n+/gm, '')
    .replace(/^[-*]\s+/gm, '')
    .replace(/^\d+\.\s+/gm, '')
    .replace(/\n{2,}/g, ' ')
    .replace(/\n/g, ' ')
    .trim();
}

const GENRES = ['総合','政治','ビジネス','株・金融','テクノロジー','スポーツ','エンタメ','科学','健康','国際','くらし','社会','グルメ','ファッション'];
const GENRE_EMOJI = {'政治':'🏛️','ビジネス':'💼','株・金融':'📈','テクノロジー':'💻','スポーツ':'⚽','エンタメ':'🎬','科学':'🔬','健康':'💊','国際':'🌏','総合':'📰','くらし':'🏡','社会':'🗞️','グルメ':'🍽️','ファッション':'👗'};

// ===== パーソナライズ =====

function recordTopicView(topic) {
  if (!topic || !topic.topicId) return;
  try {
    let history = JSON.parse(localStorage.getItem(LS_KEYS.HISTORY) || '[]');
    history = history.filter(h => h.topicId !== topic.topicId);
    history.unshift({ topicId: topic.topicId, title: topic.generatedTitle || topic.title || '', viewedAt: Date.now() });
    if (history.length > 20) history = history.slice(0, 20);
    localStorage.setItem(LS_KEYS.HISTORY, JSON.stringify(history));
  } catch {}
  if (typeof syncHistoryItemToCloud === 'function') syncHistoryItemToCloud(topic);
}
function loadPrefs() {
  try { return JSON.parse(localStorage.getItem(LS_KEYS.PREFS) || '{}'); } catch { return {}; }
}
function savePrefs(prefs) {
  try { localStorage.setItem(LS_KEYS.PREFS, JSON.stringify(prefs)); } catch {}
}

// ===== 共通ユーティリティ =====
const _prefs = loadPrefs();
const _urlFilter = new URLSearchParams(location.search).get('filter');
const _urlGenre  = new URLSearchParams(location.search).get('genre');
// ジャンル: URLパラメータ → localStorage → '総合' の優先順で復元
let allTopics = [], currentStatus = _urlFilter || _prefs.status || 'all', currentGenre = _urlGenre || _prefs.genre || '総合', currentSearch = '';
let currentPage = 1;
let lastFetchTime = null;
let _pendingHeroHighlight = false;
const _prevSnap = (() => { try { return JSON.parse(localStorage.getItem('ftpc_snap') || '{}'); } catch { return {}; } })();

function esc(s) {
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

const SOURCE_DOMAIN_MAP = {
  'NHK': 'nhk.or.jp',
  'ITmedia': 'itmedia.co.jp',
  '読売新聞': 'yomiuri.co.jp',
  '毎日新聞': 'mainichi.jp',
  '朝日新聞': 'asahi.com',
  '日本経済新聞': 'nikkei.com',
  '東洋経済': 'toyokeizai.net',
  'ダイヤモンド': 'diamond.jp',
  '産経新聞': 'sankei.com',
  'Yahoo!ニュース': 'news.yahoo.co.jp',
  'PRESIDENT Online': 'president.jp',
  '文春オンライン': 'bunshun.jp',
  'Business Insider Japan': 'businessinsider.jp',
  'Forbes Japan': 'forbesjapan.com',
  'GIGAZINE': 'gigazine.net',
  'ASCII.jp': 'ascii.jp',
  'CNET Japan': 'japan.cnet.com',
  'PC Watch': 'pc.watch.impress.co.jp',
  'ケータイWatch': 'k-tai.watch.impress.co.jp',
  'livedoorニュース': 'livedoor.com',
  'BuzzFeed Japan': 'buzzfeed.com',
  'Gizmodo Japan': 'gizmodo.jp',
  '47NEWS': 'www.47news.jp',
  '首相官邸': 'kantei.go.jp',
  'TBS NEWS DIG': 'newsdig.tbs.co.jp',
  'FNN プライムオンライン': 'fnn.jp',
  'テレ朝news': 'news.tv-asahi.co.jp',
  '日テレNEWS': 'news.ntv.co.jp',
  'NHKニュース': 'nhk.or.jp',
};
function srcFaviconUrl(source) {
  if (!source) return '';
  const raw = SOURCE_DOMAIN_MAP[source] || (source.includes('.') && !source.includes(' ') ? source : null);
  if (!raw) return '';
  const domain = raw.replace(/^https?:\/\//, '').split('/')[0];
  return `https://www.google.com/s2/favicons?domain=${encodeURIComponent(domain)}&sz=16`;
}

function safeImgUrl(url) {
  if (!url) return '';
  return url.replace(/^http:\/\//i, 'https://');
}
function srcFaviconImg(source) {
  const url = srcFaviconUrl(source);
  if (!url) return '';
  return `<img class="source-favicon" src="${url}" alt="" width="12" height="12" onerror="this.style.display='none'">`;
}

function genreEmoji(genre) { return GENRE_EMOJI[genre] || '📰'; }
function fmtDate(s) {
  if (!s) return '';
  try { return new Date(s).toLocaleString('ja-JP',{year:'numeric',month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit'}); }
  catch { return s; }
}
function apiUrl(path) { return API_BASE + path + '.json'; }

// ===== 一覧ページ =====

/**
 * トップページ一覧用の最小 payload (topics-card.json) をフェッチしトピック配列を返す。
 * T265: topics.json (200KB+) は AI 長文を含み肥大化していたため、card 表示に必要な
 * フィールドだけ含む topics-card.json (約半分) に切り替えてモバイル初回表示帯域を削減する。
 * trendingKeywords は card 側にも updatedAt 同梱で持たせるが、無い場合は topics.json に
 * 1 度だけフォールバック。
 * @returns {Promise<Array>} トピックの配列
 */
async function loadTopics() {
  const r = await fetch(apiUrl('topics-card'));
  if (!r.ok) throw new Error(`topics-card fetch failed: HTTP ${r.status}`);
  const data = await r.json();
  // trendingKeywords は card payload に含めない設計 → topics.json から軽くフェッチ。
  // 失敗してもキーワードストリップが消えるだけで一覧表示は影響しない。
  fetch(apiUrl('topics'))
    .then(rr => rr.ok ? rr.json() : null)
    .then(full => { if (full) renderKeywordStrip(full.trendingKeywords || []); })
    .catch(() => {});
  return data.topics || [];
}

// 汎用すぎて何の話か分からない単語はチップから除外する。
// 例: 「背景」「内容」「状況」「問題」「結果」など、文脈が無いと意味が伝わらないもの。
// （バックエンドで extracted されたキーワードに混入することがある）
const KEYWORD_BLACKLIST = new Set([
  '背景','内容','状況','問題','結果','理由','詳細','概要','関連','影響','発表','発生','発生時','発生地','以下','以上','以前','以後','現在','過去','将来','今回','今後','今日','昨日','明日','本日','本件','当該','一方','その後','その前','その他','その間','一部','一般','全体','全国','全員','全部','全て','全て','側面','立場','可能性','必要','重要','一連','一連の','問題点','一覧','確認','報告','回答','質問','概略','本文','文章','記事','ニュース','話題','情報','データ','時間','場所','場面','日々','日付','日時','開催','終了','開始','参加','参加者','関係','関係者','メディア','媒体','業界','分野','政界','官民','地域','地元','都内','県内','市内','官房','政府','一般的','一般論'
]);

function isMeaningfulKeyword(word) {
  if (!word) return false;
  const w = String(word).trim();
  if (!w) return false;
  if (w.length < 2) return false; // 1文字キーワードは曖昧すぎるので除外
  if (KEYWORD_BLACKLIST.has(w)) return false;
  // ひらがなのみ・カタカナのみで2-3文字の助詞/動詞っぽいものも除外（ヒューリスティック）
  if (/^[぀-ゟ]{2,3}$/.test(w)) return false; // 純ひらがな2-3文字
  return true;
}

function renderKeywordStrip(keywords) {
  const strip = document.getElementById('keyword-strip');
  if (!strip) return;
  if (!keywords || !keywords.length) { strip.style.display = 'none'; return; }
  // 不適切タグを事前にフィルタ。カウントが残れば表示、すべて除外なら非表示
  const filtered = keywords.filter(kw => {
    const word = typeof kw === 'string' ? kw : (kw.keyword || '');
    return isMeaningfulKeyword(word);
  });
  if (!filtered.length) { strip.style.display = 'none'; return; }
  strip.style.display = 'flex';
  strip.innerHTML = '<span class="keyword-strip-label">注目</span>' +
    filtered.slice(0, 12).map(kw => {
      const word = typeof kw === 'string' ? kw : (kw.keyword || '');
      return word ? `<button class="kw-chip" data-kw="${esc(word)}">#${esc(word)}</button>` : '';
    }).join('');
  strip.querySelectorAll('.kw-chip').forEach(btn => {
    btn.addEventListener('click', () => {
      const input = document.getElementById('search-input');
      if (input) {
        input.value = btn.dataset.kw;
        currentSearch = btn.dataset.kw;
        currentPage = 1;
        // キーワードはサイト全体トレンドなのでジャンルを一時的に総合にする（prefs保存しない）
        currentGenre = '総合';
        buildFilters();
        renderTopics(allTopics);
      }
    });
  });
}

/**
 * NEWバッジのHTMLを生成する（lastUpdated が NEW_BADGE_HOURS 以内の場合のみ表示）
 * @param {Object} t - トピックオブジェクト
 * @returns {string} バッジのHTML文字列
 */
function toUnixSec(v) {
  if (!v) return 0;
  const n = Number(v);
  if (!isNaN(n) && n > 1e9) return n;
  const t = new Date(v).getTime();
  return isNaN(t) ? 0 : t / 1000;
}
function renderBadges(t) {
  const ts = toUnixSec(t.lastUpdated);
  const isNew = ts > 0 && ts >= Date.now() / 1000 - CONFIG.NEW_BADGE_HOURS * 3600;
  const newBadge = isNew
    ? (t.latestUpdateHeadline ? '<span class="card-new-dot-badge"></span>' : '<span class="card-new-badge">NEW</span>')
    : '';
  const favUpdated = (typeof isFavUpdated === 'function' && isFavUpdated(t))
    ? '<span class="card-fav-updated-badge">♥ 更新</span>'
    : '';
  // AI 未解析トピック (generatedTitle も generatedSummary も無い) は明示する。
  // これがないと「raw RSS タイトル + 媒体名サフィックス」が出て「壊れている」と見える。
  const isAiPending = !t.generatedSummary && !t.generatedTitle;
  const aiPendingBadge = isAiPending
    ? '<span class="card-ai-pending-badge" title="AI解析待ち（次回 01:00/07:00/13:00/19:00 JST に処理）">🤖 解析待ち</span>'
    : '';
  return newBadge + favUpdated + aiPendingBadge;
}

/**
 * RSS生タイトル末尾の「 - 媒体名」サフィックスを除去する。
 * AI解析前のトピックでフォールバック表示する際、見栄えを揃える。
 * 媒体名は別 srcLabel で出すので二重表示にもならない。
 * @param {string} raw - 生タイトル
 * @returns {string} クリーンタイトル
 */
function stripMediaSuffix(raw) {
  if (!raw) return '';
  // 末尾の「 - XX」「 | XX」「（XX）」パターンを最大1つ除く。媒体名と思しき短語のみ。
  return String(raw).replace(/\s*[-｜|]\s*[^-｜|]{2,32}$/u, '').replace(/\s*（[^（）]{2,16}）\s*$/u, '').trim();
}

/**
 * カードのメタ情報HTML（記事件数・読書時間・ソース数・ジャンル・更新日時）を生成する
 * @param {Object} t - トピックオブジェクト
 * @returns {string} メタ情報のHTML文字列
 */
function renderCardMeta(t) {
  const readMins = Math.min(30, Math.max(1, Math.round((t.articleCount || 1) * 0.8)));
  const srcCount = t.uniqueSourceCount || (t.sources ? t.sources.length : 0);
  const srcNames = Array.isArray(t.sources) ? t.sources : [];

  // ソース表示: 2社以下はファビコン付き名前表示、3社以上は件数
  let srcLabel = '';
  if (srcCount >= 3) {
    srcLabel = `<span class="src-count-label" title="${srcNames.slice(0,6).join('、')}">📰 ${srcCount}社が報道</span>`;
  } else if (srcCount === 2) {
    srcLabel = `<span class="src-count-label">${srcNames.slice(0,2).map(s => srcFaviconImg(s) + esc(s)).join(' · ')}</span>`;
  } else if (srcCount === 1) {
    srcLabel = `<span class="src-count-label src-single">${srcFaviconImg(srcNames[0])}${esc(srcNames[0] || '1社のみ')}</span>`;
  }

  // はてなブックマーク数（ソーシャルエンゲージメント指標）
  const hatena = parseInt(t.hatenaCount || 0, 10);
  const hatenaLabel = hatena >= 10
    ? `<span class="hatena-count" title="はてなブックマーク数">🔖 ${hatena}</span>`
    : '';

  // 分岐トピック（この話から派生した話題がある）
  const childCount = Array.isArray(t.childTopics) ? t.childTopics.length : 0;
  const branchLabel = childCount > 0
    ? `<span class="branch-link" data-storymap-id="${esc(t.topicId)}" title="この話題の分岐を見る">🌿 ${childCount}件の分岐</span>`
    : '';

  // 親トピックがある場合（この話は大きな流れの一部）
  const parentLabel = t.parentTopicId
    ? `<span class="parent-indicator" title="大きなトピックから派生">↳ 派生</span>`
    : '';

  const deltaLabel = (t._deltaCnt > 0)
    ? `<span class="new-articles-delta" title="前回訪問から増加">+${t._deltaCnt}件</span>`
    : (t.articleCountDelta > 0)
        ? `<span class="new-articles-delta" title="過去24時間で増加">📈 +${t.articleCountDelta}件</span>`
        : '';
  const phaseLabel = t._phaseChanged
    ? `<span class="phase-change-badge">🔄 展開</span>` : '';
  const genres = t.genres || [t.genre || '総合'];
  return `
    <div class="topic-meta">
      <span class="article-count">📄 ${t.articleCount}件 · 約${readMins}分</span>${deltaLabel}
      ${phaseLabel}${srcLabel}
      ${hatenaLabel}
      ${branchLabel}
      ${parentLabel}
      ${genres.map(g => `<span class="genre-tag">${esc(g)}</span>`).join('')}
      <span>${fmtDate(t.lastUpdated)}</span>
    </div>`;
}

/**
 * 信頼性シグナルHTML（⚠情報確認中・情報精査中バッジ）を生成する
 * 断定せず判断材料を提供する設計（法的リスク低減）
 * @param {Object} t - トピックオブジェクト
 * @returns {string} シグナルのHTML文字列（シグナルなしの場合は空文字列）
 */
function renderReliabilitySignal(t) {
  const reliabilityBadge = (t.reliability === 'unverified' && (t.score || 0) < 80)
    ? `<span class="reliability-badge" title="複数の記事で不確実な表現が多く見られます">⚠️ 情報確認中</span>`
    : '';
  const conflictBadge = t.hasConflict
    ? `<span class="conflict-badge" title="記事間で数値に食い違いが見られる場合があります">🔍 情報精査中</span>`
    : '';
  if (!reliabilityBadge && !conflictBadge) return '';
  return `<div class="reliability-signals">${reliabilityBadge}${conflictBadge}</div>`;
}

/**
 * 1枚のトピックカードHTML文字列を生成する
 * AD_CARD_INTERVAL 枚ごとに広告カードも末尾に追加する
 * @param {Object} t - トピックオブジェクト
 * @param {number} i - ゼロ始まりのインデックス（広告挿入判定に使用）
 * @returns {string} カードHTML文字列
 */
function renderTopicCard(t, i) {
  const primaryGenre = (t.genres || [t.genre || '総合'])[0];
  // lifecycleStatus=cooling/archived はカード表示を declining に統一
  const isCooling = t.lifecycleStatus === 'cooling' || t.lifecycleStatus === 'archived';
  const displayStatus = isCooling ? 'declining' : (t.status || 'rising');

  const thumbHtml = t.imageUrl
    ? `<div class="card-thumb"><img class="card-thumb-img" src="${esc(safeImgUrl(t.imageUrl))}" alt="" loading="lazy" referrerpolicy="origin-when-cross-origin" onerror="this.parentNode.innerHTML='<div class=\\'card-thumb-placeholder ${displayStatus}\\'>${genreEmoji(primaryGenre)}</div>'"></div>`
    : `<div class="card-thumb"><div class="card-thumb-placeholder ${displayStatus}">${genreEmoji(primaryGenre)}</div></div>`;
  const isFav    = userFavorites.has(t.topicId);
  const isViewed = viewedTopics.has(t.topicId);

  // cooling時に「N日前に沈静化」を表示
  const coolingAgeHtml = (() => {
    if (!isCooling || !t.lastArticleAt) return '';
    const h = Math.floor((Date.now() / 1000 - Number(t.lastArticleAt)) / 3600);
    const label = h >= 48 ? `${Math.floor(h/24)}日前に沈静化` : `${h}時間前に沈静化`;
    return `<span class="cooling-age">${label}</span>`;
  })();

  const phaseHtml = t.storyPhase && PHASE_BADGE[t.storyPhase]
    ? `<span class="card-phase-badge ${PHASE_CLASS[t.storyPhase] || ''}">${PHASE_BADGE[t.storyPhase]}</span>`
    : '';

  const velocity = Number(t.velocityScore || 0);
  const velPct = Math.min(100, Math.round(velocity * 5));
  const velBarHtml = (displayStatus === 'rising' || displayStatus === 'peak') && velocity > 0
    ? `<div class="velocity-bar-wrap ${displayStatus}"><div class="velocity-bar" style="width:${velPct}%"></div></div>`
    : '';

  // 分岐ストーリーバー（親トピックのみ）
  const childTopics = Array.isArray(t.childTopics) ? t.childTopics : [];
  const storyBarHtml = childTopics.length > 0
    ? `<a href="storymap.html?id=${esc(t.topicId)}" class="story-branches-bar">
        <span class="story-branches-bar-label">🌿 ストーリー ${childTopics.length}件の分岐</span>
        <span class="story-branches-bar-pills">
          ${childTopics.slice(0, 2).map(c =>
            `<span class="story-branch-pill">${esc((c.title || '').slice(0, 16))}</span>`
          ).join('')}
          ${childTopics.length > 2 ? `<span class="story-branch-more">+${childTopics.length - 2}</span>` : ''}
        </span>
        <span class="story-branches-bar-arrow">→</span>
      </a>`
    : (t.storyPhase ? `<a href="storymap.html?id=${esc(t.topicId)}" class="card-storymap-link">📖 経緯を読む →</a>` : '');

  return `
    <div class="topic-card-wrapper" style="position:relative;">
      ${renderBadges(t)}
      <a class="topic-card ${displayStatus}${isViewed ? ' viewed' : ''}${childTopics.length > 0 ? ' has-story' : ''}" href="topic.html?id=${esc(t.topicId)}" data-tid="${esc(t.topicId)}">
        ${thumbHtml}
        <div class="card-body">
          <div class="topic-status ${displayStatus}">${STATUS_LABEL[displayStatus] || displayStatus}${coolingAgeHtml}${phaseHtml}</div>
          ${velBarHtml}
          <h3>${esc(t.topicTitle || t.generatedTitle || stripMediaSuffix(t.title))}</h3>
          ${t.latestUpdateHeadline ? `<p class="card-update-headline">${esc(t.latestUpdateHeadline)}</p>` : ''}
          ${renderCardMeta(t)}
          ${renderReliabilitySignal(t)}
        </div>
      </a>
      <button class="fav-btn ${isFav ? 'fav-active' : ''}" data-topic-id="${esc(t.topicId)}" title="${isFav ? 'お気に入りを解除' : 'お気に入りに追加'}" aria-label="お気に入り">♥</button>
      <button class="card-share-btn" data-share-id="${esc(t.topicId)}" data-share-title="${esc(t.generatedTitle || t.title)}" title="URLをコピー" aria-label="URLをコピー">🔗</button>
      ${storyBarHtml}
    </div>`;
}

/**
 * ジャンル多様性を確保したトピックリストを返す
 * 1ジャンルが全体の CONFIG.MAX_GENRE_RATIO を超えないようにする
 * 上限を超えたトピックは末尾に回し、表示は維持する
 * @param {Array} topics - ソート済みトピック配列
 * @param {boolean} genreFiltered - ジャンルフィルターが選択中かどうか
 * @returns {Array} 多様性を確保したトピック配列
 */
function applyGenreDiversity(topics, genreFiltered) {
  if (genreFiltered) return topics; // フィルター選択中はそのまま返す
  if (!topics.length) return topics;

  const maxPerGenre = Math.ceil(topics.length * CONFIG.MAX_GENRE_RATIO);
  const genreCount = {};
  const result = [];
  const overflow = []; // 上限超えのトピックは末尾に回す

  for (const t of topics) {
    const genre = (t.genres && t.genres[0]) || t.genre || 'その他';
    genreCount[genre] = (genreCount[genre] || 0) + 1;
    if (genreCount[genre] <= maxPerGenre) {
      result.push(t);
    } else {
      overflow.push(t);
    }
  }

  return [...result, ...overflow];
}

// T237 (2026-04-28): 「今動いているストーリー」を最上部 hero として 1件だけ大きく見せる。
// CLAUDE.md vision-roadmap フェーズ1「①トップ画面でストーリーの『動き』が見える」の実装。
// 候補条件: lifecycleStatus !== 'archived' && articleCount >= 3 && phase=拡散|ピーク && summaryMode=full|standard
// (storyTimeline は topics.json では _PROC_INTERNAL で除外されるので summaryMode で代用)
// 並び替え: velocityScore DESC → score DESC で上位1件。
// 該当なしなら placeholder を非表示にする (空コンテナ非表示ルール遵守)。
function renderHeroStoryPreview(list) {
  const el = document.getElementById('hero-story-preview');
  if (!el) return;
  // フィルター中・検索中・お気に入り表示中は出さない (主役を奪わない)
  if (currentSearch || showFavsOnly || (currentGenre && currentGenre !== '総合') || (currentStatus && currentStatus !== 'all')) {
    el.style.display = 'none'; el.innerHTML = ''; return;
  }
  const candidates = (list || []).filter(t =>
    t.lifecycleStatus !== 'archived' &&
    parseInt(t.articleCount || 0, 10) >= 3 &&
    (t.storyPhase === '拡散' || t.storyPhase === 'ピーク') &&
    (t.summaryMode === 'full' || t.summaryMode === 'standard')
  );
  candidates.sort((a, b) =>
    (Number(b.velocityScore || 0) - Number(a.velocityScore || 0)) ||
    (Number(b.score || 0) - Number(a.score || 0))
  );
  const t = candidates[0];
  if (!t) { el.style.display = 'none'; el.innerHTML = ''; return; }
  const phaseBadge = t.storyPhase && PHASE_BADGE[t.storyPhase] ? PHASE_BADGE[t.storyPhase] : '';
  const title = t.topicTitle || t.generatedTitle || t.title || '';
  const beat  = t.latestUpdateHeadline || t.keyPoint || cleanSummary(t.generatedSummary || '').slice(0, 50);
  const cnt   = parseInt(t.articleCount || 0, 10);
  el.innerHTML = `
    <div class="hero-story-tagline">⚡ 今動いているストーリー</div>
    <a href="topic.html?id=${esc(t.topicId)}" class="hero-story-card" aria-label="${esc(title)}の経緯を読む">
      <div class="hero-story-label">${esc(phaseBadge)} · 記事${cnt}件</div>
      <div class="hero-story-title">${esc(title)}</div>
      ${beat ? `<div class="hero-story-beat">${esc(beat)}</div>` : ''}
      <div class="hero-story-cta">📖 経緯を読む →</div>
    </a>`;
  el.style.display = 'block';
}

function renderTopics(topics) {
  const grid = document.getElementById('topics-grid');
  if (!grid) return;
  // T237: 「今動いているストーリー」hero を全件 (フィルター前) から選定して最上部に表示。
  //  filter/search/genre 中は renderHeroStoryPreview 内で自動的に隠す。
  try { renderHeroStoryPreview(topics); } catch (e) { console.error('hero preview error:', e); }
  let list = topics;
  if (currentSearch) {
    const q = currentSearch.toLowerCase();
    list = list.filter(t => {
      const title = (t.generatedTitle || t.title || '').toLowerCase();
      const summary = cleanSummary(t.generatedSummary || '').toLowerCase();
      const genres = ((t.genres || [t.genre || '']).join(' ')).toLowerCase();
      return title.includes(q) || summary.includes(q) || genres.includes(q);
    });
  }
  // 記事1件以下 or AI判定で内容が乖離しているトピックはフィードから除外
  list = list.filter(t => parseInt(t.articleCount) >= 2 && t.topicCoherent !== false);

  // 子トピック（parentTopicId あり）は親がリストに存在する場合はメインリストから非表示
  // 検索・ジャンルフィルター中は非表示にしない（検索で見つけられるように）
  if (!currentSearch && currentGenre === '総合' && !showFavsOnly) {
    const presentIds = new Set(list.map(t => t.topicId));
    list = list.filter(t => !t.parentTopicId || !presentIds.has(t.parentTopicId));
  }

  // declining フィルターは lifecycleStatus=cooling を含める（status=decliningは実質未使用のため）
  if (currentStatus === 'declining') {
    list = list.filter(t => t.status === 'declining' || t.lifecycleStatus === 'cooling');
  } else if (currentStatus !== 'all') {
    list = list.filter(t => t.status === currentStatus && t.lifecycleStatus !== 'cooling');
  } else {
    list = list.filter(t => t.lifecycleStatus !== 'archived');
  }
  if (currentGenre !== '総合') {
    const _GENRE_ALIAS = { 'ファッション': 'ファッション・美容' };
    const _alt = _GENRE_ALIAS[currentGenre];
    list = list.filter(t => {
      const gs = t.genres || [t.genre];
      return gs.includes(currentGenre) || (_alt && gs.includes(_alt));
    });
  }
  if (showFavsOnly) list = list.filter(t => userFavorites.has(t.topicId));

  // ジャンル多様性を確保（テック偏り防止）
  list = applyGenreDiversity(list, currentGenre !== '総合');

  const lmContainer = document.getElementById('load-more-container');
  if (!list.length) {
    if (showFavsOnly) {
      grid.innerHTML = `
        <div class="empty-state" style="padding:32px 16px;text-align:center;color:var(--text-secondary);">
          <div style="font-size:2rem;margin-bottom:8px;">♡</div>
          <div style="font-size:.95rem;font-weight:600;margin-bottom:6px;">お気に入りのトピックがまだありません</div>
          <div style="font-size:.82rem;line-height:1.6;">気になるトピックの<strong style="color:var(--primary);">♥</strong>をタップ<br>新しい動きがあれば追跡できます</div>
        </div>`;
    } else if (currentSearch) {
      grid.innerHTML = `
        <div class="empty-state" style="padding:32px 16px;text-align:center;color:var(--text-secondary);">
          <div style="font-size:2rem;margin-bottom:8px;">🔍</div>
          <div style="font-size:.95rem;font-weight:600;margin-bottom:6px;">「${esc(currentSearch)}」の結果が見つかりません</div>
          <div style="font-size:.82rem;line-height:1.6;">別のキーワードや、ジャンルから探してみてください</div>
          <div style="margin-top:12px;display:flex;gap:6px;justify-content:center;flex-wrap:wrap;">
            ${['総合','政治','国際','経済','テクノロジー','スポーツ','エンタメ'].map(g => `<button class="kw-chip" data-genre-jump="${esc(g)}" style="cursor:pointer;">${esc(g)}</button>`).join('')}
          </div>
        </div>`;
      grid.querySelectorAll('[data-genre-jump]').forEach(btn => {
        btn.addEventListener('click', () => {
          const si = document.getElementById('search-input');
          if (si) si.value = '';
          currentSearch = '';
          currentGenre = btn.dataset.genreJump;
          buildFilters();
          renderTopics(allTopics);
        });
      });
    } else {
      grid.innerHTML = `
        <div class="empty-state" style="padding:32px 16px;text-align:center;color:var(--text-secondary);">
          <div style="font-size:2rem;margin-bottom:8px;">📭</div>
          <div style="font-size:.95rem;font-weight:600;margin-bottom:6px;">このフィルターには該当するトピックがありません</div>
          <div style="font-size:.82rem;">ジャンルを「総合」に戻してみてください</div>
        </div>`;
    }
    if (lmContainer) lmContainer.innerHTML = '';
    return;
  }

  const pageList = list.slice(0, currentPage * CONFIG.TOPICS_PER_PAGE);
  grid.innerHTML = pageList.reduce((html, t, i) => {
    const cardHtml = renderTopicCard(t, i);
    if ((i + 1) % CONFIG.AD_CARD_INTERVAL !== 0) return html + cardHtml;
    const adHtml = `<div class="topic-card-wrapper ad-card-wrapper">
      <div class="ad-infeed-card">
        <span class="ad-grid-badge">広告</span>
        <div class="admax-slot"></div>
      </div>
    </div>`;
    return html + cardHtml + adHtml;
  }, '');

  // 忍者AdMax 非同期タグ（β版）: div生成 + admaxads.push() で注入
  // t.js は index.html の <head> で1回だけ読み込み済み
  grid.querySelectorAll('.admax-slot').forEach(slot => {
    const adDiv = document.createElement('div');
    adDiv.className = 'admax-ads';
    adDiv.setAttribute('data-admax-id', '26151fdf6b94c9622efaaa710e4efd04');
    adDiv.style.display = 'inline-block';
    slot.appendChild(adDiv);
    (window.admaxads = window.admaxads || []).push({
      admax_id: '26151fdf6b94c9622efaaa710e4efd04',
      type: 'banner',
    });
  });
  // 5秒後に広告未填充のスロットを非表示（空スペース防止）
  // module-level変数で前回のタイマーをキャンセルし、re-render直後の誤hideを防ぐ
  if (adHideTimer) clearTimeout(adHideTimer);
  adHideTimer = setTimeout(() => {
    adHideTimer = null;
    grid.querySelectorAll('.ad-card-wrapper').forEach(wrapper => {
      const inner = wrapper.querySelector('.admax-ads');
      if (!inner || !inner.innerHTML.trim()) wrapper.style.display = 'none';
    });
  }, 5000);

  if (lmContainer) {
    if (pageList.length < list.length) {
      const remaining = list.length - pageList.length;
      lmContainer.innerHTML = `<button class="load-more-btn">もっと見る（残り${remaining}件）</button>`;
      lmContainer.querySelector('.load-more-btn').addEventListener('click', () => { currentPage++; renderTopics(allTopics); });
    } else {
      lmContainer.innerHTML = '';
    }
  }

  // 分岐リンク（<a>のネスト回避のためspanにしてJSでナビゲート）
  grid.querySelectorAll('.branch-link[data-storymap-id]').forEach(el => {
    el.addEventListener('click', e => {
      e.preventDefault();
      e.stopPropagation();
      location.href = `storymap.html?id=${el.dataset.storymapId}`;
    });
  });

  // お気に入りボタン + 既読マーク
  grid.querySelectorAll('.fav-btn').forEach(btn => {
    btn.addEventListener('click', e => {
      e.preventDefault();
      e.stopPropagation();
      toggleFavorite(btn.dataset.topicId, btn);
    });
  });
  grid.querySelectorAll('.topic-card[data-tid]').forEach(a => {
    a.addEventListener('click', () => {
      markViewed(a.dataset.tid);
      a.classList.add('viewed');
    });
  });

  grid.querySelectorAll('.card-share-btn').forEach(btn => {
    btn.addEventListener('click', e => {
      e.preventDefault();
      e.stopPropagation();
      const url = `https://flotopic.com/topics/${btn.dataset.shareId}.html`;
      const title = btn.dataset.shareTitle || 'Flotopic';
      if (navigator.share) {
        navigator.share({ title, url }).catch(() => {});
      } else {
        navigator.clipboard.writeText(url).then(() => showToast('URLをコピーしました')).catch(() => {
          const tmp = document.createElement('textarea');
          tmp.value = url;
          document.body.appendChild(tmp);
          tmp.select();
          document.execCommand('copy');
          document.body.removeChild(tmp);
          showToast('URLをコピーしました');
        });
      }
    });
  });

  showTrendingBanner(allTopics);
}

function updateIndexOGP(genre) {
  const desc = genre === '総合'
    ? '同じ話題のニュースをAIがまとめ、時間軸で推移を可視化。30分ごと自動更新。'
    : `${genre}のニュースをAIがまとめて時間軸で可視化。急上昇トピックをリアルタイム更新。`;
  document.querySelectorAll('meta[name="description"], meta[property="og:description"], meta[name="twitter:description"]')
    .forEach(m => m.setAttribute('content', desc));
}

function buildFilters() {
  // status-filter（総合/急上昇/注目中/落ち着き）はトピックがすでに velocity 降順で並んでいるため不要。
  // 上位カードが「今一番話題のトピック」になる設計。currentStatus は内部的に 'all' で固定運用。
  const sbar = document.getElementById('status-filter');
  if (sbar) sbar.innerHTML = '';
  const gbar = document.getElementById('genre-filter');
  if (gbar) {
    gbar.innerHTML = GENRES.map(g=>`<button class="filter-btn genre-btn ${currentGenre===g?'active':''}" data-genre="${g}">${g}</button>`).join('');
    gbar.querySelectorAll('.genre-btn').forEach(btn => btn.addEventListener('click', () => {
      gbar.querySelectorAll('.genre-btn').forEach(b=>b.classList.remove('active'));
      btn.classList.add('active'); currentGenre = btn.dataset.genre;
      savePrefs({...loadPrefs(), genre: currentGenre});
      if (typeof syncGenreToCloud === 'function') syncGenreToCloud(currentGenre);
      currentPage = 1;
      currentSearch = '';
      const si = document.getElementById('search-input'); if (si) si.value = '';
      updateIndexOGP(currentGenre);
      renderTopics(allTopics);
    }));
  }
}

function renderTrendingGenres() {
  const el = document.getElementById('weather-widget');
  if (!el || !allTopics.length) return;
  const genreVelocity = {}, genreCount = {};
  for (const t of allTopics) {
    if (t.status !== 'rising' && t.status !== 'peak') continue;
    for (const g of (t.genres || [t.genre || '総合'])) {
      const v = Number(t.velocityScore || 0);
      if (!genreVelocity[g] || v > genreVelocity[g]) genreVelocity[g] = v;
      genreCount[g] = (genreCount[g] || 0) + 1;
    }
  }
  // サイト全体で今動いてるトピック数 (rising + peak)
  const totalActive = allTopics.filter(t => t.status === 'rising' || t.status === 'peak').length;
  const top = Object.entries(genreVelocity).sort((a,b)=>b[1]-a[1]).slice(0,1);
  if (!totalActive) { el.innerHTML = ''; return; }
  const genre = top.length ? top[0][0] : '';
  const genreSuffix = genre ? `<span class="trend-genre-count">急上昇: ${esc(genre)}</span>` : '';
  el.innerHTML = `<span class="trend-genre-label" id="weather-active-label">🔴 今 <strong>${totalActive}</strong> トピックが動いてる</span>${genreSuffix}`;
  // /analytics/active から実リアルタイム閲覧者数を取得して上書き
  if (typeof _GW !== 'undefined') {
    fetch(`${_GW}/analytics/active`).then(r => r.ok ? r.json() : null).then(d => {
      if (!d || typeof d.activeUsers30m !== 'number') return;
      const labelEl = document.getElementById('weather-active-label');
      if (!labelEl) return;
      const users = d.activeUsers30m;
      if (users >= 2) {
        labelEl.innerHTML = `🔴 今 <strong>${users}人</strong>が閲覧中 · 動いてるトピック ${totalActive}件`;
      }
    }).catch(()=>{});
  }
}

function setupSearch() {
  const input = document.getElementById('search-input');
  if (!input) return;
  let debounceTimer;
  input.addEventListener('input', () => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      const prev = currentSearch;
      currentSearch = input.value.trim();
      if (currentSearch) {
        // 検索中は総合に一時切替（prefs は保存しない）
        if (currentGenre !== '総合') {
          currentGenre = '総合';
          buildFilters();
        }
      } else if (prev && !currentSearch) {
        // 検索クリア時は保存済みジャンルを復元
        const saved = (loadPrefs().genre) || '総合';
        if (currentGenre !== saved) {
          currentGenre = saved;
          buildFilters();
        }
      }
      currentPage = 1;
      renderTopics(allTopics);
    }, 200);
  });
}

/**
 * トピック一覧をフェッチしてUIを更新する（REFRESH_INTERVAL_MS ごとに自動呼び出し）
 * @returns {Promise<void>}
 */
async function refreshTopics() {
  try {
    const raw = await loadTopics();
    // velocityScore に時間減衰を適用してソート（古いトピックを下に送る）
    const nowSec2 = Date.now() / 1000;
    // AI要約済みは1.0、未要約は0.80（同スコア帯で要約済みを上位に）
    const aiMult = t => t.generatedSummary ? 1.0 : 0.80;
    const decayedVS = t => {
      const vs  = Number(t.velocityScore || 0);
      const age = nowSec2 - toUnixSec(t.lastUpdated); // 秒
      if (age <= 0 || !toUnixSec(t.lastUpdated)) return vs * aiMult(t);
      const h = age / 3600;
      // 6h未満: 100% / 12h: 85% / 24h: 65% / 48h: 40% / 72h以上: 20%
      const decay = h < 6  ? 1.0
                  : h < 12 ? 0.85
                  : h < 24 ? 0.65
                  : h < 48 ? 0.40
                  :          0.20;
      return vs * decay * aiMult(t);
    };
    allTopics = raw.sort((a, b) => {
      const vs = decayedVS(b) - decayedVS(a);
      if (Math.abs(vs) > 0.5) return vs;
      const sc = Number(b.score || 0) * aiMult(b) - Number(a.score || 0) * aiMult(a);
      if (sc !== 0) return sc;
      return (b.lastUpdated || '').localeCompare(a.lastUpdated || '');
    });
    for (const t of allTopics) {
      const prev = _prevSnap[t.topicId];
      if (prev) {
        const d = (t.articleCount || 0) - (prev.cnt || 0);
        t._deltaCnt = d > 0 ? d : 0;
        t._phaseChanged = !!(prev.phase && t.storyPhase && prev.phase !== t.storyPhase);
      }
    }
    lastFetchTime = Date.now();
    updateFreshnessDisplay();
    renderReturnStrip(allTopics);
    renderFavStrip(allTopics);
    // 初訪問時（_prevSnapなし）はhot-stripで十分なためスキップ、再訪問時のみ表示
    if (Object.keys(_prevSnap).length > 0) renderQuickNews(allTopics);
    updateMypageBadge(allTopics);
    renderTopics(allTopics);
    try {
      const snap = {};
      for (const t of allTopics) snap[t.topicId] = { cnt: t.articleCount || 0, phase: t.storyPhase || '' };
      localStorage.setItem('ftpc_snap', JSON.stringify(snap));
    } catch(e) {}
    renderTrendingGenres();
    if (typeof syncFavSeenTimes === 'function') syncFavSeenTimes(allTopics);
    showOnboardingTip();
    // 初回onboardingが表示されない場合のみ genre sheet を直接表示（2回目以降訪問でgenre未選択の場合）
    if (localStorage.getItem('flotopic_onboarded')) showGenreOnboarding();
  } catch(e) {
    console.error(e);
    showErrorBanner('データの読み込みに失敗しました。しばらくしてから再度お試しください。');
  }
}

function updateFreshnessDisplay() {
  const el = document.getElementById('last-updated');
  if (!el || !lastFetchTime) return;
  const diffMin = Math.floor((Date.now() - lastFetchTime) / 60000);
  const diffH   = Math.floor(diffMin / 60);
  const diffD   = Math.floor(diffH   / 24);
  if (diffMin < 1)       el.textContent = '🔄 たった今更新';
  else if (diffMin < 60) el.textContent = `🔄 ${diffMin}分前に更新`;
  else if (diffH  < 24)  el.textContent = `🔄 ${diffH}時間前に更新`;
  else                   el.textContent = `🔄 ${diffD}日前に更新`;
}


function showOnboardingTip() {
  if (localStorage.getItem('flotopic_onboarded')) return;
  const el = document.getElementById('onboarding-tip');
  if (el) el.style.display = '';
}

window.flotopicDismissOnboarding = function() {
  _pendingHeroHighlight = true;
  localStorage.setItem('flotopic_onboarded', '1');
  const el = document.getElementById('onboarding-tip');
  if (el) el.style.display = 'none';
  // onboarding dismissal → genre selection sheet（連続フロー）
  showGenreOnboarding();
};

function showGenreOnboarding() {
  if (localStorage.getItem('flotopic_genre_selected')) return;
  // 未ログインでは表示しない（ログイン後に auth.js の _maybeShowGenreOnboarding が呼ぶ）
  if (typeof currentUser === 'undefined' || !currentUser) return;
  const prefs = loadPrefs();
  if (prefs.genre && prefs.genre !== '総合') return;
  const overlay = document.createElement('div');
  overlay.id = 'go-overlay';
  overlay.className = 'go-overlay';
  overlay.onclick = window.flotopicSkipGenreOnboarding;
  const sheet = document.createElement('div');
  sheet.id = 'go-sheet';
  sheet.className = 'go-sheet';
  const chips = GENRES.filter(g => g !== '総合').map(g =>
    `<button class="go-chip" onclick="flotopicSelectGenre('${g}')">${g}</button>`
  ).join('');
  sheet.innerHTML = `
    <p class="go-title">🎯 興味あるジャンルは？</p>
    <p class="go-sub">次回から自動で絞り込みます（後で変更できます）</p>
    <div class="go-chips">${chips}</div>
    <button class="go-skip" onclick="flotopicSkipGenreOnboarding()">スキップ</button>
  `;
  document.body.appendChild(overlay);
  document.body.appendChild(sheet);
  requestAnimationFrame(() => { overlay.classList.add('go-visible'); sheet.classList.add('go-visible'); });
}

function dismissGenreOnboarding() {
  const overlay = document.getElementById('go-overlay');
  const sheet = document.getElementById('go-sheet');
  if (overlay) overlay.classList.remove('go-visible');
  if (sheet) sheet.classList.remove('go-visible');
  setTimeout(() => {
    const o = document.getElementById('go-overlay');
    const s = document.getElementById('go-sheet');
    if (o) o.remove();
    if (s) s.remove();
    if (_pendingHeroHighlight) {
      _pendingHeroHighlight = false;
      const hero = document.getElementById('hero-story-preview');
      if (hero && hero.style.display !== 'none') {
        hero.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        hero.classList.add('hero-story-pulse');
        setTimeout(() => hero.classList.remove('hero-story-pulse'), 3500);
      }
    }
  }, 300);
}

window.flotopicSelectGenre = function(genre) {
  localStorage.setItem('flotopic_genre_selected', '1');
  currentGenre = genre;
  savePrefs({...loadPrefs(), genre: currentGenre});
  if (typeof syncGenreToCloud === 'function') syncGenreToCloud(currentGenre);
  // interests として DynamoDB users テーブルにも保存（パーソナライズ基盤）
  if (typeof syncProfileToServer === 'function') syncProfileToServer({ interests: [genre] });
  document.querySelectorAll('.genre-btn').forEach(btn => btn.classList.toggle('active', btn.dataset.genre === currentGenre));
  currentPage = 1;
  updateIndexOGP(currentGenre);
  renderTopics(allTopics);
  dismissGenreOnboarding();
};

window.flotopicSkipGenreOnboarding = function() {
  localStorage.setItem('flotopic_genre_selected', '1');
  dismissGenreOnboarding();
};


// 前回訪問から新着があったトピックを強調するストリップ（返ってきたユーザー向け）
function renderReturnStrip(topics) {
  const existing = document.getElementById('return-strip');
  if (existing) existing.remove();
  if (!Object.keys(_prevSnap).length) return; // 初回訪問はスキップ
  const moved = (topics || [])
    .filter(t => (t._deltaCnt || 0) > 0 && t.lifecycleStatus !== 'archived')
    .sort((a, b) => (b._deltaCnt || 0) - (a._deltaCnt || 0))
    .slice(0, 3);
  if (!moved.length) return;
  const hotEl = document.getElementById('hot-strip');
  const grid  = document.getElementById('topics-grid');
  if (!grid) return;
  const strip = document.createElement('section');
  strip.id = 'return-strip';
  strip.className = 'hot-strip return-strip';
  strip.innerHTML = `
    <div class="hot-strip-header">📣 前回から新着あり</div>
    <div class="hot-strip-chips">
      ${moved.map(t => `<a href="topic.html?id=${esc(t.topicId)}" class="hot-chip return-chip">+${t._deltaCnt}件 ${esc(t.generatedTitle || t.title)}</a>`).join('')}
    </div>`;
  grid.parentNode.insertBefore(strip, hotEl || grid);
}

// お気に入りトピックの最新動向ストリップ（更新があれば表示）
function renderFavStrip(topics) {
  const existingStrip = document.getElementById('fav-strip');
  if (existingStrip) existingStrip.remove();
  if (!topics || !topics.length || typeof userFavorites === 'undefined') return;

  const favTopics = topics.filter(t => userFavorites.has(t.topicId));
  if (!favTopics.length) return;

  const updated = favTopics.filter(t => typeof isFavUpdated === 'function' && isFavUpdated(t));
  const displayList = updated.length ? updated : favTopics.slice(0, 3);

  const grid = document.getElementById('topics-grid');
  if (!grid) return;
  const strip = document.createElement('section');
  strip.id = 'fav-strip';
  strip.className = 'fav-strip';
  strip.innerHTML = `
    <div class="hot-strip-header">⭐ お気に入り${updated.length ? `（${updated.length}件更新あり）` : ''}</div>
    <div class="hot-strip-chips">
      ${displayList.map(t => {
        const hasUpdate = typeof isFavUpdated === 'function' && isFavUpdated(t);
        return `<a href="topic.html?id=${esc(t.topicId)}" class="hot-chip${hasUpdate ? ' fav-chip-updated' : ''}">${esc(t.generatedTitle || t.title)}${hasUpdate ? ' <span class="fav-new-dot">●</span>' : ''}</a>`;
      }).join('')}
    </div>`;
  grid.parentNode.insertBefore(strip, grid);
}

function renderQuickNews(topics) {
  const existing = document.getElementById('quick-news-strip');
  if (existing) existing.remove();
  const grid = document.getElementById('topics-grid');
  if (!grid) return;

  const nowSec = Date.now() / 1000;
  const isGenresOnlySogo = t => { const g = t.genres || (t.genre ? [t.genre] : []); return g.length === 1 && g[0] === '総合'; };
  const candidates = (topics || [])
    .filter(t =>
      t.lifecycleStatus !== 'archived' &&
      toUnixSec(t.lastArticleAt || t.lastUpdated) >= nowSec - 86400 &&
      Number(t.velocityScore || 0) >= CONFIG.HOT_STRIP_MIN_VELOCITY &&
      Number(t.diversityScore || 0) >= 1.5 &&
      !isGenresOnlySogo(t) &&
      t.generatedSummary
    )
    .sort((a, b) => Number(b.velocityScore || 0) - Number(a.velocityScore || 0))
    .slice(0, 3);
  if (!candidates.length) return;

  const strip = document.createElement('section');
  strip.id = 'quick-news-strip';
  strip.className = 'quick-news-strip';
  strip.innerHTML = `
    <div class="hot-strip-header">⚡ 過去24時間の急展開</div>
    ${candidates.map(t => {
      const h = Math.floor((nowSec - toUnixSec(t.lastArticleAt || t.lastUpdated)) / 3600);
      const timeLabel = h < 1 ? '1時間以内' : `${h}時間前`;
      const cnt = t.articleCount || 0;
      return `<a href="topic.html?id=${esc(t.topicId)}" class="qn-item">
        <div class="qn-meta">${cnt ? `📄 ${cnt}件` : ''} · ${timeLabel}更新</div>
        <div class="qn-title">${esc(t.generatedTitle || t.title)}</div>
      </a>`;
    }).join('')}`;
  grid.parentNode.insertBefore(strip, grid);
}

function updateMypageBadge(topics) {
  const btn = document.getElementById('bn-mypage');
  if (!btn || typeof userFavorites === 'undefined' || !userFavorites.size) return;
  try {
    const lastVisitSec = Number(localStorage.getItem('flotopic_last_mypage_visit') || 0);
    if (!lastVisitSec) return;
    const toSec = v => { if (!v) return 0; const n = Number(v); if (!isNaN(n) && n > 1e9) return n; const t = new Date(v).getTime(); return isNaN(t) ? 0 : t / 1000; };
    const hasNew = topics.some(t => userFavorites.has(t.topicId) && toSec(t.lastUpdated) > lastVisitSec);
    btn.classList.toggle('has-badge', hasNew);
  } catch {}
}

function showTrendingBanner(topics) {
  const grid = document.getElementById('topics-grid');
  if (!grid) return;
  const existing = document.getElementById('trending-banner');
  if (existing) existing.remove();
  const rising = (topics || [])
    .filter(t => { const g = t.genres || (t.genre ? [t.genre] : []); const sogoOnly = g.length === 1 && g[0] === '総合'; return t.status === 'rising' && Number(t.velocityScore || 0) >= 8 && Number(t.diversityScore || 0) >= 1.5 && !sogoOnly; })
    .sort((a, b) => Number(b.velocityScore || 0) - Number(a.velocityScore || 0))
    .slice(0, 3);
  if (!rising.length) return;
  const links = rising.map(t => {
    const raw = (t.generatedTitle || t.title || '').replace(/[｜|\/].*$/, '').trim();
    const label = raw.length > 28 ? raw.slice(0, 27) + '…' : raw;
    return `<a href="topic.html?id=${esc(t.topicId)}" class="trending-link">${esc(label)}</a>`;
  }).join(' <span class="trending-sep">/</span> ');
  const banner = document.createElement('div');
  banner.id = 'trending-banner';
  banner.className = 'trending-banner';
  banner.innerHTML = `<span class="trending-label">🔥 急上昇:</span> ${links}`;
  grid.parentNode.insertBefore(banner, grid);
}

// ===== 詳細ページ（detail.js に分割）=====
// renderDetail, renderDiscovery, trackView, updateOGP 等は detail.js を参照

// ===== 既読管理 =====
const LS_VIEWED = 'flotopic_viewed';
let viewedTopics = new Set();
function loadViewedTopics() {
  try { viewedTopics = new Set(JSON.parse(localStorage.getItem(LS_VIEWED) || '[]')); } catch {}
  // flotopic_history からも既読IDをマージ（別ルートで記録された閲覧履歴を反映）
  try {
    const hist = JSON.parse(localStorage.getItem(LS_KEYS.HISTORY) || '[]');
    for (const h of hist) if (h && h.topicId) viewedTopics.add(h.topicId);
  } catch {}
}
function markViewed(topicId) {
  viewedTopics.add(topicId);
  try {
    const arr = [...viewedTopics].slice(-200);
    localStorage.setItem(LS_VIEWED, JSON.stringify(arr));
  } catch {}
  // お気に入りの場合は既読時刻を更新（次回の「更新あり」バッジを消す）
  if (typeof userFavorites !== 'undefined' && userFavorites.has(topicId) && typeof markFavSeen === 'function') {
    const t = (typeof allTopics !== 'undefined' ? allTopics : []).find(x => x.topicId === topicId);
    if (t) markFavSeen(topicId, t.lastUpdated);
  }
}
loadViewedTopics();

// ===== ページトップへ戻るボタン =====
function initBackToTop() {
  let btn = document.getElementById('back-to-top');
  if (!btn) {
    btn = document.createElement('button');
    btn.id = 'back-to-top';
    btn.className = 'back-to-top-btn';
    btn.setAttribute('aria-label', 'ページトップへ');
    btn.innerHTML = '↑';
    document.body.appendChild(btn);
  }
  const onScroll = () => btn.classList.toggle('visible', window.scrollY > 400);
  window.addEventListener('scroll', onScroll, { passive: true });
  btn.addEventListener('click', () => window.scrollTo({ top: 0, behavior: 'smooth' }));
}

// ===== スクロール位置復元（一覧→詳細→戻る） =====
function initScrollRestoration() {
  const key = 'flotopic_scroll_pos';
  const saved = sessionStorage.getItem(key);
  if (saved) { requestAnimationFrame(() => { window.scrollTo(0, Number(saved)); sessionStorage.removeItem(key); }); }
  document.addEventListener('click', e => {
    const card = e.target.closest('.topic-card');
    if (card) sessionStorage.setItem(key, String(window.scrollY));
  });
}

// ===== 読書進捗バー（詳細ページ） =====
function initReadingProgress() {
  const bar = document.createElement('div');
  bar.id = 'reading-progress';
  bar.className = 'reading-progress-bar';
  document.body.prepend(bar);
  const update = () => {
    const total = document.documentElement.scrollHeight - window.innerHeight;
    bar.style.width = total > 0 ? `${Math.min(100, window.scrollY / total * 100)}%` : '0%';
  };
  window.addEventListener('scroll', update, { passive: true });
}

// ===== キーボードショートカット =====
function initKeyboardShortcuts() {
  let focusedIdx = -1;
  const getCards = () => [...document.querySelectorAll('.topic-card-wrapper:not(.ad-card-wrapper)')];

  document.addEventListener('keydown', e => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
      if (e.key === 'Escape') { e.target.blur(); return; }
      return;
    }
    switch (e.key) {
      case '/': {
        e.preventDefault();
        const inp = document.getElementById('search-input');
        if (inp) inp.focus();
        break;
      }
      case 'j': case 'ArrowDown': {
        const cards = getCards();
        if (!cards.length) break;
        focusedIdx = Math.min(focusedIdx + 1, cards.length - 1);
        cards[focusedIdx].scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        cards[focusedIdx].querySelector('.topic-card')?.focus();
        break;
      }
      case 'k': case 'ArrowUp': {
        const cards = getCards();
        if (!cards.length) break;
        focusedIdx = Math.max(focusedIdx - 1, 0);
        cards[focusedIdx].scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        cards[focusedIdx].querySelector('.topic-card')?.focus();
        break;
      }
      case 'Enter': {
        const cards = getCards();
        if (focusedIdx >= 0 && cards[focusedIdx]) {
          const a = cards[focusedIdx].querySelector('.topic-card');
          if (a) a.click();
        }
        break;
      }
      case 'f': {
        const btn = document.getElementById('fav-toggle-btn');
        if (btn) btn.click();
        break;
      }
      case 'Escape': {
        const modal = document.getElementById('auth-modal');
        if (modal && modal.style.display !== 'none') { modal.style.display = 'none'; }
        const inp = document.getElementById('search-input');
        if (inp && document.activeElement === inp) inp.blur();
        break;
      }
    }
  });
}

// ===== オフライン検知 =====
function initOfflineDetection() {
  window.addEventListener('offline', () => showToast('オフラインです。一部機能が制限されます。', 5000));
  window.addEventListener('online',  () => showToast('オンラインに復帰しました'));
}

// ===== ボトムナビ アクティブ制御 =====
function initBottomNav() {
  const nav = document.getElementById('bottom-nav');
  if (!nav) return;
  const path = location.pathname;
  const isIndex   = path.endsWith('index.html') || path === '/' || path.endsWith('/');
  const isMypage  = path.includes('mypage.html');
  const isCatchup = path.includes('catchup.html');

  const items = {
    'bn-home':    isIndex,
    'bn-catchup': isCatchup,
    'bn-mypage':  isMypage,
  };
  Object.entries(items).forEach(([id, active]) => {
    const el = document.getElementById(id);
    if (el && active) el.classList.add('active');
  });

  // 検索ボタン: 検索入力があればフォーカス、なければindexへ
  const searchEl = document.getElementById('bn-search');
  if (searchEl && searchEl.tagName === 'BUTTON') {
    searchEl.addEventListener('click', () => {
      const inp = document.getElementById('search-input');
      if (inp) { inp.focus(); inp.scrollIntoView({ behavior: 'smooth', block: 'center' }); }
      else location.href = 'index.html';
    });
  }
}

// ===== スケルトンローダー =====
function showSkeletonCards(gridId = 'topics-grid', count = 6) {
  const grid = document.getElementById(gridId);
  if (!grid) return;
  const skels = Array.from({ length: count }, () => `
    <div class="topic-card-wrapper skel-wrapper">
      <div class="topic-card skel-card">
        <div class="card-thumb skel-thumb skel-pulse"></div>
        <div class="card-body">
          <div class="skel-line skel-pulse" style="width:40%;height:12px;margin-bottom:8px;"></div>
          <div class="skel-line skel-pulse" style="width:90%;height:16px;margin-bottom:6px;"></div>
          <div class="skel-line skel-pulse" style="width:70%;height:16px;margin-bottom:12px;"></div>
          <div class="skel-line skel-pulse" style="width:55%;height:11px;"></div>
        </div>
      </div>
    </div>`).join('');
  grid.innerHTML = skels;
}

// ===== ページ初期化 =====
document.addEventListener('DOMContentLoaded', () => {
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js').catch(err => console.warn('SW registration failed:', err));
  }

  // index ページの page_view を analytics に送信（active 閲覧者数集計用）
  (function trackIndexView() {
    if (typeof ANALYTICS_URL === 'undefined') return;
    try {
      let anonId = localStorage.getItem('flotopic_anon_id');
      if (!anonId) {
        anonId = (crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).slice(2) + Date.now());
        localStorage.setItem('flotopic_anon_id', anonId);
      }
      fetch(ANALYTICS_URL + 'analytics/event', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ anonymousId: anonId, topicId: 'home', eventType: 'page_view' }),
      }).catch(() => {});
    } catch {}
  })();

  // PWAインストールバナー
  (function initPwaBanner() {
    if (localStorage.getItem(LS_KEYS.PWA_DISMISSED) === '1') return;

    const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
    const isStandalone = window.navigator.standalone === true;

    if (isIOS && !isStandalone) {
      // iOS Safari向け: ネイティブの beforeinstallprompt は発火しないため手動で案内
      const iosBanner = document.getElementById('pwa-ios-banner');
      const iosDismiss = document.getElementById('pwa-ios-dismiss-btn');
      if (iosBanner) iosBanner.style.display = 'flex';
      if (iosDismiss) {
        iosDismiss.addEventListener('click', () => {
          if (iosBanner) iosBanner.style.display = 'none';
          localStorage.setItem(LS_KEYS.PWA_DISMISSED, '1');
        });
      }
      return;
    }

    let deferredPrompt = null;
    const banner     = document.getElementById('pwa-install-banner');
    const installBtn = document.getElementById('pwa-install-btn');
    const dismissBtn = document.getElementById('pwa-dismiss-btn');
    window.addEventListener('beforeinstallprompt', e => {
      e.preventDefault(); deferredPrompt = e;
      if (banner) banner.style.display = 'flex';
    });
    if (installBtn) {
      installBtn.addEventListener('click', () => {
        if (!deferredPrompt) return;
        deferredPrompt.prompt();
        deferredPrompt.userChoice.then(choice => {
          if (choice.outcome === 'accepted' && banner) banner.style.display = 'none';
          deferredPrompt = null;
        });
      });
    }
    if (dismissBtn) {
      dismissBtn.addEventListener('click', () => {
        if (banner) banner.style.display = 'none';
        localStorage.setItem(LS_KEYS.PWA_DISMISSED, '1');
      });
    }
    window.addEventListener('appinstalled', () => { if (banner) banner.style.display = 'none'; deferredPrompt = null; });
  })();

  initGoogleAuth();
  initBackToTop();
  initKeyboardShortcuts();
  initOfflineDetection();
  initBottomNav();

  const topicId = new URLSearchParams(location.search).get('id');
  if (topicId) {
    initReadingProgress();
    trackView(topicId);
    const showError = () => {
      const titleEl = document.getElementById('topic-title');
      if (titleEl) titleEl.textContent = '読み込みに失敗しました';
      document.querySelectorAll('.topic-sk').forEach(el => el.remove());
      const aiEl = document.getElementById('ai-analysis');
      if (aiEl && !aiEl.querySelector('.ai-analysis-inner')) {
        aiEl.innerHTML = '<p style="color:var(--text-muted);font-size:.85rem;">データを取得できませんでした。再読み込みしてください。</p>';
      }
    };
    const refresh = async () => {
      // 1. S3静的ファイル（CloudFrontキャッシュ）
      try {
        const r = await fetch(apiUrl(`topic/${topicId}`));
        if (r.ok) {
          const ct = r.headers.get('content-type') || '';
          if (ct.includes('json')) {
            const data = await r.json();
            if (data.meta) { try { renderDetail(data); } catch(e) { console.error('renderDetail:', e); } return; }
          }
        }
      } catch(e) { console.error('topic fetch:', e); }
      // 2. DynamoDB経由（S3にない古いトピック）
      try {
        const gw = typeof _GW !== 'undefined' ? _GW : null;
        if (gw) {
          const r2 = await fetch(`${gw}/topic/${topicId}`);
          if (r2.ok) {
            const data2 = await r2.json();
            if (data2.meta) { try { renderDetail(data2); } catch(e) { console.error('renderDetail(fallback):', e); } return; }
          }
        }
      } catch(e) { console.error('topic fallback:', e); }
      // 3. topics.jsonからメタデータのみ（最終手段）
      try {
        const r3 = await fetch(apiUrl('topics'));
        if (!r3.ok) { showError(); return; }
        const d3 = await r3.json();
        const t = (d3.topics || []).find(t => t.topicId === topicId);
        if (t) { try { renderDetail({ meta: t, timeline: [], views: [] }); } catch(e) { console.error('renderDetail (fallback):', e); showError(); } return; }
      } catch(e) { console.error('topics fallback fetch:', e); }
      showError();
    };
    refresh();
    setInterval(refresh, CONFIG.REFRESH_INTERVAL_MS);
    loadComments(topicId);
    setupCommentForm(topicId);
    setInterval(() => loadComments(topicId), 3 * 60 * 1000);
  } else if (document.getElementById('topics-grid')) {
    // URLパラメータ ?q= からの検索クエリを初期値として設定（Google SearchAction対応）
    const _urlParams = new URLSearchParams(location.search);
    const urlQ = _urlParams.get('q');
    if (urlQ) {
      currentSearch = urlQ.trim();
      const si = document.getElementById('search-input');
      if (si) si.value = currentSearch;
    }
    // ?focus=search — 他ページの検索ナビから遷移時に検索欄をフォーカス
    if (_urlParams.get('focus') === 'search') {
      setTimeout(() => {
        const si = document.getElementById('search-input');
        if (si) { si.scrollIntoView({ behavior: 'smooth', block: 'center' }); si.focus(); }
      }, 600);
    }
    buildFilters();
    setupSearch();
    setupFavsToggle();
    initScrollRestoration();
    showSkeletonCards();
    loadFavorites().finally(() => {
      if (typeof loadCloudHistory === 'function') loadCloudHistory();
      // クラウドから保存ジャンルを復元（非同期・先にローカル設定でリフレッシュ後に適用）
      if (typeof loadGenreFromCloud === 'function' && currentUser) {
        loadGenreFromCloud().then(savedGenre => {
          if (savedGenre && typeof GENRES !== 'undefined' && GENRES.includes(savedGenre) && savedGenre !== currentGenre && !_prefs.genre) {
            currentGenre = savedGenre;
            savePrefs({...loadPrefs(), genre: currentGenre});
            buildFilters();
            renderTopics(allTopics);
          }
        }).catch(() => {});
      }
      refreshTopics();
      setInterval(refreshTopics, CONFIG.REFRESH_INTERVAL_MS);
      setInterval(updateFreshnessDisplay, CONFIG.FRESHNESS_INTERVAL_MS);
      // タブ非表示→復帰時に古くなったデータを即更新（5分以上経過していれば）
      document.addEventListener('visibilitychange', () => {
        if (!document.hidden && lastFetchTime && (Date.now() - lastFetchTime) > CONFIG.REFRESH_INTERVAL_MS) {
          refreshTopics();
        }
      });
    });
  }
});
