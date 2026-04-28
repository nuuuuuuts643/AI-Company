## 概要

<!-- 何を変えたか・なぜ変えたかを 1〜3 行で。 -->

## 変更内容

<!-- 主な変更ファイル / 仕様の差分。-->

## 動作確認 (Verified 行)

<!--
完了の物理ゲート (CLAUDE.md ルール):
- フロント変更: 本番 URL を目視 / Lambda 変更: CloudWatch エラーなし
- commit に `Verified: <url>:<status>:<JST_timestamp>` 行を含める
- 効果検証 (該当時): `Verified-Effect: <fix_type> <metric>=<value> PASS @ <JST>` 行も含める
-->

- [ ] `Verified:` 行を含む commit を push 済み
- [ ] (修正系の場合) `Verified-Effect:` 行で改善が数値で確認できている

## チェックリスト

- [ ] **対応 SLI を `docs/sli-slo.md` に追記したか** (該当なしの場合は理由を記載) — T2026-0428-AD
  <!--
  新機能・新エンドポイント・新データソース追加時は必ず観測 SLI を 1 つ以上紐付ける。
  「観測されない機能は壊れる」ため。例: 「新規 endpoint /foo → SLI 12 reach 99%」。
  該当なし理由の例: ドキュメントのみ・既存 SLI の再利用 (どれか明記)・CI 配管のみ等。
  -->
- [ ] CI が全件パスしている
- [ ] CLAUDE.md / `docs/` の関連ルールに違反していないか確認した
- [ ] 影響ファイル一覧・依存方向・副作用シナリオを把握している (CLAUDE.md「実装前に全体影響マップ必須」)

## なぜなぜ分析 (バグ修正の場合のみ)

<!--
`docs/lessons-learned.md` に Why1〜Why5 + 仕組み的対策 3 つ以上を追記したか。
「対症療法ではなく根本原因」「外部観測 / 物理ゲートを最低 1 つ含める」が CLAUDE.md ルール。
-->

- [ ] `docs/lessons-learned.md` に Why1〜Why5 + 仕組み的対策 3 つ以上 を追記した
- [ ] 仕組み的対策に「外部観測」「物理ゲート」のいずれかが含まれている
