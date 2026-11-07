# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
"""Regression gate (TODO-43).

Compares the current measured state against the frozen 1.0.0 baseline
(`results/baseline-1.0.0.json`) and fails on any regression:

  1. Retrieval: every corpus x system OVERALL metric (R@1, R@3, MRR)
     must be >= the frozen value, and every dtd-family rtr-full taxon
     (T1/T2/T6/T7/T8/T9/T10/OVERALL) must be >= the frozen value.
  2. Engine Beneath: every case in the current evidence must still be
     VERDICT True, and the case count must equal the frozen count.

Exit 0 = ship. Exit 1 = regression (named). Exit 2 = missing source.

The gate is red-capable by construction: a deliberately broken current
file (lowered score, failed case, missing case) must make it exit 1 —
`execution/test_regression_gate.py` proves this on every suite run.

Run:
  uv run python eval/regression_gate.py

Optional path overrides (used by the red-capability test):
  uv run python eval/regression_gate.py <baseline> <versus> <engine_beneath>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RESULTS = Path(__file__).parent / "results"


def _newest_baseline() -> Path:
    """Default = the newest frozen baseline (release arcs sort lexicographically:
    1.0.0 < 1.1.0 < ...). The 1.0.0 baseline stays available as an explicit
    reference argument for cross-arc comparison (TODO-68 division)."""
    candidates = sorted(RESULTS.glob("baseline-*.json"))
    return candidates[-1] if candidates else RESULTS / "baseline-1.0.0.json"


BASELINE = _newest_baseline()
VERSUS = RESULTS / "versus.json"
ENGINE_BENEATH = RESULTS / "engine-beneath-cases.json"

METRICS = ("recall@1", "recall@3", "mrr")


def load(path: Path) -> dict:
    if not path.exists():
        print(f"REFUSED: missing source {path}")
        raise SystemExit(2)
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    baseline_path = Path(argv[0]) if len(argv) > 0 else BASELINE
    versus_path = Path(argv[1]) if len(argv) > 1 else VERSUS
    eb_path = Path(argv[2]) if len(argv) > 2 else ENGINE_BENEATH

    baseline = load(baseline_path)
    versus = load(versus_path)
    eb = load(eb_path)

    failures: list[str] = []
    bl = baseline["retrieval"]
    cv = versus["corpora"]

    # 1a. corpus x system OVERALL
    for corpus, cdata in bl["corpora"].items():
        cur_corpus = cv.get(corpus, {})
        cur_systems = cur_corpus.get("systems", {})
        for sys_name, m in cdata["systems"].items():
            cur = cur_systems.get(sys_name, {}).get("metrics", {}).get("OVERALL", {})
            for metric in METRICS:
                frozen = m[metric]
                got = cur.get(metric)
                if got is None:
                    failures.append(f"{corpus}/{sys_name}/OVERALL/{metric}: missing")
                elif got < frozen - 1e-9:
                    failures.append(
                        f"{corpus}/{sys_name}/OVERALL/{metric}: {got:.4f} < frozen {frozen:.4f}"
                    )

    # 1b. dtd-family rtr-full taxon detail
    dtd = bl["dtd_family_rtr_full_taxons"]
    cur_dtd = (
        cv.get("dtd-family", {})
        .get("systems", {})
        .get("rtr-full", {})
        .get("metrics", {})
    )
    for taxon, m in dtd.items():
        cur = cur_dtd.get(taxon, {})
        for metric in METRICS:
            frozen = m[metric]
            got = cur.get(metric)
            if got is None:
                failures.append(f"dtd-family/rtr-full/{taxon}/{metric}: missing")
            elif got < frozen - 1e-9:
                failures.append(
                    f"dtd-family/rtr-full/{taxon}/{metric}: {got:.4f} < frozen {frozen:.4f}"
                )

    # 2. Engine Beneath — count and verdicts
    frozen_summary = baseline["engine_beneath"]["summary"]
    cur_summary = eb["summary"]
    if cur_summary.get("cases") != frozen_summary.get("cases"):
        failures.append(
            f"engine_beneath cases: {cur_summary.get('cases')} != frozen {frozen_summary.get('cases')}"
        )
    for case in eb.get("cases", []):
        verdict = case.get("verdict")
        if verdict not in (True, "pass"):
            failures.append(f"engine_beneath/{case.get('case')}: verdict not pass")

    if failures:
        print("REGRESSION-GATE FAIL")
        for f in failures:
            print(f"  - {f}")
        return 1

    print(
        f"REGRESSION-GATE PASS — {len(bl['corpora'])} corpora, "
        f"{sum(len(c['systems']) for c in bl['corpora'].values())} systems, "
        f"{len(dtd)} taxons, engine_beneath {cur_summary.get('cases')}/{cur_summary.get('passed')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
