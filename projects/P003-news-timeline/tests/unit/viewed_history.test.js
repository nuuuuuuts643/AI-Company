// viewed_history.test.js — frontend/js/viewed_history.js の境界値テスト
// T2026-0501-B: 既読トピックの「続報あり」判定 + クラウド履歴マージの純粋ロジック検証。
// CLAUDE.md ルール「新規 formatter は boundary test 同梱」を「既読判定関数」に拡張。
//
// 主旨:
//  - viewedAt=0/undefined/null (legacy) で続報あり扱いになると、初回ログイン時に
//    既存ユーザーで一斉に新着バッジが出てノイズになる → 物理的に防ぐ。
//  - lastArticleAt が ISO 文字列 / unix sec 数値 / null の混在に耐える。
//  - localStorage が壊れた JSON / 不正な型でも例外を出さず空の Map を返す。

const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const VH = require('../../frontend/js/viewed_history.js');

// ─────────────────────────────────────────────
// hasNewArticlesAfter — 続報あり判定
// ─────────────────────────────────────────────
describe('hasNewArticlesAfter() 境界値', () => {
  const NOW = 1735689600000; // 2025-01-01 00:00:00 UTC, ms
  const NOW_SEC = NOW / 1000;
  const ONE_HOUR_MS = 3600 * 1000;

  it('viewedAt 後に lastArticleAt が来た → true', () => {
    assert.equal(VH.hasNewArticlesAfter(NOW, NOW_SEC + 3600), true);
  });

  it('viewedAt 前に lastArticleAt → false (古い記事)', () => {
    assert.equal(VH.hasNewArticlesAfter(NOW, NOW_SEC - 3600), false);
  });

  it('viewedAt と lastArticleAt が同時刻 (1ms 単位) → false (>= ではなく > 比較)', () => {
    assert.equal(VH.hasNewArticlesAfter(NOW, NOW_SEC), false);
  });

  it('viewedAt=0 (legacy sentinel) → false (新着判定しない)', () => {
    assert.equal(VH.hasNewArticlesAfter(0, NOW_SEC + 3600), false);
  });

  it('viewedAt=undefined → false', () => {
    assert.equal(VH.hasNewArticlesAfter(undefined, NOW_SEC + 3600), false);
  });

  it('viewedAt=null → false', () => {
    assert.equal(VH.hasNewArticlesAfter(null, NOW_SEC + 3600), false);
  });

  it('viewedAt=負の値 → false', () => {
    assert.equal(VH.hasNewArticlesAfter(-1000, NOW_SEC + 3600), false);
  });

  it('lastArticleAt=0 → false (lastArticleAt 未設定トピック)', () => {
    assert.equal(VH.hasNewArticlesAfter(NOW, 0), false);
  });

  it('lastArticleAt=null → false', () => {
    assert.equal(VH.hasNewArticlesAfter(NOW, null), false);
  });

  it('lastArticleAt=undefined → false', () => {
    assert.equal(VH.hasNewArticlesAfter(NOW, undefined), false);
  });

  it('lastArticleAt が ISO 文字列 (新しい) → true', () => {
    assert.equal(VH.hasNewArticlesAfter(NOW, '2025-01-01T01:00:00Z'), true);
  });

  it('lastArticleAt が ISO 文字列 (古い) → false', () => {
    assert.equal(VH.hasNewArticlesAfter(NOW, '2024-12-31T23:00:00Z'), false);
  });

  it('lastArticleAt=NaN相当の文字列 → false (壊れたデータでクラッシュしない)', () => {
    assert.equal(VH.hasNewArticlesAfter(NOW, 'not-a-date'), false);
  });

  it('viewedAt と lastArticleAt の差が 1ms でも > なら true', () => {
    // lastArticleAt は秒だが、ms 比較で 1ms 違いでも true になる境界
    const lastSec = (NOW + 1) / 1000; // viewedAt より 1ms 後
    assert.equal(VH.hasNewArticlesAfter(NOW, lastSec), true);
  });
});

// ─────────────────────────────────────────────
// loadViewedMap — localStorage → Map<topicId, viewedAtMs>
// ─────────────────────────────────────────────
describe('loadViewedMap() 境界値', () => {
  it('history も legacy も null → 空 Map', () => {
    const m = VH.loadViewedMap(null, null);
    assert.equal(m.size, 0);
  });

  it('history 空配列 + legacy 空配列 → 空 Map', () => {
    const m = VH.loadViewedMap('[]', '[]');
    assert.equal(m.size, 0);
  });

  it('壊れた JSON → 例外を出さず空 Map', () => {
    const m = VH.loadViewedMap('{not json', '{also not json');
    assert.equal(m.size, 0);
  });

  it('history に有効なエントリ → Map に viewedAt 入り', () => {
    const hist = JSON.stringify([
      { topicId: 'a', viewedAt: 1000 },
      { topicId: 'b', viewedAt: 2000 },
    ]);
    const m = VH.loadViewedMap(hist, null);
    assert.equal(m.get('a'), 1000);
    assert.equal(m.get('b'), 2000);
  });

  it('history.viewedAt=0 / 文字列 → sentinel=0 として記録', () => {
    const hist = JSON.stringify([
      { topicId: 'a', viewedAt: 0 },
      { topicId: 'b', viewedAt: 'invalid' },
      { topicId: 'c' }, // viewedAt 欠落
    ]);
    const m = VH.loadViewedMap(hist, null);
    assert.equal(m.get('a'), 0);
    assert.equal(m.get('b'), 0);
    assert.equal(m.get('c'), 0);
  });

  it('legacy のみ (history 空) → sentinel=0 で記録', () => {
    const m = VH.loadViewedMap('[]', JSON.stringify(['x', 'y']));
    assert.equal(m.size, 2);
    assert.equal(m.get('x'), 0);
    assert.equal(m.get('y'), 0);
  });

  it('history と legacy 両方 → history 優先 (タイムスタンプ保持)', () => {
    const hist = JSON.stringify([{ topicId: 'a', viewedAt: 1000 }]);
    const legacy = JSON.stringify(['a', 'b']);
    const m = VH.loadViewedMap(hist, legacy);
    assert.equal(m.get('a'), 1000); // history が優先
    assert.equal(m.get('b'), 0);    // legacy のみは sentinel
  });

  it('history が配列以外 (オブジェクト) → 空 Map', () => {
    const m = VH.loadViewedMap('{"a":1}', null);
    assert.equal(m.size, 0);
  });

  it('topicId 欠落エントリは無視', () => {
    const hist = JSON.stringify([
      { viewedAt: 1000 },
      { topicId: '', viewedAt: 2000 },
      { topicId: 'valid', viewedAt: 3000 },
    ]);
    const m = VH.loadViewedMap(hist, null);
    assert.equal(m.size, 1);
    assert.equal(m.get('valid'), 3000);
  });
});

// ─────────────────────────────────────────────
// mergeHistory — クラウド + ローカルのマージ
// ─────────────────────────────────────────────
describe('mergeHistory() 境界値', () => {
  it('両方空 → []', () => {
    assert.deepEqual(VH.mergeHistory([], []), []);
  });

  it('null/undefined 入力でもクラッシュしない', () => {
    assert.deepEqual(VH.mergeHistory(null, undefined), []);
  });

  it('cloudのみ → cloud をそのまま (viewedAt 降順)', () => {
    const cloud = [
      { topicId: 'a', viewedAt: 1000 },
      { topicId: 'b', viewedAt: 2000 },
    ];
    const m = VH.mergeHistory(cloud, []);
    assert.equal(m.length, 2);
    assert.equal(m[0].topicId, 'b'); // 新しい順
    assert.equal(m[1].topicId, 'a');
  });

  it('重複 topicId → viewedAt 新しい方を採用', () => {
    const cloud = [{ topicId: 'a', viewedAt: 1000, title: 'old' }];
    const local = [{ topicId: 'a', viewedAt: 2000, title: 'new' }];
    const m = VH.mergeHistory(cloud, local);
    assert.equal(m.length, 1);
    assert.equal(m[0].viewedAt, 2000);
    assert.equal(m[0].title, 'new');
  });

  it('重複 topicId で local が古い → cloud を採用', () => {
    const cloud = [{ topicId: 'a', viewedAt: 5000, title: 'cloud' }];
    const local = [{ topicId: 'a', viewedAt: 2000, title: 'local' }];
    const m = VH.mergeHistory(cloud, local);
    assert.equal(m[0].title, 'cloud');
  });

  it('topicId 欠落エントリは無視', () => {
    const cloud = [{ viewedAt: 1000 }];
    const local = [{ topicId: 'a', viewedAt: 500 }];
    const m = VH.mergeHistory(cloud, local);
    assert.equal(m.length, 1);
    assert.equal(m[0].topicId, 'a');
  });
});

// ─────────────────────────────────────────────
// toUnixSec — 補助関数
// ─────────────────────────────────────────────
describe('toUnixSec() 境界値', () => {
  it('null/undefined/空文字 → 0', () => {
    assert.equal(VH.toUnixSec(null), 0);
    assert.equal(VH.toUnixSec(undefined), 0);
    assert.equal(VH.toUnixSec(''), 0);
  });

  it('unix sec の数値はそのまま', () => {
    assert.equal(VH.toUnixSec(1735689600), 1735689600);
  });

  it('ISO 文字列 → unix sec', () => {
    assert.equal(VH.toUnixSec('2025-01-01T00:00:00Z'), 1735689600);
  });

  it('壊れた文字列 → 0', () => {
    assert.equal(VH.toUnixSec('garbage'), 0);
  });

  it('小さい数値 (1e9 未満) → Date 経由でパース試行 (ms 想定)', () => {
    // 例: 1000 は「1970-01-01 00:00:01」の ms → toUnixSec=1
    // ここは挙動を固定するためのテスト
    assert.equal(VH.toUnixSec(1000), 1);
  });
});
