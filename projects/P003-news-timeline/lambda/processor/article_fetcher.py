"""article_fetcher.py — トピック内記事の本文抽出 (メディア比較 perspectives 用)

T2026-0428-AL (2026-04-28):
  perspectives セクションは長らく「RSS スニペット (~200字) からの推測」で生成されており、
  各社の論調差を比較できなかった。本モジュールは上位3記事の全文を取得し、
  prompt に渡すことで「NHK はこう報じた / 朝日はこう」という比較を AI に書かせる。

設計原則:
  - 標準ライブラリのみ (deploy.sh が `zip *.py` で固める制約)
  - 上位3記事をカテゴリ × ドメイン多様性で選定
  - HTTP timeout 5秒・取得失敗時は description にフォールバック (落ちない)
  - 同一ドメイングループ (sankei + sankeibiz 等) は1件に制限

戻り値の各 entry:
  source: メディア名
  url: 記事URL
  title: 記事見出し
  mediaCategory: 'A'|'B'|'C'|'X' (A:公共放送 B:全国紙 C:テック X:その他)
  fullText: 本文 (取得成功なら全文・最大3000字 / 失敗時は description)
  isFull: True なら全文取得成功 / False は snippet フォールバック
"""
import html
import re
import urllib.error
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urlparse

# T2026-0502-SEC13 (2026-05-02): SSRF 防御
from url_safety import is_safe_url


# fetcher/score_utils.py と同一定義 (processor は独立 zip のためコピー)
_MEDIA_CAT_A = frozenset([
    'nhk.or.jp',
])
_MEDIA_CAT_B = frozenset([
    'asahi.com', 'yomiuri.co.jp', 'mainichi.jp', 'nikkei.com',
    'sankei.com', 'reuters.com', 'kyodo.jp', 'nordot.app', 'jiji.com',
])
_MEDIA_CAT_C = frozenset([
    'itmedia.co.jp', 'techcrunch.jp', 'techcrunch.com', 'gizmodo.jp',
    'gigazine.net', 'ascii.jp', 'cnet.com', 'impress.co.jp',
])

# 同系列メディアを1グループ化。1グループからは1件のみ採用 (論調が同じになるため比較にならない)。
_DOMAIN_GROUP_MAP = {
    'sankei.com':       'sankei',
    'sankeibiz.jp':     'sankei',
    'iza.ne.jp':        'sankei',
    'asahi.com':        'asahi',
    'digital.asahi.com': 'asahi',
    'yomiuri.co.jp':    'yomiuri',
    'mainichi.jp':      'mainichi',
    'nikkei.com':       'nikkei',
    'nikkeibp.co.jp':   'nikkei',
    'reuters.com':      'reuters',
    'kyodo.jp':         'kyodo',
    'nordot.app':       'kyodo',
    'jiji.com':         'jiji',
    'nhk.or.jp':        'nhk',
}

_USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/124.0.0.0 Safari/537.36'
)

# NHK 等の重いホストには長めのタイムアウトを設定
_HOST_TIMEOUT_MAP: dict[str, float] = {
    'nhk.or.jp': 9.0,
}

_CONTENT_TAGS = ('article', 'main')
_CONTENT_CLASS_HINTS = (
    'article-body', 'article__body', 'articlebody',
    'main-content', 'maincontent', 'story-body', 'story__body',
    'post-content', 'entry-content', 'content-body', 'newsbody',
)
_NOISE_TAGS = ('script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe', 'form', 'noscript')

_MAX_FETCH_BYTES = 500_000
_MIN_FULL_TEXT_LEN = 300


def _domain_of(url: str) -> str:
    if not url:
        return ''
    try:
        netloc = urlparse(url).netloc.lower()
        return netloc[4:] if netloc.startswith('www.') else netloc
    except Exception:
        return ''


def _domain_in_cat(domain: str, cat: frozenset) -> bool:
    return any(domain == c or domain.endswith('.' + c) for c in cat)


def _media_category(domain: str) -> str:
    if _domain_in_cat(domain, _MEDIA_CAT_A):
        return 'A'
    if _domain_in_cat(domain, _MEDIA_CAT_B):
        return 'B'
    if _domain_in_cat(domain, _MEDIA_CAT_C):
        return 'C'
    return 'X'


def _get_timeout(url: str, default: float = 5.0) -> float:
    """ホスト別タイムアウト値を返す。マップ未登録は default を使う。"""
    domain = _domain_of(url)
    for host, t in _HOST_TIMEOUT_MAP.items():
        if domain == host or domain.endswith('.' + host):
            return t
    return default


def _domain_group(domain: str) -> str:
    """同系列メディアを統合するキー。マップ未登録は domain そのまま。"""
    for d, g in _DOMAIN_GROUP_MAP.items():
        if domain == d or domain.endswith('.' + d):
            return g
    return domain or 'unknown'


def select_articles_for_comparison(articles: list, max_count: int = 3) -> list:
    """信頼性 × 多様性で上位 max_count 件を選ぶ。

    優先順位: カテゴリA > カテゴリB > その他 > カテゴリC、同 cat 内は tier 値の小さい順。
    同一ドメイングループ重複は除外 (例: 産経 + sankeibiz は1件のみ)。
    """
    if not articles:
        return []
    enriched = []
    for a in articles:
        url = a.get('url', '')
        if not url:
            continue
        domain = _domain_of(url)
        if not domain:
            continue
        cat = _media_category(domain)
        cat_rank = {'A': 0, 'B': 1, 'X': 2, 'C': 3}.get(cat, 3)
        try:
            tier = int(a.get('tier', 3) or 3)
        except (TypeError, ValueError):
            tier = 3
        enriched.append((cat_rank, tier, _domain_group(domain), a, cat))
    enriched.sort(key=lambda x: (x[0], x[1]))
    seen_groups = set()
    picked = []
    for _, _, group, a, cat in enriched:
        if group in seen_groups:
            continue
        seen_groups.add(group)
        out = dict(a)
        out['mediaCategory'] = cat
        picked.append(out)
        if len(picked) >= max_count:
            break
    return picked


class _TextExtractor(HTMLParser):
    """<article>/<main>/.content 系ノード内のテキストのみ収集。
    複数候補があれば最長のものを採用 (本文の可能性が高い)。"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._stack = []
        self._noise_depth = 0
        self._buffers = []
        self._completed = []

    def handle_starttag(self, tag, attrs):
        if tag in _NOISE_TAGS:
            self._noise_depth += 1
            self._stack.append((tag, False))
            return
        attrs_d = dict(attrs)
        cls = (attrs_d.get('class') or '').lower()
        is_content = (
            tag in _CONTENT_TAGS
            or any(h in cls for h in _CONTENT_CLASS_HINTS)
        )
        if is_content:
            self._buffers.append([])
            self._stack.append((tag, True))
        else:
            self._stack.append((tag, False))

    def handle_endtag(self, tag):
        if not self._stack:
            return
        for i in range(len(self._stack) - 1, -1, -1):
            if self._stack[i][0] == tag:
                _, is_content = self._stack.pop(i)
                if tag in _NOISE_TAGS:
                    self._noise_depth = max(0, self._noise_depth - 1)
                if is_content and self._buffers:
                    text = ' '.join(self._buffers.pop())
                    if len(text) >= 200:
                        self._completed.append((len(text), text))
                break

    def handle_data(self, data):
        if self._noise_depth > 0 or not self._buffers:
            return
        text = data.strip()
        if text:
            self._buffers[-1].append(text)

    def best_text(self) -> str:
        if not self._completed:
            return ''
        self._completed.sort(key=lambda x: x[0], reverse=True)
        return self._completed[0][1]


def _strip_tags_fallback(html_text: str) -> str:
    """<article> 抽出 → tag 除去 → 単純フォールバック。
    HTMLParser が何も拾えなかった場合の最後の砦。"""
    m = re.search(r'<article[^>]*>([\s\S]*?)</article>', html_text, re.IGNORECASE)
    target = m.group(1) if m else html_text
    target = re.sub(r'<script[\s\S]*?</script>', ' ', target, flags=re.IGNORECASE)
    target = re.sub(r'<style[\s\S]*?</style>', ' ', target, flags=re.IGNORECASE)
    target = re.sub(r'<[^>]+>', ' ', target)
    target = html.unescape(target)
    return re.sub(r'\s+', ' ', target).strip()


def fetch_full_text(url: str, timeout: float = 5.0, max_retries: int = 1) -> str:
    """URL から本文テキストを抽出する。失敗時は空文字列。

    timeout はホスト別マップで上書きされる (_HOST_TIMEOUT_MAP)。
    max_retries=1 のとき最大 2 回試みる (initial + 1 retry)。

    T2026-0502-SEC13 (2026-05-02): SSRF 防御 — internal IP / metadata endpoint へのアクセスを reject する。
    """
    if not url:
        return ''
    # T2026-0502-SEC13: SSRF 防御
    safe, reason = is_safe_url(url)
    if not safe:
        print(f'[SEC13] fetch_full_text blocked: {url} ({reason})')
        return ''
    effective_timeout = _get_timeout(url, default=timeout)
    netloc = ''
    try:
        netloc = urlparse(url).netloc
    except Exception:
        pass
    for attempt in range(max_retries + 1):
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent':       _USER_AGENT,
                'Accept':           'text/html,application/xhtml+xml',
                'Accept-Language':  'ja,en;q=0.5',
            })
            with urllib.request.urlopen(req, timeout=effective_timeout) as resp:
                ctype = (resp.headers.get('Content-Type', '') or '').lower()
                if 'html' not in ctype:
                    return ''
                raw = resp.read(_MAX_FETCH_BYTES)
            charset = 'utf-8'
            m = re.search(rb'charset=["\']?([\w-]+)', raw[:2048], re.IGNORECASE)
            if m:
                try:
                    charset = m.group(1).decode('ascii').lower()
                except Exception:
                    charset = 'utf-8'
            try:
                text = raw.decode(charset, errors='replace')
            except LookupError:
                text = raw.decode('utf-8', errors='replace')
            parser = _TextExtractor()
            try:
                parser.feed(text)
            except Exception:
                pass
            body = parser.best_text()
            if not body or len(body) < _MIN_FULL_TEXT_LEN:
                body = _strip_tags_fallback(text)
            body = re.sub(r'\s+', ' ', body).strip()
            return body
        except (urllib.error.URLError, TimeoutError, ConnectionError, ValueError) as e:
            if attempt < max_retries:
                print(f'[ArticleFetcher] {netloc} retry {attempt + 1}/{max_retries}: {type(e).__name__}')
            else:
                print(f'[ArticleFetcher] {netloc} fetch失敗: {type(e).__name__}: {e}')
        except Exception as e:
            print(f'[ArticleFetcher] {netloc} unexpected: {type(e).__name__}: {e}')
            return ''
    return ''


def fetch_full_articles(articles: list, max_count: int = 3,
                         per_url_timeout: float = 5.0,
                         max_text_chars: int = 3000) -> list:
    """選定した上位記事に full_text を付与して返す。失敗時は description フォールバック。

    Returns:
        list of dict: {source, url, title, mediaCategory, fullText, isFull}
    """
    selected = select_articles_for_comparison(articles, max_count=max_count)
    out = []
    fetched_count = 0
    for a in selected:
        url = a.get('url', '')
        snippet = (a.get('description') or a.get('title') or '').strip()
        full = fetch_full_text(url, timeout=per_url_timeout) if url else ''
        is_full = bool(full and len(full) >= _MIN_FULL_TEXT_LEN)
        if is_full:
            full = full[:max_text_chars]
            fetched_count += 1
        else:
            full = snippet[:max_text_chars]
        out.append({
            'source':        a.get('source', ''),
            'url':           url,
            'title':         a.get('title', ''),
            'mediaCategory': a.get('mediaCategory', 'X'),
            'fullText':      full,
            'isFull':        is_full,
        })
    print(f'[ArticleFetcher] 全文取得: {fetched_count}/{len(out)} 成功')
    return out
