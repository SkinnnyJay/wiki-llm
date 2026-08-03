"""Optional notification hooks (e.g. sound) after ingest / research-loop."""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

# First argv allowed when not an absolute path (portable notification binaries).
_SOUND_CMD_ALLOWLIST = frozenset(
    {"afplay", "say", "aplay", "paplay", "ffplay", "speaker-test", "play"}
)


def maybe_play_sound(cfg: dict[str, Any], event: str) -> None:
    """
    If hooks.sound.enabled and hooks.sound.on_<event>, run hooks.sound.command.
    event: \"ingest\" | \"research_loop\"
    """
    hooks = cfg.get("hooks") or {}
    sound = hooks.get("sound") or {}
    allow_any = bool(sound.get("allow_arbitrary_command"))
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
    exe = str(cmd[0])
    if not allow_any:
        ok = False
        p = Path(exe)
        if p.is_absolute() and os.path.isfile(exe) and os.access(exe, os.X_OK) or os.path.basename(exe) in _SOUND_CMD_ALLOWLIST:
            ok = True
        if not ok:
            print(
                "hooks.sound: command blocked — first element must be an absolute path to an "
                "executable, or a known player name (e.g. afplay). "
                "Set hooks.sound.allow_arbitrary_command to true only if you fully trust config.json.",
                file=sys.stderr,
            )
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
