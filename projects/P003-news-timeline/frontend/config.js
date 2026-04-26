// API経由（API Gateway HTTPS）
const API_BASE      = 'https://flotopic.com/api/';
const _APIGW        = 'https://x73mzc0v06.execute-api.ap-northeast-1.amazonaws.com';
const COMMENTS_URL  = _APIGW;
const AUTH_URL      = _APIGW + '/auth';
const FAVORITES_URL = _APIGW;
const ANALYTICS_URL = _APIGW + '/';

// Google OAuth Client ID
const GOOGLE_CLIENT_ID = '632899056251-hmk2ap6tv98miqj8n96lig3vj7uoa057.apps.googleusercontent.com';

// アフィリエイト設定（申請後にIDを設定する）
// ① もしもアフィリエイト（推奨・審査が緩い・Amazon/楽天/Yahoo!をまとめて対応）
//   https://af.moshimo.com/ で登録 → マイページ > プログラム管理 > a_id を確認
const AFFILIATE_MOSHIMO_A_ID = '1188659';
// ② Amazonアソシエイト直接（もしもIDがない場合のフォールバック）
//   https://affiliate.amazon.co.jp/ でタグIDを取得後に設定
const AFFILIATE_AMAZON_TAG = 'flotopic-22';
// ③ 楽天アフィリエイト直接（もしもIDがない場合のフォールバック）
//   https://affiliate.rakuten.co.jp/ でアフィリエイトIDを取得後に設定
const AFFILIATE_RAKUTEN_ID = '';    // 申請後に設定
