// frontend/js/build_filters.js
// app.js の buildFilters() から純粋ロジックを抽出した、Node/Browser 両対応モジュール。
// テスト容易性を上げるため、ここにある関数は副作用を持たない（DOM/window 非参照）。
//
// 設計原則:
//  - topics が空・counts が空・全ジャンル 0 件などの境界条件で必ず非空配列を返す
//    （フィルタが UI から全ボタンを消す事故を防ぐ — 空タブ表示の物理ガード）。
//  - '総合' は常時表示。currentGenre も件数 0 でも残す（クリック直後に消えると体験が壊れる）。
//  - 旧 genre (経済/教育/文化/環境) は新 genre にマージしてカウントする。

(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.BuildFilters = factory();
  }
}(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  const DEFAULT_LEGACY_MAP = {
    '経済': 'ビジネス',
    '教育': 'くらし',
    '文化': 'くらし',
    '環境': 'くらし',
  };

  /**
   * topics 配列からジャンル別件数を計算する。
   *  - lifecycleStatus === 'archived' は除外。
   *  - 1 トピックが複数ジャンルを持つ場合、各ジャンルに 1 ずつ加算（重複排除あり）。
   *  - 旧ジャンル名は legacyMap で新ジャンル名に正規化。
   * @param {Array} topics
   * @param {Object} [legacyMap]
   * @returns {Object} { genre: count }
   */
  function computeGenreCounts(topics, legacyMap) {
    const map = legacyMap || DEFAULT_LEGACY_MAP;
    const counts = {};
    if (!Array.isArray(topics)) return counts;
    for (const t of topics) {
      if (!t || t.lifecycleStatus === 'archived') continue;
      const gs = Array.isArray(t.genres) ? t.genres : (t.genre ? [t.genre] : []);
      const seen = new Set();
      for (const raw of gs) {
        if (!raw) continue;
        const g = map[raw] || raw;
        if (!seen.has(g)) {
          counts[g] = (counts[g] || 0) + 1;
          seen.add(g);
        }
      }
    }
    return counts;
  }

  /**
   * 表示すべきジャンルボタンの順序付き配列を返す。
   *  - allGenres の順序を維持しつつ、件数 0 のジャンルは省く。
   *  - '総合' と currentGenre は件数 0 でも必ず含める（UX ガード）。
   *  - 想定外の入力（topics=null, counts={}, allGenres=空）でも必ず ['総合'] を返す。
   * @param {Array} topics            allTopics 相当
   * @param {string} [currentGenre]   現在選択中のジャンル
   * @param {Array<string>} [allGenres] 全ジャンルの順序定義
   * @param {Object} [legacyMap]      旧→新ジャンル名マップ
   * @returns {Array<string>} 表示するジャンル名の配列（必ず非空）
   */
  function computeVisibleGenres(topics, currentGenre, allGenres, legacyMap) {
    const cur = currentGenre || '総合';
    const genres = (Array.isArray(allGenres) && allGenres.length) ? allGenres : ['総合'];
    const counts = computeGenreCounts(topics, legacyMap);
    const visible = genres.filter(g => g === '総合' || g === cur || (counts[g] || 0) > 0);
    if (visible.length === 0) return ['総合'];
    return visible;
  }

  return { computeGenreCounts, computeVisibleGenres, DEFAULT_LEGACY_MAP };
}));
