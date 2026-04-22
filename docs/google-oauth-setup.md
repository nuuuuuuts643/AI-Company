# Google OAuth 2.0 セットアップ手順

Flotopic の「Googleでログイン」機能を有効にするための手順です。
スマホ（iPhoneブラウザ）から15分でできます。

---

## 手順

### 1. Google Cloud Console を開く

ブラウザで以下のURLを開く。

```
https://console.cloud.google.com
```

Googleアカウントでログインする（Gmailと同じアカウントでOK）。

---

### 2. プロジェクトを作成する

1. 画面上部の「プロジェクトの選択」をタップ
2. 右上の「新しいプロジェクト」をタップ
3. プロジェクト名に `Flotopic` と入力
4. 「作成」をタップ
5. 作成したプロジェクトが選択されていることを確認する

---

### 3. Google Identity API を有効にする

1. 左のメニュー（三本線）→「APIとサービス」→「ライブラリ」をタップ
2. 検索欄に `Google Identity` と入力
3. 「Google Identity Toolkit API」をタップ
4. 「有効にする」をタップ

---

### 4. OAuth 同意画面を設定する

1. 左メニュー→「APIとサービス」→「OAuth 同意画面」をタップ
2. ユーザーの種類で「外部」を選択→「作成」をタップ
3. 以下を入力する:
   - アプリ名: `Flotopic`
   - ユーザーサポートメール: あなたのGmailアドレス
   - デベロッパーの連絡先: あなたのGmailアドレス
4. 「保存して次へ」を3回タップして完了

---

### 5. OAuth 2.0 クライアントIDを作成する

1. 左メニュー→「APIとサービス」→「認証情報」をタップ
2. 上部の「+ 認証情報を作成」→「OAuth クライアントID」をタップ
3. アプリケーションの種類: **「ウェブ アプリケーション」** を選択
4. 名前: `Flotopic Web` と入力
5. 「承認済みの JavaScript 生成元」の「+ URIを追加」をタップして以下を入力:
   ```
   https://flotopic.com
   ```
6. （ローカルテスト用に追加しても良い: `http://localhost:3000`）
7. 「作成」をタップ

---

### 6. クライアントIDをコピーする

作成後に表示される「クライアントID」をコピーする。

形式の例:
```
123456789012-abcdefghijklmnopqrstuvwxyz123456.apps.googleusercontent.com
```

---

### 7. config.js に設定する

コピーしたクライアントIDを以下のファイルに貼り付ける。

ファイルパス:
```
projects/P003-news-timeline/frontend/config.js
```

変更箇所:
```js
// 変更前
GOOGLE_CLIENT_ID: "",

// 変更後（あなたのクライアントIDを貼り付ける）
GOOGLE_CLIENT_ID: "123456789012-xxxx.apps.googleusercontent.com",
```

---

### 8. デプロイして完了

```bash
cd ~/ai-company
git add projects/P003-news-timeline/frontend/config.js
git commit -m "feat: set Google OAuth Client ID"
git push
bash projects/P003-news-timeline/deploy.sh
```

---

## トラブルシューティング

| 症状 | 原因 | 対処 |
|------|------|------|
| 「redirect_uri_mismatch」エラー | 承認済みURLが一致しない | 手順5で `https://flotopic.com` が正確に入力されているか確認 |
| ボタンが表示されない | Client IDが空欄 | config.js の GOOGLE_CLIENT_ID を確認 |
| 「このアプリは確認されていません」 | 同意画面未承認 | 開発中は「詳細」→「安全でないページに移動」で続行可能 |

---

作成日: 2026-04-22
担当: CEO（Claude）
