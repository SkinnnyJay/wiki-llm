"""Introspect llm-wiki argparse without running subcommands."""

from __future__ import annotations

import argparse


def top_level_subcommands(parser: argparse.ArgumentParser) -> set[str]:
    """Return names of direct subparsers (e.g. configure, ingest, raw)."""
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return set(action.choices.keys()) if action.choices else set()
    return set()
