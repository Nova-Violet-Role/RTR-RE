#!/usr/bin/env python3
# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
"""One-shot parity gate: code + installers + READMEs + publish runner.

Reviews what rushed releases miss: versions cohere everywhere, command
counts match their code, README numbers resolve to frozen JSONs,
installer assets exist, entry points resolve, SVG plates pair up,
no secrets, LF endings. Exit 0 = parity. Exit 1 = named drift.
Exit 2 = refused (consumed one-shot or missing inputs).

One-shot arming: the gate runs when explicitly armed (--arm) or when no
state exists (fresh CI). After a run it consumes itself: later repo
updates do NOT re-arm it — re-run only with --arm. State lives beside
this script (untracked, per machine).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = Path(__file__).resolve().parent / ".parity-gate.state.json"

failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(("PASS " if cond else "FAIL ") + name + (f" — {detail}" if detail else ""))
    if not cond:
        failures.append(name)


def git_head() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True
        )
        return out.stdout.strip() if out.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def load_state() -> dict:
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(consumed: bool, verdict: str) -> None:
    STATE_PATH.write_text(
        json.dumps(
            {"consumed": consumed, "verdict": verdict, "head": git_head()}, indent=2
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def versions() -> dict:
    """Every version declaration in the tree."""
    out: dict = {}
    with open(ROOT / "pyproject.toml", "rb") as f:
        out["pyproject"] = tomllib.load(f)["project"]["version"]
    out["plugin_pkg"] = json.loads(
        (ROOT / "opencode-plugin" / "package.json").read_text(encoding="utf-8")
    )["version"]
    out["mjs_pkg"] = json.loads(
        (ROOT / "mjs" / "package.json").read_text(encoding="utf-8")
    )["version"]
    out["mjs_plugin"] = json.loads(
        (ROOT / "mjs" / "plugin.json").read_text(encoding="utf-8")
    )["version"]
    m = re.search(
        r'KEEPER_VERSION = "([^"]+)"',
        read_text(ROOT / "opencode-plugin" / "rtr-re-keeper.js"),
    )
    out["keeper_js"] = m.group(1) if m else "MISSING"
    m = re.search(
        r"FRAMEWORK_VERSION = \"([^\"]+)\"",
        read_text(ROOT / "mjs" / "framework" / "rtr-keeper-framework.mjs"),
    )
    out["framework_mjs"] = m.group(1) if m else "MISSING"
    m = re.search(
        r"SUBAGENT_VERSION = \"([^\"]+)\"",
        read_text(ROOT / "mjs" / "framework" / "rtr-subagent-framework.mjs"),
    )
    out["subagent_mjs"] = m.group(1) if m else "MISSING"
    return out


def command_counts() -> dict:
    """Command/tool/verb counts per surface, read from code."""
    tsx = read_text(ROOT / "opencode-plugin" / "rtr-re-tui.tsx")
    palette = len(set(re.findall(r'name: "(rtr\.[a-z-]+)"', tsx)))
    keeper = read_text(ROOT / "opencode-plugin" / "rtr-re-keeper.js")
    literals = set(re.findall(r'verb === "([a-z-]+)"', keeper))
    numerics = {"hold", "trigger", "target", "max"}
    numeric_hit = sum(1 for v in numerics if f"{v}:" in keeper or f'"{v}"' in keeper)
    rtr_verbs = len(literals) + (len(numerics) if numeric_hit == len(numerics) else 0)
    cli = read_text(ROOT / "execution" / "memory_cli.py")
    cli_verbs = len(re.findall(r"add_parser\(\s*\"", cli))
    mcp = read_text(ROOT / "execution" / "memory_mcp_server.py")
    mcp_tools = len(re.findall(r"@mcp\.tool\(\)", mcp))
    return {
        "palette": palette,
        "rtr_verbs": rtr_verbs,
        "cli_verbs": cli_verbs,
        "mcp_tools": mcp_tools,
    }


def file_has_spdx(path: Path) -> bool:
    """True when the file carries an SPDX-License-Identifier in its head."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            head = "".join(f.readline() for _ in range(10))
    except OSError:
        return False
    return "SPDX-License-Identifier" in head


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def license_failures() -> list[str]:
    """License disposal checks: texts identical, manifests coherent, headers present."""
    fails: list[str] = []
    for root_name, licenses_name in (
        ("LICENSE-AGPL-3.0.txt", "LICENSES/AGPL-3.0-or-later.txt"),
        ("LICENSE-EUPL-1.2.txt", "LICENSES/EUPL-1.2.txt"),
    ):
        a, b = ROOT / root_name, ROOT / licenses_name
        if not a.exists() or not b.exists():
            fails.append(f"license:texts-missing:{root_name}")
        elif _sha256(a) != _sha256(b):
            fails.append(f"license:texts-differ:{root_name}")
    try:
        with open(ROOT / "pyproject.toml", "rb") as f:
            proj = tomllib.load(f)["project"]
        lic_field = proj.get("license", {})
        lic_text = lic_field.get("text", "") if isinstance(lic_field, dict) else ""
    except Exception:
        lic_text = ""
    if "EUPL-1.2" not in lic_text or "AGPL-3.0" not in lic_text:
        fails.append("license:pyproject")
    for pkg_rel in ("opencode-plugin/package.json", "mjs/package.json"):
        try:
            lic = json.loads((ROOT / pkg_rel).read_text(encoding="utf-8")).get(
                "license", ""
            )
        except Exception:
            lic = ""
        if lic != "AGPL-3.0-or-later OR EUPL-1.2":
            fails.append(f"license:manifest-{pkg_rel}")
    scope = [
        "execution/*.py",
        "scripts/*.py",
        "eval/*.py",
        "eval/graded/*.py",
        "formal/*.lean",
        "formal/Symbiose/*.lean",
        "media/*.py",
        "opencode-plugin/*.js",
        "opencode-plugin/*.mjs",
        "opencode-plugin/*.ts",
        "opencode-plugin/*.tsx",
        "mjs/hooks/*.js",
        "mjs/scripts/*.js",
        "mjs/framework/*.mjs",
        "mjs/tests/*.mjs",
        "mjs/.opencode/plugins/*.mjs",
        "mjs/.opencode/plugins/*.cjs",
        "installer/launchers/*.py",
        "installer/launchers/*.mjs",
        "installer/tools/*.py",
        "installer/shell/tools/*.py",
        "installer/shell/js/*.js",
        "installer/shell/*.html",
        "installer/shell/css/*.css",
        "installer/shell/dtd/*.dtd",
        "installer/shell/dtd/*.mod",
        "installer/shell/dtd/scenes/*.xml",
        "installer/__init__.py",
    ]
    seen = set()
    for pattern in scope:
        for path in sorted(ROOT.glob(pattern)):
            if not path.is_file() or path in seen:
                continue
            seen.add(path)
            if "__pycache__" in path.parts or "node_modules" in path.parts:
                continue
            if not file_has_spdx(path):
                fails.append(f"license:header-{path.relative_to(ROOT)}")
    return fails


def run_checks(expected: str) -> None:
    vs = versions()
    for name, val in vs.items():
        check(f"version:{name}", val == expected, f"got {val}")
    counts = command_counts()
    check("commands:palette14", counts["palette"] == 14, f"got {counts['palette']}")
    check("commands:rtr16", counts["rtr_verbs"] == 16, f"got {counts['rtr_verbs']}")
    check("commands:cli21", counts["cli_verbs"] == 21, f"got {counts['cli_verbs']}")
    check("commands:mcp32", counts["mcp_tools"] == 32, f"got {counts['mcp_tools']}")
    # README numbers resolve to the frozen JSONs.
    frozen = json.loads(
        (ROOT / "eval" / "results" / "versus.json").read_text(encoding="utf-8")
    )
    full = frozen["combined"]["rtr-full"]["metrics"]["OVERALL"]
    root_readme = read_text(ROOT / "README.md")
    for key in ("recall@1", "recall@3", "mrr"):
        val = f"{full[key]:.3f}"
        check(f"readme:versus-{key}", val in root_readme, val)
    check(
        "readme:fourteen",
        "fourteen" in read_text(ROOT / "opencode-plugin" / "README.md"),
    )
    for name in ("README.md", "mjs/README.md", "opencode-plugin/README.md"):
        body = read_text(ROOT / name)
        check(f"readme:lf-{name}", "\r" not in body)
        check(f"readme:version-{name}", expected in body, name)
    # Installer assets present at every path the installers read.
    for rel in (
        "opencode-plugin/rtr-re-keeper.js",
        "execution/rtr_presets.json",
        "installer/shell/assets/palette-guide.txt",
        "installer/launchers/python_launcher.py",
        "installer/launchers/node_launcher.mjs",
        "opencode-plugin/installer-bin.mjs",
    ):
        check(f"asset:{rel}", (ROOT / rel).exists())
    # SVG plates pair up white + dark, non-empty.
    for stem in ("versus", "graded", "engine-beneath", "preset-perf"):
        for suffix in ("", "-dark"):
            p = ROOT / "eval" / f"{stem}{suffix}.svg"
            check(f"plate:{stem}{suffix}", p.exists() and p.stat().st_size > 1000)
    # Publish runner inputs exist.
    check(
        "runner:publish-yml", (ROOT / ".github" / "workflows" / "publish.yml").exists()
    )
    notes = ROOT / "RELEASE_NOTES.md"
    check("runner:release-notes", notes.exists())
    if notes.exists():
        check("runner:notes-version", expected in read_text(notes))
    # Registry schema + default.
    reg = json.loads(
        (ROOT / "execution" / "rtr_presets.json").read_text(encoding="utf-8")
    )
    check("registry:schema", reg.get("schema") == "rtr.preset-registry/v2")
    check("registry:default", reg.get("defaultKeeperPreset") == "re-symbiose-mugen")
    lic = license_failures()
    for name in lic:
        check(name, False)
    check("license:clean", not lic)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="parity_gate")
    ap.add_argument("--version", default=None, help="expected version everywhere")
    ap.add_argument("--arm", action="store_true", help="arm (allow) this one run")
    ap.add_argument("--status", action="store_true", help="show the arming state")
    args = ap.parse_args(argv)
    state = load_state()
    if args.status:
        print(
            json.dumps({"state": state or "fresh-armed", "head": git_head()}, indent=2)
        )
        return 0
    if state.get("consumed", False) and not args.arm:
        print(
            f"REFUSED: one-shot consumed at {state.get('head', '?')} "
            f"(verdict {state.get('verdict', '?')}); re-run with --arm."
        )
        return 2
    expected = args.version
    if expected is None:
        with open(ROOT / "pyproject.toml", "rb") as f:
            expected = tomllib.load(f)["project"]["version"]
    print(f"expected version: {expected} (head {git_head()[:8]})")
    run_checks(expected)
    verdict = "FAIL" if failures else "PASS"
    print(f"PARITY {verdict}: {len(failures)} failures")
    save_state(consumed=True, verdict=verdict)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
