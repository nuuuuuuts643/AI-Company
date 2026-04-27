// CloudFront Function (viewer-request) — flotopic.com canonical redirects.
//
// Goal: eliminate duplicate URLs flagged by Google Search Console as
// "Duplicate, Google chose different canonical than user".
//
// Rules:
//   1. www.flotopic.com/*        -> https://flotopic.com/*           (301)
//   2. flotopic.com/index.html   -> https://flotopic.com/            (301, query preserved)
//   3. trailing /index.html on any path -> same path without it      (301)
//   4. otherwise pass through unchanged
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
  var qs = formatQuerystring(request.querystring);

  var targetHost = 'flotopic.com';
  var targetUri = uri;
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

  if (!needsRedirect) {
    return request;
  }

  var location = 'https://' + targetHost + targetUri + qs;
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
