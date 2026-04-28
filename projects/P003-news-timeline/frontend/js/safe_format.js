// safe_format.js — 汎用の安全フォーマッタ集
// 「無効な値が UI に漏れる」事故を物理的に防ぐためのライブラリ。
// 任意のプロジェクトで再利用可能 (Node も Browser も両対応の UMD パターン)。
//
// 設計原則:
//   - 関数は『無効入力 → ''/null/false』を必ず返す。例外ではなく明示的に。
//   - 「0 を valid とする」or「0 を無効とする」をフラグで分けず、
//     用途別に別関数を提供することで呼び出し側の判断ミスを消す。
//   - 1970-01-01 周辺の epoch 値は『timestamp が来てない』のサインとして無効扱い。

(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.SafeFormat = factory();
  }
}(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  /**
   * 日時 (Unix秒 / ISO文字列 / Date) を経過時間表記にする。
   * - 0/null/undefined/空文字 → '' (UI に漏らさない)
   * - 1990年以前の Date → '' (epoch=0 由来の偽装値ガード)
   * - <1h: N分前 / <24h: N時間前 / <7日: N日前 / それ以上: YYYY/M/D
   */
  function fmtElapsed(input) {
    if (input === 0 || input === '0' || input === null || input === undefined || input === '') {
      return '';
    }
    try {
      const d = typeof input === 'number'
        ? new Date(input * 1000)
        : (input instanceof Date ? input : new Date(input));
      if (isNaN(d)) return '';
      if (d.getFullYear() < 1990) return '';  // epoch=0 由来の 1970-01-01 ガード
      const diff = (Date.now() - d.getTime()) / 1000;
      if (diff < 0) return '';  // 未来の日付は無効扱い (タイムゾーンミスマッチ等)
      if (diff < 3600)   return `${Math.floor(diff / 60)}分前`;
      if (diff < 86400)  return `${Math.floor(diff / 3600)}時間前`;
      if (diff < 604800) return `${Math.floor(diff / 86400)}日前`;
      return `${d.getFullYear()}/${d.getMonth() + 1}/${d.getDate()}`;
    } catch (e) {
      return '';
    }
  }

  /**
   * カウンタ表示 (件数等)。0 / 不明値は null 返却で『表示しない』を明示する。
   * 「0件」表示が誤情報になるケースが多いので、0 は null 扱いがデフォルト。
   * 「0件」を明示したい場合は formatCountAllowZero を使う。
   */
  function formatCount(input, suffix = '件') {
    const n = parseInt(input, 10);
    if (!Number.isFinite(n) || n <= 0) return null;
    return `${n}${suffix}`;
  }

  /** 0 を valid とする counter フォーマット。在庫=0 等の本物の 0 用。 */
  function formatCountAllowZero(input, suffix = '件') {
    const n = parseInt(input, 10);
    if (!Number.isFinite(n) || n < 0) return null;
    return `${n}${suffix}`;
  }

  /**
   * メタ行のドット連結。null/'' を自動除去。空配列なら null 返却で
   * 呼び出し側が「メタ行ごと省略するか、フォールバック文言にすり替え」できる。
   * @example join(['🔴','5件','3時間前']) → '🔴 · 5件 · 3時間前'
   * @example join([null, null, '']) → null
   */
  function join(parts, separator = ' · ') {
    if (!Array.isArray(parts)) return null;
    const filtered = parts.filter(p => p !== null && p !== undefined && p !== '');
    if (filtered.length === 0) return null;
    return filtered.join(separator);
  }

  /**
   * lifecycleStatus → 状態ドット。未指定時は '' で「ドット表示しない」を明示。
   */
  function lifecycleDot(status) {
    if (status === 'active')   return '🔴';
    if (status === 'cooling')  return '🟡';
    if (status === 'archived') return '⚪';
    return '';
  }

  return {
    fmtElapsed,
    formatCount,
    formatCountAllowZero,
    join,
    lifecycleDot,
  };
}));
