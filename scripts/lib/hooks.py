"""Optional notification hooks (e.g. sound) after ingest / research-loop."""

from __future__ import annotations

import shlex
import subprocess
import sys
from typing import Any


def maybe_play_sound(cfg: dict[str, Any], event: str) -> None:
    """
    If hooks.sound.enabled and hooks.sound.on_<event>, run hooks.sound.command.
    event: \"ingest\" | \"research_loop\"
    """
    hooks = cfg.get("hooks") or {}
    sound = hooks.get("sound") or {}
    if not sound.get("enabled"):
        return
    on_key = f"on_{event}"
    if not sound.get(on_key, True):
        return
    cmd = sound.get("command")
    if not cmd:
        return
    if isinstance(cmd, str):
        cmd = shlex.split(cmd)
    if not isinstance(cmd, list) or not cmd:
        return
    try:
        subprocess.run(
            [str(x) for x in cmd],
            timeout=float(sound.get("timeout_seconds") or 30),
            capture_output=True,
            check=False,
        )
    except Exception as e:
        print(f"hooks.sound ({event}):", e, file=sys.stderr)
