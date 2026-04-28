"""flotopic-bluesky Lambda handler.

EventBridge から rate(30 minutes) で起動される BlueSky 自動投稿の薄いラッパ。
GitHub Actions 無料枠の cron が 1 日 3〜5 回しか発火しない問題（T2026-0428-AU 調査）
を根本解決するため、cron トリガーを EventBridge → Lambda に移管した（T2026-0428-AV）。

実体ロジックは scripts/bluesky_agent.py の run() を CLI とこのハンドラで共用する。
deploy-lambdas.yml の bluesky ステップが scripts/bluesky_agent.py と
scripts/_governance_check.py をこのディレクトリにコピーしてから zip するため、
Lambda 実行時はカレントディレクトリ直下に bluesky_agent.py が存在する。

イベントスキーマ:
    {"mode": "daily" | "weekly" | "monthly", "dry_run": bool}
省略時は EventBridge ルール側で渡される input を見るか、デフォルト daily を使う。
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from typing import Any


def _resolve_mode(event: dict | None) -> str:
    """イベント or 環境変数から mode を解決する。"""
    if isinstance(event, dict):
        mode = event.get('mode')
        if isinstance(mode, str) and mode in ('daily', 'weekly', 'monthly', 'morning'):
            return mode
    env_mode = os.environ.get('BLUESKY_MODE', '').strip()
    if env_mode in ('daily', 'weekly', 'monthly', 'morning'):
        return env_mode
    return 'daily'


def _resolve_dry_run(event: dict | None) -> bool:
    if isinstance(event, dict):
        v = event.get('dry_run')
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() in ('1', 'true', 'yes')
    env_dry = os.environ.get('BLUESKY_DRY_RUN', '').strip().lower()
    return env_dry in ('1', 'true', 'yes')


def lambda_handler(event: Any, context: Any) -> dict:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        from bluesky_agent import run  # type: ignore
    except Exception:
        err = traceback.format_exc()
        print(f'[flotopic-bluesky] import error:\n{err}')
        return {'ok': False, 'error': f'import: {err[:500]}'}

    mode = _resolve_mode(event if isinstance(event, dict) else None)
    dry_run = _resolve_dry_run(event if isinstance(event, dict) else None)

    print(
        f'[flotopic-bluesky] invoke mode={mode} dry_run={dry_run} '
        f'request_id={getattr(context, "aws_request_id", "n/a")}'
    )

    try:
        result = run(mode=mode, dry_run=dry_run)
    except Exception:
        err = traceback.format_exc()
        print(f'[flotopic-bluesky] unhandled error:\n{err}')
        return {'ok': False, 'mode': mode, 'error': err[:500]}

    print(f'[flotopic-bluesky] result={json.dumps(result, ensure_ascii=False, default=str)}')
    return result
