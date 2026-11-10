#!/usr/bin/env python3
# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
"""Pre-publish content checks (TODO-35, secret-free verification).

Builds the wheel plus both npm packs and asserts, without publishing
anything: manifest versions cohere, entry points resolve, expected
files are present, tests are absent from the wheel, and no text file
carries secret-shaped content. Exit 0 = ship-shape. Exit 1 = named
failure. Exit 2 = build tooling missing.

Run:  uv run python scripts/verify_release.py [--version 1.1.1]
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SECRET_PATTERNS = [
    # Word patterns require quoted values: bare `token: str` (a function
    # signature) must never trip the alarm, while pasted credentials
    # (`"api_key": "sk-..."`, `token = "..."`) always do. Keys may be
    # quoted (JSON) or bare (code/config).
    re.compile(r"(?i)[\"']?\bapi[_-]?key\b[\"']?\s*[:=]\s*[\"'][^\"']{4,}[\"']"),
    re.compile(r"(?i)[\"']?\bsecret\b[\"']?\s*[:=]\s*[\"'][^\"']{4,}[\"']"),
    re.compile(r"(?i)[\"']?\btoken\b[\"']?\s*[:=]\s*[\"'][^\"']{4,}[\"']"),
    re.compile(r"(?i)[\"']?\bpasswd\b[\"']?\s*[:=]\s*[\"'][^\"']{4,}[\"']"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
]

failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(("PASS " if cond else "FAIL ") + name + (f" — {detail}" if detail else ""))
    if not cond:
        failures.append(name)


def run(argv: list[str], cwd: Path) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            argv, cwd=cwd, capture_output=True, text=True, timeout=900
        )
    except FileNotFoundError:
        return subprocess.CompletedProcess(argv, 127, "", f"{argv[0]}: not found")


def scan_text_for_secrets(text: str, label: str) -> None:
    for rx in SECRET_PATTERNS:
        m = rx.search(text)
        if m:
            check(f"secret-free:{label}", False, f"matches {rx.pattern[:24]}...")
            return
    check(f"secret-free:{label}", True)


def _pack_argv(out_dir: Path) -> list[str] | None:
    """npm pack argv, resolving npm.cmd on Windows (needs cmd /c)."""
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    if npm is None:
        scoop = Path.home() / "scoop" / "apps" / "nodejs" / "current" / "npm.cmd"
        npm = str(scoop) if scoop.exists() else None
    if npm is None:
        return None
    base = ["cmd", "/c", npm] if npm.lower().endswith(".cmd") else [npm]
    return base + ["pack", "--pack-destination", str(out_dir)]


def main() -> int:
    ap = argparse.ArgumentParser(prog="verify_release")
    ap.add_argument("--version", default=None, help="expected version everywhere")
    args = ap.parse_args()

    expected = args.version
    if expected is None:
        import tomllib

        with open(ROOT / "pyproject.toml", "rb") as f:
            expected = tomllib.load(f)["project"]["version"]
    print(f"expected version: {expected}")

    with tempfile.TemporaryDirectory(prefix="rtrre-verify-") as td:
        tmp = Path(td)
        # --- wheel ---
        uv = shutil.which("uv")
        if uv is None:
            print("REFUSED: uv not on PATH")
            return 2
        proc = run(
            [uv, "build", "--wheel", "--out-dir", str(tmp)],
            ROOT,
        )
        if proc.returncode != 0:
            print(proc.stderr[-2000:])
            print("REFUSED: wheel build failed")
            return 2
        wheels = sorted(tmp.glob("rtr_role_type_retrieval-*.whl"))
        check("wheel-built", len(wheels) == 1, f"found {len(wheels)}")
        if not wheels:
            return 1
        wheel = wheels[0]
        check("wheel-version", f"-{expected}-" in wheel.name, wheel.name)
        with zipfile.ZipFile(wheel) as zf:
            names = zf.namelist()
            check("wheel-no-tests", not any("/test_" in n for n in names))
            check(
                "wheel-entry-points",
                any(n.endswith("entry_points.txt") for n in names),
            )
            meta = [n for n in names if n.endswith("METADATA")]
            check("wheel-metadata", len(meta) == 1)
            if meta:
                body = zf.read(meta[0]).decode("utf-8", errors="replace")
                check("wheel-metadata-version", f"Version: {expected}" in body)
                scan_text_for_secrets(body, "wheel-METADATA")
            for n in names:
                if n.endswith((".py", ".json", ".md", ".txt")):
                    try:
                        scan_text_for_secrets(
                            zf.read(n).decode("utf-8", errors="replace"),
                            f"wheel:{Path(n).name}",
                        )
                    except Exception as e:  # noqa: BLE001
                        check(f"wheel-read:{n}", False, str(e))
        # --- npm plugin pack ---
        plugdir = ROOT / "opencode-plugin"
        pack_argv = _pack_argv(tmp)
        if pack_argv is None:
            print("REFUSED: npm unavailable on PATH")
            return 2
        proc = run(pack_argv, plugdir)
        if proc.returncode != 0:
            print(proc.stderr[-2000:])
            print("REFUSED: npm pack failed")
            return 2
        plugtars = sorted(tmp.glob("rtr-re-opencode-plugin-*.tgz"))
        check("plugin-pack-built", len(plugtars) == 1)
        if plugtars:
            with tarfile.open(plugtars[0], "r:gz") as tf:
                names = tf.getnames()
                check(
                    "plugin-has-keeper",
                    any(n.endswith("rtr-re-keeper.js") for n in names),
                )
                check(
                    "plugin-has-installer",
                    any("installer/launchers" in n for n in names),
                )
                pkg = [n for n in names if n.endswith("package/package.json")]
                check("plugin-manifest", len(pkg) == 1)
                if pkg:
                    body = tf.extractfile(pkg[0]).read().decode("utf-8")
                    check(
                        "plugin-version",
                        json.loads(body)["version"] == expected,
                    )
                    scan_text_for_secrets(body, "plugin-package.json")
        # --- npm mjs pack ---
        mjsdir = ROOT / "mjs"
        pack_argv = _pack_argv(tmp)
        if pack_argv is None:
            print("REFUSED: npm unavailable on PATH")
            return 2
        proc = run(pack_argv, mjsdir)
        mjs_name = "saimonokuma-rtr-re-mjs"
        mjstars = sorted(tmp.glob(f"{mjs_name}-*.tgz"))
        check("mjs-pack-built", len(mjstars) == 1)
        if mjstars:
            with tarfile.open(mjstars[0], "r:gz") as tf:
                names = tf.getnames()
                check(
                    "mjs-has-plugin",
                    any(n.endswith("rtr.mjs") for n in names),
                )
                check(
                    "mjs-has-manifest",
                    any(n.endswith("plugin.json") for n in names),
                )
                pkg = [n for n in names if n.endswith("package/package.json")]
                if pkg:
                    body = tf.extractfile(pkg[0]).read().decode("utf-8")
                    check(
                        "mjs-version",
                        json.loads(body)["version"] == expected,
                    )
    print(f"VERIFY {'FAIL' if failures else 'PASS'}: {len(failures)} failures")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
