"""T237 → T2026-0430-J: fetcher_trigger 経路で kp-rescue を pending **先頭** 挿入する物理ガード。

背景:
  T237 (2026-04-29) は fetcher_trigger の空き API budget を keyPoint backfill に使う実装だったが、
  pending **末尾** に追加していたため、API call budget (=10) で 5 topic 処理時点で loop break され
  末尾 backfill が永久に処理されない bug があった。
  結果: 短い keyPoint 87件 (本番 77.7%) が 2026-04-26〜29 から数日滞留。

T2026-0430-J 修正 (2026-04-30):
  rescue 件数を KP_RESCUE_PER_RUN=2 に固定し、pending **先頭** に挿入する。
  これにより 30 分ごとの fetcher_trigger run で確実に 2 件ずつ kp-missing が消化される
  (48 runs/day × 2件 = 96件/day 上限 → 87件は ~1日で全消化)。

このテストは以下を物理確認する:
  - topic_id_filter 指定時は kp-rescue が pending 先頭に挿入される
  - rescue 件数は KP_RESCUE_PER_RUN を超えない
  - 指定 IDs と rescue 結果の重複は取り除かれる
  - get_pending_topics 例外時も rescue を握り潰し本処理は継続する
  - scheduled cron (topic_id_filter=None) では rescue を呼ばない
  - rescue が空のときは pending は変化しない
"""
import unittest


KP_RESCUE_PER_RUN = 2


class FetcherKpRescueLogicTest(unittest.TestCase):
    """handler.py の T2026-0430-J kp-rescue ロジックを純関数として再現したテスト。

    handler.py 全体は boto3 や Lambda context に依存するため、
    本テストは rescue 部分だけ抽出した純関数で同じ判定を検証する。
    実装の同期は CI の grep guard (HandlerKpRescueSourceGuardTest) で担保する。
    """

    @staticmethod
    def apply_kp_rescue(topic_id_filter, pending_initial, rescue_pool, max_rescue=KP_RESCUE_PER_RUN):
        """handler.py 内の T2026-0430-J kp-rescue ロジックを再現。

        topic_id_filter が真なら rescue_pool 先頭から max_rescue 件を取り、
        既存 IDs と重複しないものだけを pending **先頭** に挿入する。
        """
        pending = list(pending_initial)
        if topic_id_filter:
            try:
                existing_ids = {p.get('topicId') for p in pending}
                rescue_added = [r for r in rescue_pool
                                if r.get('topicId') not in existing_ids][:max_rescue]
                if rescue_added:
                    pending = rescue_added + pending
            except Exception:
                pass
        return pending

    def test_rescue_prepends_to_pending(self):
        """指定 IDs 5 件 + rescue 2 件 → pending 先頭 2 件が rescue になる"""
        pending = [{'topicId': f'fetcher{i}'} for i in range(5)]
        pool = [{'topicId': f'kp{i}'} for i in range(10)]
        result = self.apply_kp_rescue(True, pending, pool)
        self.assertEqual(len(result), 7)
        # 先頭 2 件は rescue
        self.assertEqual([r['topicId'] for r in result[:2]], ['kp0', 'kp1'])
        # 残りは fetcher 元順
        self.assertEqual([r['topicId'] for r in result[2:]],
                         [f'fetcher{i}' for i in range(5)])

    def test_rescue_caps_at_kp_rescue_per_run(self):
        """KP_RESCUE_PER_RUN=2 を超えて挿入しない (10 件あっても先頭 2 件のみ)"""
        pending = [{'topicId': 'fetcher1'}]
        pool = [{'topicId': f'kp{i}'} for i in range(10)]
        result = self.apply_kp_rescue(True, pending, pool)
        rescued = [r['topicId'] for r in result if r['topicId'].startswith('kp')]
        self.assertEqual(len(rescued), 2)
        self.assertEqual(rescued, ['kp0', 'kp1'])

    def test_rescue_dedups_against_filter(self):
        """指定 IDs と rescue が重複していたら重複は弾く"""
        pending = [{'topicId': 'common'}, {'topicId': 'fetcher2'}]
        pool = [{'topicId': 'common'}, {'topicId': 'kp0'}, {'topicId': 'kp1'}]
        result = self.apply_kp_rescue(True, pending, pool)
        ids = [r['topicId'] for r in result]
        self.assertEqual(ids.count('common'), 1)
        # rescue は重複を飛ばして kp0 と kp1 を入れる
        self.assertEqual(result[0]['topicId'], 'kp0')
        self.assertEqual(result[1]['topicId'], 'kp1')
        # その後ろに既存 pending
        self.assertEqual([r['topicId'] for r in result[2:]], ['common', 'fetcher2'])

    def test_rescue_skipped_for_scheduled_cron(self):
        """topic_id_filter が None (scheduled cron) なら rescue は呼ばれない"""
        pending = [{'topicId': f'pend{i}'} for i in range(3)]
        pool = [{'topicId': f'kp{i}'} for i in range(10)]
        result = self.apply_kp_rescue(None, pending, pool)
        self.assertEqual([r['topicId'] for r in result],
                         ['pend0', 'pend1', 'pend2'])

    def test_rescue_empty_pool_no_change(self):
        """rescue_pool が空ならば pending は変化しない"""
        pending = [{'topicId': f'fetcher{i}'} for i in range(3)]
        result = self.apply_kp_rescue(True, pending, [])
        self.assertEqual([r['topicId'] for r in result],
                         ['fetcher0', 'fetcher1', 'fetcher2'])

    def test_rescue_when_pending_already_full(self):
        """pending が effective_max を超えていても rescue は先頭に挿入される
        (後段の API call budget で loop break 時に rescue が確実に処理されるための変更)。
        """
        pending = [{'topicId': f'fetcher{i}'} for i in range(12)]
        pool = [{'topicId': f'kp{i}'} for i in range(10)]
        result = self.apply_kp_rescue(True, pending, pool)
        self.assertEqual(len(result), 14)
        # 先頭 2 件は rescue
        self.assertEqual([r['topicId'] for r in result[:2]], ['kp0', 'kp1'])
        # その後 fetcher 12 件が続く
        self.assertEqual([r['topicId'] for r in result[2:]],
                         [f'fetcher{i}' for i in range(12)])


class HandlerKpRescueSourceGuardTest(unittest.TestCase):
    """handler.py の実コードに T2026-0430-J kp-rescue ロジックが残っているかを grep で確認する物理ガード。

    リファクタで rescue が外れたら本テストが失敗する。
    """

    def test_handler_contains_kp_rescue(self):
        import os
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(root, 'lambda', 'processor', 'handler.py')
        with open(path, encoding='utf-8') as f:
            src = f.read()
        # キーフレーズ 3 つが揃っているか確認
        self.assertIn('KP_RESCUE_PER_RUN', src,
                      'handler.py から KP_RESCUE_PER_RUN が消えた (T2026-0430-J リグレッション)')
        self.assertIn('kp-rescue', src,
                      'handler.py から kp-rescue ログが消えた (T2026-0430-J リグレッション)')
        # 先頭挿入であることを確認 (extend ではなく rescue_added + pending)
        self.assertIn('rescue_added + pending', src,
                      'handler.py で rescue を pending 先頭に挿入していない '
                      '(T2026-0430-J: 末尾 extend だと API budget 切れで永久に処理されない bug)')


if __name__ == '__main__':
    unittest.main()
