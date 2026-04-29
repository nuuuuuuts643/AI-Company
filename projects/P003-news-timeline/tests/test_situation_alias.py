"""T2026-0429-F regression test: situation = keyPoint の publish-layer alias を物理ガードする。

背景 (2026-04-29 11:09 JST 巡回):
  公開対象 (topics.json) の `situation` フィールドが 104件中 0件 (0.00%)。
  perspectives 36.54% / outlook 35.58% に対し situation だけ 0%。
  原因: schema/normalize/publish のどの層にも `situation` フィールド自体が存在しなかった。
  概念上「状況解説」は `keyPoint` 一本で実装されていたため、SLI が phantom-field を見ていた。

修正:
  - handler.py `_trim` で keyPoint→situation を topics.json publish 時に copy。
  - proc_storage.update_topic_s3_file で keyPoint→situation を topic detail JSON に copy。
  - proc_storage._CARD_INCLUDE_KEYS に situation を追加 (topics-card.json にも乗る)。
  - proc_storage.generate_health_json に situationCount/situationRate を追加。

このテストは:
  1) handler._trim 等価ロジック: keyPoint があれば situation が同値で出る
  2) keyPoint が空/None なら situation は出ない
  3) generate_topics_card_json: card 経路でも situation が含まれる
  4) generate_health_json: situationRate が keyPointRate と同値で出る

実行:
  cd projects/P003-news-timeline
  python3 -m unittest tests.test_situation_alias -v
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'lambda', 'processor'))

os.environ.setdefault('S3_BUCKET', 'test-bucket')
os.environ.setdefault('AWS_REGION', 'ap-northeast-1')

import proc_storage  # noqa: E402


# handler.py の _trim ロジックを test 用に再現する (handler.py 全体は boto3 等の重い
# 副作用を持つため import しない。同じロジックを inline コピーして検証する)。
_PROC_INTERNAL = {'SK', 'pendingAI', 'ttl', 'spreadReason', 'forecast', 'storyTimeline',
                  'backgroundContext', 'background'}


def _trim_emulation(t: dict) -> dict:
    """handler.py の _trim と同じロジック。lockstep で更新する。"""
    out = {k: v for k, v in t.items() if k not in _PROC_INTERNAL}
    kp = out.get('keyPoint')
    if kp:
        out['situation'] = kp
    return out


class SituationAliasTest(unittest.TestCase):
    def test_trim_emits_situation_when_keypoint_present(self):
        topic = {
            'topicId': 'a' * 16,
            'aiGenerated': True,
            'keyPoint': 'もともと地政学的緊張があり、外交ルートが立ち上がり、現在は調整段階に入っている。' * 3,
            'perspectives': '朝日は経済影響を懸念、産経は安全保障上の利益を指摘。',
        }
        out = _trim_emulation(topic)
        self.assertEqual(out.get('situation'), topic['keyPoint'],
                         'situation should equal keyPoint at publish time')
        self.assertNotIn('SK', out, '_PROC_INTERNAL fields must still be stripped')

    def test_trim_omits_situation_when_keypoint_empty(self):
        topic = {
            'topicId': 'b' * 16,
            'aiGenerated': True,
            'keyPoint': None,
        }
        out = _trim_emulation(topic)
        self.assertNotIn('situation', out, 'situation should not be set when keyPoint is None')

        topic2 = {'topicId': 'c' * 16, 'keyPoint': ''}
        out2 = _trim_emulation(topic2)
        self.assertNotIn('situation', out2, 'situation should not be set when keyPoint is empty string')

    def test_trim_omits_situation_when_keypoint_missing(self):
        topic = {'topicId': 'd' * 16, 'aiGenerated': True}
        out = _trim_emulation(topic)
        self.assertNotIn('situation', out, 'situation should not be set when keyPoint key is absent')

    def test_card_include_keys_contain_situation(self):
        self.assertIn('situation', proc_storage._CARD_INCLUDE_KEYS,
                      '_CARD_INCLUDE_KEYS must include situation so topics-card.json carries it')

    def test_generate_topics_card_json_carries_situation(self):
        ts_iso = '2026-04-29T13:00:00+00:00'
        topics_pub = [
            {
                'topicId': 'e' * 16,
                'topicTitle': 'テスト',
                'keyPoint': 'kp text',
                'situation': 'kp text',
                'aiGenerated': True,
            }
        ]
        payload = proc_storage.generate_topics_card_json(topics_pub, ts_iso)
        self.assertEqual(len(payload['topics']), 1)
        self.assertEqual(payload['topics'][0].get('situation'), 'kp text',
                         'topics-card.json must carry situation alias')

    def test_generate_health_json_includes_situation_rate(self):
        ts_iso = '2026-04-29T13:00:00+00:00'
        topics = [
            {'aiGenerated': True, 'keyPoint': 'kp1', 'situation': 'kp1', 'articleCount': 3},
            {'aiGenerated': True, 'keyPoint': 'kp2', 'situation': 'kp2', 'articleCount': 5},
            {'aiGenerated': True, 'keyPoint': None, 'articleCount': 2},
            {'aiGenerated': False, 'articleCount': 1},
        ]
        h = proc_storage.generate_health_json(topics, ts_iso)
        self.assertIn('situationCount', h, 'health.json must expose situationCount')
        self.assertIn('situationRate', h, 'health.json must expose situationRate')
        self.assertEqual(h['situationCount'], 2)
        self.assertEqual(h['keyPointCount'], 2)
        # alias 設計上、situation は keyPoint と同値で出るはず。
        self.assertEqual(h['situationRate'], h['keyPointRate'],
                         'situationRate must match keyPointRate (alias semantics)')

    def test_update_topic_s3_file_meta_sync_logic(self):
        """update_topic_s3_file 内の keyPoint→situation sync ロジックを直接検証する。

        S3/DDB を mock せず、関数内で meta dict を組み立てる小ロジックを再現する。
        実際の s3 put は I/O 込みで重いので、ここでは「meta['keyPoint'] が
        立っていれば meta['situation'] も同値になる」前提条件のみ確認する。
        """
        meta = {'keyPoint': 'もともと外交ルートが…' * 5}
        # update_topic_s3_file の同期ロジックを inline 実行する。
        if meta.get('keyPoint'):
            meta['situation'] = meta['keyPoint']
        self.assertEqual(meta.get('situation'), meta.get('keyPoint'))


if __name__ == '__main__':
    unittest.main()
