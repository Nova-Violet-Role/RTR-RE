# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
"""Plates for the Engine Beneath case registry — data-driven SVG in the house style.

Reads eval/results/engine-beneath-cases.json, writes eval/engine-beneath.svg +
eval/engine-beneath-dark.svg. Like plates_versus.py: edit the DATA (re-run
the case registry), then run this script. Never hand-edit the SVG.

The 3D presentation is presentation only: the scoreboard is rendered as an
extruded block, while every number behind it stays in exact 2D tables that
resolve to the JSON evidence records.

Usage:  python eval/plates_engine_beneath.py
"""

import json
from pathlib import Path

HERE = Path(__file__).parent
RESULTS = HERE / "results" / "engine-beneath-cases.json"

FONT = "-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica,Arial,sans-serif"
MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"

W = 980
LEFT = 24
RIGHT = 24
PLOT_L = 260
PLOT_R = 40

PASS_FILL = "#1a7f37"
FAIL_FILL = "#c62828"
WARN_FILL = "#b26a00"
MUTED = "#5b6472"
HERO = "#7d3c98"
GRID = "#e2e5ec"

DARK_BG = "#1a1d24"
DARK_INK = "#e2e5ec"
DARK_MUTED = "#9aa3b2"
DARK_GRID = "#2e3440"
DARK_HERO = "#bb86fc"


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render(data, dark):
    bg = DARK_BG if dark else "#ffffff"
    ink = DARK_INK if dark else "#1a1d24"
    muted = DARK_MUTED if dark else MUTED
    grid = DARK_GRID if dark else GRID
    hero = DARK_HERO if dark else HERO

    summary = data["summary"]
    cases = data["cases"]
    n = summary["cases"]
    passed = summary["passed"]
    failed = summary["failed"]
    verdict = summary["pass"]
    run_at = data["run_at"]

    y = 0
    parts = []

    def text(x, yy, s, size=13, fill=None, anchor="start", mono=False, bold=False):
        f = MONO if mono else FONT
        w = " font-weight='bold'" if bold else ""
        parts.append(
            f"<text x='{x}' y='{yy}' font-family='{f}' font-size='{size}'"
            f" fill='{fill or ink}' text-anchor='{anchor}'{w}>{esc(s)}</text>"
        )

    # header
    y += 44
    text(24, y, "Engine Beneath — case scoreboard (RE edition)", size=21, bold=True)
    y += 24
    text(
        24,
        y,
        f"{n} cases · {passed} passed · {failed} failed · run {run_at}",
        size=13,
        fill=muted,
        mono=True,
    )
    y += 14
    parts.append(f"<line x1='24' y1='{y}' x2='{W - 24}' y2='{y}' stroke='{grid}'/>")
    y += 8

    # 3D presentation: extruded scoreboard block
    # The block is presentation only — the exact numbers are in the 2D tables below.
    block_w = 320
    block_h = 56
    block_x = W - 24 - block_w
    block_y = y
    frac = passed / n if n else 0.0
    fill_w = max(4, int(block_w * frac))
    # back face (extrusion)
    parts.append(
        f"<rect x='{block_x + 6}' y='{block_y + 6}' width='{block_w}' height='{block_h}'"
        f" fill='{grid}'/>"
    )
    # side face
    parts.append(
        f"<polygon points='{block_x + block_w},{block_y + 6} {block_x + block_w + 6},{block_y + 12} "
        f"{block_x + block_w + 6},{block_y + block_h + 12} {block_x + block_w},{block_y + block_h}'"
        f" fill='{grid}'/>"
    )
    # front face
    parts.append(
        f"<rect x='{block_x}' y='{block_y}' width='{block_w}' height='{block_h}'"
        f" fill='{bg}' stroke='{grid}'/>"
    )
    # fill bar
    parts.append(
        f"<rect x='{block_x}' y='{block_y}' width='{fill_w}' height='{block_h}'"
        f" fill='{PASS_FILL if verdict else FAIL_FILL}'/>"
    )
    text(
        block_x + 12,
        block_y + 24,
        f"{passed}/{n} passed",
        size=15,
        bold=True,
        fill="#ffffff",
    )
    text(
        block_x + 12,
        block_y + 44,
        "VERDICT " + ("PASS" if verdict else "FAIL"),
        size=12,
        mono=True,
        fill="#ffffff",
    )
    y += block_h + 24

    # case rows: one row per case with its required checks as 2D bars
    text(24, y, "Cases — required checks (1.0 = holds)", size=15, bold=True)
    y += 20
    text(24, y, "case", size=11, fill=muted, mono=True)
    text(PLOT_L, y, "check", size=11, fill=muted, mono=True)
    y += 6

    for case in cases:
        name = case["case"]
        cverdict = case["verdict"]
        checks = case["checks"]
        required = case["required"]
        y += 22
        # case label
        text(24, y + 11, name, size=11, fill=muted, mono=True)
        # verdict chip
        chip_fill = PASS_FILL if cverdict == "pass" else FAIL_FILL
        parts.append(
            f"<rect x='{PLOT_L - 78}' y='{y}' width='56' height='16' rx='3' fill='{chip_fill}'/>"
        )
        text(
            PLOT_L - 50,
            y + 12,
            cverdict.upper(),
            size=10,
            mono=True,
            fill="#ffffff",
            anchor="middle",
        )
        # required check bars
        if required:
            bar_w = (W - PLOT_L - PLOT_R - 60) / len(required)
            for i, chk in enumerate(required):
                v = checks.get(chk, 0.0)
                bx = PLOT_L + i * bar_w
                parts.append(
                    f"<rect x='{bx}' y='{y + 2}' width='{bar_w - 6}' height='12'"
                    f" fill='{grid}'/>"
                )
                parts.append(
                    f"<rect x='{bx}' y='{y + 2}' width='{max(2, (bar_w - 6) * v)}' height='12'"
                    f" fill='{PASS_FILL if v >= 1.0 else FAIL_FILL}'/>"
                )
                text(bx + 2, y + 22, chk, size=9, fill=muted, mono=True)
        else:
            text(PLOT_L, y + 11, "(no required checks)", size=10, fill=muted)

    y += 34
    parts.append(f"<line x1='24' y1='{y}' x2='{W - 24}' y2='{y}' stroke='{grid}'/>")
    y += 22

    # exact evidentiary table: extreme-protection evidence
    text(24, y, "Extreme-protection evidence (exact, from JSON)", size=15, bold=True)
    y += 22
    extreme = next(
        (
            c
            for c in cases
            if c["case"] == "production-scale-extreme-protection-warning"
        ),
        None,
    )
    if extreme and extreme.get("evidence"):
        ev = extreme["evidence"]
        rows = [
            ("messages", ev.get("messages")),
            ("keep", ev.get("keep")),
            ("evict", ev.get("evict")),
            ("total_tokens", ev.get("total_tokens")),
            ("keep_tokens", ev.get("keep_tokens")),
            ("plan_ms", ev.get("plan_ms")),
            ("todowrite_index", ev.get("todowrite_index")),
            ("todowrite_retained", ev.get("todowrite_retained")),
        ]
        col_x = PLOT_L
        text(24, y, "metric", size=11, fill=muted, mono=True)
        text(col_x, y, "value", size=11, fill=muted, mono=True)
        y += 6
        for label, value in rows:
            y += 18
            text(24, y, label, size=11, mono=True)
            text(
                col_x,
                y,
                str(value),
                size=11,
                mono=True,
                fill=hero if label == "todowrite_retained" else None,
            )
        y += 24

    # exact evidentiary table: preset axis
    text(24, y, "Preset axis (all six resolve)", size=15, bold=True)
    y += 22
    preset_case = next((c for c in cases if c["case"] == "preset-axis-all-six"), None)
    if preset_case and preset_case.get("evidence", {}).get("presets"):
        presets = preset_case["evidence"]["presets"]
        cols = ["preset", "trigger", "target", "maxKeep", "compress", "keep_count"]
        col_x = [24, PLOT_L, PLOT_L + 90, PLOT_L + 180, PLOT_L + 270, PLOT_L + 360]
        for j, cname in enumerate(cols):
            text(col_x[j], y, cname, size=11, fill=muted, mono=True)
        y += 6
        for name, meta in presets.items():
            y += 18
            text(24, y, name, size=11, mono=True)
            text(col_x[1], y, str(meta.get("trigger")), size=11, mono=True)
            text(col_x[2], y, str(meta.get("target")), size=11, mono=True)
            text(col_x[3], y, str(meta.get("maxKeep")), size=11, mono=True)
            text(col_x[4], y, str(meta.get("plan_compress")), size=11, mono=True)
            text(col_x[5], y, str(meta.get("plan_keep_count")), size=11, mono=True)
        y += 24

    y += 8
    parts.append(f"<line x1='24' y1='{y}' x2='{W - 24}' y2='{y}' stroke='{grid}'/>")
    y += 22
    text(
        24,
        y,
        "method: eval/engine_beneath_cases.py · evidence: eval/results/engine-beneath-cases.json",
        size=11,
        fill=muted,
    )
    y += 18
    text(24, y, "Nova-Violet Role · Reality is the judge.", size=11, fill=muted)
    height = y + 24

    body = "\n".join(parts)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<!-- SPDX-License-Identifier: AGPL-3.0-or-later OR EUPL-1.2 -->\n"
        "<!-- Copyright 2026 Saimonokuma. GENERATED by eval/plates_engine_beneath.py"
        " from eval/results/engine-beneath-cases.json; re-run the case registry, then this script. -->\n"
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{W}' height='{height}'"
        f" viewBox='0 0 {W} {height}' font-family='{FONT}'>\n"
        f"<rect width='{W}' height='{height}' fill='{bg}'/>\n"
        f"{body}\n</svg>\n"
    )


def main():
    data = json.loads(RESULTS.read_text(encoding="utf-8"))
    (HERE / "engine-beneath.svg").write_text(
        render(data, dark=False), encoding="utf-8", newline="\n"
    )
    (HERE / "engine-beneath-dark.svg").write_text(
        render(data, dark=True), encoding="utf-8", newline="\n"
    )
    print("wrote eval/engine-beneath.svg + eval/engine-beneath-dark.svg")


if __name__ == "__main__":
    main()
