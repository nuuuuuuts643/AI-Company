// frontend/js/formatters.js
// app.js から純粋な整形ロジックを抽出した、Node/Browser 両対応モジュール。
// テスト容易性を上げるため、ここにある関数は副作用を持たない。
//
// 設計原則:
//  - null/undefined/0/NaN/未来日付は『無効』として扱い、無害な戻り値（空文字 or 既定値）を返す。
//  - 例外を投げない（UI に未処理エラーが漏れない）。
//  - DOM/window/document を参照しない。

(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.Formatters = factory();
  }
}(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  /**
   * HTML 特殊文字をエスケープする。null/undefined → '' で安全に返す。
   */
  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  /**
   * Markdown / リスト / 連続改行を取り除き、1 行サマリにする。
   */
  function cleanSummary(s) {
    if (s == null || s === '') return s;
    return String(s)
      .replace(/^#{1,3}\s+.+?\n+/gm, '')
      .replace(/^[-*]\s+/gm, '')
      .replace(/^\d+\.\s+/gm, '')
      .replace(/\n{2,}/g, ' ')
      .replace(/\n/g, ' ')
      .trim();
  }

  /**
   * 任意の日付入力（ISO 文字列 / Unix 秒 / Date）を ja-JP の
   * 「M/D HH:MM」表示にする。無効入力は '' を返す（UI に "Invalid Date" を漏らさない）。
   */
  function formatDate(input) {
    if (input == null || input === '' || input === 0 || input === '0') return '';
    let d;
    try {
      if (typeof input === 'number') {
        // 1e9 以下はミリ秒スケールでも先史時代になるので無効扱い。
        if (input < 1e9) return '';
        // 秒・ミリ秒の両対応（>= 1e12 なら ms とみなす）
        d = new Date(input >= 1e12 ? input : input * 1000);
      } else if (input instanceof Date) {
        d = input;
      } else {
        d = new Date(input);
      }
      if (isNaN(d.getTime())) return '';
      // 1990 年以前は epoch=0 起源の bogus 値とみなす
      if (d.getFullYear() < 1990) return '';
      // 未来日付は「タイムゾーンずれ等の異常値」として無効扱い
      if (d.getTime() > Date.now() + 365 * 24 * 3600 * 1000) return '';
      return d.toLocaleString('ja-JP', {
        month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit',
      });
    } catch (e) {
      return '';
    }
  }

  /**
   * 数値を 3 桁区切りで返す。NaN/null/undefined は '0'、負数は '-' 付きで返す。
   */
  function formatNumber(n) {
    if (n == null || n === '') return '0';
    const num = Number(n);
    if (!Number.isFinite(num)) return '0';
    return num.toLocaleString('ja-JP');
  }

  /**
   * Unix 秒/ミリ秒/ISO 文字列を Unix 秒に正規化する。失敗時 0。
   */
  function toUnixSec(v) {
    if (!v) return 0;
    const n = Number(v);
    if (!isNaN(n) && n > 1e9) return n >= 1e12 ? Math.floor(n / 1000) : n;
    const t = new Date(v).getTime();
    return isNaN(t) ? 0 : Math.floor(t / 1000);
  }

  /**
   * タイトル末尾の媒体名サフィックス（「 - 朝日新聞」「（NHK）」等）を 1 つ取り除く。
   */
  function stripMediaSuffix(raw) {
    if (raw == null || raw === '') return '';
    return String(raw)
      .replace(/\s*[-｜|]\s*[^-｜|]{2,32}$/u, '')
      .replace(/\s*（[^（）]{2,16}）\s*$/u, '')
      .trim();
  }

  /**
   * 「キーワードチップに出すに値する語かどうか」を判定する。
   * KEYWORD_BLACKLIST は呼び出し側から差し込み可能（テスト容易化）。
   */
  function isMeaningfulKeyword(word, blacklist) {
    if (word == null) return false;
    const w = String(word).trim();
    if (!w) return false;
    if (w.length < 2) return false;
    if (blacklist && typeof blacklist.has === 'function' && blacklist.has(w)) return false;
    if (/^[぀-ゟ]{2,3}$/.test(w)) return false;
    return true;
  }

  /**
   * URL を https に強制する（mixed content 防止）。
   */
  function safeImgUrl(url) {
    if (url == null || url === '') return '';
    return String(url).replace(/^http:\/\//i, 'https://');
  }

  return {
    esc,
    cleanSummary,
    formatDate,
    formatNumber,
    toUnixSec,
    stripMediaSuffix,
    isMeaningfulKeyword,
    safeImgUrl,
  };
}));
