# P003 schedule-task report — 2026-04-28

> 本セッションは bash workspace 障害により探索フェーズのみ実行。
> 実装・push・効果検証は未実施（次セッションで継続）。

## 環境制約

bash workspace が初手の `aws logs describe-log-streams` 呼び出しでデッドロック。
20+ 回リトライしても `process with name "nice-wonderful-thompson" already running` で復旧不可。

不可だったもの:
- processor 静止確認（pre-check）
- session_bootstrap.sh
- git pull / commit / push
- Lambda invoke
- 効果検証 verify_effect.sh
- TASKS.md / WORKING.md 更新

実施できたもの: HTTP 観測（外部 web_fetch）と Read tool による file 読込のみ。

## 主要な発見

### 1. 静的 SEO HTML（T2026-0428-AB）✅ 復旧済

news-sitemap.xml から 3 件サンプリングし、全て HTTP 200 を返却。
- `4dd63052a2e285e9.html` — 200 / 脳老化記事
- `eb44c4807c3ec07d.html` — 200 / 世界軍事費
- `3e77f51bf959c8b9.html` — 200 / iPhone前ケータイ

`docs/system-status.md` の「🔴 本番断絶」記述は古い。次セッションで `[AUTO]` 観測値で上書き or 手書き訂正。

### 2. AI 要約スキーマ（T2026-0428-E）⚠️ 部分実装

3 件サンプリング確認、`schemaVersion: 3` 適用済。

| field | minimal mode | full mode |
|---|---|---|
| keyPoint | ✅ 約 250 字 OK | ⚠️ 30 字（要件 200-300 字に未達） |
| statusLabel | ❌ 欠落 | ✅「進行中」等 |
| watchPoints | ❌ 欠落 | ✅ ①②③形式 |
| outlook + predictionMadeAt | ✅ | ✅ |
| perspectives | ❌ 欠落 | ✅ |
| 旧 spreadReason/backgroundContext/background/forecast | — | ❌ 残存（task で削除予定） |

**proc_ai.py 側の問題**:
- minimal mode で新フィールド (statusLabel/watchPoints/perspectives) が出力されない
- full mode で keyPoint の文字数強制が効いていない
- 旧フィールドの削除がプロンプト・schema 共に未着手

### 3. その他の観察

- 「世界軍事費 460兆円」記事（国際/軍事）に対しアフィリエイトキーワード「旅行 グッズ」が表示されており違和感
  → T241（センシティブトピックの affiliate 非表示）を昇格検討
- topics.json は 170KB 超で Read tool 拒否、bash 不可で `jq` も実行不可。鮮度は SLI workflow に委任

## 次セッションでやること

優先順位順:

1. `find .git -maxdepth 4 -name "*.lock"` で残ロック確認 → 退避
2. `session_bootstrap.sh` で正常起動可否を確認
3. T2026-0428-E2（新規タスク提案）切り出し:
   - minimal mode で statusLabel/watchPoints/perspectives 必須化 or 対象外明示
   - full mode keyPoint 文字数強制（プロンプトレベル）
   - 旧 spreadReason/backgroundContext/background/forecast 削除
4. `docs/system-status.md` の「静的 SEO HTML 生成」行を「✅ 稼働中」に修正
5. T241 をメインキューに昇格判断（軍事費トピック × 旅行グッズ問題）

## なぜなぜ分析（bash workspace ハング）

- Why1: 初手の `aws logs describe-log-streams` がタイムアウトした
- Why2: aws CLI に AWS_REGION が未設定 or credentials の取得が遅延した可能性
- Why3: workspace の oneshot プロセスがそのまま wedged 状態で残り、新規 create が衝突
- Why4: bash MCP server に「stuck process を kill / reset する」エスケープハッチがない
- Why5: 1 回の長時間 stuck で session 全体が以降使えなくなる構造（fail-safe 不在）

仕組み的対策:
1. **timeout 強制**: scheduled-task の pre-check は `timeout 30 aws ...` で wrap し、CLI 側で必ず終わらせる
2. **代替パス**: bash 不可時に CloudWatch を REST API（curl ベース）で叩く軽量チェッカーを scripts/ に配置
3. **bootstrap 失敗時のフェールセーフ**: bash 不可を検知したら HTTP-only モードで観測のみ実行 → outputs に report 保存して終了するパスを scheduled-task-protocol.md に明文化

---

生成: 2026-04-28 P003 schedule-task / 環境: bash dead, HTTP-only 観測
