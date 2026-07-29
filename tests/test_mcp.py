# tests/test_mcp.py
"""Tests for MCP server, search backends, and knowledge graph."""
from __future__ import annotations

import builtins
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
MCP_SERVER = SCRIPTS / "mcp_server.py"


def _env():
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SCRIPTS) + os.pathsep + env.get("PYTHONPATH", "")
    return env


@pytest.fixture
def vault(tmp_path):
    """Create a minimal vault for testing."""
    v = tmp_path / "llm-wiki"
    v.mkdir()
    (v / "config.json").write_text(json.dumps({
        "version": 1,
        "mcp": {"enabled": True, "search_backend": "fts5"},
        "knowledge_graph": {"enabled": True, "backend": "json", "auto_update_on_ingest": True},
        "git": {"enabled": False},
    }))
    (v / "wiki").mkdir()
    (v / "wiki" / "index.md").write_text("# Welcome\nThis is the index.\n")
    (v / "wiki" / "auth.md").write_text("---\ntitle: Authentication\nllm_wiki_tags: [auth, security]\n---\n# Auth\nWe use [[oauth]] for login.\n")
    (v / "raw").mkdir()
    (v / "raw" / "notes.md").write_text("---\ntitle: Meeting Notes\nllm_wiki_tags: [meetings]\n---\n# Sprint Planning\nDiscussed auth migration.\n")
    (v / "CLAUDE.md").write_text("# Vault rules\n")
    return v


# ---------------------------------------------------------------------------
# FTS5 Search Backend
# ---------------------------------------------------------------------------

class TestFTS5Search:
    def test_reindex_and_search(self, vault):
        sys.path.insert(0, str(SCRIPTS))
        from lib.search import FTS5SearchBackend
        backend = FTS5SearchBackend(vault)
        result = backend.reindex()
        assert result["indexed"] == 3

        results = backend.search("auth")
        assert len(results) >= 1
        assert any("auth" in r.path for r in results)

    def test_search_with_tag_filter(self, vault):
        sys.path.insert(0, str(SCRIPTS))
        from lib.search import FTS5SearchBackend
        backend = FTS5SearchBackend(vault)
        backend.reindex()

        results = backend.search("auth", tag="security")
        assert len(results) >= 1
        assert all("security" in r.tags for r in results)

    def test_auto_index_on_empty(self, vault):
        sys.path.insert(0, str(SCRIPTS))
        from lib.search import FTS5SearchBackend
        backend = FTS5SearchBackend(vault)
        results = backend.search("sprint")
        assert len(results) >= 1

    def test_index_status(self, vault):
        sys.path.insert(0, str(SCRIPTS))
        from lib.search import FTS5SearchBackend
        backend = FTS5SearchBackend(vault)
        backend.reindex()
        status = backend.index_status()
        assert status["backend"] == "fts5"
        assert status["indexed_pages"] == 3

    def test_find_related(self, vault):
        sys.path.insert(0, str(SCRIPTS))
        from lib.search import FTS5SearchBackend
        backend = FTS5SearchBackend(vault)
        backend.reindex()
        related = backend.find_related("wiki/auth.md")
        assert isinstance(related, list)


# ---------------------------------------------------------------------------
# Grep Search Backend
# ---------------------------------------------------------------------------

class TestGrepSearch:
    def test_search_re(self, vault):
        sys.path.insert(0, str(SCRIPTS))
        from lib.search import GrepSearchBackend
        backend = GrepSearchBackend(vault)
        results = backend.search("auth")
        assert len(results) >= 1

    def test_search_scope(self, vault):
        sys.path.insert(0, str(SCRIPTS))
        from lib.search import GrepSearchBackend
        backend = GrepSearchBackend(vault)
        results = backend.search("auth", scope="wiki")
        assert all(r.path.startswith("wiki/") for r in results)

    def test_index_status(self, vault):
        sys.path.insert(0, str(SCRIPTS))
        from lib.search import GrepSearchBackend
        backend = GrepSearchBackend(vault)
        assert backend.index_status()["backend"] == "grep"


# ---------------------------------------------------------------------------
# raw/ validation (shared lib — CLI + MCP)
# ---------------------------------------------------------------------------


class TestRawValidate:
    def test_validate_ok(self, vault):
        sys.path.insert(0, str(SCRIPTS))
        from lib.config_loader import load_config
        from lib.raw_validate import validate_raw_file_result

        cfg = load_config(vault)
        r = validate_raw_file_result(vault, cfg, "notes.md", autofix=False)
        assert r["valid"] is True
        assert r["path"] == "raw/notes.md"
        assert not r.get("issues")

    def test_validate_issues(self, vault):
        sys.path.insert(0, str(SCRIPTS))
        from lib.config_loader import load_config
        from lib.raw_validate import validate_raw_file_result

        bad = vault / "raw" / "bad.md"
        bad.write_text("```\nno closing fence\n", encoding="utf-8")
        cfg = load_config(vault)
        r = validate_raw_file_result(vault, cfg, "bad.md", autofix=False)
        assert r["valid"] is False
        assert r.get("issues")


# ---------------------------------------------------------------------------
# Search backend factory (get_search_backend)
# ---------------------------------------------------------------------------


class TestGetSearchBackend:
    def test_defaults_to_fts5(self, vault):
        sys.path.insert(0, str(SCRIPTS))
        from lib.config_loader import load_config
        from lib.search import get_search_backend

        cfg = load_config(vault)
        backend = get_search_backend(vault, cfg)
        assert backend.index_status()["backend"] == "fts5"

    def test_explicit_grep(self, vault):
        sys.path.insert(0, str(SCRIPTS))
        from lib.search import get_search_backend

        cfg = {"mcp": {"search_backend": "grep"}}
        backend = get_search_backend(vault, cfg)
        assert backend.index_status()["backend"] == "grep"

    def test_chromadb_falls_back_to_grep_when_submodule_import_fails(self, vault, monkeypatch):
        """If ChromaDBSearchBackend cannot be imported, factory uses GrepSearchBackend."""
        sys.path.insert(0, str(SCRIPTS))
        real_import = builtins.__import__

        def _import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "lib.search_chromadb":
                raise ImportError("simulated missing chromadb")
            return real_import(name, globals, locals, fromlist, level)

        monkeypatch.setattr(builtins, "__import__", _import)
        from lib.search import get_search_backend

        cfg = {"mcp": {"search_backend": "chromadb"}}
        backend = get_search_backend(vault, cfg)
        assert backend.index_status()["backend"] == "grep"

    def test_hybrid_falls_back_to_fts5_when_chromadb_unavailable(self, vault, monkeypatch):
        """If ChromaDBSearchBackend cannot be imported, hybrid uses FTS5SearchBackend."""
        sys.path.insert(0, str(SCRIPTS))
        real_import = builtins.__import__

        def _import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "lib.search_chromadb":
                raise ImportError("simulated missing chromadb")
            return real_import(name, globals, locals, fromlist, level)

        monkeypatch.setattr(builtins, "__import__", _import)
        from lib.search import get_search_backend

        cfg = {"mcp": {"search_backend": "hybrid"}}
        backend = get_search_backend(vault, cfg)
        assert backend.index_status()["backend"] == "fts5"


# ---------------------------------------------------------------------------
# JSON Knowledge Graph
# ---------------------------------------------------------------------------

class TestJSONKnowledgeGraph:
    def test_add_and_query(self, vault):
        sys.path.insert(0, str(SCRIPTS))
        from lib.knowledge_graph import JSONFileKG
        kg = JSONFileKG(vault)
        tid = kg.add_triple("team", "uses", "GraphQL", valid_from="2026-01-15")
        assert tid

        facts = kg.query_entity("team")
        assert len(facts) == 1
        assert facts[0]["o"] == "GraphQL"

    def test_invalidate(self, vault):
        sys.path.insert(0, str(SCRIPTS))
        from lib.knowledge_graph import JSONFileKG
        kg = JSONFileKG(vault)
        kg.add_triple("Kai", "works_on", "Orion", valid_from="2025-06-01")
        ok = kg.invalidate("Kai", "works_on", "Orion", ended="2026-03-01")
        assert ok

        current = kg.query_entity("Kai")
        assert len(current) == 0

        historical = kg.query_entity("Kai", as_of="2026-01-01")
        assert len(historical) == 1

    def test_timeline(self, vault):
        sys.path.insert(0, str(SCRIPTS))
        from lib.knowledge_graph import JSONFileKG
        kg = JSONFileKG(vault)
        kg.add_triple("A", "rel1", "B", valid_from="2026-01-01")
        kg.add_triple("A", "rel2", "C", valid_from="2026-02-01")
        tl = kg.timeline("A")
        assert len(tl) == 2
        assert tl[0]["valid_from"] <= tl[1]["valid_from"]

    def test_stats(self, vault):
        sys.path.insert(0, str(SCRIPTS))
        from lib.knowledge_graph import JSONFileKG
        kg = JSONFileKG(vault)
        kg.add_triple("X", "knows", "Y")
        s = kg.stats()
        assert s["entities"] == 2
        assert s["triples_total"] == 1
        assert s["triples_active"] == 1

    def test_rebuild(self, vault):
        sys.path.insert(0, str(SCRIPTS))
        from lib.knowledge_graph import JSONFileKG
        kg = JSONFileKG(vault)
        result = kg.rebuild(vault)
        assert result["added"] > 0
        assert result["entities"] > 0

    def test_idempotent_add(self, vault):
        sys.path.insert(0, str(SCRIPTS))
        from lib.knowledge_graph import JSONFileKG
        kg = JSONFileKG(vault)
        t1 = kg.add_triple("A", "rel", "B")
        t2 = kg.add_triple("A", "rel", "B")
        assert t1 == t2
        assert kg.stats()["triples_total"] == 1


class TestSQLiteKnowledgeGraph:
    @pytest.fixture
    def sqlite_vault(self, vault):
        cfg = json.loads((vault / "config.json").read_text())
        cfg.setdefault("knowledge_graph", {}).update(
            {"enabled": True, "backend": "sqlite", "auto_update_on_ingest": True}
        )
        cfg.setdefault("storage", {})["kg_sqlite_db"] = ".kg.sqlite3"
        (vault / "config.json").write_text(json.dumps(cfg))
        return vault

    def test_add_query_invalidate(self, sqlite_vault):
        sys.path.insert(0, str(SCRIPTS))
        from lib.knowledge_graph import get_kg_backend
        from lib.config_loader import load_config

        cfg = load_config(sqlite_vault)
        kg = get_kg_backend(sqlite_vault, cfg)
        assert kg.stats()["backend"] == "sqlite"
        tid = kg.add_triple("team", "uses", "GraphQL", valid_from="2026-01-15")
        assert tid
        facts = kg.query_entity("team")
        assert len(facts) == 1
        assert facts[0]["o"] == "GraphQL"
        kg.add_triple("Kai", "works_on", "Orion", valid_from="2025-06-01")
        assert kg.invalidate("Kai", "works_on", "Orion", ended="2026-03-01")
        assert len(kg.query_entity("Kai")) == 0
        assert len(kg.query_entity("Kai", as_of="2026-01-01")) == 1

    def test_rebuild(self, sqlite_vault):
        sys.path.insert(0, str(SCRIPTS))
        from lib.knowledge_graph import get_kg_backend
        from lib.config_loader import load_config

        cfg = load_config(sqlite_vault)
        kg = get_kg_backend(sqlite_vault, cfg)
        result = kg.rebuild(sqlite_vault)
        assert result["added"] > 0


# ---------------------------------------------------------------------------
# MCP Server JSON-RPC
# ---------------------------------------------------------------------------

class TestMCPServer:
    def _call(self, vault, method, params=None):
        req = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}
        env = _env()
        env["LLM_WIKI_VAULT"] = str(vault)
        proc = subprocess.run(
            [sys.executable, str(MCP_SERVER)],
            input=json.dumps(req) + "\n",
            capture_output=True,
            text=True,
            env=env,
            timeout=15,
        )
        assert proc.returncode == 0, proc.stderr
        return json.loads(proc.stdout.strip())

    def test_initialize(self, vault):
        resp = self._call(vault, "initialize")
        assert resp["result"]["serverInfo"]["name"] == "llm-wiki"

    def test_tools_list(self, vault):
        resp = self._call(vault, "tools/list")
        tools = resp["result"]["tools"]
        names = [t["name"] for t in tools]
        assert "wiki_wake_up" in names
        assert "wiki_search" in names
        assert "wiki_kg_query" in names
        # Safer defaults: benchmark + ingest tools off unless opted in
        assert "wiki_benchmark_run" not in names
        assert "wiki_ingest" not in names
        assert "wiki_metrics_stats" in names
        assert "wiki_graph_build" in names
        assert len(tools) >= 25

    def test_tools_list_with_write_opt_in(self, tmp_path):
        v = tmp_path / "llm-wiki-full"
        v.mkdir()
        (v / "config.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "mcp": {
                        "enabled": True,
                        "search_backend": "fts5",
                        "benchmark_tool_enabled": True,
                        "ingest_enabled": True,
                    },
                    "knowledge_graph": {"enabled": True, "backend": "json"},
                    "git": {"enabled": False},
                }
            ),
            encoding="utf-8",
        )
        (v / "wiki").mkdir()
        (v / "wiki" / "index.md").write_text("# i\n", encoding="utf-8")
        (v / "raw").mkdir()
        (v / "CLAUDE.md").write_text("# r\n", encoding="utf-8")
        resp = self._call(v, "tools/list")
        names = [t["name"] for t in resp["result"]["tools"]]
        assert "wiki_benchmark_run" in names
        assert "wiki_ingest" in names

    def test_tool_call_status(self, vault):
        resp = self._call(vault, "tools/call", {"name": "wiki_status", "arguments": {}})
        data = json.loads(resp["result"]["content"][0]["text"])
        assert data["wiki_pages"] == 2
        assert data["raw_files"] == 1
        assert data.get("search_backend") == "fts5"
        assert data.get("search_backend_active") == "fts5"
        assert data.get("search_backend_fallback") is False

    def test_tool_call_status_chromadb_fallback_when_package_missing(self, tmp_path):
        """When chromadb is not installed but config asks for it, status reports fallback."""
        if importlib.util.find_spec("chromadb") is not None:
            pytest.skip("chromadb installed; active backend would be chromadb, not grep fallback")
        v = tmp_path / "llm-wiki"
        v.mkdir()
        (v / "config.json").write_text(
            json.dumps({
                "version": 1,
                "mcp": {"enabled": True, "search_backend": "chromadb"},
                "knowledge_graph": {"enabled": True, "backend": "json"},
                "git": {"enabled": False},
            })
        )
        (v / "wiki").mkdir()
        (v / "wiki" / "index.md").write_text("# i\n")
        (v / "raw").mkdir()
        (v / "CLAUDE.md").write_text("# c\n")
        resp = self._call(v, "tools/call", {"name": "wiki_status", "arguments": {}})
        data = json.loads(resp["result"]["content"][0]["text"])
        assert data["search_backend"] == "chromadb"
        assert data["search_backend_active"] == "grep"
        assert data["search_backend_fallback"] is True

    def test_tool_call_status_hybrid_fallback_when_chromadb_missing(self, tmp_path):
        """When chromadb is not installed but config asks for hybrid, status reports fts5 fallback."""
        if importlib.util.find_spec("chromadb") is not None:
            pytest.skip("chromadb installed; hybrid would use Chroma")
        v = tmp_path / "llm-wiki"
        v.mkdir()
        (v / "config.json").write_text(
            json.dumps({
                "version": 1,
                "mcp": {"enabled": True, "search_backend": "hybrid"},
                "knowledge_graph": {"enabled": True, "backend": "json"},
                "git": {"enabled": False},
            })
        )
        (v / "wiki").mkdir()
        (v / "wiki" / "index.md").write_text("# i\n")
        (v / "raw").mkdir()
        (v / "CLAUDE.md").write_text("# c\n")
        resp = self._call(v, "tools/call", {"name": "wiki_status", "arguments": {}})
        data = json.loads(resp["result"]["content"][0]["text"])
        assert data["search_backend"] == "hybrid"
        assert data["search_backend_active"] == "fts5"
        assert data["search_backend_fallback"] is True

    def test_tool_call_search(self, vault):
        resp = self._call(vault, "tools/call", {"name": "wiki_search", "arguments": {"query": "auth"}})
        data = json.loads(resp["result"]["content"][0]["text"])
        assert data["count"] >= 1

    def test_tool_call_kg_add_and_query(self, vault):
        self._call(vault, "tools/call", {
            "name": "wiki_kg_add",
            "arguments": {"subject": "team", "predicate": "uses", "object_": "FastAPI"},
        })
        resp = self._call(vault, "tools/call", {
            "name": "wiki_kg_query",
            "arguments": {"entity": "team"},
        })
        data = json.loads(resp["result"]["content"][0]["text"])
        assert data["count"] >= 1

    def test_unknown_tool(self, vault):
        resp = self._call(vault, "tools/call", {"name": "nonexistent", "arguments": {}})
        assert "error" in resp


class TestMCPServerDisabled:
    def test_exits_nonzero_when_mcp_disabled(self, tmp_path):
        v = tmp_path / "llm-wiki"
        v.mkdir()
        (v / "config.json").write_text(
            json.dumps({
                "version": 1,
                "mcp": {"enabled": False},
                "knowledge_graph": {"enabled": False},
                "git": {"enabled": False},
            })
        )
        env = _env()
        env["LLM_WIKI_VAULT"] = str(v)
        proc = subprocess.run(
            [sys.executable, str(MCP_SERVER)],
            input=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}) + "\n",
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )
        assert proc.returncode != 0
        combined = (proc.stderr or "") + (proc.stdout or "")
        assert "disabled" in combined.lower()


class TestMCPHttpBridge:
    def test_post_jsonrpc_initialize(self, vault):
        import socket
        import threading
        import time
        import urllib.error
        import urllib.request

        cfg = json.loads((vault / "config.json").read_text(encoding="utf-8"))
        cfg.setdefault("mcp", {})["sse_allow_empty_token"] = True
        (vault / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()

        def run():
            sys.path.insert(0, str(SCRIPTS))
            from mcp_sse import run_sse_server

            run_sse_server(vault, port=port, host="127.0.0.1")

        threading.Thread(target=run, daemon=True).start()
        for _ in range(50):
            try:
                req = urllib.request.Request(
                    f"http://127.0.0.1:{port}/",
                    data=json.dumps(
                        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
                    ).encode(),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=2) as resp:
                    out = json.loads(resp.read().decode())
                assert out["result"]["serverInfo"]["name"] == "llm-wiki"
                return
            except (urllib.error.URLError, ConnectionRefusedError, OSError):
                time.sleep(0.05)
        raise AssertionError("HTTP MCP server did not become ready")

    def test_post_notification_initialized_returns_204(self, vault):
        import socket
        import threading
        import time
        import urllib.error
        import urllib.request

        cfg = json.loads((vault / "config.json").read_text(encoding="utf-8"))
        cfg.setdefault("mcp", {})["sse_allow_empty_token"] = True
        (vault / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()

        def run():
            sys.path.insert(0, str(SCRIPTS))
            from mcp_sse import run_sse_server

            run_sse_server(vault, port=port, host="127.0.0.1")

        threading.Thread(target=run, daemon=True).start()
        body = json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"})
        for _ in range(50):
            try:
                req = urllib.request.Request(
                    f"http://127.0.0.1:{port}/",
                    data=body.encode(),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=2) as resp:
                    assert resp.status == 204
                    assert resp.read() == b""
                return
            except (urllib.error.URLError, ConnectionRefusedError, OSError):
                time.sleep(0.05)
        raise AssertionError("HTTP MCP server did not become ready")


class TestMCPNotifications:
    """JSON-RPC notifications: no response on stdio; HTTP 204."""

    def test_stdio_notifications_initialized_empty_stdout(self, vault):
        env = _env()
        env["LLM_WIKI_VAULT"] = str(vault)
        proc = subprocess.run(
            [sys.executable, str(MCP_SERVER)],
            input=json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n",
            capture_output=True,
            text=True,
            env=env,
            timeout=15,
        )
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.strip() == ""

    def test_stdio_notifications_cancelled_empty_stdout(self, vault):
        env = _env()
        env["LLM_WIKI_VAULT"] = str(vault)
        proc = subprocess.run(
            [sys.executable, str(MCP_SERVER)],
            input=json.dumps(
                {
                    "jsonrpc": "2.0",
                    "method": "notifications/cancelled",
                    "params": {"requestId": 42, "reason": "test"},
                }
            )
            + "\n",
            capture_output=True,
            text=True,
            env=env,
            timeout=15,
        )
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout.strip() == ""


class TestMCPHardening:
    """MCP tool filtering, validation, truncation, and HTTP gate (Phase hardening)."""

    def _call(self, vault, method, params=None):
        req = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}}
        env = _env()
        env["LLM_WIKI_VAULT"] = str(vault)
        proc = subprocess.run(
            [sys.executable, str(MCP_SERVER)],
            input=json.dumps(req) + "\n",
            capture_output=True,
            text=True,
            env=env,
            timeout=15,
        )
        assert proc.returncode == 0, proc.stderr
        return json.loads(proc.stdout.strip())

    def test_tools_list_read_only_excludes_mutating_tools(self, tmp_path):
        v = tmp_path / "llm-wiki"
        v.mkdir()
        (v / "config.json").write_text(
            json.dumps({
                "version": 1,
                "mcp": {"enabled": True, "search_backend": "fts5", "tools_mode": "read_only"},
                "knowledge_graph": {"enabled": True, "backend": "json"},
                "git": {"enabled": False},
            })
        )
        (v / "wiki").mkdir()
        (v / "wiki" / "index.md").write_text("# i\n")
        (v / "raw").mkdir()
        (v / "CLAUDE.md").write_text("# c\n")
        resp = self._call(v, "tools/list")
        names = {t["name"] for t in resp["result"]["tools"]}
        assert "wiki_search" in names
        assert "wiki_kg_add" not in names
        assert "wiki_configure" not in names

    def test_tools_list_benchmark_disabled(self, tmp_path):
        v = tmp_path / "llm-wiki"
        v.mkdir()
        (v / "config.json").write_text(
            json.dumps({
                "version": 1,
                "mcp": {"enabled": True, "search_backend": "fts5", "benchmark_tool_enabled": False},
                "knowledge_graph": {"enabled": True, "backend": "json"},
                "git": {"enabled": False},
            })
        )
        (v / "wiki").mkdir()
        (v / "wiki" / "index.md").write_text("# i\n")
        (v / "raw").mkdir()
        (v / "CLAUDE.md").write_text("# c\n")
        resp = self._call(v, "tools/list")
        names = {t["name"] for t in resp["result"]["tools"]}
        assert "wiki_benchmark_run" not in names
        assert "wiki_benchmark_suites" not in names

    def test_configure_allowlist_blocks(self, tmp_path):
        v = tmp_path / "llm-wiki"
        v.mkdir()
        (v / "config.json").write_text(
            json.dumps({
                "version": 1,
                "mcp": {
                    "enabled": True,
                    "search_backend": "fts5",
                    "configure_allowlist": ["viewer."],
                },
                "viewer": {"enabled": True, "port": 8765},
                "knowledge_graph": {"enabled": True, "backend": "json"},
                "git": {"enabled": False},
            })
        )
        (v / "wiki").mkdir()
        (v / "wiki" / "index.md").write_text("# i\n")
        (v / "raw").mkdir()
        (v / "CLAUDE.md").write_text("# c\n")
        resp = self._call(
            v,
            "tools/call",
            {
                "name": "wiki_configure",
                "arguments": {"key": "mcp.search_backend", "value": '"grep"'},
            },
        )
        data = json.loads(resp["result"]["content"][0]["text"])
        assert data.get("success") is False
        assert "configure_allowlist" in (data.get("error") or "")

    def test_invalid_search_scope(self, vault):
        resp = self._call(
            vault,
            "tools/call",
            {"name": "wiki_search", "arguments": {"query": "x", "scope": "bad"}},
        )
        assert resp.get("error", {}).get("code") == -32602

    def test_max_response_truncation(self, tmp_path):
        v = tmp_path / "llm-wiki"
        v.mkdir()
        (v / "config.json").write_text(
            json.dumps({
                "version": 1,
                "mcp": {
                    "enabled": True,
                    "search_backend": "fts5",
                    "max_response_chars": 80,
                },
                "knowledge_graph": {"enabled": True, "backend": "json"},
                "git": {"enabled": False},
            })
        )
        (v / "wiki").mkdir()
        (v / "wiki" / "index.md").write_text("# i\n")
        (v / "raw").mkdir()
        (v / "CLAUDE.md").write_text("# c\n")
        resp = self._call(v, "tools/call", {"name": "wiki_status", "arguments": {}})
        text = resp["result"]["content"][0]["text"]
        assert len(text) <= 200
        assert "truncated" in text.lower()

    def test_sse_exits_non_loopback_when_required(self, tmp_path):
        v = tmp_path / "llm-wiki"
        v.mkdir()
        (v / "config.json").write_text(
            json.dumps({
                "version": 1,
                "mcp": {"enabled": True, "sse_require_loopback": True},
                "knowledge_graph": {"enabled": False},
                "git": {"enabled": False},
            })
        )
        code = (
            "import sys\n"
            f"sys.path.insert(0, {repr(str(SCRIPTS))})\n"
            "from pathlib import Path\n"
            "from mcp_sse import run_sse_server\n"
            f"run_sse_server(Path({repr(str(v))}), port=19991, host='0.0.0.0')\n"
        )
        proc = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert proc.returncode == 1
        assert "loopback" in (proc.stderr + proc.stdout).lower()

    def test_sse_token_unauthorized(self, tmp_path):
        import socket
        import threading
        import time
        import urllib.error
        import urllib.request

        v = tmp_path / "llm-wiki"
        v.mkdir()
        (v / "config.json").write_text(
            json.dumps({
                "version": 1,
                "mcp": {"enabled": True, "sse_token": "test-secret-token"},
                "knowledge_graph": {"enabled": False},
                "git": {"enabled": False},
            })
        )
        (v / "wiki").mkdir()
        (v / "wiki" / "index.md").write_text("# i\n")
        (v / "raw").mkdir()
        (v / "CLAUDE.md").write_text("# c\n")

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()

        def run():
            sys.path.insert(0, str(SCRIPTS))
            from mcp_sse import run_sse_server

            run_sse_server(v, port=port, host="127.0.0.1")

        threading.Thread(target=run, daemon=True).start()
        for _ in range(50):
            try:
                req = urllib.request.Request(
                    f"http://127.0.0.1:{port}/",
                    data=json.dumps(
                        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
                    ).encode(),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                try:
                    urllib.request.urlopen(req, timeout=2)
                except urllib.error.HTTPError as e:
                    if e.code == 401:
                        return
            except (urllib.error.URLError, ConnectionRefusedError, OSError):
                time.sleep(0.05)
        raise AssertionError("Expected 401 from MCP HTTP without token")


# ---------------------------------------------------------------------------
# FTS5 SQLite PRAGMAs and config
# ---------------------------------------------------------------------------

class TestFTS5Pragmas:
    def test_default_wal_journal(self, vault):
        sys.path.insert(0, str(SCRIPTS))
        from lib.search import FTS5SearchBackend
        cfg = {"performance": {"sqlite": {}}}
        backend = FTS5SearchBackend(vault, cfg)
        with backend._conn() as conn:
            row = conn.execute("PRAGMA journal_mode").fetchone()
            assert row[0] == "wal"

    def test_custom_pragmas(self, vault):
        sys.path.insert(0, str(SCRIPTS))
        from lib.search import FTS5SearchBackend
        cfg = {
            "performance": {"sqlite": {
                "journal_mode": "delete",
                "synchronous": "full",
                "cache_size": -4096,
                "busy_timeout": 2000,
            }},
        }
        backend = FTS5SearchBackend(vault, cfg)
        with backend._conn() as conn:
            assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
            assert conn.execute("PRAGMA synchronous").fetchone()[0] == 2  # FULL=2
            assert conn.execute("PRAGMA cache_size").fetchone()[0] == -4096
            assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 2000

    def test_custom_storage_path(self, vault):
        sys.path.insert(0, str(SCRIPTS))
        from lib.search import FTS5SearchBackend
        custom_dir = vault / "data"
        custom_dir.mkdir()
        cfg = {"storage": {"search_db": "data/custom.sqlite3"}}
        backend = FTS5SearchBackend(vault, cfg)
        assert backend._db_path == custom_dir / "custom.sqlite3"
        backend.reindex()
        assert (custom_dir / "custom.sqlite3").exists()

    def test_absolute_storage_path(self, vault):
        sys.path.insert(0, str(SCRIPTS))
        from lib.search import FTS5SearchBackend

        abs_path = (vault / "external" / "search.db").resolve()
        abs_path.parent.mkdir(parents=True)
        cfg = {"storage": {"search_db": str(abs_path)}}
        backend = FTS5SearchBackend(vault, cfg)
        assert backend._db_path == abs_path


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

class TestMetrics:
    def test_disabled_noop(self, vault):
        sys.path.insert(0, str(SCRIPTS))
        from lib.metrics import get_metrics
        m = get_metrics(vault, {"metrics": {"enabled": False}})
        assert not m.enabled
        m.record("test.key", 42)
        assert m.query() == []
        assert m.stats() == {"enabled": False}

    def test_record_and_query(self, vault):
        sys.path.insert(0, str(SCRIPTS))
        from lib.metrics import MetricsRecorder
        cfg = {"metrics": {"enabled": True}}
        m = MetricsRecorder(vault, cfg)
        m.record("search.query_ms", 12.5, meta={"query": "auth"}, tags=["search"])
        m.record("kg.add_triple", 1, meta={"subject": "team"})
        records = m.query()
        assert len(records) == 2
        assert records[0]["key"] == "search.query_ms"
        assert records[0]["value"] == 12.5
        assert records[0]["meta"]["query"] == "auth"
        assert records[0]["tags"] == ["search"]

    def test_query_by_key(self, vault):
        sys.path.insert(0, str(SCRIPTS))
        from lib.metrics import MetricsRecorder
        m = MetricsRecorder(vault, {"metrics": {"enabled": True}})
        m.record("a", 1)
        m.record("b", 2)
        m.record("a", 3)
        assert len(m.query(key="a")) == 2
        assert len(m.query(key="b")) == 1

    def test_stats(self, vault):
        sys.path.insert(0, str(SCRIPTS))
        from lib.metrics import MetricsRecorder
        m = MetricsRecorder(vault, {"metrics": {"enabled": True}})
        m.record("x", 1)
        m.record("x", 2)
        m.record("y", 3)
        s = m.stats()
        assert s["enabled"] is True
        assert s["records"] == 3
        assert s["keys"]["x"] == 2
        assert s["keys"]["y"] == 1

    def test_clear_all(self, vault):
        sys.path.insert(0, str(SCRIPTS))
        from lib.metrics import MetricsRecorder
        m = MetricsRecorder(vault, {"metrics": {"enabled": True}})
        m.record("a", 1)
        m.record("b", 2)
        result = m.clear()
        assert result["removed"] == 2
        assert m.query() == []

    def test_custom_storage_path(self, vault):
        sys.path.insert(0, str(SCRIPTS))
        from lib.metrics import MetricsRecorder
        custom_dir = vault / "data"
        custom_dir.mkdir()
        cfg = {"metrics": {"enabled": True}, "storage": {"metrics_db": "data/custom.jsonl"}}
        m = MetricsRecorder(vault, cfg)
        m.record("test", 1)
        assert (custom_dir / "custom.jsonl").exists()

    def test_max_file_size(self, vault):
        sys.path.insert(0, str(SCRIPTS))
        from lib.metrics import MetricsRecorder
        cfg = {"metrics": {"enabled": True, "max_file_size_mb": 0}}
        m = MetricsRecorder(vault, cfg)
        m.record("before_limit", 1)
        assert len(m.query()) <= 1


# ---------------------------------------------------------------------------
# Metrics report / summary
# ---------------------------------------------------------------------------

class TestMetricsReport:
    def test_build_metrics_summary_json_structure(self, vault):
        sys.path.insert(0, str(SCRIPTS))
        from lib.metrics_report import build_metrics_summary

        metrics_path = vault / ".metrics.jsonl"
        lines = [
            json.dumps({"ts": "2026-04-01T12:00:00+00:00", "key": "search.query_ms", "value": 10.0}) + "\n",
            json.dumps({"ts": "2026-04-01T12:01:00+00:00", "key": "search.query_ms", "value": 20.0}) + "\n",
            json.dumps({"ts": "2026-04-01T12:02:00+00:00", "key": "mcp.tool_call", "value": "foo"}) + "\n",
        ]
        metrics_path.write_text("".join(lines), encoding="utf-8")
        cfg = json.loads((vault / "config.json").read_text())
        out = build_metrics_summary(vault, cfg, since="2026-03-01", as_json=True)
        assert isinstance(out, dict)
        assert out["record_count"] == 3
        assert out["key_count"] == 2
        assert "rows" in out and len(out["rows"]) == 2
        ms_rows = [r for r in out["rows"] if r["key"] == "search.query_ms"]
        assert len(ms_rows) == 1 and ms_rows[0]["numeric"] is True
        tool_rows = [r for r in out["rows"] if r["key"] == "mcp.tool_call"]
        assert len(tool_rows) == 1 and tool_rows[0]["numeric"] is False

    def test_build_metrics_report_writes_html(self, vault, tmp_path):
        sys.path.insert(0, str(SCRIPTS))
        from lib.metrics_report import build_metrics_report

        metrics_path = vault / ".metrics.jsonl"
        metrics_path.write_text(
            json.dumps({"ts": "2026-04-01T12:00:00+00:00", "key": "search.query_ms", "value": 15.0}) + "\n",
            encoding="utf-8",
        )
        cfg = json.loads((vault / "config.json").read_text())
        out_dir = tmp_path / "metrics-out"
        path = build_metrics_report(vault, cfg, out_dir, since="2026-03-01")
        assert path.is_file()
        text = path.read_text(encoding="utf-8")
        assert "METRICS_DATA" in text or "search.query_ms" in text
        assert "Chart" in text or "chart" in text


# ---------------------------------------------------------------------------
# Knowledge Graph config
# ---------------------------------------------------------------------------

class TestKGConfig:
    def test_custom_kg_path(self, vault):
        sys.path.insert(0, str(SCRIPTS))
        from lib.knowledge_graph import JSONFileKG
        custom_dir = vault / "data"
        custom_dir.mkdir()
        cfg = {"storage": {"kg_db": "data/kg.json"}}
        kg = JSONFileKG(vault, cfg)
        kg.add_triple("A", "rel", "B")
        assert (custom_dir / "kg.json").exists()
        facts = kg.query_entity("A")
        assert len(facts) == 1
