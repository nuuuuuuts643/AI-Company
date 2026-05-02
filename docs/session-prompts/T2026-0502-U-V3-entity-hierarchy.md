# Code セッション起動プロンプト: T2026-0502-U-V3 Entity Hierarchy で false-split 解消

> **これを丸ごと Code セッションに渡してください**
> **作成**: 2026-05-02 (Cowork) / **モデル**: Sonnet 4.6 推奨 / **想定**: 1 セッション
> **前提**: T2026-0502-U (embedding 移行) Phase 1 不採用判断後の pivot

---

## 1 行サマリ

`欧州駐留米軍 vs ドイツ駐留米軍` のような **false-split を rule-based (entity hierarchy) で恒久解消** する。
embedding は overkill だった。月 $0・unit test で品質物理担保・改善継続可能。

---

## 経緯（30 秒で読める）

- 2026-05-02 朝: PR #118 で `_JACCARD_BORDERLINE_LOW` を 0.10 に下げ + Haiku merge judge 復活
  → fetcher Haiku call 1100/run → 月 $380 増。品質効果は SLI 不在で実証なし
- Cowork が止血: env override で `AI_MERGE_ENABLED=false` → pairs=0・月 $12 復帰
- Phase 1 PoC: multilingual-e5-small ONNX qint8 で bench → **misses=3/6** (`同一事件最低類似度 < 別事件最高類似度` で閾値分離不可能・docs/p003-embedding-migration-research.md §9 参照)
- voyage-3-lite API も検討候補だが API 依存・bench 結果次第・PO は「品質よりコスト・恒久対処」を優先
- → **pivot: rule-based entity hierarchy** で false-split 解消

## なぜ embedding でなく rule か

1. **問題は意味類似ではなく階層関係**: 「欧州 ⊃ ドイツ」「関西 ⊃ 大阪」は確率推論不要・dict で表現可能
2. **改善コストが線形**: false-split 事例 → fixture 追加 → ルール 1 行追加で恒久解消
3. **品質物理担保**: unit test で fixture pass を CI で検証可能 (embedding bench は統計勝負)
4. **退避路あり**: rule で取れない真の意味類似 (5-10%) が残ったら、対象を絞った上で voyage 評価復活可

---

## やること

### Step 0: 起動チェック

```bash
cd ~/ai-company/AI-COMPANY
bash scripts/session_bootstrap.sh

# WORKING.md 着手宣言
echo "| [Code] T2026-0502-U-V3 entity hierarchy | Code | lambda/fetcher/config.py, lambda/fetcher/cluster_utils.py, lambda/fetcher/text_utils.py, tests/test_entity_hierarchy.py | $(date '+%Y-%m-%d %H:%M') | yes |" >> WORKING.md
git add WORKING.md && git commit -m "wip: T2026-0502-U-V3 着手" && git push
```

### Step 1: 既存 entity 抽出ロジックを把握 (15 分)

```bash
grep -n "ENTITY_PATTERNS\|SYNONYMS\|extract_title_entities\|_extract_primary_entity" \
  lambda/fetcher/config.py lambda/fetcher/text_utils.py lambda/fetcher/cluster_utils.py \
  lambda/fetcher/handler.py | head -30
```

理解する点:
- `_extract_title_entities()` がタイトルから entity set を抜く実装
- `_resolve_tid_collisions_by_title()` / `_merge_within_run_duplicates()` で `shared_entities` 計算
- 「shared_entities が空 → 別事件」の entity gate がすでにある (これが効く前提を維持する)

### Step 2: ENTITY_HIERARCHY 設計 + 追加 (30 分)

`lambda/fetcher/config.py` に追加:

```python
# T2026-0502-U-V3 (2026-05-02): rule-based hierarchy で false-split 解消。
# embedding (multilingual-e5-small) で閾値分離不可能だったため pivot。
# 親 → 子のリスト。「親」が一方の entity に含まれ、「子」のいずれかが他方に含まれれば
# 同一階層として shared_entities にカウントする。
#
# 改善ルール: false-split 事例が観察されたら、tests/test_entity_hierarchy.py に
# fixture を 1 件追加 + ここに dict 1 行追加。CI で regression を物理担保。
ENTITY_HIERARCHY = {
    # 地理 (大陸・地域)
    '欧州':   ['ドイツ', 'フランス', 'イタリア', '英国', 'スペイン', 'オランダ', 'ベルギー',
               '北欧', '東欧', 'EU', 'NATO', 'ポーランド', 'スウェーデン', 'フィンランド',
               'ノルウェー', 'デンマーク', 'スイス', 'オーストリア', 'チェコ'],
    'EU':     ['ドイツ', 'フランス', 'イタリア', 'スペイン', 'オランダ', 'ベルギー',
               'ポーランド', 'スウェーデン', 'デンマーク', 'チェコ'],
    '北米':   ['米国', 'カナダ', 'メキシコ'],
    '中南米': ['ブラジル', 'アルゼンチン', 'チリ', 'ペルー', 'メキシコ', 'コロンビア',
               'ベネズエラ', 'キューバ'],
    '中東':   ['イスラエル', 'パレスチナ', 'イラン', 'サウジアラビア', 'UAE', 'カタール',
               'トルコ', 'シリア', 'イラク', 'レバノン', 'ヨルダン', 'エジプト', 'イエメン'],
    '東南アジア': ['ベトナム', 'タイ', 'マレーシア', 'シンガポール', 'インドネシア',
                  'フィリピン', 'ミャンマー', 'カンボジア', 'ラオス'],
    'アフリカ': ['南アフリカ', 'ナイジェリア', 'エジプト', 'ケニア', 'エチオピア', 'モロッコ',
                'アルジェリア', 'ガーナ', 'タンザニア'],
    # 日本国内 (地方ブロック)
    '関東':   ['東京', '神奈川', '千葉', '埼玉', '茨城', '栃木', '群馬'],
    '関西':   ['大阪', '京都', '兵庫', '奈良', '滋賀', '和歌山'],
    '東海':   ['愛知', '静岡', '岐阜', '三重'],
    '東北':   ['青森', '岩手', '宮城', '秋田', '山形', '福島'],
    '九州':   ['福岡', '佐賀', '長崎', '熊本', '大分', '宮崎', '鹿児島'],
    '北陸':   ['新潟', '富山', '石川', '福井'],
    '中国地方': ['広島', '岡山', '山口', '島根', '鳥取'],
    '四国':   ['徳島', '香川', '愛媛', '高知'],
    # 組織・政府
    '政府':   ['官房', '内閣', '財務省', '外務省', '防衛省', '経産省', '総務省', '厚労省',
               '文科省', '農水省', '国交省', '環境省', '法務省', 'デジタル庁'],
    '日銀':   ['日本銀行', '中央銀行', '中銀'],
    '米軍':   ['在日米軍', '在韓米軍', '駐留米軍', 'NATO軍', '海兵隊', '陸軍', '空軍', '海軍'],
    '与党':   ['自民党', '公明党'],
    # 国際機関
    '国連':   ['UNICEF', 'UNHCR', 'WHO', 'WFP', 'UNESCO', 'IAEA', '安保理'],
    'G7':     ['米国', 'カナダ', '英国', 'フランス', 'ドイツ', 'イタリア', '日本'],
    'G20':    ['米国', 'カナダ', '英国', 'フランス', 'ドイツ', 'イタリア', '日本',
               '中国', 'インド', 'ブラジル', 'ロシア', 'メキシコ', 'インドネシア',
               'トルコ', 'サウジアラビア', '韓国', '南アフリカ', 'アルゼンチン',
               'オーストラリア', 'EU'],
}

# 逆引き: child → parent の set を事前計算 (cluster_utils で hot loop で参照するため)
ENTITY_HIERARCHY_REVERSE: dict[str, set[str]] = {}
for _parent, _children in ENTITY_HIERARCHY.items():
    for _c in _children:
        ENTITY_HIERARCHY_REVERSE.setdefault(_c, set()).add(_parent)
```

### Step 3: shared_entities 計算に hierarchy 統合 (30 分)

既存の `_extract_title_entities()` または entity intersection ロジックを拡張する箇所を特定し
（`lambda/fetcher/handler.py` および `lambda/fetcher/cluster_utils.py` の entity overlap 判定箇所）、
以下のヘルパを追加:

```python
# lambda/fetcher/text_utils.py に追加
from config import ENTITY_HIERARCHY, ENTITY_HIERARCHY_REVERSE

def hierarchy_aware_overlap(entities_a: set, entities_b: set) -> set:
    """A と B の entity が「同じ階層を共有」する場合を含めて overlap を返す。

    例: A={'欧州', 'トランプ', '米軍'}, B={'ドイツ', 'トランプ', '米軍'}
        既存ロジックの直接 overlap = {'トランプ', '米軍'}
        hierarchy 込み overlap = {'トランプ', '米軍', '欧州'} (欧州⊃ドイツ で hit)

    判定:
      1. 直接 overlap (set intersection)
      2. A の各 entity について、ENTITY_HIERARCHY[entity] が B のいずれかと一致 → 親 (A side) を overlap に追加
      3. 逆方向も同様 (B が親、A が子)
    """
    direct = entities_a & entities_b
    extended = set(direct)
    for ea in entities_a:
        children = ENTITY_HIERARCHY.get(ea)
        if children and any(c in entities_b for c in children):
            extended.add(ea)
    for eb in entities_b:
        children = ENTITY_HIERARCHY.get(eb)
        if children and any(c in entities_a for c in children):
            extended.add(eb)
    return extended
```

`handler.py` の `_resolve_tid_collisions_by_title()` および `_merge_within_run_duplicates()` 内で `shared_entities` を計算している箇所を、`hierarchy_aware_overlap()` 呼び出しに置換。

### Step 4: unit test 追加 (15 分)

`projects/P003-news-timeline/tests/test_entity_hierarchy.py` 新設:

```python
import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lambda', 'fetcher'))
from text_utils import hierarchy_aware_overlap


class TestEntityHierarchy(unittest.TestCase):
    """T2026-0501-M フィクスチャを物理担保するテスト群。
    
    新しい false-split 事例が見つかったら、ここに 1 ケース追加 +
    config.py の ENTITY_HIERARCHY に dict 1 行追加。CI で regression を防ぐ。
    """

    def test_europe_subsumes_germany(self):
        """T2026-0501-M 元事例: 欧州駐留米軍 vs ドイツ駐留米軍。"""
        a = {'欧州', 'トランプ', '米軍'}
        b = {'ドイツ', 'トランプ', '米軍'}
        overlap = hierarchy_aware_overlap(a, b)
        self.assertIn('欧州', overlap, '欧州⊃ドイツ で hit すべき')
        self.assertGreaterEqual(len(overlap), 3, 'shared >=3 で同一事件と判定可能')

    def test_kanto_subsumes_tokyo(self):
        a = {'関東', '気象庁', '大雨'}
        b = {'東京', '気象庁', '大雨'}
        overlap = hierarchy_aware_overlap(a, b)
        self.assertIn('関東', overlap)

    def test_government_subsumes_ministry(self):
        a = {'政府', '改革'}
        b = {'財務省', '改革'}
        overlap = hierarchy_aware_overlap(a, b)
        self.assertIn('政府', overlap)

    def test_no_false_match_us_vs_japan(self):
        """米国 GDP vs 日本 GDP は別事件のまま (hierarchy で誤マージしない)。"""
        a = {'米国', 'GDP', '速報値'}
        b = {'日本', 'GDP', '速報値'}
        overlap = hierarchy_aware_overlap(a, b)
        # 米国 と 日本 は親子関係でない → overlap は GDP, 速報値 のみ (米国 / 日本 は入らない)
        self.assertNotIn('米国', overlap)
        self.assertNotIn('日本', overlap)
        # ただし「G7」階層に両方入るので G7 経由でくっつくか確認 (両方 G7 子要素)
        # → 現実装は親→子方向のみなので G7 は加わらない (これが正しい動作・主体異なるペアは別事件)

    def test_g7_member_pairs_no_match(self):
        """G7 加盟国同士は階層的に「同 G7」だが別主体 → 誤マージしない。"""
        a = {'米国', '関税'}  # G7 子要素
        b = {'ドイツ', '関税'}  # G7 子要素
        overlap = hierarchy_aware_overlap(a, b)
        # 親 (G7) は両 entities に含まれていないので加わらない (実装意図通り)
        self.assertEqual(overlap, {'関税'}, '主体違いは G7 経由で誤マージしないこと')

    def test_empty_returns_empty(self):
        self.assertEqual(hierarchy_aware_overlap(set(), set()), set())
        self.assertEqual(hierarchy_aware_overlap({'a'}, set()), set())


if __name__ == '__main__':
    unittest.main()
```

### Step 5: 動作確認 + PR 作成 (10 分)

```bash
cd projects/P003-news-timeline
python3 -m unittest tests.test_entity_hierarchy -v
# → 6/6 PASS

# 既存テストも通ることを確認
python3 -m unittest tests.test_title_dedup_guard -v
# → 全 PASS

# PR
git checkout -b feat/T2026-0502-U-V3-entity-hierarchy
git add lambda/fetcher/config.py lambda/fetcher/text_utils.py \
        lambda/fetcher/handler.py tests/test_entity_hierarchy.py \
        docs/p003-embedding-migration-research.md
git commit -m "feat: T2026-0502-U-V3 entity hierarchy で false-split を rule-based 解消

embedding (multilingual-e5-small) は Phase 1 bench で misses=3/6 (閾値分離不可能) だった
ため pivot。rule-based hierarchy で「欧州⊃ドイツ」「関西⊃大阪」「政府⊃財務省」等を
shared_entities 拡張で表現。

- ENTITY_HIERARCHY (地理・組織・国際機関) を config.py に追加
- hierarchy_aware_overlap() を text_utils.py に追加
- handler.py の shared_entities 計算箇所を置換
- tests/test_entity_hierarchy.py に T2026-0501-M フィクスチャ含む 6 ケース

恒久・最安 (\$0)・物理品質担保 (unit test) の三点同時成立。
embedding 路線は不採用判断 → docs/p003-embedding-migration-research.md §9 結論更新。

Verified: tests/test_entity_hierarchy.py:6passed:$(date +%Y-%m-%d) + tests/test_title_dedup_guard.py 全 PASS
Verified-Effect-Pending: 2026-05-09 production で suspected_mismerge_count 推移確認 +
                        手動 sample で「欧州駐留米軍」型 false-split が消えてるか確認"
git push origin HEAD
gh pr create --fill
```

PR 作成したら**即セッション exit**。CI 待ち禁止 (CLAUDE.md 規則)。

### Step 6: 観察ループ追加（オプション・余裕あれば）

`p003-haiku` schedule task の朝確認プロンプトに「直近 24h で suspected_mismerge_count 上位 5 件の topic ペアを sample → false-split 候補として WORKING.md に記録」を追加。
これで毎朝、新しい hierarchy 補強候補が見える。

---

## 完了条件（妥協禁止）

- [ ] `tests/test_entity_hierarchy.py` 6/6 PASS
- [ ] 既存 `tests/test_title_dedup_guard.py` 全 PASS (regression なし)
- [ ] `lambda/fetcher/handler.py` の shared_entities 計算が `hierarchy_aware_overlap()` 経由
- [ ] `docs/p003-embedding-migration-research.md` の状態 line を「entity hierarchy に pivot 完了 (T2026-0502-U-V3)」に更新
- [ ] PR 作成 + auto-merge 待ち + Lambda 自動 deploy 確認
- [ ] WORKING.md 自分の行を削除して push
- [ ] HISTORY.md に T2026-0502-U-V3 完了記録 + Verified-Effect-Pending 5/9

## 失敗パターン回避

- ❌ `T2026-0501-M` フィクスチャを fixture 化せず実装する → 改善継続性が失われる
- ❌ ENTITY_HIERARCHY を hierarchy で循環参照にする → set 操作で無限ループ
- ❌ G7/G20 のような「同列メンバー集合」を hierarchy として扱って誤マージ誘発 → test 4-5 で防ぐ
- ❌ 既存 entity gate (shared_entities 空 → False) を弱める変更 → 「混入>分裂」原則に反する
- ❌ embedding コードを削除する → 将来の Tier 2 退避路として残す（disable のまま）

## Verified-Effect 書き方 (commit-msg hook T2026-0502-AA で必須)

immediate (PR 作成時):
```
Verified: tests/test_entity_hierarchy.py:6passed:YYYY-MM-DD
Verified-Effect-Pending: 2026-05-09 1 週間後に suspected_mismerge_count の推移と
  T2026-0501-M 型 false-split の消滅を観察
```

1 週間後 schedule task で:
```
Verified-Effect: production fetcher_health で false-split 候補ペア数が
  base 14/run → after 4/run (-71%) (CloudWatch:YYYY-MM-DD)
```

---

## 改善ロードマップ (本セッション後)

| Phase | 期間 | 内容 |
|---|---|---|
| **A: 本セッション** | 1 セッション | hierarchy 基礎 dict + unit test + production deploy |
| **B: 観察 1 週間** | 自動 (p003-haiku 朝確認) | 残った false-split を WORKING.md に sample |
| **C: 月次補強** | 月 1 回・rule 追加 PR | hierarchy / SYNONYMS / ENTITY_PATTERNS の継続拡張 |
| **D (必要なら): voyage 評価** | 1 セッション | rule で取れない 5% に絞った embedding 導入 |

C は p003-sonnet 月次タスクとして自動化可能（観察 → PR 提案）。

---

## 関連リンク

- 経緯: `docs/p003-embedding-migration-research.md` §9 (Phase 1 bench misses=3/6 結論)
- 元タスク: TASKS.md `T2026-0502-U` (本 V3 で代替・取消線にする)
- 既存 entity 抽出: `lambda/fetcher/config.py`・`lambda/fetcher/text_utils.py`
- 物理化済 hook: PR #226 (`Verified-Effect:` 必須・commit-msg level reject)
