# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
"""Background span indexer (RRD-169).

Watches project memory dirs and indexes new/changed spans through the
bounded index_files call, so sunk spans become searchable without a
manual index run. Stateless: the hash registry decides new vs unchanged,
so restarts and overlapping writers are safe. Runs on the server's own
thread and engine (no new model loads); skips ticks under commit
pressure via the shared worker-refusal guard.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any, Dict, List

AUTOINDEX_ENV = "OPENCODE_MEMORY_AUTOINDEX"
AUTOINDEX_INTERVAL_ENV = "OPENCODE_MEMORY_AUTOINDEX_INTERVAL"
DEFAULT_INTERVAL_SECONDS = 30.0


def autoindex_enabled(env=None) -> bool:
    """Auto-indexer switch: on unless explicitly disabled."""
    src = os.environ if env is None else env
    raw = str(src.get(AUTOINDEX_ENV, "") or "").strip().lower()
    if raw in ("", "1", "true", "yes", "on"):
        return True
    if raw in ("0", "false", "no", "off"):
        return False
    return True


def autoindex_interval(env=None) -> float:
    """Seconds between ticks (positive float, default 30)."""
    src = os.environ if env is None else env
    raw = str(src.get(AUTOINDEX_INTERVAL_ENV, "") or "").strip()
    if not raw:
        return DEFAULT_INTERVAL_SECONDS
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_INTERVAL_SECONDS
    return value if value > 0 else DEFAULT_INTERVAL_SECONDS


class SpanIndexer(threading.Thread):
    """Daemon thread: tick() indexes new/changed spans, then sleeps."""

    def __init__(self, engine, roots, interval_seconds=None):
        super().__init__(daemon=True, name="rtrre-span-indexer")
        self._engine = engine
        # Roots may be a list or a zero-arg callable (the server passes a
        # live resolver so newly registered projects are picked up).
        self._roots = roots
        self._interval = (
            float(interval_seconds)
            if interval_seconds is not None
            else autoindex_interval()
        )
        self._stop = threading.Event()

    def _candidates(self) -> List[str]:
        found: List[str] = []
        seen = set()
        dirs: List[Path] = []
        roots = self._roots() if callable(self._roots) else self._roots
        for root in roots:
            # Extra roots are project dirs themselves; PROJECT_ROOTS are
            # parents holding projects one level down. Watch both shapes.
            dirs.append(Path(root) / ".opencode" / "memory")
            try:
                if Path(root).is_dir():
                    for child in sorted(Path(root).iterdir()):
                        if child.is_dir():
                            dirs.append(child / ".opencode" / "memory")
            except OSError:
                continue
        for memdir in dirs:
            try:
                if not memdir.is_dir():
                    continue
                for path in sorted(memdir.glob("rtrre-*.dtd")):
                    key = str(path)
                    if key not in seen and path.is_file():
                        seen.add(key)
                        found.append(key)
            except OSError:
                continue
        return found

    def tick(self) -> Dict[str, Any]:
        """One bounded indexing pass over current span files."""
        return self._engine.index_files(self._candidates())

    def run(self) -> None:
        while not self._stop.wait(self._interval):
            try:
                self.tick()
            except Exception:
                continue

    def stop(self) -> None:
        self._stop.set()
        if self.is_alive():
            self.join(timeout=max(1.0, self._interval + 5.0))
