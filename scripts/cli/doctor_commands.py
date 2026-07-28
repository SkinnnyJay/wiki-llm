"""Vault doctor command."""
from __future__ import annotations

import argparse
import json

from lib.doctor import doctor_report
from lib.paths import resolve_vault


def cmd_doctor(args: argparse.Namespace) -> int:
    report = doctor_report(resolve_vault(override=args.vault), fix=getattr(args, "fix", False))
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1
