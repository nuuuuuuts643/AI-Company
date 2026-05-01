"""テーブル初期化パスのユニットテスト."""
import importlib
import sys
import types
from unittest.mock import MagicMock, patch


def _make_governance_module(table_exists: bool):
    """_governance_check モジュールをモックとして生成する。"""
    mod = types.ModuleType("_governance_check")

    def ensure_agent_status_table_exists():
        if table_exists:
            print("[governance] テーブル ai-company-agent-status は既存")
        else:
            print("[governance] テーブル ai-company-agent-status を作成しました")
        return True

    mod.ensure_agent_status_table_exists = ensure_agent_status_table_exists
    return mod


def _reload_handler(governance_mod):
    """handler モジュールを再ロードして _table_initialized をリセット。"""
    # 既存のキャッシュを除去
    for key in list(sys.modules.keys()):
        if key in ("handler", "_governance_check"):
            del sys.modules[key]

    sys.modules["_governance_check"] = governance_mod

    import projects.P003_news_timeline  # noqa: F401 — パス追加のため
    import importlib.util
    import os
    handler_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "lambda",
        "bluesky",
        "handler.py",
    )
    spec = importlib.util.spec_from_file_location("handler", handler_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestBlueSkyHandlerTableInit:
    """handler.py がコールドスタート時にテーブル初期化を呼ぶことを確認。"""

    def test_ensure_called_when_table_missing(self, capsys):
        """テーブルが存在しない場合、ensure_agent_status_table_exists が呼ばれる。"""
        governance = _make_governance_module(table_exists=False)
        called = []
        original = governance.ensure_agent_status_table_exists

        def spy():
            called.append(True)
            return original()

        governance.ensure_agent_status_table_exists = spy

        for key in list(sys.modules.keys()):
            if key in ("handler", "_governance_check"):
                del sys.modules[key]
        sys.modules["_governance_check"] = governance

        import importlib.util, os
        handler_path = os.path.join(
            os.path.dirname(__file__), "..", "lambda", "bluesky", "handler.py"
        )
        spec = importlib.util.spec_from_file_location("handler_fresh", handler_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        assert called, "ensure_agent_status_table_exists が呼ばれていない"
        assert mod._table_initialized is True

    def test_ensure_called_when_table_exists(self, capsys):
        """テーブルが既存でも ensure が呼ばれ、_table_initialized が True になる。"""
        governance = _make_governance_module(table_exists=True)
        called = []
        original = governance.ensure_agent_status_table_exists

        def spy():
            called.append(True)
            return original()

        governance.ensure_agent_status_table_exists = spy

        for key in list(sys.modules.keys()):
            if key in ("handler_fresh2", "_governance_check"):
                del sys.modules[key]
        sys.modules["_governance_check"] = governance

        import importlib.util, os
        handler_path = os.path.join(
            os.path.dirname(__file__), "..", "lambda", "bluesky", "handler.py"
        )
        spec = importlib.util.spec_from_file_location("handler_fresh2", handler_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        assert called, "ensure_agent_status_table_exists が呼ばれていない"
        assert mod._table_initialized is True

    def test_init_not_called_twice(self):
        """_init_table() を2回呼んでも ensure は1回しか実行されない。"""
        governance = _make_governance_module(table_exists=True)
        called = []
        original = governance.ensure_agent_status_table_exists

        def spy():
            called.append(True)
            return original()

        governance.ensure_agent_status_table_exists = spy

        for key in list(sys.modules.keys()):
            if key in ("handler_fresh3", "_governance_check"):
                del sys.modules[key]
        sys.modules["_governance_check"] = governance

        import importlib.util, os
        handler_path = os.path.join(
            os.path.dirname(__file__), "..", "lambda", "bluesky", "handler.py"
        )
        spec = importlib.util.spec_from_file_location("handler_fresh3", handler_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        # 2回目呼び出し
        mod._init_table()

        assert len(called) == 1, f"ensure が {len(called)} 回呼ばれた（1回のみのはず）"
