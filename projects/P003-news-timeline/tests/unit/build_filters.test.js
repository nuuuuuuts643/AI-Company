// build_filters.test.js — frontend/js/build_filters.js の境界値テスト
// CLAUDE.md ルール「新規 formatter は boundary test 同梱」を「フィルタ関数」に拡張。
//
// 主旨: visibleGenres が空配列になると UI からジャンルボタンが全消失し、
//       ユーザーが「総合」にすら戻れなくなる。これを物理的に防ぐ。
// 対応タスク: T2026-0428-BE

const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const BF = require('../../frontend/js/build_filters.js');

const GENRES = ['総合','政治','ビジネス','株・金融','テクノロジー','スポーツ','エンタメ','科学','健康','国際','くらし','社会','グルメ','ファッション'];

describe('computeVisibleGenres() 境界値', () => {
  it('topics=[] (トピック空) でも空配列にならない — 少なくとも 総合 を含む', () => {
    const result = BF.computeVisibleGenres([], '総合', GENRES);
    assert.ok(Array.isArray(result), 'returns array');
    assert.ok(result.length >= 1, 'non-empty');
    assert.ok(result.includes('総合'), 'includes 総合');
  });

  it('topics=[{genre:"総合"}] (総合ジャンルのみ) でも空配列にならない', () => {
    const result = BF.computeVisibleGenres([{ genre: '総合' }], '総合', GENRES);
    assert.ok(Array.isArray(result), 'returns array');
    assert.ok(result.length >= 1, 'non-empty');
    assert.ok(result.includes('総合'), 'includes 総合');
  });

  it('counts={} 相当 (全トピックが archived) でも空配列にならない', () => {
    const archivedOnly = [
      { genre: '政治', lifecycleStatus: 'archived' },
      { genre: 'テクノロジー', lifecycleStatus: 'archived' },
    ];
    const result = BF.computeVisibleGenres(archivedOnly, '総合', GENRES);
    assert.ok(Array.isArray(result), 'returns array');
    assert.ok(result.length >= 1, 'non-empty');
    assert.ok(result.includes('総合'), 'includes 総合');
  });

  it('topics=null/undefined でも空配列にならない', () => {
    assert.ok(BF.computeVisibleGenres(null, '総合', GENRES).length >= 1);
    assert.ok(BF.computeVisibleGenres(undefined, '総合', GENRES).length >= 1);
  });

  it('allGenres=[] (ジャンル定義空) でも 総合 にフォールバック', () => {
    const result = BF.computeVisibleGenres([], '総合', []);
    assert.deepEqual(result, ['総合']);
  });

  it('currentGenre が件数 0 でも残る（クリック直後に消えない）', () => {
    const topics = [{ genre: '総合' }];
    const result = BF.computeVisibleGenres(topics, '政治', GENRES);
    assert.ok(result.includes('政治'), 'currentGenre 政治 が残る');
    assert.ok(result.includes('総合'), '総合 も残る');
  });

  it('件数 > 0 のジャンルは含まれる', () => {
    const topics = [
      { genre: 'テクノロジー' },
      { genre: 'テクノロジー' },
      { genre: 'スポーツ' },
    ];
    const result = BF.computeVisibleGenres(topics, '総合', GENRES);
    assert.ok(result.includes('テクノロジー'));
    assert.ok(result.includes('スポーツ'));
  });

  it('件数 0 のジャンル（総合・currentGenre 以外）は含まれない', () => {
    const topics = [{ genre: 'テクノロジー' }];
    const result = BF.computeVisibleGenres(topics, '総合', GENRES);
    assert.ok(!result.includes('政治'), '政治 は 0 件なので非表示');
    assert.ok(!result.includes('スポーツ'), 'スポーツ も 0 件なので非表示');
  });

  it('旧ジャンル名 (経済) は新ジャンル名 (ビジネス) にマージされる', () => {
    const topics = [{ genre: '経済' }];
    const result = BF.computeVisibleGenres(topics, '総合', GENRES);
    assert.ok(result.includes('ビジネス'), '経済→ビジネス マージ');
    assert.ok(!result.includes('経済'), '旧ジャンル名は表示されない');
  });

  it('genres 配列形式 (複数ジャンル) も正しく集計', () => {
    const topics = [{ genres: ['テクノロジー', 'ビジネス'] }];
    const result = BF.computeVisibleGenres(topics, '総合', GENRES);
    assert.ok(result.includes('テクノロジー'));
    assert.ok(result.includes('ビジネス'));
  });

  it('GENRES の順序を維持して返す', () => {
    const topics = [
      { genre: 'スポーツ' },
      { genre: '政治' },
      { genre: 'テクノロジー' },
    ];
    const result = BF.computeVisibleGenres(topics, '総合', GENRES);
    const idxPolitics = result.indexOf('政治');
    const idxTech = result.indexOf('テクノロジー');
    const idxSports = result.indexOf('スポーツ');
    assert.ok(idxPolitics < idxTech, '政治 → テクノロジー');
    assert.ok(idxTech < idxSports, 'テクノロジー → スポーツ');
  });
});

describe('computeGenreCounts() 境界値', () => {
  it('topics=[] は {} を返す', () => {
    assert.deepEqual(BF.computeGenreCounts([]), {});
  });

  it('topics=null/undefined は {} を返す（throw しない）', () => {
    assert.deepEqual(BF.computeGenreCounts(null), {});
    assert.deepEqual(BF.computeGenreCounts(undefined), {});
  });

  it('archived は除外', () => {
    const topics = [
      { genre: 'テクノロジー' },
      { genre: 'テクノロジー', lifecycleStatus: 'archived' },
    ];
    const counts = BF.computeGenreCounts(topics);
    assert.equal(counts['テクノロジー'], 1);
  });

  it('1 トピックが同じジャンルを 2 回持っても重複カウントしない', () => {
    const topics = [{ genres: ['テクノロジー', 'テクノロジー'] }];
    const counts = BF.computeGenreCounts(topics);
    assert.equal(counts['テクノロジー'], 1);
  });

  it('null / 空文字 ジャンルは無視', () => {
    const topics = [
      { genre: null },
      { genre: '' },
      { genres: [null, '', 'テクノロジー'] },
    ];
    const counts = BF.computeGenreCounts(topics);
    assert.equal(counts['テクノロジー'], 1);
    assert.ok(!('' in counts));
  });
});
