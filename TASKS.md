# タスクキュー（複数セッション共有）

> **finder セッション**: このファイルの「未着手」にのみ書く。コードファイルには触れない。
> **実装セッション**: 未着手を取得 → WORKING.md に宣言 → 実装 → 完了後 HISTORY.md に移動。

---

## 未着手（実装待ち）

取得手順: `git pull --rebase && cat TASKS.md` で確認後、WORKING.md に宣言して着手。

| ID | 優先 | 内容 | 変更予定ファイル | 追加日 |
|---|---|---|---|---|
| T019 | 中 | **SES本番アクセス申請後のLambda環境変数設定**。AWSコンソール → Lambda `p003-contact` → 環境変数 → `TO_EMAIL` に受信メールアドレスを設定。SES本番承認後に実施（ナオヤ手動） | — | 2026-04-26 |
| T045 | 高 | **アバター保存「保存中...」のまま固まるバグ修正**。`uploadAvatarBlob`のfetchにAbortController+30秒タイムアウト追加。catchブロックで必ずsaveBtnをリセット（現状はネットワーク障害時にS3がデータ受け取り済みでもJSが応答待ちで永遠に止まる） | `frontend/mypage.html` | 2026-04-26 |
| T046 | 中 | **ログインモーダルの「🔔 通知」文言修正**。`auth.js`L130の「🔔 急上昇・続報の通知を受け取る」はWeb Push未実装なので嘘。実際は@メンション通知のみ。文言を「🔔 @メンション通知・コメント返信を受け取る」に修正するか、実際にWeb Pushを実装する（pushManager.subscribe+VAPID+Lambda送信が必要） | `frontend/js/auth.js` | 2026-04-26 |

## 進行中
→ WORKING.md で管理（実装セッションが記入）

## 完了
→ HISTORY.md に移動済み
