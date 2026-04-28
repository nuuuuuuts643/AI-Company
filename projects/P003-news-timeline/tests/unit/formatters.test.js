// formatters.test.js — frontend/js/formatters.js の境界値テスト
// CLAUDE.md ルール「新規 formatter は boundary test 同梱」に対応:
//   0 / null / undefined / NaN / 未来日付 / 空文字を全部 assert する。

const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const F = require('../../frontend/js/formatters.js');

describe('esc()', () => {
  it('null/undefined → 空文字', () => {
    assert.equal(F.esc(null), '');
    assert.equal(F.esc(undefined), '');
  });
  it('数値もエスケープ済み文字列で返す', () => {
    assert.equal(F.esc(42), '42');
  });
  it('XSS 用の記号をすべて変換する', () => {
    assert.equal(F.esc('<img src=x onerror="alert(1)">'),
      '&lt;img src=x onerror=&quot;alert(1)&quot;&gt;');
  });
  it('& も変換する（二重エスケープ防止のため最初に処理）', () => {
    assert.equal(F.esc('a & b'), 'a &amp; b');
  });
});

describe('cleanSummary()', () => {
  it('null は null のまま返す（書き込み済みデータの不在を区別したいケース）', () => {
    assert.equal(F.cleanSummary(null), null);
  });
  it('空文字は空文字のまま', () => {
    assert.equal(F.cleanSummary(''), '');
  });
  it('Markdown 見出しを取り除く', () => {
    assert.equal(F.cleanSummary('# 見出し\n本文'), '本文');
  });
  it('箇条書き（- / *）を取り除く', () => {
    assert.equal(F.cleanSummary('- a\n- b\n- c'), 'a b c');
  });
  it('番号付きリストを取り除く', () => {
    assert.equal(F.cleanSummary('1. one\n2. two'), 'one two');
  });
  it('連続改行はスペース 1 つに圧縮', () => {
    assert.equal(F.cleanSummary('段落1\n\n\n段落2'), '段落1 段落2');
  });
});

describe('formatDate()', () => {
  it('null/undefined は空文字', () => {
    assert.equal(F.formatDate(null), '');
    assert.equal(F.formatDate(undefined), '');
  });
  it('0 / "0" は空文字（epoch=0 起源の bogus 値ガード）', () => {
    assert.equal(F.formatDate(0), '');
    assert.equal(F.formatDate('0'), '');
  });
  it('空文字は空文字', () => {
    assert.equal(F.formatDate(''), '');
  });
  it('NaN/不正文字列は空文字', () => {
    assert.equal(F.formatDate(NaN), '');
    assert.equal(F.formatDate('not-a-date'), '');
  });
  it('1970-01-01 周辺の小さい数値（< 1e9）は空文字', () => {
    assert.equal(F.formatDate(1), '');
    assert.equal(F.formatDate(86400), '');
  });
  it('1989-12-31 → 空文字（< 1990 ガード）', () => {
    assert.equal(F.formatDate('1989-12-31T00:00:00Z'), '');
  });
  it('未来日付（1 年以上先）は空文字', () => {
    const future = Date.now() / 1000 + 2 * 365 * 86400;
    assert.equal(F.formatDate(future), '');
  });
  it('Unix 秒（10 桁）を整形できる', () => {
    const s = F.formatDate(1735689600); // 2025-01-01 09:00 JST
    assert.match(s, /\d{4}\/\d+\/\d+ \d{2}:\d{2}/);
  });
  it('Unix ミリ秒（13 桁）を整形できる', () => {
    const s = F.formatDate(1735689600000);
    assert.match(s, /\d{4}\/\d+\/\d+ \d{2}:\d{2}/);
  });
  it('ISO 文字列を整形できる', () => {
    const s = F.formatDate('2025-01-01T00:00:00Z');
    assert.match(s, /\d{4}\/\d+\/\d+ \d{2}:\d{2}/);
  });
  it('Date オブジェクトを受け付ける', () => {
    const s = F.formatDate(new Date('2025-06-01T00:00:00Z'));
    assert.match(s, /\d{4}\/\d+\/\d+ \d{2}:\d{2}/);
  });
  it('例外時に throw しない（{} を渡しても落ちない）', () => {
    assert.doesNotThrow(() => F.formatDate({}));
  });
});

describe('formatNumber()', () => {
  it('null/undefined → "0"', () => {
    assert.equal(F.formatNumber(null), '0');
    assert.equal(F.formatNumber(undefined), '0');
  });
  it('NaN → "0"', () => {
    assert.equal(F.formatNumber(NaN), '0');
  });
  it('空文字 → "0"', () => {
    assert.equal(F.formatNumber(''), '0');
  });
  it('Infinity → "0"（finite ガード）', () => {
    assert.equal(F.formatNumber(Infinity), '0');
    assert.equal(F.formatNumber(-Infinity), '0');
  });
  it('0 はそのまま "0"', () => {
    assert.equal(F.formatNumber(0), '0');
  });
  it('1234 → "1,234"', () => {
    assert.equal(F.formatNumber(1234), '1,234');
  });
  it('1234567 → "1,234,567"', () => {
    assert.equal(F.formatNumber(1234567), '1,234,567');
  });
  it('負数も区切り表示', () => {
    assert.equal(F.formatNumber(-1234), '-1,234');
  });
  it('文字列の数値を受け付ける', () => {
    assert.equal(F.formatNumber('5000'), '5,000');
  });
});

describe('toUnixSec()', () => {
  it('falsy 全部 0', () => {
    assert.equal(F.toUnixSec(null), 0);
    assert.equal(F.toUnixSec(undefined), 0);
    assert.equal(F.toUnixSec(0), 0);
    assert.equal(F.toUnixSec(''), 0);
  });
  it('Unix 秒（10 桁）はそのまま', () => {
    assert.equal(F.toUnixSec(1735689600), 1735689600);
  });
  it('Unix ミリ秒（13 桁）は秒に正規化', () => {
    assert.equal(F.toUnixSec(1735689600000), 1735689600);
  });
  it('ISO 文字列は秒に変換', () => {
    const v = F.toUnixSec('2025-01-01T00:00:00Z');
    assert.equal(v, 1735689600);
  });
  it('不正値は 0', () => {
    assert.equal(F.toUnixSec('garbage'), 0);
  });
});

describe('stripMediaSuffix()', () => {
  it('null/undefined/空 → ""', () => {
    assert.equal(F.stripMediaSuffix(null), '');
    assert.equal(F.stripMediaSuffix(undefined), '');
    assert.equal(F.stripMediaSuffix(''), '');
  });
  it('「タイトル - 媒体名」を除去', () => {
    assert.equal(F.stripMediaSuffix('地震速報 - 朝日新聞'), '地震速報');
  });
  it('「タイトル | 媒体名」も除去', () => {
    assert.equal(F.stripMediaSuffix('特集 | 日経新聞'), '特集');
  });
  it('「タイトル（媒体名）」も除去', () => {
    assert.equal(F.stripMediaSuffix('解説（NHK）'), '解説');
  });
  it('媒体名が長すぎる場合は除去しない（誤検知防止）', () => {
    // 33文字以上 → 媒体名としては不自然なので除去対象外
    const t = '速報 - これは媒体名ではなく長い説明文章なので除去対象外として残してほしい部分です';
    assert.equal(F.stripMediaSuffix(t), t);
  });
});

describe('isMeaningfulKeyword()', () => {
  const blacklist = new Set(['内容', '背景']);
  it('null/undefined/空 → false', () => {
    assert.equal(F.isMeaningfulKeyword(null), false);
    assert.equal(F.isMeaningfulKeyword(undefined), false);
    assert.equal(F.isMeaningfulKeyword(''), false);
    assert.equal(F.isMeaningfulKeyword('   '), false);
  });
  it('1 文字は曖昧すぎ → false', () => {
    assert.equal(F.isMeaningfulKeyword('a'), false);
    assert.equal(F.isMeaningfulKeyword('政'), false);
  });
  it('blacklist に含まれていれば false', () => {
    assert.equal(F.isMeaningfulKeyword('内容', blacklist), false);
  });
  it('純ひらがな 2-3 文字は除外（助詞・動詞らしき）', () => {
    assert.equal(F.isMeaningfulKeyword('から'), false);
    assert.equal(F.isMeaningfulKeyword('について'), true); // 4文字以上は OK
  });
  it('意味のあるキーワードは true', () => {
    assert.equal(F.isMeaningfulKeyword('生成AI'), true);
    assert.equal(F.isMeaningfulKeyword('北海道'), true);
  });
});

describe('safeImgUrl()', () => {
  it('null/undefined/空 → ""', () => {
    assert.equal(F.safeImgUrl(null), '');
    assert.equal(F.safeImgUrl(undefined), '');
    assert.equal(F.safeImgUrl(''), '');
  });
  it('http:// は https:// に強制（mixed content 防止）', () => {
    assert.equal(F.safeImgUrl('http://example.com/x.png'), 'https://example.com/x.png');
  });
  it('https は変更なし', () => {
    assert.equal(F.safeImgUrl('https://example.com/x.png'), 'https://example.com/x.png');
  });
  it('プロトコル相対 URL は変更なし', () => {
    assert.equal(F.safeImgUrl('//cdn.example.com/x.png'), '//cdn.example.com/x.png');
  });
});
