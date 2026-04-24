// API_BASE: S3静的ホスティング（fetcher が api/topics.json を書き込む設計）
const API_BASE       = 'http://p003-news-946554699567.s3-website-ap-northeast-1.amazonaws.com/api/';
const COMMENTS_URL   = 'https://mqixchdufs5ky52wrqhovx2t7e0bghcx.lambda-url.ap-northeast-1.on.aws/';
const AUTH_URL       = 'https://qfkescjdcxfvxhrjnky67za4em0sdqcs.lambda-url.ap-northeast-1.on.aws/';
const FAVORITES_URL  = 'https://mumlvztiuzh5pqxgndgn4anzfu0wzvlt.lambda-url.ap-northeast-1.on.aws/';
const ANALYTICS_URL  = 'https://2svmxx7aou6w5ekdruw5maqnfu0aplju.lambda-url.ap-northeast-1.on.aws/';

// Google OAuth Client ID
// Google Cloud Console → APIs & Services → OAuth 2.0 Client IDs で取得
// 許可済みOrigin: https://flotopic.com を追加すること
const GOOGLE_CLIENT_ID = '';
