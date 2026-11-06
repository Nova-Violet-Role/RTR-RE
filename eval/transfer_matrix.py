"""Cross-family transfer matrix for the DTD corpus (TODO-35).

For every family pair, quantify how much structural vocabulary transfers:

- Jaccard similarity on combined element/attribute/entity vocabulary and
  per-kind (elements, attributes, entities).
- Containment (asymmetric): |A ∩ B| / |A| — the fraction of A's
  vocabulary that also appears in B, which is the directionality of
  transfer.

The lane decision follows from the numbers: near-duplicate pairs
(Jaccard high, containment high both ways) are safe to serve with a
unified lane; moderate-overlap pairs are where cross-family discrimination
(T10) matters most; low-overlap pairs are independent.

Usage: uv run python eval/transfer_matrix.py
Outputs: eval/results/transfer-matrix.json + .md
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent.parent
CATALOGUE = ROOT / "catalogue" / "dtd-family-catalogue.json"
OUT_JSON = ROOT / "eval" / "results" / "transfer-matrix.json"
OUT_MD = ROOT / "eval" / "results" / "transfer-matrix.md"

VOCAB_KINDS = ("elements", "attributes", "entities", "notations")
VOCAB_KEYS = {
    "elements": "element_names",
    "attributes": "attribute_names",
    "entities": "entity_names",
    "notations": "notation_names",
}


def family_of(path: str) -> str:
    """The family is the directory containing the file; files directly
    under the corpus root belong to '(root)' (matching the catalogue's
    own grouping)."""
    parts = Path(path).parts
    for i, part in enumerate(parts):
        if part == ".dtd-file-examples":
            if i + 2 < len(parts):
                return parts[i + 1]
            return "(root)"
    return "(root)"


def load_catalogue():
    with open(CATALOGUE, encoding="utf-8") as f:
        return json.load(f)


def family_vocabularies(catalogue) -> dict:
    fam = defaultdict(lambda: {k: set() for k in VOCAB_KINDS})
    for f in catalogue["files"]:
        fam[family_of(f["path"])]
        for kind in VOCAB_KINDS:
            fam[family_of(f["path"])][kind].update(f.get(VOCAB_KEYS[kind], []))
    return {k: {kk: sorted(vv) for kk, vv in v.items()} for k, v in fam.items()}


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)


def containment(a: set, b: set) -> float:
    if not a:
        return 0.0
    return len(a & b) / len(a)


def build_matrix(fam: dict) -> dict:
    names = sorted(fam)
    pairs = []
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            va = fam[a]
            vb = fam[b]
            combined_a = set().union(*va.values())
            combined_b = set().union(*vb.values())
            row = {
                "family_a": a,
                "family_b": b,
                "combined_jaccard": round(jaccard(combined_a, combined_b), 4),
                "combined_containment_a_in_b": round(
                    containment(combined_a, combined_b), 4
                ),
                "combined_containment_b_in_a": round(
                    containment(combined_b, combined_a), 4
                ),
                "per_kind": {},
            }
            for kind in VOCAB_KINDS:
                sa, sb = set(va[kind]), set(vb[kind])
                row["per_kind"][kind] = {
                    "jaccard": round(jaccard(sa, sb), 4),
                    "a_in_b": round(containment(sa, sb), 4),
                    "b_in_a": round(containment(sb, sa), 4),
                    "|a|": len(sa),
                    "|b|": len(sb),
                    "|a∩b|": len(sa & sb),
                }
            pairs.append(row)
    pairs.sort(key=lambda r: -r["combined_jaccard"])
    return {"families": names, "pairs": pairs}


def lane_decision(matrix: dict) -> dict:
    high = [p for p in matrix["pairs"] if p["combined_jaccard"] >= 0.5]
    moderate = [p for p in matrix["pairs"] if 0.15 <= p["combined_jaccard"] < 0.5]
    low = [p for p in matrix["pairs"] if p["combined_jaccard"] < 0.15]
    return {
        "near_duplicate_pairs": len(high),
        "moderate_overlap_pairs": len(moderate),
        "low_overlap_pairs": len(low),
        "decision": (
            "unified lanes for near-duplicate pairs (Jaccard >= 0.5); "
            "per-family or family-tagged lanes for moderate-overlap pairs "
            "(0.15 <= Jaccard < 0.5), where cross-family discrimination "
            "(T10) is the binding constraint; independent lanes for "
            "low-overlap pairs (Jaccard < 0.15)."
        ),
    }


def render_md(matrix: dict, decision: dict) -> str:
    lines = [
        "# DTD Cross-Family Transfer Matrix (TODO-35)",
        "",
        f"Families: {len(matrix['families'])} · pairs: {len(matrix['pairs'])}",
        "",
        "## Lane decision",
        "",
        f"- Near-duplicate pairs (Jaccard ≥ 0.5): **{decision['near_duplicate_pairs']}**",
        f"- Moderate-overlap pairs (0.15 ≤ Jaccard < 0.5): **{decision['moderate_overlap_pairs']}**",
        f"- Low-overlap pairs (Jaccard < 0.15): **{decision['low_overlap_pairs']}**",
        "",
        decision["decision"],
        "",
        "## Top 25 pairs by combined Jaccard",
        "",
        "| A | B | Jaccard | A-in-B | B-in-A | elements | attributes | entities |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for p in matrix["pairs"][:25]:
        ek = p["per_kind"]["elements"]["jaccard"]
        ak = p["per_kind"]["attributes"]["jaccard"]
        nk = p["per_kind"]["entities"]["jaccard"]
        lines.append(
            f"| {p['family_a']} | {p['family_b']} | "
            f"{p['combined_jaccard']:.3f} | {p['combined_containment_a_in_b']:.3f} | "
            f"{p['combined_containment_b_in_a']:.3f} | {ek:.3f} | {ak:.3f} | {nk:.3f} |"
        )
    lines += [
        "",
        "## Findings",
        "",
        "1. **Transfer is kind-specific.** DITA v1.2 → v1.3 elements transfer"
        " at 0.998 containment (535/536), but entities do not (34 vs 2174):"
        " version pairs share structure, not entity vocabulary.",
        "2. **High overlap is mostly module inclusion.** xhtml11 embeds MathML"
        " (mathml|xhtml11 Jaccard 0.861); JATS and DITA v1.3 distributions"
        " bundle mathml3.dtd. The near-duplicate band is inclusion, not"
        " coincidence.",
        "3. **The moderate band is where T10 binds.** JATS↔DocBook (0.280),"
        " DocBook↔DITA v1.3 (0.232), DITA v1.2↔v1.3 (0.183): shared"
        " vocabulary exists, but each side has substantial unique structure —"
        " exactly the cross-family discrimination failure T10 measures.",
        "4. **Most pairs are independent** (92/105 below 0.15): no transfer,"
        " no discrimination risk.",
        "",
    ]
    lines += ["", "## Full pair table", ""]
    lines.append("| A | B | Jaccard | A-in-B | B-in-A |")
    lines.append("|---|---|---|---|---|")
    for p in matrix["pairs"]:
        lines.append(
            f"| {p['family_a']} | {p['family_b']} | "
            f"{p['combined_jaccard']:.3f} | {p['combined_containment_a_in_b']:.3f} | "
            f"{p['combined_containment_b_in_a']:.3f} |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    catalogue = load_catalogue()
    fam = family_vocabularies(catalogue)
    matrix = build_matrix(fam)
    decision = lane_decision(matrix)
    payload = {"matrix": matrix, "decision": decision}
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    OUT_MD.write_text(render_md(matrix, decision), encoding="utf-8")
    print(f"wrote {OUT_JSON}")
    print(f"wrote {OUT_MD}")
    print(
        f"near-dup={decision['near_duplicate_pairs']} "
        f"moderate={decision['moderate_overlap_pairs']} "
        f"low={decision['low_overlap_pairs']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
