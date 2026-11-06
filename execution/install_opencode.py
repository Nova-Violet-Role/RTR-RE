# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
"""Install the native RTR-RE Keeper plugin into an OpenCode config dir.

The published architecture is self-contained: memory MCP (this package)
plus the first-party Keeper plugin. No ACP plugin, no acp.jsonc. This
installer copies the keeper plus its preset registry and prints the config
snippet to merge; it never rewrites an existing opencode config.
"""

import argparse
import hashlib
import sys
from pathlib import Path
from typing import Any, Dict, Sequence

KEEPER_NAME = "rtr-re-keeper.js"
REGISTRY_NAME = "rtr_presets.json"


def keeper_asset_path() -> Path:
    """Bundled asset (wheel) first, repo layout (lab/standalone) second."""
    here = Path(__file__).resolve().parent
    candidates = [
        here / "assets" / KEEPER_NAME,
        here.parent / "opencode-plugin" / KEEPER_NAME,
    ]
    for cand in candidates:
        if cand.exists():
            return cand
    raise FileNotFoundError(
        "keeper asset not found; looked in " + ", ".join(str(c) for c in candidates)
    )


def config_snippet(mcp_command: str = "rtr-re-mcp") -> str:
    return (
        "{\n"
        '  "plugin": ["./plugin/rtr-re-keeper.js"],\n'
        '  "mcp": {\n'
        '    "memory": {\n'
        '      "type": "local",\n'
        f'      "command": ["{mcp_command}"],\n'
        '      "enabled": true,\n'
        '      "environment": {\n'
        '        "PYTHONIOENCODING": "utf-8"\n'
        "      }\n"
        "    }\n"
        "  }\n"
        "}\n"
    )


def registry_asset_path() -> Path:
    """Preset registry: repo layout (lab/standalone) first, wheel asset second."""
    here = Path(__file__).resolve().parent
    candidates = [
        here / REGISTRY_NAME,
        here / "assets" / REGISTRY_NAME,
    ]
    for cand in candidates:
        if cand.exists():
            return cand
    raise FileNotFoundError(
        "preset registry not found; looked in " + ", ".join(str(c) for c in candidates)
    )


def install(config_dir: Path, force: bool = False) -> Dict[str, Any]:
    asset = keeper_asset_path()
    data = asset.read_bytes()
    dest = Path(config_dir) / "plugin" / KEEPER_NAME
    if dest.exists() and dest.read_bytes() != data and not force:
        raise FileExistsError(
            f"{dest} exists and differs from the bundled keeper; "
            "re-run with --force to overwrite"
        )
    reg_asset = registry_asset_path()
    reg_data = reg_asset.read_bytes()
    reg_dest = Path(config_dir) / "plugin" / "assets" / REGISTRY_NAME
    if reg_dest.exists() and reg_dest.read_bytes() != reg_data and not force:
        raise FileExistsError(
            f"{reg_dest} exists and differs from the bundled registry; "
            "re-run with --force to overwrite"
        )
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    reg_dest.parent.mkdir(parents=True, exist_ok=True)
    reg_dest.write_bytes(reg_data)
    return {
        "plugin": str(dest),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "registry": str(reg_dest),
    }


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="rtr-re-install-opencode",
        description="Install the RTR-RE:Symbiose Keeper plugin for OpenCode.",
    )
    ap.add_argument(
        "--config-dir",
        type=Path,
        default=Path.home() / ".config" / "opencode",
        help="OpenCode config directory (default: ~/.config/opencode)",
    )
    ap.add_argument("--force", action="store_true", help="overwrite a differing keeper")
    ap.add_argument("--mcp-command", default="rtr-re-mcp")
    args = ap.parse_args(list(argv) if argv is not None else None)
    try:
        result = install(args.config_dir, force=args.force)
    except FileExistsError as e:
        print(f"REFUSED: {e}")
        return 2
    except FileNotFoundError as e:
        print(f"REFUSED: {e}")
        return 2
    print(f"Keeper installed: {result['plugin']}")
    print(f"Bytes: {result['bytes']}  sha256: {result['sha256']}")
    print("Merge into your opencode.jsonc:")
    print(config_snippet(args.mcp_command))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
