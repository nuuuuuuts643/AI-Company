// tests/utils.test.js
// node:test + assert (Node 18+ 組み込み。Jest不要)

const { describe, it } = require('node:test');
const assert = require('node:assert/strict');

const { CONFIG, LS_KEYS, relativeTime, isNewTopic, isHotTopic } =
  require('../../frontend/js/utils');

// ─────────────────────────────────────────────
// CONFIG
// ─────────────────────────────────────────────
describe('CONFIG', () => {
  it('HOT_STRIP_HOURS is 6', () => assert.equal(CONFIG.HOT_STRIP_HOURS, 6));
  it('NEW_BADGE_HOURS is 1', () => assert.equal(CONFIG.NEW_BADGE_HOURS, 1));
  it('AD_CARD_INTERVAL is 5', () => assert.equal(CONFIG.AD_CARD_INTERVAL, 5));
  it('TOPICS_PER_PAGE is 20', () => assert.equal(CONFIG.TOPICS_PER_PAGE, 20));
  it('FRESHNESS_INTERVAL_MS is 60000', () =>
    assert.equal(CONFIG.FRESHNESS_INTERVAL_MS, 60000));
});

// ─────────────────────────────────────────────
// LS_KEYS
// ─────────────────────────────────────────────
describe('LS_KEYS', () => {
  it('FAVORITES key is correct', () =>
    assert.equal(LS_KEYS.FAVORITES, 'flotopic_favorites'));
  it('HISTORY key is correct', () =>
    assert.equal(LS_KEYS.HISTORY, 'flotopic_history'));
  it('AVATAR key is correct', () =>
    assert.equal(LS_KEYS.AVATAR, 'flotopic_avatar'));
  it('PROFILE_SET key is correct', () =>
    assert.equal(LS_KEYS.PROFILE_SET, 'flotopic_profile_set'));
  it('DARK_MODE key is correct', () =>
    assert.equal(LS_KEYS.DARK_MODE, 'flotopic_dark'));
  it('PREFS key is correct', () =>
    assert.equal(LS_KEYS.PREFS, 'flotopic_prefs'));
  it('PWA_DISMISSED key is correct', () =>
    assert.equal(LS_KEYS.PWA_DISMISSED, 'pwa_dismissed'));
  it('all keys are strings', () => {
    Object.values(LS_KEYS).forEach(v => assert.equal(typeof v, 'string'));
  });
  it('has exactly 7 keys', () =>
    assert.equal(Object.keys(LS_KEYS).length, 7));
});

// ─────────────────────────────────────────────
// isNewTopic
// ─────────────────────────────────────────────
describe('isNewTopic', () => {
  const nowSec = () => Date.now() / 1000;

  it('returns true for topic updated 30 minutes ago', () => {
    assert.equal(isNewTopic({ lastUpdated: nowSec() - 30 * 60 }), true);
  });

  it('returns true for topic updated 59 minutes ago (boundary)', () => {
    assert.equal(isNewTopic({ lastUpdated: nowSec() - 59 * 60 }), true);
  });

  it('returns false for topic updated exactly 1 hour ago', () => {
    assert.equal(isNewTopic({ lastUpdated: nowSec() - 3600 }), false);
  });

  it('returns false for topic updated 2 hours ago', () => {
    assert.equal(isNewTopic({ lastUpdated: nowSec() - 2 * 3600 }), false);
  });

  it('returns false when lastUpdated is null', () => {
    assert.equal(isNewTopic({ lastUpdated: null }), false);
  });

  it('returns false when lastUpdated is 0', () => {
    assert.equal(isNewTopic({ lastUpdated: 0 }), false);
  });

  it('returns false when lastUpdated is undefined', () => {
    assert.equal(isNewTopic({}), false);
  });

  it('returns false when lastUpdated is string "0"', () => {
    assert.equal(isNewTopic({ lastUpdated: '0' }), false);
  });

  it('accepts string timestamps (coerces to number)', () => {
    const ts = String(Math.floor(nowSec() - 10 * 60));
    assert.equal(isNewTopic({ lastUpdated: ts }), true);
  });
});

// ─────────────────────────────────────────────
// isHotTopic
// ─────────────────────────────────────────────
describe('isHotTopic', () => {
  const nowSec = () => Date.now() / 1000;

  it('returns true for topic updated 1 hour ago', () => {
    assert.equal(isHotTopic({ lastUpdated: nowSec() - 1 * 3600 }), true);
  });

  it('returns true for topic updated 359 minutes ago (boundary)', () => {
    assert.equal(isHotTopic({ lastUpdated: nowSec() - 359 * 60 }), true);
  });

  it('returns false for topic updated exactly 6 hours ago', () => {
    assert.equal(isHotTopic({ lastUpdated: nowSec() - 6 * 3600 }), false);
  });

  it('returns false for topic updated 7 hours ago', () => {
    assert.equal(isHotTopic({ lastUpdated: nowSec() - 7 * 3600 }), false);
  });

  it('returns false when lastUpdated is null', () => {
    assert.equal(isHotTopic({ lastUpdated: null }), false);
  });

  it('returns false when lastUpdated is 0', () => {
    assert.equal(isHotTopic({ lastUpdated: 0 }), false);
  });

  it('returns false when lastUpdated is undefined', () => {
    assert.equal(isHotTopic({}), false);
  });

  it('isHotTopic true implies isNewTopic may be false (different thresholds)', () => {
    // 90分前のトピック: hot=true (6h以内), new=false (1h超)
    const t = { lastUpdated: nowSec() - 90 * 60 };
    assert.equal(isHotTopic(t), true);
    assert.equal(isNewTopic(t), false);
  });
});

// ─────────────────────────────────────────────
// relativeTime
// ─────────────────────────────────────────────
describe('relativeTime', () => {
  const nowSec = () => Date.now() / 1000;

  it('returns "たった今更新" for less than 1 minute ago', () => {
    assert.equal(relativeTime(nowSec() - 30), 'たった今更新');
  });

  it('returns "たった今更新" for 0 seconds ago', () => {
    assert.equal(relativeTime(nowSec()), 'たった今更新');
  });

  it('returns "5分前に更新" for 5 minutes ago', () => {
    assert.equal(relativeTime(nowSec() - 5 * 60), '5分前に更新');
  });

  it('returns "59分前に更新" for 59 minutes ago (boundary)', () => {
    assert.equal(relativeTime(nowSec() - 59 * 60), '59分前に更新');
  });

  it('returns "1時間前に更新" for exactly 60 minutes ago', () => {
    assert.equal(relativeTime(nowSec() - 60 * 60), '1時間前に更新');
  });

  it('returns "3時間前に更新" for 3 hours ago', () => {
    assert.equal(relativeTime(nowSec() - 3 * 3600), '3時間前に更新');
  });

  it('returns "23時間前に更新" for 23 hours ago (boundary)', () => {
    assert.equal(relativeTime(nowSec() - 23 * 3600), '23時間前に更新');
  });

  it('returns "1日前に更新" for exactly 24 hours ago', () => {
    assert.equal(relativeTime(nowSec() - 24 * 3600), '1日前に更新');
  });

  it('returns "2日前に更新" for 2 days ago', () => {
    assert.equal(relativeTime(nowSec() - 2 * 86400), '2日前に更新');
  });

  it('handles null gracefully (does not throw)', () => {
    assert.doesNotThrow(() => relativeTime(null));
  });

  it('returns string type', () => {
    assert.equal(typeof relativeTime(nowSec() - 10), 'string');
  });
});
