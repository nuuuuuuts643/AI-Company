// safe_format.test.js — UI に「無効な値が漏れる」事故を物理的に防ぐ
// 既存バグ: fmtElapsed(0) が '1/1' (1970-01-01) を返し、childTopics ref が
// timestamp を持たない場合に「0件 · 1/1」が本番に出ていた。
//
// このテストは boundary case (0/null/undefined/'') を網羅的に通すことで
// 同種バグの再発を CI で blocking する。

const test = require('node:test');
const assert = require('node:assert');
const SF = require('../../frontend/js/safe_format.js');

// ============================================================
// fmtElapsed: 0/null/undefined/empty は必ず '' を返す
// 1970-01-01 由来の '1/1' が UI に出ないことを保証する
// ============================================================
test('fmtElapsed(0) returns empty (no 1970-01-01 leak)', () => {
  assert.strictEqual(SF.fmtElapsed(0), '');
});
test('fmtElapsed("0") returns empty', () => {
  assert.strictEqual(SF.fmtElapsed('0'), '');
});
test('fmtElapsed(null) returns empty', () => {
  assert.strictEqual(SF.fmtElapsed(null), '');
});
test('fmtElapsed(undefined) returns empty', () => {
  assert.strictEqual(SF.fmtElapsed(undefined), '');
});
test('fmtElapsed("") returns empty', () => {
  assert.strictEqual(SF.fmtElapsed(''), '');
});
test('fmtElapsed(NaN) returns empty', () => {
  assert.strictEqual(SF.fmtElapsed(NaN), '');
});
test('fmtElapsed("invalid date") returns empty', () => {
  assert.strictEqual(SF.fmtElapsed('not-a-date'), '');
});
test('fmtElapsed handles year < 1990 as empty (epoch=0 leak guard)', () => {
  assert.strictEqual(SF.fmtElapsed(new Date('1985-06-01')), '');
});
test('fmtElapsed accepts valid Unix seconds', () => {
  // 1時間前
  const oneHrAgo = Math.floor(Date.now() / 1000) - 3600;
  const result = SF.fmtElapsed(oneHrAgo);
  assert.match(result, /(時間前|分前)/);
});
test('fmtElapsed accepts valid ISO string', () => {
  const oneDayAgo = new Date(Date.now() - 24 * 3600 * 1000).toISOString();
  const result = SF.fmtElapsed(oneDayAgo);
  assert.match(result, /(日前|時間前)/);
});
test('fmtElapsed of future date returns empty (timezone mismatch guard)', () => {
  const future = Math.floor(Date.now() / 1000) + 3600 * 24 * 365;  // 1年後
  assert.strictEqual(SF.fmtElapsed(future), '');
});

// ============================================================
// formatCount: 0/不明値は null (UI に「0件」を出さない)
// ============================================================
test('formatCount(0) returns null (no zero-count display)', () => {
  assert.strictEqual(SF.formatCount(0), null);
});
test('formatCount(null) returns null', () => {
  assert.strictEqual(SF.formatCount(null), null);
});
test('formatCount(undefined) returns null', () => {
  assert.strictEqual(SF.formatCount(undefined), null);
});
test('formatCount(5) returns "5件"', () => {
  assert.strictEqual(SF.formatCount(5), '5件');
});
test('formatCount("3", "本") returns "3本"', () => {
  assert.strictEqual(SF.formatCount('3', '本'), '3本');
});
test('formatCount("abc") returns null', () => {
  assert.strictEqual(SF.formatCount('abc'), null);
});
test('formatCount(-1) returns null (no negative count)', () => {
  assert.strictEqual(SF.formatCount(-1), null);
});

// formatCountAllowZero: 0 を valid とする本物 0 用
test('formatCountAllowZero(0) returns "0件"', () => {
  assert.strictEqual(SF.formatCountAllowZero(0), '0件');
});
test('formatCountAllowZero(null) returns null', () => {
  assert.strictEqual(SF.formatCountAllowZero(null), null);
});

// ============================================================
// join: null/'' を自動除去、空配列は null 返却
// ============================================================
test('join filters out null/empty', () => {
  assert.strictEqual(SF.join(['🔴', null, '5件', '', '3時間前']), '🔴 · 5件 · 3時間前');
});
test('join of all-empty returns null', () => {
  assert.strictEqual(SF.join([null, null, '']), null);
});
test('join of empty array returns null', () => {
  assert.strictEqual(SF.join([]), null);
});
test('join with custom separator', () => {
  assert.strictEqual(SF.join(['a', 'b', 'c'], ' / '), 'a / b / c');
});

// ============================================================
// lifecycleDot
// ============================================================
test('lifecycleDot maps active/cooling/archived', () => {
  assert.strictEqual(SF.lifecycleDot('active'), '🔴');
  assert.strictEqual(SF.lifecycleDot('cooling'), '🟡');
  assert.strictEqual(SF.lifecycleDot('archived'), '⚪');
});
test('lifecycleDot of unknown returns empty', () => {
  assert.strictEqual(SF.lifecycleDot(undefined), '');
  assert.strictEqual(SF.lifecycleDot(null), '');
  assert.strictEqual(SF.lifecycleDot('legacy'), '');
});
