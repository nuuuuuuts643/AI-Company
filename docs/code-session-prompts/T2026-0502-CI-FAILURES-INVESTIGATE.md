# Code セッション起動 prompt: T2026-0502-CI-FAILURES-INVESTIGATE

> 用途: PR #316 (T2026-0502-IAM-FILTER-FIX) merge 後から main で持続している 2 件の CI failure を診断
> 関連: 横展開チェックリスト landing 検証 / 思想・表記ドリフト検出 — どちらも `bash scripts/check_lessons_landings.sh` を呼んで failure
> 推奨モデル: **Sonnet** (調査 + 修復)
> 想定所要: 1 時間

---

## prompt 本文

```
## 状況

main HEAD (2026-05-02 時点) で以下 2 つの CI が継続的に failure:
- 横展開チェックリスト landing 検証（過去対策の fossilize 検出）— meta-doc-guard.yml
- 思想・表記ドリフト検出（守らないと進めない仕組み）— ci.yml の step「横展開チェックリスト landing 検証 (T2026-0428-BC)」

両方とも `bash scripts/check_lessons_landings.sh` を実行して failure。

## ローカル動作との差分

Cowork セッション (2026-05-02 23:20 JST) で同じ HEAD のスクリプトをローカル実行 → exit 0 (全 ✅)。
CI でだけ failure。CI 環境固有の何かが違う。

## 失敗が始まった commit

- adfaad48 (PR #313 BI-PERMANENT 物理ガード): success
- b5f9d84e (PR #316 T2026-0502-IAM-FILTER-FIX) **以降** failure

PR #316 が変更したファイル:
- .github/workflows/ci.yml
- docs/lessons-learned.md
- scripts/install_hooks.sh
- tests/test_pre_commit_iam_filter.sh (added)

## 調査手順

1. main HEAD で gh CLI から CI ログ実体を取得:
   gh run view <最新 failure run id> --log-failed
   → 何の行で exit 1 されているか確認

2. ローカル実行と CI 実行の差分仮説:
   - CI は Ubuntu ubuntu-latest、ローカルは macOS / FUSE Linux
   - bash version 違い (regex, set -e 挙動)
   - file permission の違い (chmod +x 順序)
   - CRLF / LF 改行の違い (PR #316 の install_hooks.sh が CRLF 混入してる可能性)
   - check_lessons_landings.sh の Python regex が PR #316 の lessons-learned.md 改修で破綻

3. 仮説を 1 つずつ検証:
   - PR #316 の docs/lessons-learned.md diff を確認
   - check_lessons_landings.sh の Python regex (`### 横展開チェックリスト（過去仕組み的対策の landing 検証ルーチン・新設）`) が現在 main の lessons-learned.md で match するか
   - install_hooks.sh の必須パターン3つ ('pre-push', 'refs/heads/main', 'ALLOW_MAIN_PUSH') が PR #316 の改修後も grep ヒットするか

4. 真因確定後、修復 PR

## 完了条件

- 両 CI が main で success に戻る
- 真因が docs/lessons-learned.md (新セクション) に追記される

## 注意

- 既存 install_hooks.sh の機能を壊さない
- check_lessons_landings.sh のロジックは維持 (誤検出パターン拡張で済むなら最小修正)

## Verified-Effect

最新 main commit で:
- 横展開チェックリスト landing 検証: success
- 思想・表記ドリフト検出: success
```
