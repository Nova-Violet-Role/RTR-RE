"""Freeze the 0.5.0 architecture baseline (TODO-29).

Reads the three immutable source artifacts and writes:
  - eval/results/baseline-0.5.0.json  (machine-readable, frozen)
  - eval/results/baseline-0.5.0.md    (human-readable)

Every score below is a copy of a measured run, never a claim. The sha256
manifest pins the exact source artifacts so a later re-run can prove the
baseline is reproducible or detect drift.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict

RESULTS = Path(__file__).parent / "results"
SOURCES = {
    "versus": RESULTS / "versus.json",
    "engine_beneath": RESULTS / "engine-beneath-cases.json",
    "parity_matrix": RESULTS / "parity-matrix-1.0.0.md",
}
OUT_JSON = RESULTS / "baseline-0.5.0.json"
OUT_MD = RESULTS / "baseline-0.5.0.md"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def overall_table(versus: Dict[str, Any]) -> Dict[str, Any]:
    corpora: Dict[str, Any] = {}
    for corpus, data in sorted(versus["corpora"].items()):
        systems: Dict[str, Any] = {}
        for sys_name, sdata in sorted(data["systems"].items()):
            o = sdata["metrics"]["OVERALL"]
            systems[sys_name] = {
                "n": o["n"],
                "recall@1": o["recall@1"],
                "recall@3": o["recall@3"],
                "mrr": o["mrr"],
                "p50_ms": o.get("p50_ms"),
            }
        corpora[corpus] = {
            "files": data["files"],
            "queries": data["queries"],
            "systems": systems,
        }
    return corpora


def dtd_taxons(versus: Dict[str, Any]) -> Dict[str, Any]:
    dtd = versus["corpora"].get("dtd-family", {})
    rtr_full = dtd.get("systems", {}).get("rtr-full", {})
    return rtr_full.get("metrics", {})


def main() -> int:
    manifest: Dict[str, str] = {}
    for name, path in SOURCES.items():
        if not path.exists():
            print(f"REFUSED: missing source {path}")
            return 2
        manifest[name] = sha256(path)

    versus = load_json(SOURCES["versus"])
    eb = load_json(SOURCES["engine_beneath"])

    baseline: Dict[str, Any] = {
        "schema": "rtr-re.baseline/0.5.0/v1",
        "release_arc": "1.0.0",
        "frozen_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "source_manifest": manifest,
        "retrieval": {
            "seed": versus.get("seed"),
            "tool": versus.get("tool"),
            "corpora": overall_table(versus),
            "dtd_family_rtr_full_taxons": dtd_taxons(versus),
        },
        "engine_beneath": {
            "summary": eb["summary"],
            "cases": {
                c["case"]: {
                    "verdict": c["verdict"],
                    "checks": c["checks"],
                }
                for c in eb["cases"]
            },
        },
        "parity_matrix": "eval/results/parity-matrix-1.0.0.md",
    }

    OUT_JSON.write_text(
        json.dumps(baseline, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    lines = [
        "# RTR-RE baseline — 0.5.0 (frozen, TODO-29)",
        "",
        f"- Frozen at: {baseline['frozen_at']}",
        f"- Release arc: {baseline['release_arc']}",
        f"- Source manifest (sha256):",
    ]
    for name, digest in manifest.items():
        lines.append(f"  - `{name}`: `{digest}`")
    lines += ["", "## Retrieval — overall per corpus × system", ""]
    lines.append("| Corpus | System | n | R@1 | R@3 | MRR | p50 ms |")
    lines.append("|---|---|---|---|---|---|---|")
    for corpus, cdata in baseline["retrieval"]["corpora"].items():
        for sys_name, m in cdata["systems"].items():
            lines.append(
                f"| {corpus} | {sys_name} | {m['n']} | {m['recall@1']} "
                f"| {m['recall@3']} | {m['mrr']} | {m['p50_ms']} |"
            )
    lines += ["", "## DTD family — rtr-full taxon detail", ""]
    lines.append("| Taxon | n | R@1 | R@3 | MRR |")
    lines.append("|---|---|---|---|---|")
    for taxon, m in baseline["retrieval"]["dtd_family_rtr_full_taxons"].items():
        lines.append(
            f"| {taxon} | {m['n']} | {m['recall@1']} | {m['recall@3']} | {m['mrr']} |"
        )
    lines += ["", "## Engine Beneath", ""]
    s = baseline["engine_beneath"]["summary"]
    lines.append(
        f"- Cases: {s['cases']} — passed {s['passed']}, failed {s['failed']} "
        f"({('PASS' if s['pass'] else 'FAIL')})"
    )
    lines.append("- Per-case verdicts and checks: `eval/results/baseline-0.5.0.json`")
    lines += ["", "## Parity", ""]
    lines.append(
        "- `eval/results/parity-matrix-1.0.0.md` (four-column matrix, parity on shared retrieval core)"
    )
    lines.append("")

    OUT_MD.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(f"WROTE {OUT_JSON}")
    print(f"WROTE {OUT_MD}")
    print("BASELINE-FROZEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
