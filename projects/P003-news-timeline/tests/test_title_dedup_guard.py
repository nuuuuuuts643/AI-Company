"""T2026-0428-E2-3: title 重複による tid 分裂 dedup 再発防止 boundary test。

検証対象:
1. fetcher/handler.py に `_resolve_tid_collisions_by_title` が存在し、
   group_tids 構築直後に呼ばれていること
2. `_title_dedup_key` が punct/whitespace/速報プレフィックスを除いた
   先頭18文字を返すこと (proc_storage `_dedup_topics` と整合)
3. 既存 active/cooling かつ 直近14日 の topic と title 一致すれば既存 tid に再バインド
4. archived/legacy はマップに入らない (古いゴミ topic への誤バインド防止)
5. 14 日より古い lastArticleAt も除外
6. 同 run 内で 2 group が同 tid に着地したら記事マージ + URL 重複排除
7. existing_topics が空なら group_tids を素通し (運用初期の no-op 保証)

実行:
  cd projects/P003-news-timeline
  python3 -m unittest tests.test_title_dedup_guard -v
"""
import os
import re
import sys
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HANDLER_PATH = os.path.join(ROOT, 'lambda', 'fetcher', 'handler.py')


class TitleDedupGuardTest(unittest.TestCase):
    """fetcher/handler.py の静的解析で title-dedup ステップが残存することを確認。"""

    def setUp(self):
        with open(HANDLER_PATH, 'r', encoding='utf-8') as f:
            self.source = f.read()

    def test_helper_exists(self):
        self.assertIn('def _resolve_tid_collisions_by_title(', self.source,
                      '_resolve_tid_collisions_by_title が削除されている。'
                      'title 重複による tid 分裂 dedup が外れた可能性。')
        self.assertIn('def _title_dedup_key(', self.source,
                      '_title_dedup_key が削除されている。')

    def test_called_after_group_tids(self):
        """group_tids 構築直後に呼ばれていること (prefetch より前)。"""
        gt_pos = self.source.find('group_tids    = [(g, topic_fingerprint(g))')
        # 呼び出し行 (= 代入式) を関数定義行と区別して探す
        call_pos = self.source.find('group_tids = _resolve_tid_collisions_by_title(')
        self.assertGreater(gt_pos, 0, 'group_tids 行が見つからない')
        self.assertGreater(call_pos, 0,
                           '_resolve_tid_collisions_by_title 呼び出しが見つからない')
        self.assertLess(gt_pos, call_pos,
                        'title-dedup が group_tids 構築より前にある')
        # prefetch は call_pos より後ろで呼ばれる
        next_prefetch = self.source.find('ex.submit(_prefetch_group', call_pos)
        self.assertGreater(next_prefetch, call_pos,
                           'title-dedup が prefetch より後ろに移動している。'
                           'prefetch は dedup 後の tid を使わなければ既存 META が引けない。')


class _FakeArticle(dict):
    pass


# handler.py から正規化と再バインドのコアロジックを再現する。
# handler 本体は boto3 import が走るためテストでは self-contained に再現する。
# 逸脱したら TitleDedupGuardTest 側の文字列照合で失敗する二重ガード構造。
_PUNCT_RE = re.compile(r'[「」【】・、。,!?！？\[\]()（）『』""\'\'#＃\s　]+')
_LIVE_RE = re.compile(r'^(中継|速報|更新|独自|詳報|続報|緊急|号外)\s*')
_INACTIVE = ('archived', 'legacy')


def _title_dedup_key(title):
    if not title:
        return ''
    s = str(title).lower()
    s = _PUNCT_RE.sub('', s)
    s = _LIVE_RE.sub('', s)
    return s[:18]


def _extractive_title(articles):
    if not articles:
        return ''
    first = articles[0].get('title', '')
    return first[:40] + ('…' if len(first) > 40 else '')


def _resolve(group_tids, existing_topics, now_ts=None):
    if not existing_topics or not group_tids:
        return group_tids
    if now_ts is None:
        now_ts = int(time.time())
    cutoff = now_ts - 14 * 86400
    title_to_tid = {}
    for t in existing_topics:
        tid_e = t.get('topicId', '')
        if not tid_e:
            continue
        if t.get('lifecycleStatus') in _INACTIVE:
            continue
        last = int(t.get('lastArticleAt', 0) or 0)
        if not last or last < cutoff:
            continue
        for src_title in (t.get('title'), t.get('generatedTitle')):
            norm = _title_dedup_key(src_title)
            if norm and norm not in title_to_tid:
                title_to_tid[norm] = tid_e
    if not title_to_tid:
        return group_tids
    rebound_resolved = []
    for g, tid in group_tids:
        candidate = _extractive_title(g) or (g[0].get('title', '') if g else '')
        norm = _title_dedup_key(candidate)
        target = title_to_tid.get(norm)
        if target and target != tid:
            tid = target
        rebound_resolved.append((g, tid))
    by_tid = {}
    order = []
    for g, tid in rebound_resolved:
        if tid in by_tid:
            existing_g = by_tid[tid]
            seen_urls = {a.get('url') for a in existing_g if a.get('url')}
            for a in g:
                u = a.get('url')
                if u and u not in seen_urls:
                    existing_g.append(a)
                    seen_urls.add(u)
        else:
            by_tid[tid] = list(g)
            order.append(tid)
    return [(by_tid[tid], tid) for tid in order]


class TitleDedupKeyTest(unittest.TestCase):
    def test_empty_returns_empty(self):
        self.assertEqual(_title_dedup_key(''), '')
        self.assertEqual(_title_dedup_key(None), '')

    def test_strips_punct_and_whitespace(self):
        self.assertEqual(
            _title_dedup_key('「速報」 トランプ大統領、関税を撤廃'),
            _title_dedup_key('速報　トランプ大統領、関税を撤廃'),
        )

    def test_strips_live_prefix(self):
        # 【 】を strip した後 _LIVE_RE が「速報」を除く
        self.assertEqual(
            _title_dedup_key('【速報】トランプ関税撤廃'),
            _title_dedup_key('トランプ関税撤廃'),
        )

    def test_truncates_to_18_chars(self):
        long = 'あ' * 30
        self.assertEqual(len(_title_dedup_key(long)), 18)


class TidRebindBehaviorTest(unittest.TestCase):
    def setUp(self):
        self.now = 1_700_000_000  # 固定 now で 14 日 cutoff を再現可能に

    def test_no_existing_returns_input(self):
        gt = [([_FakeArticle(url='u1', title='X')], 'tid_new')]
        self.assertEqual(_resolve(gt, [], self.now), gt)
        self.assertEqual(_resolve(gt, None, self.now), gt)

    def test_rebinds_to_existing_active(self):
        existing = [{
            'topicId': 'tid_existing',
            'title': 'トランプ大統領 関税を撤廃',
            'lastArticleAt': self.now - 86400,
            'lifecycleStatus': 'active',
        }]
        # 新 cluster の最初の記事タイトルが既存 title と完全一致
        gt = [([_FakeArticle(url='new1', title='トランプ大統領 関税を撤廃')], 'tid_new')]
        out = _resolve(gt, existing, self.now)
        self.assertEqual(out[0][1], 'tid_existing',
                         '完全一致 title なら既存 tid に再バインドされるべき')

    def test_rebinds_via_generatedTitle(self):
        # 既存 META が AI 上書きで generatedTitle を持つケース
        existing = [{
            'topicId': 'tid_existing',
            'title': '生 raw タイトル',
            'generatedTitle': 'トランプ関税撤廃の動き',
            'lastArticleAt': self.now - 3600,
            'lifecycleStatus': 'active',
        }]
        gt = [([_FakeArticle(url='new1', title='トランプ関税撤廃の動き')], 'tid_new')]
        out = _resolve(gt, existing, self.now)
        self.assertEqual(out[0][1], 'tid_existing')

    def test_skip_archived_legacy(self):
        # archived/legacy には再バインドしない (古いゴミに新記事を流し込まない)
        existing = [
            {'topicId': 'tid_arch', 'title': '同じタイトル',
             'lastArticleAt': self.now - 86400, 'lifecycleStatus': 'archived'},
            {'topicId': 'tid_legacy', 'title': '同じタイトル',
             'lastArticleAt': self.now - 86400, 'lifecycleStatus': 'legacy'},
        ]
        gt = [([_FakeArticle(url='new1', title='同じタイトル')], 'tid_new')]
        out = _resolve(gt, existing, self.now)
        self.assertEqual(out[0][1], 'tid_new', 'archived/legacy には bind しない')

    def test_skip_old_topics_beyond_cutoff(self):
        # 14 日より古い topic は無視
        existing = [{
            'topicId': 'tid_old',
            'title': '同じタイトル',
            'lastArticleAt': self.now - 15 * 86400,
            'lifecycleStatus': 'active',
        }]
        gt = [([_FakeArticle(url='new1', title='同じタイトル')], 'tid_new')]
        out = _resolve(gt, existing, self.now)
        self.assertEqual(out[0][1], 'tid_new', '14日超は title 一致でも bind しない')

    def test_skip_lastArticleAt_zero(self):
        # lastArticleAt=0 (未設定) も無視
        existing = [{
            'topicId': 'tid_no_last',
            'title': '同じタイトル',
            'lastArticleAt': 0,
            'lifecycleStatus': 'active',
        }]
        gt = [([_FakeArticle(url='new1', title='同じタイトル')], 'tid_new')]
        out = _resolve(gt, existing, self.now)
        self.assertEqual(out[0][1], 'tid_new')

    def test_merges_same_run_collisions(self):
        # 既存 tid に 2 group が再バインドされた場合、記事をマージ + URL 重複排除
        existing = [{
            'topicId': 'tid_existing',
            'title': '共通タイトル',
            'lastArticleAt': self.now - 3600,
            'lifecycleStatus': 'active',
        }]
        # group A は url=u1,u2 / group B は url=u2,u3 (u2 重複)
        gt = [
            ([_FakeArticle(url='u1', title='共通タイトル'),
              _FakeArticle(url='u2', title='共通タイトル')], 'tid_a'),
            ([_FakeArticle(url='u2', title='共通タイトル'),
              _FakeArticle(url='u3', title='共通タイトル')], 'tid_b'),
        ]
        out = _resolve(gt, existing, self.now)
        self.assertEqual(len(out), 1, '同 tid 着地 → 1 group にマージ')
        merged_g, merged_tid = out[0]
        self.assertEqual(merged_tid, 'tid_existing')
        urls = sorted(a.get('url') for a in merged_g)
        self.assertEqual(urls, ['u1', 'u2', 'u3'], 'URL 重複排除付きマージ')

    def test_no_change_if_title_differs(self):
        # title が異なれば bind しない
        existing = [{
            'topicId': 'tid_existing',
            'title': '別の話題',
            'lastArticleAt': self.now - 3600,
            'lifecycleStatus': 'active',
        }]
        gt = [([_FakeArticle(url='u1', title='全然違うタイトル')], 'tid_new')]
        out = _resolve(gt, existing, self.now)
        self.assertEqual(out[0][1], 'tid_new')

    def test_real_world_343_split_scenario(self):
        # 本番再現: 同じイベントに対し fingerprint 違いで別 tid が生まれた状況。
        # 既存 tid_orig (3 articles で active) があり、新 fetch で fingerprint 差分で
        # tid_dup が生まれた場合 → 既存 tid_orig に再バインドされるべき
        existing = [{
            'topicId': 'tid_orig',
            'title': '佐々木朗希、メジャー初登板で勝利',
            'generatedTitle': '佐々木朗希、メジャー初登板で勝利',
            'articleCount': 5,
            'lastArticleAt': self.now - 7200,
            'lifecycleStatus': 'active',
        }]
        gt = [
            ([_FakeArticle(url='nhk1', title='佐々木朗希、メジャー初登板で勝利',
                           source='NHK')], 'tid_dup_a'),
            ([_FakeArticle(url='asahi1', title='佐々木朗希、メジャー初登板で勝利',
                           source='朝日')], 'tid_dup_b'),
        ]
        out = _resolve(gt, existing, self.now)
        # 両方とも tid_orig に着地 + マージで 1 group になる
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0][1], 'tid_orig')
        self.assertEqual(len(out[0][0]), 2, 'NHK + 朝日 が 1 group にマージ')


if __name__ == '__main__':
    unittest.main()
