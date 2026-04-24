// API_BASE: CloudFront経由HTTPS（flotopic.com → CloudFront → S3）
const API_BASE       = 'https://flotopic.com/api/';

// API Gateway HTTP API (Lambda URLの代替 - 403問題解消)
const _GW            = 'https://x73mzc0v06.execute-api.ap-northeast-1.amazonaws.com';
const COMMENTS_URL   = _GW;
const AUTH_URL       = _GW + '/auth';
const FAVORITES_URL  = _GW;
const ANALYTICS_URL  = _GW + '/analytics';

// Google OAuth Client ID
const GOOGLE_CLIENT_ID = '632899056251-hmk2ap6tv98miqj8n96lig3vj7uoa057.apps.googleusercontent.com';
