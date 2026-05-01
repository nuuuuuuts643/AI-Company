// tests/unit/timestamp.test.js
// frontend/js/timestamp.js の境界値テスト
// (T2026-0501-TS: SNAP[*].timestamp ISO / publishedAt Unix秒 / predictionMadeAt ISO の
//  混在フォーマットを 1 関数で正規化する)

const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const { toMs, _warnBadTs } = require('../../frontend/js/timestamp');

describe('toMs() — null / 空文字 / 0', () => {
  it('null → 0', () => assert.equal(toMs(null), 0));
  it('undefined → 0', () => assert.equal(toMs(undefined), 0));
  it('空文字 → 0', () => assert.equal(toMs(''), 0));
  it('0 (数値) → 0', () => assert.equal(toMs(0), 0));
  it('"0" (文字列) → 0', () => assert.equal(toMs('0'), 0));
});

describe('toMs() — Unix 秒 (10桁整数)', () => {
  it('1746097800 → 1746097800000 (秒×1000)', () => {
    assert.equal(toMs(1746097800), 1746097800 * 1000);
  });
  it('1e9 + 1 (秒の下限近傍) → ms に変換', () => {
    assert.equal(toMs(1e9 + 1), (1e9 + 1) * 1000);
  });
  it('1e12 - 1 (秒の上限近傍) → ms に変換', () => {
    const v = 1e12 - 1;
    assert.equal(toMs(v), v * 1000);
  });
  it('"1746097800" (秒の文字列) → 1746097800000', () => {
    assert.equal(toMs('1746097800'), 1746097800 * 1000);
  });
});

describe('toMs() — Unix ミリ秒 (13桁整数)', () => {
  it('1e12 → そのまま (ms 境界)', () => {
    assert.equal(toMs(1e12), 1e12);
  });
  it('1746097800000 → そのまま', () => {
    assert.equal(toMs(1746097800000), 1746097800000);
  });
  it('"1746097800000" (ms の文字列) → そのまま', () => {
    assert.equal(toMs('1746097800000'), 1746097800000);
  });
});

describe('toMs() — 1e9 以下の数値 (1970年代に解釈される値) は無効扱い', () => {
  it('1 → 0 (1970-01-01 起源を avoid)', () => assert.equal(toMs(1), 0));
  it('1000 → 0', () => assert.equal(toMs(1000), 0));
  it('1e9 → 0 (境界: ちょうど 1e9 は秒として扱わない)', () => assert.equal(toMs(1e9), 0));
  it('"1000" → 0', () => assert.equal(toMs('1000'), 0));
  it('-1 (負数) → 0', () => assert.equal(toMs(-1), 0));
});

describe('toMs() — ISO 文字列', () => {
  it('"2026-05-01T11:15:00+00:00" → 正しい ms', () => {
    const ms = toMs('2026-05-01T11:15:00+00:00');
    assert.equal(ms, Date.UTC(2026, 4, 1, 11, 15, 0));
  });
  it('"2026-05-01" (日付のみ) → 0時 UTC の ms', () => {
    const ms = toMs('2026-05-01');
    assert.equal(ms, Date.UTC(2026, 4, 1, 0, 0, 0));
  });
  it('"invalid date string" → 0', () => assert.equal(toMs('invalid date string'), 0));
  it('"2026-05-01T11:15:00.123Z" → 正しい ms (ms 含む)', () => {
    const ms = toMs('2026-05-01T11:15:00.123Z');
    assert.equal(ms, Date.UTC(2026, 4, 1, 11, 15, 0, 123));
  });
});

describe('toMs() — Date オブジェクト', () => {
  it('Date(2026,4,1) → そのインスタンスの getTime()', () => {
    const d = new Date(Date.UTC(2026, 4, 1));
    assert.equal(toMs(d), d.getTime());
  });
  it('new Date(NaN) → 0', () => {
    assert.equal(toMs(new Date(NaN)), 0);
  });
});

describe('toMs() — 異常値', () => {
  it('NaN → 0', () => assert.equal(toMs(NaN), 0));
  it('Infinity → 0', () => assert.equal(toMs(Infinity), 0));
  it('-Infinity → 0', () => assert.equal(toMs(-Infinity), 0));
  it('オブジェクト → 0 ({} は Invalid Date)', () => assert.equal(toMs({}), 0));
  it('配列 → 0', () => assert.equal(toMs([]), 0));
});

describe('toMs() — 未来日付 (5 年後相当)', () => {
  it('2031 年 ISO → 解析自体は成功（_warnBadTs で警告）', () => {
    const ms = toMs('2031-01-01T00:00:00Z');
    assert.equal(ms, Date.UTC(2031, 0, 1));
    assert.ok(ms > 0);
  });
});

describe('_warnBadTs() — 異常検知', () => {
  it('1970年 (ms=0 + 1秒) → false (msVal=0 は警告対象外、無効扱い)', () => {
    const result = _warnBadTs('test', 0, 0);
    assert.equal(result, false);
  });
  it('1970年 (ms=86400000 = 1970-01-02) → true', () => {
    const result = _warnBadTs('test', 86400000, 86400000);
    assert.equal(result, true);
  });
  it('2026年 (現在) → false (正常)', () => {
    const ms = Date.UTC(2026, 4, 1);
    assert.equal(_warnBadTs('test', '2026-05-01', ms), false);
  });
  it('2030年 (5年後以内) → false (正常範囲)', () => {
    const ms = Date.UTC(2030, 0, 1);
    // 現在 2026 年で +4 年 → futureLimit (現在 +5) 内なので正常
    assert.equal(_warnBadTs('test', '2030-01-01', ms), false);
  });
  it('2050年 (遠い未来) → true (警告)', () => {
    const ms = Date.UTC(2050, 0, 1);
    assert.equal(_warnBadTs('test', '2050-01-01', ms), true);
  });
  it('msVal=0 → false (無効扱い、警告は出さない)', () => {
    assert.equal(_warnBadTs('test', null, 0), false);
  });
  it('msVal=NaN → false', () => {
    assert.equal(_warnBadTs('test', 'bad', NaN), false);
  });
});

describe('toMs() — フォーマット混在シナリオ (実環境再現)', () => {
  it('SNAP[*].timestamp が ISO 文字列 → 正規化', () => {
    const ms = toMs('2026-05-01T11:15:00+00:00');
    assert.ok(ms > 0);
    const yr = new Date(ms).getUTCFullYear();
    assert.equal(yr, 2026);
  });
  it('article.publishedAt が Unix 秒整数 → 正規化', () => {
    const ms = toMs(1746097800);
    assert.ok(ms > 0);
    const yr = new Date(ms).getUTCFullYear();
    assert.equal(yr, 2025);  // 1746097800 sec = 2025-05-01
  });
  it('predictionMadeAt が ISO 文字列 → 正規化', () => {
    const ms = toMs('2026-04-30T08:00:00+09:00');
    assert.ok(ms > 0);
  });
  it('lastArticleAt が Unix 秒文字列 → 正規化', () => {
    const ms = toMs('1746097800');
    assert.equal(ms, 1746097800 * 1000);
  });
});
