from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar


@dataclass
class IngestResult:
    output_path: Path
    message: str
    commit_body: str | None = None


class Adapter(ABC):
    id: ClassVar[str] = "base"
    label: ClassVar[str] = "Base"
    CONFIG_SCHEMA: ClassVar[dict[str, Any]] = {}

    @abstractmethod
    def run(self, vault: Path, cfg: dict[str, Any], argv: list[str]) -> IngestResult:
        raise NotImplementedError

    @classmethod
    def setup_checks(cls, cfg_slice: dict[str, Any]) -> list[str]:
        return []
