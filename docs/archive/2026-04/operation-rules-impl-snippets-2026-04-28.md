# 運用ルール 実装スニペット集（2026-04-28 スケジュール再実行 出力）

> 03:30 出力の `docs/operation-rules-proposal-2026-04-28.md` で提案した運用ルール群を「コピペ可能なファイル」レベルに具体化する。
> 本ファイルは write 操作なし。ナオヤが Code セッションで内容をそのままコミットすることを想定。
> 性格: 提案の前進補完。新たな分析ではない。

---

## なぜこの追加レポートを書いたか（短く）

03:30 レポートは提案表 (OR-1〜OR-17) で止まり、CLAUDE.md は依然 440 行 (上限超過)。提案を「読む」段階のままだとまた肥大化するだけなので、最低限の物理ゲート 3 種を実装ドラフトに落とした。意思決定はナオヤ、コピペ実行は Code セッション、で完結する形にする。

---

## 1. CLAUDE.md 短縮版ドラフト（200 行以内目標）

> 適用方法: 現在の CLAUDE.md と入れ替える前に diff を取り、消す情報が `docs/lessons-learned.md` 等に転写済みか確認する。冒頭〜「絶対ルール」までは構造を保つ。

```markdown
# ⚡ セッション開始

```bash
rm -f ~/ai-company/.git/index.lock
cd ~/ai-company
git add -A && git commit -m "chore: sync $(date '+%Y-%m-%d %H:%M')" || true
git pull --rebase origin main || true
git push || true
git log --oneline -5 -- CLAUDE.md
```

直近の CLAUDE.md commit があれば本ファイル冒頭〜「絶対ルール」までを再読してから続行。完了後「✅ 起動チェック完了」と報告。

# ⚡ 起動後の自動タスク実行

`cat ~/ai-company/TASKS.md` → 状態が「未着手」のタスクを優先度順で実行。

各タスクで以下を順守:
1. WORKING.md の stale (8h 超) を削除
2. WORKING.md に自分の行を追記して即 push (記載なしでコード変更禁止)
3. 実装
4. 完了したら WORKING.md から自分の行を削除し commit & push

ナオヤから新指示があれば優先。未着手なし → 「タスクなし、待機中」と報告して待機。

# ⚡ 絶対ルール（最低限）

| ルール | 内容 |
|---|---|
| **完了 = 動作確認済み** | push しただけは未完了。フロント=本番URL目視 / Lambda=CloudWatchエラーなし。`done.sh <task_id> <verify_target>` で自動検証 |
| **変更前に副作用確認** | コード変更前に「このファイルが何に依存されているか」を声に出す。言えなければ変更しない |
| **同名ファイル並行編集禁止** | WORKING.md 宣言なしで触らない |
| **scriptタグ defer/async 禁止** | chart.js/config.js/app.js/detail.js。CI で物理ブロック |
| **新規 formatter は boundary test 同梱** | 0/null/undefined/NaN/未来日付を全部 assert |
| **PII / secrets コード直書き禁止** | env var か Secrets Manager 必須 |
| **対症療法ではなく根本原因** | 足回りで誤魔化さない |
| **なぜなぜ分析は自発的に・構造化** | 問題発生時 Why1〜Why5 + 仕組み的対策 3 つ以上を `docs/lessons-learned.md` に追記。テーブル 1 行追記は再発防止と呼ばない |
| **Lambda 主ループ wallclock guard 必須** | 外部 API 呼び出しを伴うループは `context.get_remaining_time_in_millis()` ベースで break。回数ベース上限と時間予算を整合させる |
| **CLAUDE.md は 250 行以内** | CI で物理ガード。超えたら lessons-learned / anti-patterns / vision に外出しする |

# ⚡ 完了の流れ

1. 完了タスクを HISTORY.md に追記。CLAUDE.md には1行痕跡のみ
2. `bash done.sh <task_id> <verify_target>` で動作確認込みで完了処理
3. commit メッセージに `Verified: <url>:<status>:<timestamp>` 行必須 (pre-commit hook で物理ゲート)

# ⚡ 規則の置き場所

| 性質 | ファイル |
|---|---|
| 起動チェック・絶対ルール (本ファイル) | `CLAUDE.md` (250 行以内) |
| なぜなぜ事例集 (append-only) | `docs/lessons-learned.md` |
| 再発防止ルール表 | `docs/rules/bug-prevention.md` |
| 設計ミスパターン | `docs/rules/design-mistakes.md` |
| 品質改善の進め方 | `docs/rules/quality-process.md` |
| 実装前ユーザー文脈チェック | `docs/rules/user-context-check.md` |
| プロダクトビジョン | `docs/flotopic-vision-roadmap.md` |
| プロジェクト状態 | (本ファイル末尾) |

# Team Operating Rules

完了条件: build/compile 通過 + 主要機能動作確認 + 全テストパス + フロントは本番 URL で目視 + Verified 行付き。

完了報告ルール: 「できた」の前に①エラーログ確認②動作確認③警告修正。自力で直せない場合「ここで詰まっている」と報告する。

# AI-Company CEO システム状態

## 会社構造
- 出資者・取締役: ナオヤ（承認のみ）
- CEO: Claude（自律運営）
- 方針: 指示待ちせず前進。空報告禁止。証拠ない完了禁止。

## プロジェクト状態（最終更新: <YYYY-MM-DD>）

| プロジェクト | 状態 | 備考 |
|---|---|---|
| P001 自走システム | 保留 | API 費用削減で停止中 |
| P002 Flutterゲーム | 開発中 | 動作確認未実施 |
| P003 Flotopic | 本番稼働中 | flotopic.com / AdSense 審査中 |
| P004 Slackボット | 保留 | Slash Command 未設定 |
| P005 メモリDB | 保留 | DynamoDB 稼働中・未使用 |

## 技術状態スナップショットは `docs/p003-status-snapshot.md` 参照

## 残タスク（ナオヤ手動）
- P002 動作確認: `cd ~/ai-company/projects/P002-flutter-game && flutter pub get && flutter run`
- SES 本番アクセス申請
- AdSense 審査待ち

## 現在着手中 → `WORKING.md`
## 完了済み → `HISTORY.md`

# 絶対ルール（毎セッション遵守）

- `frontend/` `lambda/` `scripts/` `.github/` 配下は CEO エージェント専用ルールに従う
- 決まったことは即ファイルに書く（会話で終わらせない）
- URL 確認・デプロイ確認は自分で（ナオヤに聞かない）
- 「書きました」「やります」は信用されない。ファイル存在が証拠
- 空報告禁止
```

---

## 2. CI ガード（行数チェック）スニペット

> 適用先: `.github/workflows/ci.yml` の jobs 配下に追加。

```yaml
  claude-md-size:
    name: CLAUDE.md size guard
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Check CLAUDE.md is within 250 lines
        run: |
          LINES=$(wc -l < CLAUDE.md)
          echo "CLAUDE.md is $LINES lines"
          if [ "$LINES" -gt 250 ]; then
            echo "❌ CLAUDE.md exceeds 250 lines ($LINES). Move content to docs/lessons-learned.md or docs/rules/ ."
            exit 1
          fi
          echo "✅ CLAUDE.md is within budget"
```

---

## 3. pre-commit hook: Verified 行の物理ゲート

> 適用先: `.git/hooks/pre-commit` (実行権限 chmod +x)。または `scripts/pre-commit.sh` を `core.hooksPath` で参照。

```bash
#!/usr/bin/env bash
# Verified 行を要求する commit prefix のリスト
REQUIRE_VERIFIED='^(feat|fix|perf):'

# WIP commit / docs / chore は対象外
SKIP='^(wip|docs|chore|test|refactor|style):'

MSG_FILE="${1:-.git/COMMIT_EDITMSG}"
if [ ! -f "$MSG_FILE" ]; then
  exit 0
fi

FIRST_LINE=$(head -n 1 "$MSG_FILE")

# skip 対象なら通す
if echo "$FIRST_LINE" | grep -qE "$SKIP"; then
  exit 0
fi

# Verified 必須対象なのにヘッダがない → スキップ
if ! echo "$FIRST_LINE" | grep -qE "$REQUIRE_VERIFIED"; then
  exit 0
fi

# Verified: <url>:<status>:<timestamp> 形式が含まれているか
if ! grep -qE '^Verified: ' "$MSG_FILE"; then
  echo "❌ commit prefix '$FIRST_LINE' requires a 'Verified:' line."
  echo "   format: Verified: <url>:<http_status>:<JST_timestamp>"
  echo "   skip prefixes: wip, docs, chore, test, refactor, style"
  exit 1
fi

# URL の HTTP status を 200 番台で含んでいるか軽くチェック
if ! grep -qE '^Verified: .*:2[0-9]{2}:' "$MSG_FILE"; then
  echo "⚠️  Verified line found but HTTP status is not 2xx. Continuing but please double-check."
fi

exit 0
```

「`Verified` 行を埋めるための軽量スクリプト」も同時に用意:

```bash
#!/usr/bin/env bash
# scripts/verified_line.sh <url>
# stdout: "Verified: <url>:<status>:<JST_timestamp>"
URL="${1:-}"
if [ -z "$URL" ]; then
  echo "usage: $0 <url>" >&2
  exit 2
fi
STATUS=$(curl -o /dev/null -s -w "%{http_code}" "$URL" || echo "000")
TS=$(TZ=Asia/Tokyo date "+%Y-%m-%dT%H:%M%z")
echo "Verified: ${URL}:${STATUS}:${TS}"
```

使い方: `git commit -m "fix: T999 hoge" -m "$(bash scripts/verified_line.sh https://flotopic.com/api/topics.json)"`

---

## 4. タスクID 採番スクリプト

> 適用先: `scripts/next_task_id.sh`。日付ベースで衝突しない ID を返す。

```bash
#!/usr/bin/env bash
# scripts/next_task_id.sh
# stdout: 次の task ID (例: T2026-0428-A)
DATE=$(date '+%Y-%m%d')
PREFIX="T${DATE}-"

# TASKS.md / HISTORY.md / WORKING.md の全 ID から本日分の suffix を抽出
SUFFIXES=$(grep -hoE "T${DATE}-[A-Z]+" TASKS.md HISTORY.md WORKING.md 2>/dev/null \
  | sed "s/T${DATE}-//" | sort -u)

# A, B, C... の最初の未使用を選ぶ
for L in {A..Z}; do
  if ! echo "$SUFFIXES" | grep -qx "$L"; then
    echo "${PREFIX}${L}"
    exit 0
  fi
done

# A〜Z 全部使い切ったら AA, AB...
for L1 in {A..Z}; do
  for L2 in {A..Z}; do
    if ! echo "$SUFFIXES" | grep -qx "${L1}${L2}"; then
      echo "${PREFIX}${L1}${L2}"
      exit 0
    fi
  done
done

echo "ERROR: ran out of suffixes for $DATE" >&2
exit 1
```

CI 重複検出も併設:

```yaml
  task-id-uniqueness:
    name: Task ID uniqueness guard
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Detect duplicate task IDs
        run: |
          DUPES=$(grep -hoE "T[0-9]{4}-[0-9]{4}-[A-Z]+|T[0-9]+" TASKS.md HISTORY.md WORKING.md 2>/dev/null \
            | sort | uniq -d)
          if [ -n "$DUPES" ]; then
            echo "❌ Duplicate task IDs detected:"
            echo "$DUPES"
            exit 1
          fi
          echo "✅ All task IDs unique"
```

---

## 5. 適用手順（壊さない順序）

> ナオヤが Code セッションで上から実行することを想定。各ステップ単独で動作確認できる粒度に分けた。

### Step 1 (10 分): タスクID 採番スクリプトと CI 重複検出

- `scripts/next_task_id.sh` を作成 (上記 4 のコード)
- `.github/workflows/ci.yml` に task-id-uniqueness ジョブ追加
- 既存 ID 重複があれば修正
- commit: `feat: T2026-0428-A タスクID 採番スクリプト + CI 重複検出`
- Verified: `https://github.com/<repo>/actions:200:<ts>` (CI が green)

### Step 2 (15 分): pre-commit hook で Verified 必須化

- `scripts/pre-commit.sh` (上記 3) を新設
- `scripts/verified_line.sh` も新設
- `git config core.hooksPath scripts/git-hooks` で参照、もしくは `.git/hooks/pre-commit` symlink
- ナオヤ手元で 1 回試す（自分で fix: のテスト commit を作って Verified 行なしで reject されるか確認）
- commit: `feat: T2026-0428-B Verified 行 pre-commit hook`

### Step 3 (30 分): CLAUDE.md 短縮版へ移行

- 現 CLAUDE.md の長文ブロックを `docs/lessons-learned.md`, `docs/rules/bug-prevention.md` 等へ転記 (既に分割途中なので diff で確認)
- 上記 1 のドラフトに置き換え
- `wc -l CLAUDE.md` が 250 以下を確認
- `.github/workflows/ci.yml` に CLAUDE.md size guard ジョブ追加 (上記 2)
- commit: `refactor: T2026-0428-C CLAUDE.md を 250 行以内に圧縮 + CI ガード`
- Verified: 起動チェックスクリプトを 1 セッション流して全規則が読み取れるかを確認

### Step 4 (任意・将来): TASKS.md 状態カラム追加

- 03:30 レポート OR-4 のみ。Step 1〜3 完了後にナオヤ判断で着手
- 既存 23 件を「未着手 / 保留 / 廃案候補」に振り分け

---

## 6. 意図的に書かなかったもの

- **新たななぜなぜ分析**: 03:30 レポートで網羅済み。重複は context 浪費なので避けた
- **CLAUDE.md の直接編集**: ナオヤ未承認のうちに単一情報源を破壊するリスクが大きい。本ファイルはドラフト止まり
- **ESLint hex 直書き検出**: 既存提案 OR-2 だが、ESLint プラグイン作成が独立した工数になる。Step 3 完了後の別タスクで扱う
- **Playwright ダークモード自動目視**: 工数大きい (OR-11)。フェーズ 3 想定通り後送り

---

**生成元**: Cowork スケジュールタスク再実行 (Claude)
**生成日時 JST**: 2026-04-28 04:30 頃
**前段レポート**: `docs/operation-rules-proposal-2026-04-28.md` (03:30 出力)
**性格**: 実装ドラフト集 (write 系操作なし。本ファイル新規作成のみ)
