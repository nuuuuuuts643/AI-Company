// API経由（API Gateway HTTPS）
const API_BASE      = 'https://flotopic.com/api/';
const _APIGW        = 'https://x73mzc0v06.execute-api.ap-northeast-1.amazonaws.com';
const _GW           = _APIGW;
const COMMENTS_URL  = _APIGW;
const AUTH_URL      = _APIGW + '/auth';
const FAVORITES_URL = _APIGW;
const ANALYTICS_URL = _APIGW + '/';
const CONTACT_URL   = _APIGW + '/contact';  // T235 (2026-04-28): contact.html がハードコードしていたため config に集約

// Google OAuth Client ID
const GOOGLE_CLIENT_ID = '632899056251-hmk2ap6tv98miqj8n96lig3vj7uoa057.apps.googleusercontent.com';
