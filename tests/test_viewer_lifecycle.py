"""Safety checks for the static viewer's detached-process lifecycle."""

from __future__ import annotations

import json
from pathlib import Path

from cli import core_commands


def test_stop_viewer_never_terminates_a_legacy_pid_only_record(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    vault = tmp_path / "llm-wiki"
    og_dir = vault / "wiki" / ".og"
    og_dir.mkdir(parents=True)
    pid_path = og_dir / core_commands.VIEWER_HTTP_PID_NAME
    pid_path.write_text("4321\n", encoding="utf-8")

    terminated: list[int] = []
    monkeypatch.setattr(core_commands, "_pid_is_running", lambda pid: pid == 4321)
    monkeypatch.setattr(
        core_commands,
        "_terminate_pid",
        lambda pid: terminated.append(pid) or True,
    )

    assert core_commands.cmd_stop_viewer_http(vault) == 1
    assert terminated == []
    assert not pid_path.exists()
    assert "legacy" in capsys.readouterr().err.lower()


def test_stop_viewer_terminates_only_a_verified_identity(
    tmp_path: Path,
    monkeypatch,
) -> None:
    vault = tmp_path / "llm-wiki"
    og_dir = vault / "wiki" / ".og"
    og_dir.mkdir(parents=True)
    pid_path = og_dir / core_commands.VIEWER_HTTP_PID_NAME
    pid_path.write_text(
        json.dumps(
            {
                "version": core_commands.VIEWER_HTTP_RECORD_VERSION,
                "pid": 4321,
                "port": 8765,
                "token": "test-token",
            }
        ),
        encoding="utf-8",
    )

    terminated: list[int] = []
    monkeypatch.setattr(core_commands, "_pid_is_running", lambda pid: pid == 4321)
    monkeypatch.setattr(core_commands, "_viewer_identity_matches", lambda _dir, _record: True)
    monkeypatch.setattr(
        core_commands,
        "_terminate_pid",
        lambda pid: terminated.append(pid) or True,
    )

    assert core_commands.cmd_stop_viewer_http(vault) == 0
    assert terminated == [4321]
    assert not pid_path.exists()
