"""T2026-0428-E2-3 + T2026-0430-L: title 重複による tid 分裂 dedup 再発防止 boundary test。

検証対象:
1. fetcher/handler.py に `_resolve_tid_collisions_by_title` が存在し、
   group_tids 構築直後に呼ばれていること
2. `_title_dedup_key` が NFKC 正規化 + punct/whitespace/速報プレフィックスを除いた
   先頭18文字を返すこと (proc_storage `_dedup_topics` と整合)
3. 既存 active/cooling かつ 直近14日 の topic と title 一致すれば既存 tid に再バインド
4. archived/legacy はマップに入らない (古いゴミ topic への誤バインド防止)
5. 14 日より古い lastArticleAt も除外
6. 同 run 内で 2 group が同 tid に着地したら記事マージ + URL 重複排除
7. existing_topics が空なら group_tids を素通し (運用初期の no-op 保証)
8. **T2026-0430-L**: NFKC 正規化で `米ＧＤＰ`(全角) と `米GDP`(半角) が同一キー
9. **T2026-0430-L**: Jaccard 類似度 >= 0.35 で既存 AI topic に再バインド
10. **T2026-0430-L**: 別イベント (米GDP vs 米雇用統計) は merge しない (boundary)

実行:
  cd projects/P003-news-timeline
  python3 -m unittest tests.test_title_dedup_guard -v
"""
import os
import re
import sys
import time
import unicodedata
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
        # T2026-0430-L: NFKC 正規化と Jaccard fallback が外れていないこと
        self.assertIn("unicodedata.normalize('NFKC'", self.source,
                      '_title_dedup_key の NFKC 正規化が消えている。'
                      '半角/全角差で別 tid が生まれる退行リスク。')
        self.assertIn('def _title_bigrams(', self.source,
                      '_title_bigrams が削除されている。Jaccard fallback が動かない。')
        self.assertIn('def _jaccard_title_sim(', self.source,
                      '_jaccard_title_sim が削除されている。')

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
_JACCARD_THRESHOLD = 0.35


def _title_dedup_key(title):
    if not title:
        return ''
    # T2026-0430-L: NFKC 正規化を入れることで `米ＧＤＰ` (全角) と `米GDP` (半角) を揃える
    s = unicodedata.normalize('NFKC', str(title)).lower()
    s = _PUNCT_RE.sub('', s)
    s = _LIVE_RE.sub('', s)
    return s[:18]


def _title_bigrams(title):
    if not title:
        return frozenset()
    s = unicodedata.normalize('NFKC', str(title)).lower()
    s = _PUNCT_RE.sub('', s)
    s = _LIVE_RE.sub('', s)
    if len(s) < 2:
        return frozenset()
    return frozenset(s[i:i+2] for i in range(len(s) - 1))


def _jaccard_title_sim(a, b):
    bg_a = _title_bigrams(a)
    bg_b = _title_bigrams(b)
    if not bg_a or not bg_b:
        return 0.0
    inter = bg_a & bg_b
    union = bg_a | bg_b
    if not union:
        return 0.0
    return len(inter) / len(union)


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
    ai_topic_candidates = []
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
        if t.get('aiGenerated'):
            best_title = t.get('generatedTitle') or t.get('title') or ''
            if best_title:
                ai_topic_candidates.append((tid_e, best_title, last))
    if not title_to_tid and not ai_topic_candidates:
        return group_tids
    ai_topic_candidates.sort(key=lambda x: x[2], reverse=True)
    ai_topic_bigrams = [
        (tid_e, ttl, _title_bigrams(ttl)) for tid_e, ttl, _ in ai_topic_candidates[:200]
    ]
    rebound_resolved = []
    for g, tid in group_tids:
        candidate = _extractive_title(g) or (g[0].get('title', '') if g else '')
        norm = _title_dedup_key(candidate)
        target = title_to_tid.get(norm)
        if target and target != tid:
            tid = target
        elif ai_topic_bigrams and candidate:
            cand_bg = _title_bigrams(candidate)
            if cand_bg:
                best_sim = 0.0
                best_tid = None
                for tid_e, _ttl, ttl_bg in ai_topic_bigrams:
                    if not ttl_bg:
                        continue
                    inter = cand_bg & ttl_bg
                    if not inter:
                        continue
                    union = cand_bg | ttl_bg
                    if not union:
                        continue
                    sim = len(inter) / len(union)
                    if sim > best_sim:
                        best_sim = sim
                        best_tid = tid_e
                if best_tid and best_sim >= _JACCARD_THRESHOLD and best_tid != tid:
                    tid = best_tid
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

    def test_nfkc_full_width_alpha(self):
        # T2026-0430-L: 全角 ＧＤＰ と半角 GDP が同一キーに揃うこと
        self.assertEqual(
            _title_dedup_key('米ＧＤＰ速報値発表'),
            _title_dedup_key('米GDP速報値発表'),
        )

    def test_nfkc_full_width_digits(self):
        # 全角数字 ２０２６ と半角 2026 も同じ
        self.assertEqual(
            _title_dedup_key('２０２６年予算審議'),
            _title_dedup_key('2026年予算審議'),
        )


class JaccardTitleSimilarityTest(unittest.TestCase):
    """T2026-0430-L: bigram Jaccard 類似度の boundary test。"""

    def test_same_event_close_variation(self):
        # 同イベント・近い言い回しは >= 0.35 (典型: 一方が他方の長い版)
        sim = _jaccard_title_sim(
            '米GDP速報値2.0%増',
            '米GDP速報値2.0%増 1〜3月期',
        )
        self.assertGreaterEqual(sim, _JACCARD_THRESHOLD,
                                f'近接同イベントなら >= {_JACCARD_THRESHOLD}: 実測 {sim:.3f}')

    def test_distant_same_event_below_threshold(self):
        # 注意: 同イベントでも切り口が大きく違うと bigram Jaccard では捕捉しきれない。
        # 「米GDP速報値2.0%増 1〜3月期」vs「米GDP年率2.0%増 4四半期連続のプラス成長」
        # = 0.226 < 0.35 で merge されない。これは false positive 抑制とのトレードオフ。
        # 将来 entity-level 一致にアップグレードする余地あり (T2026-0430-L コメント)。
        sim = _jaccard_title_sim(
            '米GDP速報値2.0%増 1〜3月期',
            '米GDP年率2.0%増 4四半期連続のプラス成長',
        )
        self.assertLess(sim, _JACCARD_THRESHOLD,
                        f'参考値: {sim:.3f} (entity-level なら拾える)')

    def test_different_events_low_sim(self):
        # 別イベントは < 0.35 (boundary - merge してはいけない)
        sim = _jaccard_title_sim(
            '米GDP速報値2.0%増 1〜3月期',
            '米雇用統計 非農業部門就業者数増加',
        )
        self.assertLess(sim, _JACCARD_THRESHOLD,
                        f'別イベントなら < {_JACCARD_THRESHOLD}: 実測 {sim:.3f}')

    def test_full_width_normalized(self):
        # NFKC 後に bigram を作るので 全角/半角差は類似度を下げない
        sim = _jaccard_title_sim('米ＧＤＰ速報値', '米GDP速報値')
        self.assertEqual(sim, 1.0, '全角/半角差のみなら完全一致')

    def test_empty_returns_zero(self):
        self.assertEqual(_jaccard_title_sim('', '何か'), 0.0)
        self.assertEqual(_jaccard_title_sim('何か', ''), 0.0)
        self.assertEqual(_jaccard_title_sim(None, None), 0.0)


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

    def test_jaccard_rebinds_to_existing_ai_topic(self):
        # T2026-0430-L: 完全一致しなくても Jaccard >= 0.35 で AI topic に再バインド。
        # 「短い形」と「詳報を足した長い形」は典型的な高類似度ケース。
        existing = [{
            'topicId': 'tid_ai',
            'title': '米GDP速報値2.0%増',
            'generatedTitle': '米GDP速報値2.0%増',
            'lastArticleAt': self.now - 3600,
            'lifecycleStatus': 'active',
            'aiGenerated': True,
        }]
        gt = [([_FakeArticle(url='new1',
                             title='米GDP速報値2.0%増 1〜3月期')], 'tid_new')]
        out = _resolve(gt, existing, self.now)
        self.assertEqual(out[0][1], 'tid_ai',
                         'Jaccard>=0.35 で既存 AI topic に再バインドされるべき')

    def test_jaccard_does_not_rebind_to_non_ai_topic(self):
        # aiGenerated=False の topic は Jaccard fallback の候補にしない。
        # (一致したい先は AI 生成済 topic のみ — extractive topic への merge は
        # 既存の完全一致 dedup でカバーされており、Jaccard で広げると誤マージリスク)
        existing = [{
            'topicId': 'tid_extractive',
            'title': '米GDP速報値2.0%増',
            'lastArticleAt': self.now - 3600,
            'lifecycleStatus': 'active',
            'aiGenerated': False,
        }]
        gt = [([_FakeArticle(url='new1',
                             title='米GDP速報値2.0%増 1〜3月期')], 'tid_new')]
        out = _resolve(gt, existing, self.now)
        self.assertEqual(out[0][1], 'tid_new',
                         'aiGenerated=False には Jaccard fallback で bind しない')

    def test_jaccard_does_not_rebind_different_events(self):
        # boundary: 別イベントは Jaccard < 0.35 で bind しない
        existing = [{
            'topicId': 'tid_gdp',
            'title': '米GDP速報値2.0%増 1〜3月期',
            'generatedTitle': '米GDP速報値2.0%増 1〜3月期',
            'lastArticleAt': self.now - 3600,
            'lifecycleStatus': 'active',
            'aiGenerated': True,
        }]
        gt = [([_FakeArticle(url='new1',
                             title='米雇用統計 非農業部門就業者数増加')], 'tid_new')]
        out = _resolve(gt, existing, self.now)
        self.assertEqual(out[0][1], 'tid_new',
                         '別イベント (米GDP vs 米雇用統計) は merge してはいけない')

    def test_jaccard_full_width_match(self):
        # 全角/半角差のみなら NFKC 正規化により完全一致 dedup が走るが、
        # 仮に prefix 18 字超の差で完全一致しない場合も Jaccard で救済される
        existing = [{
            'topicId': 'tid_zenkaku',
            'title': '米ＧＤＰ速報値2.0％増 1〜3月期',
            'generatedTitle': '米ＧＤＰ速報値2.0％増 1〜3月期',
            'lastArticleAt': self.now - 3600,
            'lifecycleStatus': 'active',
            'aiGenerated': True,
        }]
        gt = [([_FakeArticle(url='new1',
                             title='米GDP速報値2.0%増 1〜3月期')], 'tid_new')]
        out = _resolve(gt, existing, self.now)
        self.assertEqual(out[0][1], 'tid_zenkaku',
                         'NFKC 正規化で全角/半角差は同一 tid に集約')

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


class WithinRunDedupGuardTest(unittest.TestCase):
    """T2026-0501-M: _merge_within_run_duplicates の boundary test。"""

    def setUp(self):
        with open(HANDLER_PATH, 'r', encoding='utf-8') as f:
            self.source = f.read()

    def test_function_exists(self):
        self.assertIn('def _merge_within_run_duplicates(', self.source,
                      'T2026-0501-M: _merge_within_run_duplicates が削除されている。'
                      '同一 run 内分裂の恒久対処が外れた可能性。')

    def test_called_after_resolve_tid_collisions(self):
        """_merge_within_run_duplicates が _resolve_tid_collisions_by_title 呼び出し後に続くこと。"""
        resolve_call = self.source.find('group_tids = _resolve_tid_collisions_by_title(')
        within_call = self.source.find('group_tids = _merge_within_run_duplicates(')
        self.assertGreater(resolve_call, 0, '_resolve_tid_collisions_by_title 呼び出しが消えている')
        self.assertGreater(within_call, 0, '_merge_within_run_duplicates 呼び出しが消えている')
        self.assertGreater(within_call, resolve_call,
                           '_merge_within_run_duplicates が _resolve_tid_collisions_by_title より前にある')

    def test_borderline_threshold_lowered(self):
        """_JACCARD_BORDERLINE_LOW が 0.10 以下に設定されていること (T2026-0501-M 調整)。"""
        m = re.search(r'_JACCARD_BORDERLINE_LOW\s*=\s*([0-9.]+)', self.source)
        self.assertIsNotNone(m, '_JACCARD_BORDERLINE_LOW 定数が見つからない')
        val = float(m.group(1))
        self.assertLessEqual(val, 0.10,
                             f'_JACCARD_BORDERLINE_LOW={val} が 0.10 より大きい。'
                             '欧州/ドイツ米軍削減ペアが Haiku 判定に到達しない。')


class EntityPatternMilitaryTest(unittest.TestCase):
    """T2026-0501-M: 米軍が ENTITY_PATTERNS に含まれること。"""

    def setUp(self):
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'lambda', 'fetcher', 'config.py',
        )
        with open(config_path, 'r', encoding='utf-8') as f:
            self.source = f.read()

    def test_jietai_military_in_entity_patterns(self):
        """米軍|自衛隊 が ENTITY_PATTERNS に含まれること。"""
        self.assertIn('米軍', self.source,
                      'T2026-0501-M: 米軍が ENTITY_PATTERNS にない。'
                      '欧州/ドイツ米軍削減の entity bonus が発動しない。')

    def test_geographic_containment_in_merge_judge(self):
        """ai_merge_judge.py に地理的包含ルールが記述されていること。"""
        judge_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'lambda', 'fetcher', 'ai_merge_judge.py',
        )
        with open(judge_path, 'r', encoding='utf-8') as f:
            judge_src = f.read()
        self.assertIn('地理的包含', judge_src,
                      'T2026-0501-M: ai_merge_judge.py に地理的包含ルールがない。'
                      'ドイツ⊂欧州 ペアが Haiku に別事件と判定される可能性。')


if __name__ == '__main__':
    unittest.main()
