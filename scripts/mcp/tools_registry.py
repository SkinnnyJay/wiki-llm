"""MCP tool registry (schemas + handlers)."""
from __future__ import annotations

from typing import Any

from mcp.tools_kg import (
    tool_wiki_find_connections,
    tool_wiki_kg_add,
    tool_wiki_kg_invalidate,
    tool_wiki_kg_query,
    tool_wiki_kg_rebuild,
    tool_wiki_kg_stats,
    tool_wiki_kg_timeline,
    tool_wiki_kg_traverse,
)
from mcp.tools_read import (
    tool_memory_list,
    tool_memory_recall,
    tool_memory_show,
    tool_wiki_agent_diary_read,
    tool_wiki_benchmark_suites,
    tool_wiki_check_duplicate,
    tool_wiki_doctor,
    tool_wiki_find_related,
    tool_wiki_git_status,
    tool_wiki_graph,
    tool_wiki_list_topics,
    tool_wiki_metrics_query,
    tool_wiki_metrics_stats,
    tool_wiki_raw_validate,
    tool_wiki_read_page,
    tool_wiki_search,
    tool_wiki_search_index_status,
    tool_wiki_status,
    tool_wiki_validate,
    tool_wiki_wake_up,
)
from mcp.tools_write import (
    tool_memory_log,
    tool_memory_prune,
    tool_memory_save,
    tool_wiki_agent_diary_append,
    tool_wiki_benchmark_run,
    tool_wiki_build_site,
    tool_wiki_configure,
    tool_wiki_graph_build,
    tool_wiki_ingest,
    tool_wiki_reindex,
)

TOOLS: dict[str, dict[str, Any]] = {
    # -- Read --
    "wiki_wake_up": {
        "description": "Load L0+L1 context blob — persona, topics, recent activity. Call this on session start.",
        "input_schema": {"type": "object", "properties": {}},
        "handler": tool_wiki_wake_up,
    },
    "wiki_status": {
        "description": "Vault overview: file counts, config, backend modes.",
        "input_schema": {"type": "object", "properties": {}},
        "handler": tool_wiki_status,
    },
    "wiki_doctor": {
        "description": "Diagnose vault health (same report as `llm-wiki doctor`; does not apply fixes).",
        "input_schema": {"type": "object", "properties": {}},
        "handler": tool_wiki_doctor,
    },
    "wiki_list_topics": {
        "description": "Tag index with wiki coverage markers.",
        "input_schema": {"type": "object", "properties": {}},
        "handler": tool_wiki_list_topics,
    },
    "wiki_validate": {
        "description": "Vault health check — returns issues (empty = healthy).",
        "input_schema": {"type": "object", "properties": {}},
        "handler": tool_wiki_validate,
    },
    "wiki_read_page": {
        "description": "Read markdown + frontmatter from a wiki/ or raw/ file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path within vault, e.g. wiki/auth.md"},
                "max_chars": {
                    "type": "integer",
                    "description": "Truncate body (0 = use mcp.read_page_max_chars; both 0 = full file)",
                },
            },
            "required": ["path"],
        },
        "handler": tool_wiki_read_page,
    },
    "wiki_graph": {
        "description": "JSON graph of wiki pages: nodes and edges (wikilinks + md links).",
        "input_schema": {"type": "object", "properties": {}},
        "handler": tool_wiki_graph,
    },
    "wiki_git_status": {
        "description": "Vault git state (short status).",
        "input_schema": {"type": "object", "properties": {}},
        "handler": tool_wiki_git_status,
    },
    "wiki_search": {
        "description": "Search vault content. FTS5/BM25 by default, ChromaDB if configured. Returns ranked results with snippets.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "limit": {"type": "integer", "description": "Max results (default 5)"},
                "tag": {"type": "string", "description": "Filter by tag (optional)"},
                "scope": {"type": "string", "description": "all | wiki | raw | memory (default: all)"},
                "wing": {
                    "type": "string",
                    "description": "Optional palace-style scope: project/person (frontmatter wing / llm_wiki_wing)",
                },
                "room": {
                    "type": "string",
                    "description": "Optional topic scope (frontmatter room / llm_wiki_room)",
                },
            },
            "required": ["query"],
        },
        "handler": tool_wiki_search,
    },
    "wiki_find_related": {
        "description": "Find pages related to a given page (by title/tag similarity).",
        "input_schema": {
            "type": "object",
            "properties": {
                "page_path": {"type": "string", "description": "Path to the page, e.g. wiki/auth.md"},
                "limit": {"type": "integer", "description": "Max results (default 5)"},
            },
            "required": ["page_path"],
        },
        "handler": tool_wiki_find_related,
    },
    "wiki_search_index_status": {
        "description": "Search index stats: backend, file count, last indexed.",
        "input_schema": {"type": "object", "properties": {}},
        "handler": tool_wiki_search_index_status,
    },
    "wiki_kg_query": {
        "description": "Query entity relationships from the knowledge graph. Returns current facts for an entity.",
        "input_schema": {
            "type": "object",
            "properties": {
                "entity": {"type": "string", "description": "Entity name to look up"},
                "as_of": {"type": "string", "description": "Point-in-time filter (YYYY-MM-DD, optional)"},
            },
            "required": ["entity"],
        },
        "handler": tool_wiki_kg_query,
    },
    "wiki_kg_timeline": {
        "description": "Chronological history of an entity, or all facts if no entity given.",
        "input_schema": {
            "type": "object",
            "properties": {"entity": {"type": "string", "description": "Entity (optional — omit for full timeline)"}},
        },
        "handler": tool_wiki_kg_timeline,
    },
    "wiki_kg_stats": {
        "description": "Knowledge graph overview: entity count, triple count, predicates.",
        "input_schema": {"type": "object", "properties": {}},
        "handler": tool_wiki_kg_stats,
    },
    "wiki_check_duplicate": {
        "description": "Content-hash duplicate check (same as ingest dedup). Pass raw markdown body or vault-relative path.",
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Raw markdown to hash (optional if path set)"},
                "path": {"type": "string", "description": "Vault-relative path to a file to hash"},
            },
        },
        "handler": tool_wiki_check_duplicate,
    },
    "wiki_kg_traverse": {
        "description": "BFS from an entity over active KG triples (undirected).",
        "input_schema": {
            "type": "object",
            "properties": {
                "start": {"type": "string", "description": "Starting entity name"},
                "max_depth": {"type": "integer", "description": "Hop depth (default 2)"},
            },
            "required": ["start"],
        },
        "handler": tool_wiki_kg_traverse,
    },
    "wiki_find_connections": {
        "description": "Shortest triple-path between two entities (tunnel / bridge discovery).",
        "input_schema": {
            "type": "object",
            "properties": {
                "entity_a": {"type": "string"},
                "entity_b": {"type": "string"},
                "max_depth": {"type": "integer", "description": "Max triples on path (default 12)"},
            },
            "required": ["entity_a", "entity_b"],
        },
        "handler": tool_wiki_find_connections,
    },
    "wiki_agent_diary_read": {
        "description": "Read per-agent diary (raw/agents/<id>/diary.md).",
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string"},
                "max_chars": {"type": "integer", "description": "Truncate (0 = full)"},
            },
            "required": ["agent_id"],
        },
        "handler": tool_wiki_agent_diary_read,
    },
    "wiki_agent_diary_append": {
        "description": "Append a line to an agent diary (creates file if missing).",
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string"},
                "line": {"type": "string", "description": "One log line (markdown bullet added)"},
                "source": {"type": "string", "description": "Optional provenance label"},
            },
            "required": ["agent_id", "line"],
        },
        "handler": tool_wiki_agent_diary_append,
    },
    # -- Write --
    "wiki_ingest": {
        "description": "Trigger an ingest adapter (url, file, pdf, youtube, etc.) and run post-ingest pipeline (CLI parity).",
        "input_schema": {
            "type": "object",
            "properties": {
                "adapter": {"type": "string", "description": "Adapter name (url, file, pdf, youtube, brave, etc.)"},
                "source": {"type": "string", "description": "Source URL or file path"},
                "tags": {"type": "string", "description": "Comma-separated tags (optional)"},
                "out": {"type": "string", "description": "Output path under raw/ (optional)"},
                "force": {
                    "type": "boolean",
                    "description": "Bypass integration enable check and dedup/security gates where applicable (matches CLI --force)",
                },
                "force_security": {
                    "type": "boolean",
                    "description": "Run security scan even when ingest security is disabled (CLI --force-security)",
                },
            },
            "required": ["adapter", "source"],
        },
        "handler": tool_wiki_ingest,
    },
    "wiki_raw_validate": {
        "description": "Validate a raw/ file for structural issues (optional autofix, same rules as CLI raw validate).",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path under raw/, e.g. notes/auth.md"},
                "autofix": {"type": "boolean", "description": "Apply safe deterministic fixes before validating"},
            },
            "required": ["path"],
        },
        "handler": tool_wiki_raw_validate,
    },
    "wiki_build_site": {
        "description": "Rebuild the static wiki viewer.",
        "input_schema": {
            "type": "object",
            "properties": {
                "if_stale": {
                    "type": "boolean",
                    "description": "If true, skip build when viewer output is already up to date (CLI --if-stale)",
                }
            },
        },
        "handler": tool_wiki_build_site,
    },
    "wiki_metrics_stats": {
        "description": "Metrics file summary (read-only). CLI: llm-wiki metrics stats",
        "input_schema": {"type": "object", "properties": {}},
        "handler": tool_wiki_metrics_stats,
    },
    "wiki_metrics_query": {
        "description": "Query metrics JSONL records (read-only). CLI: llm-wiki metrics query",
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Filter by metric key (optional)"},
                "since": {"type": "string", "description": "ISO timestamp lower bound (optional)"},
                "limit": {"type": "integer", "description": "Max records (default 100)"},
            },
        },
        "handler": tool_wiki_metrics_query,
    },
    "wiki_benchmark_suites": {
        "description": "Print benchmark suite help text. CLI: llm-wiki benchmark suites",
        "input_schema": {"type": "object", "properties": {}},
        "handler": tool_wiki_benchmark_suites,
    },
    "wiki_graph_build": {
        "description": "Build D3 link/knowledge graph bundle (HTML) under output dir. Distinct from wiki_graph JSON export.",
        "input_schema": {
            "type": "object",
            "properties": {
                "mode": {"type": "string", "description": "links | knowledge"},
                "out": {"type": "string", "description": "Output directory (default: .tmp/llm-wiki-graph under cwd)"},
            },
        },
        "handler": tool_wiki_graph_build,
    },
    "wiki_configure": {
        "description": "Update a config.json key. Dot-separated path, e.g. 'mcp.search_backend'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Config key path (dot-separated)"},
                "value": {"type": "string", "description": "New value (JSON-parsed if valid, string otherwise)"},
            },
            "required": ["key", "value"],
        },
        "handler": tool_wiki_configure,
    },
    "wiki_reindex": {
        "description": "Rebuild the search index from vault files.",
        "input_schema": {"type": "object", "properties": {}},
        "handler": tool_wiki_reindex,
    },
    "wiki_kg_add": {
        "description": "Add a fact triple to the knowledge graph. E.g. ('team', 'decided_to_use', 'GraphQL').",
        "input_schema": {
            "type": "object",
            "properties": {
                "subject": {"type": "string", "description": "Entity doing/being something"},
                "predicate": {"type": "string", "description": "Relationship (e.g. 'uses', 'decided_to_use', 'assigned_to')"},
                "object_": {"type": "string", "description": "Connected entity"},
                "valid_from": {"type": "string", "description": "When this became true (YYYY-MM-DD, optional)"},
                "source": {"type": "string", "description": "Source file path (optional)"},
            },
            "required": ["subject", "predicate", "object_"],
        },
        "handler": tool_wiki_kg_add,
    },
    "wiki_kg_invalidate": {
        "description": "Mark a fact as no longer true (set end date).",
        "input_schema": {
            "type": "object",
            "properties": {
                "subject": {"type": "string", "description": "Entity"},
                "predicate": {"type": "string", "description": "Relationship"},
                "object_": {"type": "string", "description": "Connected entity"},
                "ended": {"type": "string", "description": "When it stopped being true (YYYY-MM-DD, default: today)"},
            },
            "required": ["subject", "predicate", "object_"],
        },
        "handler": tool_wiki_kg_invalidate,
    },
    "wiki_kg_rebuild": {
        "description": "Rebuild knowledge graph from vault files (extracts wikilinks + tags).",
        "input_schema": {"type": "object", "properties": {}},
        "handler": tool_wiki_kg_rebuild,
    },
    "memory_save": {
        "description": "Update session memory (raw/memory/<id>.md). Prefer: llm-wiki memory save --current …",
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Chat session id (omit if current=true)"},
                "current": {"type": "boolean", "description": "Use .current-session in vault"},
                "summary": {"type": "string", "description": "Agent notes section"},
                "compact_summary": {"type": "string", "description": "Compact summary section"},
                "tags": {"type": "string", "description": "Comma-separated tags"},
                "metadata": {"type": "string", "description": "JSON object string (optional)"},
            },
        },
        "handler": tool_memory_save,
    },
    "memory_log": {
        "description": "Append a conversation round to session memory. Prefer: llm-wiki memory log",
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Chat session id (omit if current=true)"},
                "current": {"type": "boolean", "description": "Use .current-session in vault"},
                "message_preview": {"type": "string", "description": "Short preview of the conversation round (max 500 chars)"},
            },
        },
        "handler": tool_memory_log,
    },
    "memory_list": {
        "description": "List session memory files. Prefer: llm-wiki memory list",
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "Filter: id, glob, or comma list"},
                "tag": {"type": "string", "description": "Filter by frontmatter tag"},
            },
        },
        "handler": tool_memory_list,
    },
    "memory_show": {
        "description": "Read one session memory file. Prefer: llm-wiki memory show --current",
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "current": {"type": "boolean"},
            },
        },
        "handler": tool_memory_show,
    },
    "memory_recall": {
        "description": "Search session memories (indexed). Prefer: llm-wiki memory recall …",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "session_id": {"type": "string", "description": "Scope to session(s)"},
                "tag": {"type": "string"},
                "limit": {"type": "integer"},
                "current": {"type": "boolean", "description": "Scope to current session"},
            },
            "required": ["query"],
        },
        "handler": tool_memory_recall,
    },
    "memory_prune": {
        "description": "Delete session memory files. Prefer: llm-wiki memory prune …",
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "tag": {"type": "string"},
                "older_than_days": {"type": "integer"},
                "keep": {"type": "integer"},
                "dry_run": {"type": "boolean"},
            },
        },
        "handler": tool_memory_prune,
    },
    "wiki_benchmark_run": {
        "description": "Run retrieval benchmark (LME / LoCoMo / ConvoMem) with vault config. CLI: llm-wiki benchmark run …",
        "input_schema": {
            "type": "object",
            "properties": {
                "suite": {
                    "type": "string",
                    "description": "lme | locomo | convomem (aliases: longmemeval → lme)",
                },
                "limit": {"type": "integer", "description": "Max questions (0 = all)"},
                "backend": {"type": "string", "description": "fts5 | grep | chromadb | hybrid"},
                "compressor": {"type": "string", "description": "raw | steno | prune | extract | compact"},
                "use_llm": {
                    "type": "boolean",
                    "description": "Set LLM_WIKI_BENCHMARK_LLM=1 for this run (rerank per benchmark.search.rerank_llm)",
                },
                "top_k": {"type": "integer", "description": "Retrieval depth for LME (default 5)"},
                "data_path": {
                    "type": "string",
                    "description": "Optional dataset path (must be under vault or benchmark cache dir)",
                },
                "no_metrics": {
                    "type": "boolean",
                    "description": "If true, disable auto_record_metrics for this run (CLI --no-metrics)",
                },
                "peers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional peer ids (mem0, mempalace, claude-mem, supermemory) for LME; same LongMemEval JSON as vault LME",
                },
                "strict_peers": {
                    "type": "boolean",
                    "description": "Fail if any peer cannot run (CLI --strict-peers / benchmark.peers.strict)",
                },
            },
        },
        "handler": tool_wiki_benchmark_run,
    },
}

READ_ONLY_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "wiki_wake_up",
        "wiki_status",
        "wiki_doctor",
        "wiki_list_topics",
        "wiki_validate",
        "wiki_read_page",
        "wiki_graph",
        "wiki_git_status",
        "wiki_search",
        "wiki_find_related",
        "wiki_search_index_status",
        "wiki_kg_query",
        "wiki_kg_timeline",
        "wiki_kg_stats",
        "wiki_check_duplicate",
        "wiki_kg_traverse",
        "wiki_find_connections",
        "wiki_agent_diary_read",
        "wiki_raw_validate",
        "wiki_metrics_stats",
        "wiki_metrics_query",
        "wiki_benchmark_suites",
        "memory_list",
        "memory_show",
        "memory_recall",
    }
)


