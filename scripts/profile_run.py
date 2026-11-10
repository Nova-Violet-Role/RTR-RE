#!/usr/bin/env python3
# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
"""py-spy profiler wrapper: record a command, report hot frames as data.

py-spy is a first-class RTR-RE measurement instrument (not ad-hoc): this
script records a speedscope profile of any command and prints the hottest
frames by sample weight, so hot paths are measured evidence, not guesses.

Requires the `py-spy` binary on PATH (uv tool install py-spy).

Usage:
    uv run python scripts/profile_run.py --out profile.json -- pytest test_x.py -q
    uv run python scripts/profile_run.py --pid 12345 --duration 10 --out live.json
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path


def _have_pyspy() -> str | None:
    return shutil.which("py-spy")


def record_command(argv: list[str], out: Path) -> None:
    pyspy = _have_pyspy()
    if pyspy is None:
        raise FileNotFoundError("py-spy not on PATH (uv tool install py-spy)")
    proc = subprocess.run(
        [pyspy, "record", "--format", "speedscope", "-o", str(out), "--", *argv],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0 and not out.exists():
        raise RuntimeError(f"py-spy record failed: {proc.stderr[-2000:]}")


def dump_pid(pid: int) -> str:
    """One py-spy stack dump of a live process (text passthrough)."""
    pyspy = _have_pyspy()
    if pyspy is None:
        raise FileNotFoundError("py-spy not on PATH (uv tool install py-spy)")
    proc = subprocess.run(
        [pyspy, "dump", "--pid", str(pid)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"py-spy dump failed: {proc.stderr[-2000:]}")
    return proc.stdout


def record_pid(pid: int, seconds: float, out: Path) -> None:
    pyspy = _have_pyspy()
    if pyspy is None:
        raise FileNotFoundError("py-spy not on PATH (uv tool install py-spy)")
    proc = subprocess.run(
        [
            pyspy,
            "record",
            "--format",
            "speedscope",
            "-o",
            str(out),
            "--pid",
            str(pid),
            "--duration",
            str(seconds),
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0 and not out.exists():
        raise RuntimeError(f"py-spy record failed: {proc.stderr[-2000:]}")


def hot_frames(speedscope_path: Path, top: int = 15) -> list[dict]:
    """Hottest frames by sample weight from a speedscope file."""
    data = json.loads(speedscope_path.read_text(encoding="utf-8"))
    profiles = data.get("profiles", [])
    if not profiles:
        return []
    prof = profiles[0]
    frames = prof.get("frames") or data.get("shared", {}).get("frames", [])
    samples = prof.get("samples", [])
    weights_list = prof.get("weights", [])
    weights: Counter = Counter()
    for i, stack in enumerate(samples):
        w = weights_list[i] if i < len(weights_list) else 1
        if not isinstance(stack, list):
            continue
        for idx in stack:
            if isinstance(idx, int) and 0 <= idx < len(frames):
                weights[frames[idx].get("name", "?")] += w
    total = sum(weights.values()) or 1
    ranked = weights.most_common(top)
    return [
        {"frame": name, "weight": w, "share": round(w / total, 4)} for name, w in ranked
    ]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="profile_run")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--pid", type=int, default=None)
    ap.add_argument("--duration", type=float, default=10.0)
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("command", nargs="*")
    args, rest = ap.parse_known_args(argv)
    command = list(args.command) + list(rest)
    # A literal `--` separator (if present) is not part of the command.
    command = [c for c in command if c != "--"]
    if args.pid is None and not command:
        print("REFUSED: give a command or --pid", file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory(prefix="rtrre-profile-") as td:
        speedscope = Path(td) / "profile.speedscope.json"
        if args.pid is not None:
            record_pid(args.pid, args.duration, speedscope)
        else:
            record_command(command, speedscope)
        report = {
            "hot": hot_frames(speedscope, top=args.top),
        }
    text = json.dumps(report, indent=2)
    if args.out is not None:
        args.out.write_text(text + "\n", encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
