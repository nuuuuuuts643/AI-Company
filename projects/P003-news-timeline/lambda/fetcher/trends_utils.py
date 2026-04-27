"""Google Trends unofficial API (stdlib-only, best-effort)."""
import json
import urllib.request
import urllib.parse
from datetime import datetime, timezone

_UA = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/124.0.0.0 Safari/537.36'
)
_HEADERS = {
    'User-Agent': _UA,
    'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
    'Referer': 'https://trends.google.com/',
    'Accept': 'application/json, text/plain, */*',
}


def _strip_junk(raw):
    idx = raw.find('{')
    if idx < 0:
        idx = raw.find('[')
    return raw[idx:] if idx >= 0 else raw


def fetch_trends(keyword, geo='JP', timeframe='today 30-d'):
    """
    Fetch Google Trends interest-over-time for a keyword.
    Returns {'YYYY-MM-DD': int} or None on any error.
    Best-effort: returns None silently on network/parse errors.
    """
    try:
        req_json = json.dumps({
            'comparisonItem': [{'keyword': keyword, 'geo': geo, 'time': timeframe}],
            'category': 0,
            'property': '',
        }, separators=(',', ':'))
        params1 = urllib.parse.urlencode({'req': req_json, 'hl': 'ja', 'tz': '-540'})
        url1 = f'https://trends.google.com/trends/api/explore?{params1}'

        r1 = urllib.request.Request(url1, headers=_HEADERS)
        with urllib.request.urlopen(r1, timeout=10) as resp:
            if resp.status != 200:
                return None
            raw1 = resp.read().decode('utf-8', errors='ignore')

        data1 = json.loads(_strip_junk(raw1))
        widgets = data1.get('widgets', [])
        ts_widget = next((w for w in widgets if w.get('id') == 'TIMESERIES'), None)
        if not ts_widget:
            return None

        token = ts_widget['token']
        widget_req = ts_widget['request']

        params2 = urllib.parse.urlencode({
            'req': json.dumps(widget_req, separators=(',', ':')),
            'token': token,
            'tz': '-540',
        })
        url2 = f'https://trends.google.com/trends/api/widgetdata/multiline?{params2}'

        r2 = urllib.request.Request(url2, headers=_HEADERS)
        with urllib.request.urlopen(r2, timeout=10) as resp2:
            if resp2.status != 200:
                return None
            raw2 = resp2.read().decode('utf-8', errors='ignore')

        data2 = json.loads(_strip_junk(raw2))
        points = data2.get('default', {}).get('timelineData', [])
        if not points:
            return None

        result = {}
        for pt in points:
            ts_str = pt.get('time', '')
            values = pt.get('value', [])
            if ts_str and values:
                try:
                    dt = datetime.fromtimestamp(int(ts_str), tz=timezone.utc)
                    result[dt.strftime('%Y-%m-%d')] = int(values[0])
                except (ValueError, TypeError):
                    pass

        return result if result else None

    except Exception as e:
        print(f'[trends] "{keyword[:30]}": {type(e).__name__}: {e}')
        return None
