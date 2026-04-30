// frontend/js/viewed_history.js
// T2026-0501-B: 既読トピックの「新着あり」判定 — 純粋関数として抽出。
// 主旨: 一度閲覧したトピックでも viewedAt 後に新記事が追加されたらグレーアウト解除し
//       「続報あり」バッジを出す (PO 指摘: 別デバイスログイン後の同期 + グレーアウトリセット)。
//
// 設計原則:
//  - viewedAtMs=0 (legacy sentinel) / undefined / null → 続報判定しない (false)
//  - lastArticleValue=null/undefined/0/'' → false (lastArticleAt 未設定トピックは判定対象外)
//  - lastArticleValue は unix sec (number > 1e9) または ISO 文字列を受け付ける (toUnixSec が両対応)
//  - viewedAtMs は millis 単位、lastArticleAt は seconds → 比較時に lastSec*1000 に揃える
//
// loadViewedMap:
//  - flotopic_history (cloud-synced, viewedAt 付) を一次ソースとして Map を構築
//  - flotopic_viewed (legacy Set, タイムスタンプ無) は history に無い ID のみ補う (sentinel=0)
//  - sentinel=0 は「見たことはあるが時刻不明」→ topicHasNewArticles で false を返し
//    legacy ユーザーで一斉に続報あり化させない (互換性のための設計)。

(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.ViewedHistory = factory();
  }
}(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  function toUnixSec(v) {
    if (v === null || v === undefined || v === '') return 0;
    const n = Number(v);
    if (!isNaN(n) && n > 1e9) return n;
    const t = new Date(v).getTime();
    return isNaN(t) ? 0 : t / 1000;
  }

  function hasNewArticlesAfter(viewedAtMs, lastArticleValue) {
    if (!viewedAtMs || viewedAtMs <= 0) return false;
    const lastSec = toUnixSec(lastArticleValue);
    if (!lastSec) return false;
    return lastSec * 1000 > viewedAtMs;
  }

  function loadViewedMap(historyJson, legacyJson) {
    const map = new Map();
    let hist = [];
    try { hist = JSON.parse(historyJson || '[]'); } catch { hist = []; }
    if (Array.isArray(hist)) {
      for (const h of hist) {
        if (!h || !h.topicId) continue;
        const ts = Number(h.viewedAt);
        map.set(h.topicId, Number.isFinite(ts) && ts > 0 ? ts : 0);
      }
    }
    let legacy = [];
    try { legacy = JSON.parse(legacyJson || '[]'); } catch { legacy = []; }
    if (Array.isArray(legacy)) {
      for (const id of legacy) {
        if (id && !map.has(id)) map.set(id, 0);
      }
    }
    return map;
  }

  // クラウド側 history と localStorage history のマージ。
  // topicId 重複は viewedAt 新しい方を残す。
  function mergeHistory(cloudItems, localItems) {
    const all = [];
    if (Array.isArray(cloudItems)) all.push(...cloudItems);
    if (Array.isArray(localItems)) all.push(...localItems);
    const acc = [];
    for (const item of all) {
      if (!item || !item.topicId) continue;
      const existing = acc.find(a => a.topicId === item.topicId);
      if (!existing) {
        acc.push({ ...item });
      } else if ((item.viewedAt || 0) > (existing.viewedAt || 0)) {
        Object.assign(existing, item);
      }
    }
    acc.sort((a, b) => (b.viewedAt || 0) - (a.viewedAt || 0));
    return acc;
  }

  return { hasNewArticlesAfter, loadViewedMap, mergeHistory, toUnixSec };
}));
