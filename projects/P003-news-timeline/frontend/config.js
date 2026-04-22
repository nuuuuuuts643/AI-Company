// API_BASE: S3静的ホスティング（topics.json等を直接読む設計）
const API_BASE       = 'https://flotopic.com/api/';
const COMMENTS_URL   = 'https://kj22x2hxiqus7p65jebstcf5fe0xwvwr.lambda-url.ap-northeast-1.on.aws/';
const AUTH_URL       = 'https://jimustpeaznrwhdrz5lstddz640ftmjp.lambda-url.ap-northeast-1.on.aws/';
const FAVORITES_URL  = 'https://mumlvztiuzh5pqxgndgn4anzfu0wzvlt.lambda-url.ap-northeast-1.on.aws/';
const ANALYTICS_URL  = 'https://2svmxx7aou6w5ekdruw5maqnfu0aplju.lambda-url.ap-northeast-1.on.aws/';

// Google OAuth Client ID
// Google Cloud Console → APIs & Services → OAuth 2.0 Client IDs で取得
// 許可済みOrigin: https://flotopic.com を追加すること
const GOOGLE_CLIENT_ID = '632899056251-hmk2ap6tv98miqj8n96lig3vj7uoa057.apps.googleusercontent.com';
