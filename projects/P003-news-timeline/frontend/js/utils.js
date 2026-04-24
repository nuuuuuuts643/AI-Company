// frontend/js/utils.js
// テスト可能な純粋ユーティリティ関数
// app.js から参照される定数・関数群。ブラウザ/Node 両環境で動作する。

const CONFIG = {
  HOT_STRIP_HOURS: 2,           // 今急上昇中セクションの対象時間（時間）
  NEW_BADGE_HOURS: 1,           // NEWバッジを表示する最大経過時間（時間）
  AD_CARD_INTERVAL: 10,         // 広告を挿入する間隔（カード枚数）
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

// utils.js から — ブラウザでは何もしない、Node では export
if (typeof module !== 'undefined') {
  module.exports = { CONFIG, LS_KEYS, relativeTime, isNewTopic, isHotTopic };
}
