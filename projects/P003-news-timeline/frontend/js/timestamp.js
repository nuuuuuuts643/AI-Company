// frontend/js/timestamp.js
// detail.js / app.js が混在で扱う timestamp フォーマットを 1 箇所で正規化する。
// なぜ作ったか: SNAP[*].timestamp は ISO 文字列、article.publishedAt は Unix 秒整数、
// predictionMadeAt は ISO 文字列、と書き込み元が複数あり、`new Date(v)` を生で
// 呼ぶと Unix 秒（例: 1746097800）が 1970 年代に解釈される事故が起きていた。
// (例: cc7f78cd55b81da6 の「スナップショットのタイミングがおかしい」報告)
//
// 設計原則:
//  - 任意の timestamp 入力 (ISO 文字列 / Unix 秒整数 / Unix ミリ秒 / Date) を
//    必ず Unix ミリ秒整数に正規化する toMs() を提供する。
//  - 1970 年代 / 35 年以上未来は『ありえない値』として _warnBadTs() で警告ログ。
//  - DOM/window/document を参照しない（Node テスト可能）。

(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    const exported = factory();
    root.Timestamp = exported;
    // detail.js から `toMs(v)` で呼べるように global にも置く。
    // 既に同名関数が定義されている場合は上書きしない（後方互換）。
    if (typeof root.toMs === 'undefined') root.toMs = exported.toMs;
    if (typeof root._warnBadTs === 'undefined') root._warnBadTs = exported._warnBadTs;
  }
}(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  /**
   * 任意の timestamp 入力を Unix ミリ秒整数に正規化する。
   * 失敗時は 0 を返す（new Date(0) で 1970-01-01 になるが、呼び元側で
   * ガードする想定。toMs(v) > 0 が「有効な timestamp が得られた」シグナル）。
   *
   * 判定境界:
   *   1e9 < n < 1e12 → Unix 秒整数 → ms へ変換 (× 1000)
   *   n >= 1e12      → 既にミリ秒なのでそのまま
   *   n <= 1e9       → ISO 文字列扱い (new Date(v))
   *   非数           → ISO 文字列扱い (new Date(v))
   *
   * @param {string|number|Date|null|undefined} v
   * @returns {number} Unix ミリ秒、または 0
   */
  function toMs(v) {
    if (v == null || v === '') return 0;
    if (v instanceof Date) {
      const t = v.getTime();
      return isNaN(t) ? 0 : t;
    }
    if (typeof v === 'number') {
      if (!isFinite(v) || v <= 0) return 0;
      // Unix 秒 (10 桁) → ms に変換 (1e9 = 2001-09-09, 1e12 = 2001-09-09 ms)
      if (v > 1e9 && v < 1e12) return v * 1000;
      // ms 以上はそのまま
      if (v >= 1e12) return v;
      // 1e9 以下の正数は ms にしても 1970 年付近の bogus 値になるため 0 を返す
      return 0;
    }
    // 文字列: 数字だけなら Number 変換で再帰、それ以外は ISO/RFC として new Date
    const s = String(v).trim();
    if (!s) return 0;
    if (/^-?\d+(\.\d+)?$/.test(s)) {
      const n = Number(s);
      return toMs(n);
    }
    const t = new Date(s).getTime();
    return isNaN(t) ? 0 : t;
  }

  /**
   * timestamp が異常（1970 年代 or 35 年以上未来）であれば console.warn を出す。
   * 復旧は呼び元側で行う（この関数は副作用を出さない検知のみ）。
   *
   * @param {string} label - 出力に含めるラベル（例: 'snap.timestamp'）
   * @param {*} raw - 元の入力値
   * @param {number} msVal - toMs() で正規化した結果
   * @returns {boolean} 異常だったか
   */
  function _warnBadTs(label, raw, msVal) {
    if (!msVal || !isFinite(msVal)) return false;
    const yr = new Date(msVal).getFullYear();
    const futureLimit = new Date().getFullYear() + 5;
    if (yr < 2020 || yr > futureLimit) {
      try {
        console.warn(
          '[Flotopic] Bad timestamp (' + label + '): raw=' +
          JSON.stringify(raw) + ' → ' + yr + '年 (msVal=' + msVal + ')'
        );
      } catch (e) { /* console 不在環境（テスト等）は無視 */ }
      return true;
    }
    return false;
  }

  return { toMs, _warnBadTs };
}));
