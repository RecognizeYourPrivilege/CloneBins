"""Progress reporting hooks used by the CLI (core stays UI-agnostic)."""

from __future__ import annotations

from typing import Protocol


class ProgressReporter(Protocol):
    def log(self, message: str) -> None: ...

    def start(self, phase: str, total: int | None = None) -> None: ...

    def advance(self, phase: str, step: int = 1, message: str = "") -> None: ...

    def finish(self, phase: str) -> None: ...


class NullProgress:
    def log(self, message: str) -> None:
        return

    def start(self, phase: str, total: int | None = None) -> None:
        return

    def advance(self, phase: str, step: int = 1, message: str = "") -> None:
        return

    def finish(self, phase: str) -> None:
        return
