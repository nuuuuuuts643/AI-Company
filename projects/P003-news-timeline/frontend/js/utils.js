// frontend/js/utils.js
// テスト可能な純粋ユーティリティ関数
// app.js から参照される定数・関数群。ブラウザ/Node 両環境で動作する。

const CONFIG = {
  HOT_STRIP_HOURS: 6,           // 今急上昇中セクションの対象時間（時間）
  NEW_BADGE_HOURS: 1,           // NEWバッジを表示する最大経過時間（時間）
  AD_CARD_INTERVAL: 5,          // 広告を挿入する間隔（カード枚数）
  FRESHNESS_INTERVAL_MS: 60000, // 鮮度表示テキストの更新間隔（ミリ秒）
  TOPICS_PER_PAGE: 20,          // 1ページに表示するトピック数
};

const LS_KEYS = {
  FAVORITES:    'flotopic_favorites',
  HISTORY:      'flotopic_history',
  AVATAR:       'flotopic_avatar',
  PROFILE_SET:  'flotopic_profile_set',
  DARK_MODE:    'flotopic_dark',
  PREFS:        'flotopic_prefs',
  PWA_DISMISSED:'pwa_dismissed',
};

/**
 * Unix秒タイムスタンプを相対時間文字列に変換する
 * app.js の updateFreshnessDisplay() 内のロジックを抽出
 * @param {number|null} unixSec - Unix秒タイムスタンプ
 * @returns {string}
 */
function relativeTime(unixSec) {
  if (unixSec == null) return 'たった今更新';
  const diffMin = Math.floor((Date.now() / 1000 - Number(unixSec)) / 60);
  const diffH   = Math.floor(diffMin / 60);
  const diffD   = Math.floor(diffH   / 24);
  if (diffMin < 1)       return 'たった今更新';
  else if (diffMin < 60) return `${diffMin}分前に更新`;
  else if (diffH  < 24)  return `${diffH}時間前に更新`;
  else                   return `${diffD}日前に更新`;
}

/**
 * トピックがNEWバッジ対象かどうかを返す
 * app.js の renderBadges() 内のロジックに対応
 * @param {Object} topic
 * @returns {boolean}
 */
function isNewTopic(topic) {
  if (!topic.lastUpdated || Number(topic.lastUpdated) === 0) return false;
  const nowSec = Date.now() / 1000;
  return nowSec - Number(topic.lastUpdated) < CONFIG.NEW_BADGE_HOURS * 3600;
}

/**
 * トピックがhot-strip（今急上昇中）対象かどうかを返す
 * app.js の renderHotStrip() 内のフィルタロジックに対応
 * @param {Object} topic
 * @returns {boolean}
 */
function isHotTopic(topic) {
  if (!topic.lastUpdated || Number(topic.lastUpdated) === 0) return false;
  const nowSec = Date.now() / 1000;
  return nowSec - Number(topic.lastUpdated) < CONFIG.HOT_STRIP_HOURS * 3600;
}

/**
 * URL を <a href> / src 等にレンダーする前にスキーム検証する。
 * T2026-0502-SEC11 (2026-05-02): 旧実装は esc() で HTML entity escape のみ行い、
 * `javascript:`/`data:`/`vbscript:` 等の dangerous scheme を block していなかった。
 * RSS 由来の article URL に javascript: が混入すると clicked XSS が発火する。
 *
 * @param {string} url - 任意の URL 文字列
 * @returns {string} 安全な URL ('#' フォールバック含む)
 */
function safeHref(url) {
  if (url == null) return '#';
  const s = String(url).trim();
  if (!s) return '#';
  // 許可: http(s):// 絶対 URL、/ 始まりの相対 URL、# 始まりの fragment、? 始まりの query
  // 拒否: javascript:, data:, vbscript:, file:, blob: 等
  if (/^(https?:\/\/|\/|#|\?)/i.test(s)) return s;
  // mailto: も明示的に許可 (将来 contact link 用途で使う場合)
  if (/^mailto:/i.test(s)) return s;
  return '#';
}

/**
 * 画像 src を安全に整形する。http:// は https:// に昇格、それ以外の dangerous scheme は ''。
 * T2026-0502-SEC11 (2026-05-02): 旧 safeImgUrl は scheme 検証なしだった。
 * <img src> の javascript: は modern browser では発火しないが、defense in depth として block。
 */
function safeImgUrl(url) {
  if (url == null) return '';
  const s = String(url).trim();
  if (!s) return '';
  // http(s) のみ許可。http は https に昇格。
  if (/^https?:\/\//i.test(s)) return s.replace(/^http:\/\//i, 'https://');
  // / 始まりの相対 URL も許可 (自社配信)
  if (s.startsWith('/')) return s;
  return '';
}

// utils.js から — ブラウザでは何もしない、Node では export
if (typeof module !== 'undefined') {
  module.exports = { CONFIG, LS_KEYS, relativeTime, isNewTopic, isHotTopic, safeHref, safeImgUrl };
}
