# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
"""Graded telemetry plates: per-query depth made visible.

Reads eval/results/graded.json (claim basis) and, when present,
eval/results/graded-lane-on.json (STRUCT lane comparison). Writes:
  eval/results/graded-plates.md  Lightpaper tables (combined, per-query
                                  deltas, unjudged accounting)
  eval/graded.svg, eval/graded-dark.svg  per-query nDCG@10 bars

Doctor invariants run first and refuse by name: dataset must be gold-v2,
system sets must agree across corpora, and the combined table must
re-derive from the per-query rows. Numbers are never hand-copied.

Usage:  python eval/plates_graded.py
"""

import json
import statistics
from pathlib import Path

HERE = Path(__file__).parent
RESULTS = HERE / "results"
FONT = "-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica,Arial,sans-serif"
MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"
SERIES_FILL = {
    "rag-dense": "#b0b7c3",
    "rag-dense-base": "#8a93a3",
    "rag-hybrid": "#5b6472",
    "rag-hybrid-base": "#3f4653",
    "rtr-arctic": "#2874a6",
    "rtr-bge": "#1a7f37",
    "rtr-full": "#7d3c98",
}
W = 980
LEFT = 150
RIGHT = 70
BAR_H = 11
BAR_GAP = 3


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def doctor(data):
    if not str(data.get("dataset", "")).startswith("gold-v2"):
        raise SystemExit(f"REFUSED: dataset {data.get('dataset')!r} is not gold-v2")
    systems = list(data["combined"].keys())
    rows = {s: [] for s in systems}
    for cname, corp in data["corpora"].items():
        if set(corp["systems"]) != set(systems):
            raise SystemExit(f"REFUSED: system set drift in corpus {cname}")
        for s in systems:
            rows[s].extend(corp["systems"][s]["rows"])
    for s in systems:
        mean = statistics.fmean(r["scores"]["ndcg@10"] for r in rows[s])
        claimed = data["combined"][s]["ndcg@10"]
        if abs(mean - claimed) > 5e-5:
            raise SystemExit(
                f"REFUSED: combined nDCG@10 for {s} claims {claimed}, rows give {mean:.4f}"
            )
        unj = sum(r["scores"]["unjudged_returned"] for r in rows[s])
        if unj != data["combined"][s]["unjudged_returned"]:
            raise SystemExit(f"REFUSED: unjudged accounting drift for {s}")
    return systems, rows


def per_query(rows, systems):
    by_q = {}
    for s in systems:
        for r in rows[s]:
            by_q.setdefault(r["query_id"], {"corpus": r["corpus"]})[s] = r["scores"][
                "ndcg@10"
            ]
    return by_q


def write_md(path, data, systems, by_q, lane_on):
    lines = [
        "<!-- SPDX-FileCopyrightText: Nova-Violet Role ORG -->",
        "<!-- SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later -->",
        "# Graded telemetry plates (generated, do not edit)",
        "",
        f"Dataset {data['dataset']} | depth {data['depth']} | "
        f"queries {data['queries']} | judgments {data['judgments']}",
        "",
        "## Combined",
        "",
        "| System | nDCG@3 | nDCG@10 | nDCG@20 | ERR@10 | MAP | unjudged |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for s in systems:
        m = data["combined"][s]
        lines.append(
            f"| {s} | {m['ndcg@3']:.4f} | {m['ndcg@10']:.4f} | {m['ndcg@20']:.4f} "
            f"| {m['err@10']:.4f} | {m['ap']:.4f} | {m['unjudged_returned']} |"
        )
    lines += [
        "",
        "## Per-query nDCG@10 deltas (rtr-full minus rag-dense-base, worst first)",
        "",
        "| Query | Corpus | dense-base | rtr-full | delta | best |"
        + (" lane-on full |" if lane_on else ""),
        "|---|---|---:|---:|---:|---|" + ("---:|" if lane_on else ""),
    ]
    lane_rows = {}
    if lane_on:
        _, lrows = doctor(lane_on)
        lane_rows = {r["query_id"]: r["scores"]["ndcg@10"] for r in lrows["rtr-full"]}
    items = sorted(
        by_q.items(),
        key=lambda kv: kv[1].get("rtr-full", 0.0) - kv[1].get("rag-dense-base", 0.0),
    )
    for qid, vals in items:
        d = vals.get("rag-dense-base", 0.0)
        f = vals.get("rtr-full", 0.0)
        best = max(systems, key=lambda s: vals.get(s, 0.0))
        row = (
            f"| {qid} | {vals['corpus']} | {d:.4f} | {f:.4f} | {f - d:+.4f} | {best} |"
        )
        if lane_on:
            row += f" {lane_rows.get(qid, 0.0):.4f} |"
        lines.append(row)
    lines += [
        "",
        "Formulas and supervision: eval/graded/PROTOCOL.md. "
        "Claim basis: artifacts/geometry/2026-10-27-final-freeze.md.",
        "",
    ]
    path.write_bytes("\n".join(lines).encode("utf-8"))


def render(data, systems, by_q, dark):
    bg = "#1a1d24" if dark else "#ffffff"
    ink = "#e2e5ec" if dark else "#1a1d24"
    muted = "#9aa3b2" if dark else "#5b6472"
    grid = "#2e3440" if dark else "#e2e5ec"
    parts = []
    y = 44
    scale = (W - LEFT - RIGHT) / 1.08

    def text(x, yy, s, size=12, fill=None, mono=False, bold=False):
        f = MONO if mono else FONT
        w = " font-weight='bold'" if bold else ""
        parts.append(
            f"<text x='{x}' y='{yy}' font-family='{f}' font-size='{size}'"
            f" fill='{fill or ink}'{w}>{esc(s)}</text>"
        )

    text(24, y, "Graded nDCG@10 by query (gold-v2)", size=20, bold=True)
    y += 22
    text(
        24,
        y,
        f"{data['dataset']} · {data['queries']} queries · {data['judgments']} judgments",
        size=12,
        fill=muted,
        mono=True,
    )
    y += 12
    lx = 24
    for s in systems:
        fill = SERIES_FILL.get(s, "#888888")
        parts.append(f"<rect x='{lx}' y='{y}' width='11' height='11' fill='{fill}'/>")
        text(lx + 15, y + 10, s, size=11, fill=muted, mono=True)
        lx += 15 + len(s) * 7 + 18
    y += 30
    order = sorted(by_q, key=lambda q: (by_q[q]["corpus"], q))
    for qid in order:
        vals = by_q[qid]
        text(24, y + 10, f"{qid}", size=11, bold=True, mono=True)
        text(24, y + 23, vals["corpus"], size=9, fill=muted, mono=True)
        best = max(vals.get(s, 0.0) for s in systems)
        for i, s in enumerate(systems):
            v = vals.get(s, 0.0)
            by = y + i * (BAR_H + BAR_GAP)
            bw = max(2, v * scale)
            parts.append(
                f"<rect x='{LEFT}' y='{by}' width='{bw:.1f}' height='{BAR_H}'"
                f" fill='{SERIES_FILL.get(s, '#888888')}'/>"
            )
            text(
                LEFT + bw + 7,
                by + 10,
                f"{v:.3f}",
                size=10,
                fill=muted,
                mono=True,
                bold=abs(v - best) < 1e-9 and v > 0,
            )
        y += len(systems) * (BAR_H + BAR_GAP) + 16
        parts.append(
            f"<line x1='24' y1='{y - 8}' x2='{W - 24}' y2='{y - 8}' stroke='{grid}'/>"
        )
    text(
        24,
        y + 8,
        "generated by eval/plates_graded.py from eval/results/graded.json · Nova-Violet Role",
        size=11,
        fill=muted,
    )
    height = y + 30
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<!-- SPDX-License-Identifier: AGPL-3.0-or-later OR EUPL-1.2 -->\n"
        "<!-- GENERATED by eval/plates_graded.py; re-run the bench, then this script. -->\n"
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{W}' height='{height}'"
        f" viewBox='0 0 {W} {height}' font-family='{FONT}'>\n"
        f"<rect width='{W}' height='{height}' fill='{bg}'/>\n"
        + "\n".join(parts)
        + "\n</svg>\n"
    )


def main():
    data = json.loads((RESULTS / "graded.json").read_text(encoding="utf-8"))
    systems, rows = doctor(data)
    by_q = per_query(rows, systems)
    lane_path = RESULTS / "graded-lane-on.json"
    lane_on = (
        json.loads(lane_path.read_text(encoding="utf-8"))
        if lane_path.exists()
        else None
    )
    write_md(RESULTS / "graded-plates.md", data, systems, by_q, lane_on)
    (HERE / "graded.svg").write_text(
        render(data, systems, by_q, dark=False), encoding="utf-8", newline="\n"
    )
    (HERE / "graded-dark.svg").write_text(
        render(data, systems, by_q, dark=True), encoding="utf-8", newline="\n"
    )
    print(
        "wrote eval/results/graded-plates.md + eval/graded.svg + eval/graded-dark.svg"
    )


if __name__ == "__main__":
    main()
