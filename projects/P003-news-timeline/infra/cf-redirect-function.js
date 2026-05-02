// CloudFront Function (viewer-request) — flotopic.com canonical redirects.
//
// Goal: eliminate duplicate URLs flagged by Google Search Console as
// "Duplicate, Google chose different canonical than user".
//
// Rules:
//   1. www.flotopic.com/*                   -> https://flotopic.com/*                  (301)
//   2. flotopic.com/index.html              -> https://flotopic.com/                   (301, query preserved)
//   3. trailing /index.html on any path     -> same path without it                    (301)
//   4. /topic.html?id=<TID>(&...)           -> /topics/<TID>.html (drop id, keep rest) (301)
//        T2026-0502-BI: 動的 SPA URL を静的 SEO URL に正規化。
//        従来は topic.html?id=X (動的・初期 canonical=topic.html) と topics/X.html
//        (静的・canonical=self) が両方 indexable で canonical が破綻していた。
//        内部リンク 14 箇所は topics/X.html に統一済み (多重防御の一段目)。
//        この CFF は外部 backlink / 旧 SNS シェア URL / 古い search index 等からの
//        流入を 301 で吸収する (多重防御の二段目)。tid に英数 + ハイフン + 下線 +
//        ドットのみ許容 (S3 key 安全性 + open redirect 防止)。
//   5. /storymap.html?id=<TID>(&...) は SPA で正当なナビゲーション (storymap は
//        トピック単独ページではなく分岐ビューア) なのでリダイレクトしない。
//   6. otherwise pass through unchanged
//
// HTTPS-only is already enforced by the CloudFront distribution
// (ViewerProtocolPolicy=redirect-to-https), so we don't handle http here.
//
// Runtime: cloudfront-js-2.0
// Event:   viewer-request

function handler(event) {
  var request = event.request;
  var headers = request.headers;
  var host = headers.host && headers.host.value ? headers.host.value.toLowerCase() : '';
  var uri = request.uri || '/';

  var targetHost = 'flotopic.com';
  var targetUri = uri;
  var targetQs = null; // null = use formatQuerystring(request.querystring)
  var needsRedirect = false;

  // Rule 1: www -> apex
  if (host === 'www.flotopic.com') {
    needsRedirect = true;
  }

  // Rule 2 & 3: strip /index.html
  if (uri === '/index.html') {
    targetUri = '/';
    needsRedirect = true;
  } else if (uri.length >= 11 && uri.slice(-11) === '/index.html') {
    targetUri = uri.slice(0, uri.length - 10); // keep trailing slash
    needsRedirect = true;
  }

  // Rule 4: /topic.html?id=<TID> -> /topics/<TID>.html
  // ※ id クエリが正規 (英数 / ハイフン / 下線 / ドット) のときのみ。
  //   それ以外 (空 id・記号混入) は SPA fallback (topic.html 単独) に流す。
  if (uri === '/topic.html') {
    var idEntry = request.querystring && request.querystring.id;
    var rawId = idEntry ? (idEntry.value || (idEntry.multiValue && idEntry.multiValue[0] && idEntry.multiValue[0].value) || '') : '';
    if (rawId && /^[A-Za-z0-9._-]{1,128}$/.test(rawId)) {
      targetUri = '/topics/' + rawId + '.html';
      // id 以外のクエリは保持 (utm_* 等)
      var rest = [];
      for (var k in request.querystring) {
        if (!Object.prototype.hasOwnProperty.call(request.querystring, k)) continue;
        if (k === 'id') continue;
        var ent = request.querystring[k];
        if (ent.multiValue) {
          for (var i = 0; i < ent.multiValue.length; i++) {
            rest.push(encodeKV(k, ent.multiValue[i].value));
          }
        } else {
          rest.push(encodeKV(k, ent.value));
        }
      }
      targetQs = rest.length ? '?' + rest.join('&') : '';
      needsRedirect = true;
    }
  }

  if (!needsRedirect) {
    return request;
  }

  if (targetQs === null) {
    targetQs = formatQuerystring(request.querystring);
  }
  var location = 'https://' + targetHost + targetUri + targetQs;
  return {
    statusCode: 301,
    statusDescription: 'Moved Permanently',
    headers: {
      location: { value: location },
      'cache-control': { value: 'max-age=3600' }
    }
  };
}

function formatQuerystring(querystring) {
  if (!querystring) return '';
  var parts = [];
  for (var key in querystring) {
    if (!Object.prototype.hasOwnProperty.call(querystring, key)) continue;
    var entry = querystring[key];
    if (entry.multiValue) {
      for (var i = 0; i < entry.multiValue.length; i++) {
        parts.push(encodeKV(key, entry.multiValue[i].value));
      }
    } else {
      parts.push(encodeKV(key, entry.value));
    }
  }
  return parts.length ? '?' + parts.join('&') : '';
}

function encodeKV(k, v) {
  if (v === undefined || v === null || v === '') return encodeURIComponent(k);
  return encodeURIComponent(k) + '=' + encodeURIComponent(v);
}
