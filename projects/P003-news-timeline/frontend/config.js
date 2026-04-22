// この値は deploy.sh 実行時に Lambda の Function URL で自動上書きされる。
// ローカル確認用のプレースホルダー（実際の値は deploy.sh が書き込む）。
const API_BASE      = 'https://YOUR_API_FUNCTION_URL/';
const COMMENTS_URL  = 'https://YOUR_COMMENTS_FUNCTION_URL/';

// ===== 認証・ユーザー機能 =====
// Google OAuth Client ID（Google Cloud Consoleで取得: APIs & Services → Credentials → OAuth 2.0 Client IDs）
// 許可するOrigin: https://flotopic.com を追加すること
const GOOGLE_CLIENT_ID = '';  // 例: '123456789-xxx.apps.googleusercontent.com'

// 認証Lambda URL（deploy.sh実行後に自動設定）
const AUTH_URL      = '';  // 例: 'https://xxx.lambda-url.ap-northeast-1.on.aws'

// お気に入りLambda URL（deploy.sh実行後に自動設定）
const FAVORITES_URL = '';  // 例: 'https://xxx.lambda-url.ap-northeast-1.on.aws'

// ===== フェーズ管理 =====
// Phase 2（Googleログイン）を解禁するにはGOOGLE_CLIENT_IDを設定する
// Phase 3（コメント）を解禁するにはCOMMENTS_URLを設定する
// 各フェーズの解禁条件は docs/flotopic-launch-strategy.md を参照
