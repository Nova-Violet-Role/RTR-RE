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
AUTOINDEX_MAX_FILES_ENV = "OPENCODE_MEMORY_AUTOINDEX_MAX_FILES"
DEFAULT_INTERVAL_SECONDS = 30.0
DEFAULT_MAX_FILES_PER_TICK = 200


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


def autoindex_max_files(env=None) -> int:
    """Max span files per tick (positive int, default 200)."""
    src = os.environ if env is None else env
    raw = str(src.get(AUTOINDEX_MAX_FILES_ENV, "") or "").strip()
    if not raw:
        return DEFAULT_MAX_FILES_PER_TICK
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_MAX_FILES_PER_TICK
    return value if value > 0 else DEFAULT_MAX_FILES_PER_TICK


class SpanIndexer(threading.Thread):
    """Daemon thread: tick() indexes new/changed spans, then sleeps."""

    def __init__(self, engine, roots, interval_seconds=None, max_files=None):
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
        self._max_files = (
            int(max_files) if max_files is not None else autoindex_max_files()
        )
        if self._max_files <= 0:
            self._max_files = DEFAULT_MAX_FILES_PER_TICK
        self._stop = threading.Event()
        # mtime watermark: spans are keeper-written with fresh mtimes, so
        # anything older than the newest file already seen cannot be new.
        # This prefilter keeps a broken registry from re-embedding the
        # whole memory dir every 30s; the registry stays authoritative
        # for what actually gets hashed. Every 20th tick scans fully so
        # a preserved-mtime copy can never hide forever. The taken map
        # (path -> mtime taken) keeps capped ticks converging on
        # same-mtime bursts the watermark alone would starve.
        self._watermark = 0.0
        self._taken: Dict[str, float] = {}
        self._ticks = 0

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
        full = self._ticks % 20 == 0
        # Collect (mtime, key) first, then take oldest-first up to the cap.
        # Strictly-older-than-watermark skips; same-mtime files re-list and
        # the taken map dedups the already-taken, so capped bursts converge.
        # The watermark advances only over TAKEN files.
        staged: List[tuple] = []
        for memdir in dirs:
            try:
                if not memdir.is_dir():
                    continue
                for path in sorted(memdir.glob("rtrre-*.dtd")):
                    key = str(path)
                    if key not in seen and path.is_file():
                        try:
                            mtime = path.stat().st_mtime
                        except OSError:
                            mtime = 0.0
                        if not full and mtime > 0 and mtime < self._watermark:
                            continue
                        if key in self._taken and self._taken[key] >= mtime > 0:
                            continue
                        seen.add(key)
                        staged.append((mtime, key))
            except OSError:
                continue
        staged.sort(key=lambda t: (t[0], t[1]))
        tick_max = self._watermark
        for mtime, key in staged[: self._max_files]:
            tick_max = max(tick_max, mtime)
            self._taken[key] = mtime
            found.append(key)
        self._watermark = tick_max
        self._ticks += 1
        return found

    def _opencode_dirs(self) -> List[Path]:
        dirs: List[Path] = []
        roots = self._roots() if callable(self._roots) else self._roots
        for root in roots:
            dirs.append(Path(root) / ".opencode")
            try:
                if Path(root).is_dir():
                    for child in sorted(Path(root).iterdir()):
                        if child.is_dir():
                            dirs.append(child / ".opencode")
            except OSError:
                continue
        return dirs

    def _serve_repair_requests(self) -> None:
        """Execute file-channel repair requests (TODO-13 bus).

        The keeper (palette//rtr) writes .opencode/rtr-re-repair.requested.json;
        the tick runs repair_registry + janitor, writes
        .opencode/rtr-re-repair.report.json, then deletes the request.
        Refusal-free: failures are reported, never raised into the tick.
        """
        import json
        import time

        for opencode in self._opencode_dirs():
            req = opencode / "rtr-re-repair.requested.json"
            try:
                if not req.is_file():
                    continue
            except OSError:
                continue
            report: Dict[str, Any] = {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "recall": "Symbiotising in process — accessing the digital world.",
            }
            try:
                rep = self._engine.repair_registry()
                jan = self._engine.janitor(dry_run=False)
                report.update(
                    {
                        "status": "done",
                        "repaired": rep.get("repaired", 0),
                        "registry_total": rep.get("total", 0),
                        "freed": jan.get("freed", 0),
                        "pruned_roots": jan.get("pruned_roots", []),
                    }
                )
            except Exception as e:  # noqa: BLE001
                report.update({"status": "error", "error": f"{type(e).__name__}: {e}"})
            try:
                (opencode / "rtr-re-repair.report.json").write_text(
                    json.dumps(report, indent=2) + "\n", encoding="utf-8"
                )
            except OSError:
                continue
            try:
                req.unlink()
            except OSError:
                pass

    def tick(self) -> Dict[str, Any]:
        """One bounded indexing pass over current span files."""
        self._serve_repair_requests()
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
