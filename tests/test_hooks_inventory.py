"""hooks/hooks.json: declared hook scripts exist and pass bash -n."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
HOOKS_JSON = REPO / "hooks" / "hooks.json"


def _collect_command_paths(obj: object) -> set[str]:
    out: set[str] = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "command" and isinstance(v, str):
                out.add(v)
            else:
                out |= _collect_command_paths(v)
    elif isinstance(obj, list):
        for item in obj:
            out |= _collect_command_paths(item)
    return out


def test_every_hooks_sh_file_is_listed_in_hooks_json() -> None:
    """No orphan shell under hooks/ — every *.sh appears in hooks.json."""
    blob = HOOKS_JSON.read_text(encoding="utf-8")
    for script in sorted((REPO / "hooks").glob("*.sh")):
        assert script.name in blob, (
            f"{script.name} exists under hooks/ but is not referenced in hooks/hooks.json"
        )


def test_hooks_json_references_existing_scripts() -> None:
    data = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))
    commands = _collect_command_paths(data)
    sh_paths = [c for c in commands if c.endswith(".sh")]
    assert sh_paths, "expected at least one .sh hook in hooks.json"

    root_token = "${CLAUDE_PLUGIN_ROOT}"
    for raw in sh_paths:
        if root_token in raw:
            path = Path(raw.replace(root_token, str(REPO)))
        else:
            path = Path(raw)
            if not path.is_file():
                path = REPO / raw.lstrip("/")
        assert path.is_file(), f"missing hook script: {raw} -> {path}"


def test_hook_shell_scripts_pass_bash_n() -> None:
    bash = shutil.which("bash")
    if not bash:
        pytest.skip("bash not on PATH")

    for script in sorted((REPO / "hooks").glob("*.sh")):
        r = subprocess.run(
            [bash, "-n", str(script)],
            cwd=str(REPO),
            capture_output=True,
            text=True,
        )
        assert r.returncode == 0, f"bash -n {script}: {r.stderr or r.stdout}"
