"""url_safety.py — SSRF / XXE 防御ヘルパ (T2026-0502-SEC13/SEC14, 2026-05-02)

Lambda zip は *.py のみで固める制約があるため、外部依存なしで完結する純粋ヘルパに留める。
fetcher / processor 双方にコピーで配置される (deploy.sh の `zip *.py` モデル維持)。

提供関数:
  is_safe_url(url) -> (bool, reason)
    URL のスキーム + 解決後 IP をチェックする。
    deny: 169.254.0.0/16 (link-local + AWS metadata) / 10.x / 172.16.0.0/12 / 192.168.0.0/16 /
          127.0.0.0/8 / 0.0.0.0/8 / fc00::/7 / fe80::/10 / ::1 / multicast
    allow: それ以外の public IP / http(s) スキームのみ
  parse_xml_safely(content) -> ElementTree.Element
    billion laughs / external entity 攻撃に対する防御つき XML パース。
    DOCTYPE / ENTITY 宣言を検出したら ValueError を raise する。
"""
from __future__ import annotations

import ipaddress
import re
import socket
import xml.etree.ElementTree as ET
from urllib.parse import urlparse


# 内部・予約 IP 範囲 (RFC1918 + link-local + loopback + reserved)
_PRIVATE_NETS_V4 = [
    ipaddress.ip_network('0.0.0.0/8'),
    ipaddress.ip_network('10.0.0.0/8'),
    ipaddress.ip_network('100.64.0.0/10'),     # CGNAT
    ipaddress.ip_network('127.0.0.0/8'),
    ipaddress.ip_network('169.254.0.0/16'),    # link-local + AWS metadata 169.254.169.254
    ipaddress.ip_network('172.16.0.0/12'),
    ipaddress.ip_network('192.0.0.0/24'),      # IETF protocol assignments
    ipaddress.ip_network('192.168.0.0/16'),
    ipaddress.ip_network('198.18.0.0/15'),     # benchmark
    ipaddress.ip_network('224.0.0.0/4'),       # multicast
    ipaddress.ip_network('240.0.0.0/4'),       # reserved future
]
_PRIVATE_NETS_V6 = [
    ipaddress.ip_network('::1/128'),
    ipaddress.ip_network('fe80::/10'),
    ipaddress.ip_network('fc00::/7'),          # ULA
    ipaddress.ip_network('::ffff:0:0/96'),     # IPv4-mapped — 別途 v4 として再評価される
    ipaddress.ip_network('ff00::/8'),          # multicast
]


def _is_internal_ip(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return True  # parse 不能は安全側で deny
    if ip.version == 4:
        return any(ip in net for net in _PRIVATE_NETS_V4)
    return any(ip in net for net in _PRIVATE_NETS_V6)


def is_safe_url(url: str, allow_schemes=('http', 'https')) -> tuple[bool, str]:
    """URL が外部 fetch 安全か判定する。

    Returns:
        (True, '')                      OK
        (False, '<deny reason>')        deny
    """
    if not url or not isinstance(url, str):
        return False, 'empty url'
    try:
        p = urlparse(url)
    except Exception as e:
        return False, f'parse error: {e}'
    if p.scheme.lower() not in allow_schemes:
        return False, f'disallowed scheme: {p.scheme}'
    host = p.hostname
    if not host:
        return False, 'no host'
    # 直接 IP 指定の場合は即座にチェック
    try:
        ipaddress.ip_address(host)
        if _is_internal_ip(host):
            return False, f'internal ip: {host}'
        return True, ''
    except ValueError:
        pass
    # ホスト名 → DNS 解決 (timeout 2s)
    socket.setdefaulttimeout(2.0)
    try:
        results = socket.getaddrinfo(host, None)
    except (socket.gaierror, socket.herror, OSError) as e:
        # 解決失敗は外部 fetch 不可 → そもそも外部 URL なら問題ない判定にしてもよいが、
        # 安全側で deny。fetcher は urllib.error.URLError を catch するので fail close。
        return False, f'dns resolution failed: {e}'
    finally:
        socket.setdefaulttimeout(None)
    # 解決結果のいずれかが内部 IP なら deny (DNS rebinding 対策)
    for fam, _t, _p, _c, sa in results:
        ip_str = sa[0]
        if _is_internal_ip(ip_str):
            return False, f'host {host} resolves to internal ip {ip_str}'
    return True, ''


# ── XML パース安全化 ──────────────────────────────────────────────────────
# defusedxml を使えない (Lambda zip 制約) ので、parse 前に DOCTYPE / ENTITY を grep で reject。
# 実用上 RSS フィード由来の DOCTYPE は使われないので false positive は無視できる。

_DOCTYPE_RE = re.compile(rb'<!DOCTYPE\b', re.IGNORECASE)
_ENTITY_RE  = re.compile(rb'<!ENTITY\b',  re.IGNORECASE)


def parse_xml_safely(content: bytes) -> ET.Element:
    """billion laughs / XXE 防御付き XML パース。

    Args:
        content: bytes (RSS feed の本文)
    Returns:
        ET.Element (root)
    Raises:
        ValueError: DOCTYPE / ENTITY 宣言検出時 (XXE / billion laughs 攻撃の可能性)
        xml.etree.ElementTree.ParseError: XML 構文エラー
    """
    if isinstance(content, str):
        content = content.encode('utf-8', errors='replace')
    # 先頭 8KB のみチェック (DOCTYPE / ENTITY は通常 prolog にある)
    head = content[:8192]
    if _DOCTYPE_RE.search(head):
        raise ValueError('XML DOCTYPE declaration is not allowed (T2026-0502-SEC14)')
    if _ENTITY_RE.search(head):
        raise ValueError('XML ENTITY declaration is not allowed (T2026-0502-SEC14)')
    return ET.fromstring(content)
