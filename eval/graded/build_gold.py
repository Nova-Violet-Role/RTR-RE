# SPDX-FileCopyrightText: Nova-Violet Role ORG
# SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
"""Build graded gold v1 from curated intents declared before any ranking.

Grades are authored from staged filename/title inventory and corpus
families (see PROTOCOL.md), NOT from system output. Grade lists name
canonical (3), sibling/high (2), marginal (1) and inspected negatives (0)
per intent. The builder validates every doc against the versus manifest
and refuses unknown files, so a typo can never become a silent judgment.
"""

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "execution"))
from graded_metrics import validate_dataset  # noqa: E402

VERSION = "gold-v1-2026-10-26"
ANNOTATOR = (
    "muse-wonder-full-1.0-contributor (operator-directed, title/family authoring)"
)

# (id, corpus, taxon, text, intent, {3:[...], 2:[...], 1:[...], 0:[...]})
INTENTS = [
    # ---- nt-studies ----
    (
        "NT-G1",
        "nt-studies",
        "G1",
        "How is the SVG DTD family modularized across its module files?",
        "SVG module architecture census",
        {
            3: ["svg-modules.nt"],
            2: ["dtd-families.nt", "xhtml11.nt"],
            1: ["mathml-docbook-xhtml11.duo.nt"],
            0: ["greek.duo.nt", "tocjs.nt"],
        },
    ),
    (
        "NT-G2",
        "nt-studies",
        "G2",
        "What distinguishes DAISY and DTBook accessible book formats in the corpus?",
        "DAISY DTBook accessible formats",
        {
            3: ["daisy.nt", "dtbook.nt"],
            2: ["office-dtds-daisy.duo.nt"],
            1: ["dtd-families.nt"],
            0: ["svg-modules.nt", "jats.duo.nt"],
        },
    ),
    (
        "NT-G1B",
        "nt-studies",
        "G3",
        "How do XHTML strict and transitional variants differ in element counts and modularization?",
        "XHTML variants comparison",
        {
            3: ["xhtml-diff.nt", "xhtml11.nt"],
            2: ["mathml-docbook-xhtml11.duo.nt"],
            1: ["svg-modules.nt"],
            0: ["daisy.nt", "tei-modules.nt"],
        },
    ),
    (
        "NT-G3",
        "nt-studies",
        "G1",
        "Which studies census DITA plugin and shell distributions?",
        "DITA plugins shells census",
        {
            3: ["dita-plugins.nt", "dita-shells.duo.nt"],
            2: ["dita11.nt", "ditaversion.nt"],
            1: ["lwdita.nt", "xdita.nt"],
            0: ["ooxml.nt", "form-tokens.nt"],
        },
    ),
    (
        "NT-G4",
        "nt-studies",
        "G1",
        "How are argument variants and sigil variables catalogued?",
        "arguments and sigils catalog",
        {
            3: ["arguments-dtd-variants.nt", "arguments.duo.nt", "sigil-variables.nt"],
            2: ["form-tokens.nt"],
            1: ["terminal-sections.nt"],
            0: ["jats.duo.nt", "dtbook.nt"],
        },
    ),
    (
        "NT-G5",
        "nt-studies",
        "G5",
        "Where is the complete numbering system with polyglot examples collected?",
        "Greek numbering collection paraphrase",
        {
            3: ["greek.duo.nt", "polyglot-greek.nt"],
            2: ["sigil-variables.nt"],
            1: ["form-tokens.nt"],
            0: ["xhtml11.nt", "ooxml.nt"],
        },
    ),
    (
        "NT-G1C",
        "nt-studies",
        "G1",
        "What does the journal article tag suite distribution contain?",
        "JATS distribution census",
        {
            3: ["jats.duo.nt"],
            2: ["dtd-families.nt"],
            1: ["docbook-sch.nt"],
            0: ["greek.duo.nt", "tocjs.nt"],
        },
    ),
    (
        "NT-G2B",
        "nt-studies",
        "G2",
        "How was the whole DTD tree rewritten and audited batch by batch?",
        "rewrite audit programme",
        {
            3: ["rewrite-ledger.nt"],
            2: ["build-survey.nt", "corpus-index.nt"],
            1: ["spec-deltas.nt"],
            0: ["daisy.nt", "svg-modules.nt"],
        },
    ),
    # ---- dita-spec ----
    (
        "DT-G1",
        "dita-spec",
        "G2",
        "How does conditional processing filter and flag content with DITAVAL conditions?",
        "conditional processing DITAVAL procedure",
        {
            3: [
                "aboutconditionalprocessing.dita",
                "evaluating-conditional-processing-attributes.dita",
            ],
            2: [
                "example-ditaval-with-conditions-for-groups.dita",
                "branch-filtering-overview.dita",
                "example-flagging-outputclass.dita",
            ],
            1: ["diratt.dita"],
            0: ["fileext.dita", "example-of-an-index-range.dita"],
        },
    ),
    (
        "DT-G3",
        "dita-spec",
        "G3",
        "How do key scopes change which key definition wins?",
        "key scopes precedence",
        {
            3: ["example-keys-scope-defining-precedence.dita", "examples-of-keys.dita"],
            2: [
                "example-key-scopes-omnibus-publications.dita",
                "example-conref-range-conkeyref.dita",
            ],
            1: ["ditaaddressing.dita"],
            0: ["fileext.dita", "diratt.dita"],
        },
    ),
    (
        "DT-G4",
        "dita-spec",
        "G4",
        "Show an example of pushing reused content before another element.",
        "conaction pushbefore example",
        {
            3: ["example-conref-conaction-pushbefore.dita"],
            2: ["example-conref-range-conkeyref.dita"],
            1: ["ditaaddressing.dita"],
            0: ["classification-maps.dita", "fileext.dita"],
        },
    ),
    (
        "DT-G4B",
        "dita-spec",
        "G4",
        "How can chunking combine topics or split a nested hierarchy apart?",
        "chunk combine split examples",
        {
            3: ["example-chunk-combine-all.dita", "example-chunk-split-nested.dita"],
            2: ["example-simple-map-w-reltable.dita"],
            1: ["cascading-of-metadata-elements-from-map-to-map.dita"],
            0: ["diratt.dita", "fileext.dita"],
        },
    ),
    (
        "DT-G3B",
        "dita-spec",
        "G3",
        "Restrict a content model with constraints in DTD versus RNG: what differs?",
        "constraints DTD RNG comparison",
        {
            3: [
                "example-contraints-redefine-content-model.dita",
                "example-rng-constraints-redefine-content-model.dita",
                "constraints-processing-interoperability.dita",
            ],
            2: ["configuration.dita", "document-type-shells-conformance.dita"],
            1: ["dtd-coding-element-types.dita"],
            0: ["example-of-an-index-range.dita", "classification-maps.dita"],
        },
    ),
    (
        "DT-G2",
        "dita-spec",
        "G2",
        "How does metadata cascade from one map to another?",
        "metadata cascading maps",
        {
            3: ["cascading-of-metadata-elements-from-map-to-map.dita"],
            2: ["classification-maps.dita", "example-simple-map-w-reltable.dita"],
            1: ["branch-filtering-overview.dita"],
            0: ["dtd-coding-element-types.dita", "fileext.dita"],
        },
    ),
    (
        "DT-G1B",
        "dita-spec",
        "G1",
        "What makes a document-type shell conformant and configurable?",
        "shells conformance configuration",
        {
            3: ["document-type-shells-conformance.dita", "configuration.dita"],
            2: [
                "dtd-coding-element-types.dita",
                "examples-expansion-implemented-using-rng.dita",
            ],
            1: ["generalization-w-cross-specialization-dependencies.dita"],
            0: ["example-of-an-index-range.dita", "diratt.dita"],
        },
    ),
    (
        "DT-G6",
        "dita-spec",
        "G6",
        "ditaaddressing and fileext: addressing and filename extension rules",
        "identifier intent addressing extensions",
        {
            3: ["ditaaddressing.dita", "fileext.dita"],
            2: ["basic-dita-terminology.dita"],
            1: ["example-conref-range-conkeyref.dita"],
            0: ["classification-maps.dita", "example-flagging-outputclass.dita"],
        },
    ),
    # ---- dtd-commands ----
    (
        "CMD-G3",
        "dtd-commands",
        "G3",
        "Which command should grow a sound codebase by replacement rather than beside-the-old additions?",
        "overhaul versus amplify enhance comparison",
        {
            3: ["overhaul-codebase-dtd.md"],
            2: ["enhance-codebase-dtd.md", "amplify-codebase-dtd.md"],
            1: ["codebase-architect-dtd.md"],
            0: ["coin-flip-best-of-dtd.md", "havamal-dtd.md"],
        },
    ),
    (
        "CMD-G2",
        "dtd-commands",
        "G2",
        "How do I bound a search space before enumerating it?",
        "count bounds before search procedure",
        {
            3: ["count-the-library-dtd.md"],
            2: ["babel-dtd.md", "catalog-dtd.md", "feasibility-dtd.md"],
            1: ["formula-dtd.md"],
            0: ["havamal-dtd.md", "coin-flip-best-of-dtd.md"],
        },
    ),
    (
        "CMD-G1",
        "dtd-commands",
        "G1",
        "Which channels are unclean by default and what rite makes each safe?",
        "clean unclean channels rites",
        {
            3: ["clean-unclean-dtd.md"],
            2: ["code-blacklist-dtd.md", "file-blacklist-dtd.md"],
            1: ["audit-skill-dtd.md"],
            0: ["loci-dtd.md", "eisenhower-matrix-dtd.md"],
        },
    ),
    (
        "CMD-G1B",
        "dtd-commands",
        "G1",
        "How does the memory palace fixed walk store and recall facts?",
        "loci fixed walk recall",
        {
            3: ["loci-dtd.md"],
            2: ["catalog-dtd.md", "history-dtd.md"],
            1: ["havamal-dtd.md"],
            0: ["coin-flip-best-of-dtd.md", "git-gh-amplification-dtd.md"],
        },
    ),
    (
        "CMD-G3B",
        "dtd-commands",
        "G3",
        "Compare decision frameworks for choosing among options under time pressure.",
        "decision frameworks comparison",
        {
            3: ["options-dtd.md", "eisenhower-matrix-dtd.md"],
            2: [
                "one-thing-dtd.md",
                "coin-flip-best-of-dtd.md",
                "opportunity-cost-dtd.md",
            ],
            1: ["inversion-dtd.md"],
            0: ["babel-dtd.md", "atharvan-dtd.md"],
        },
    ),
    (
        "CMD-G2B",
        "dtd-commands",
        "G2",
        "How do I audit a skill, heal it, or create a new agent skill?",
        "skill audit heal create procedure",
        {
            3: ["audit-skill-dtd.md", "heal-skill-dtd.md", "create-agent-skill-dtd.md"],
            2: ["ai-slop-dtd.md"],
            1: ["debug-dtd.md"],
            0: ["loci-dtd.md", "landscape-dtd.md"],
        },
    ),
    (
        "CMD-G1C",
        "dtd-commands",
        "G1",
        "Which command declares codebase shape without rewriting code?",
        "architect declare shape no rewrite",
        {
            3: ["codebase-architect-dtd.md"],
            2: ["amplify-codebase-dtd.md", "enhance-codebase-dtd.md"],
            1: ["overhaul-codebase-dtd.md"],
            0: ["add-to-todos-dtd.md", "check-todos-dtd.md"],
        },
    ),
    (
        "CMD-G6",
        "dtd-commands",
        "G6",
        "ccc and corpus routing: which search instrument by what is known",
        "identifier intent search routing ccc corpus",
        {
            3: ["ccc-dtd.md", "corpus-dtd.md"],
            2: ["catalog-dtd.md"],
            1: ["deep-dive-dtd.md"],
            0: ["eleusis-dtd.md", "goetia-dtd.md"],
        },
    ),
]

# Pool adjudications (v2): additions/overrides after blind worksheet
# inspection of titles, headings and snippets. A doc named here replaces
# any v1 grade for that query. Remaining pooled docs receive inspected
# grade 0 in v2 only; v1 files are never rewritten.
ADJUDICATIONS = {
    "DT-G1": {1: ["classification-maps.dita"]},
    "DT-G1B": {
        2: [
            "basic-dita-terminology.dita",
            "adding-an-attribute-to-certain-table-elements.dita",
            "constraints-processing-interoperability.dita",
        ]
    },
    "DT-G2": {1: ["example-subjectScheme-extension.dita", "examples-of-keys.dita"]},
    "DT-G3B": {
        2: ["examples-expansion-implemented-using-rng.dita"],
        1: ["adding-an-attribute-to-certain-table-elements.dita"],
    },
    "DT-G6": {1: ["configuration.dita", "examples-of-keys.dita"]},
    "NT-G1": {1: ["tei-modules.nt", "dtds.nt"]},
    "NT-G1B": {1: ["dtd-families.nt", "rewrite-ledger.nt"]},
    "NT-G1C": {1: ["tei-modules.nt", "mathml-docbook-xhtml11.duo.nt"]},
    "NT-G2B": {2: ["triple-proof.nt"], 1: ["dtd-families.nt"]},
    "NT-G3": {2: ["tocjs.nt", "ooxml.nt"], 1: ["dtd-families.nt"]},
    "NT-G4": {1: ["answers-catalog.nt", "corpus-index.nt"]},
    "NT-G5": {1: ["form-tokens.nt"]},
    "CMD-G1": {1: ["chain-dtd.md"]},
    "CMD-G1B": {1: ["babel-dtd.md", "corpus-dtd.md"]},
    "CMD-G1C": {1: ["landscape-dtd.md", "chain-dtd.md"]},
    "CMD-G2": {1: ["ccc-dtd.md", "corpus-dtd.md", "landscape-dtd.md"]},
    "CMD-G3B": {1: ["feasibility-dtd.md", "first-principles-dtd.md"]},
}

RATIONALE = {
    3: "canonical document for the intent (title/family authored pre-ranking)",
    2: "sibling mechanism or one required side of the intent",
    1: "background or fragment relevance only",
    0: "inspected family neighbour: does not satisfy the intent",
}


# v3 (2026-10-27): additive-only lane-on gap adjudication. Every pair here
# surfaced in lane-on top-20s and carries NO v1/v2 label (verified by
# v3_gap.py: 12 unjudged pairs). Grades follow the true v2 intent strings
# and the frozen v2 precedents named per row. v1/v2 files are never read
# for writing — v2 is loaded, never modified.
V3_VERSION = "gold-v3-2026-10-27"
V3_ADDITIONS = [
    # (query_id, doc filename, grade, rationale)
    (
        "CMD-G1B",
        "eleusis-dtd.md",
        1,
        "ordered initiation gates: sequenced-teaching fragment adjacent to the loci fixed-walk family (cf. havamal-dtd judged 1 for this intent)",
    ),
    (
        "CMD-G1B",
        "hadal-deep-dive-dtd.md",
        0,
        "research-excavation family; v2 gave deep-dive-dtd 0 for this intent",
    ),
    (
        "CMD-G1B",
        "hadopelagia-deep-dive-dtd.md",
        0,
        "same research family as hadal; no fixed-walk mechanism",
    ),
    (
        "CMD-G1C",
        "inversion-dtd.md",
        0,
        "failure-recipe family, no codebase-shape declaration",
    ),
    (
        "CMD-G2",
        "chain-dtd.md",
        0,
        "command-chaining family; v2 gave chain-dtd 0 for the sibling G1B pool",
    ),
    (
        "CMD-G3",
        "eisenhower-matrix-dtd.md",
        0,
        "prioritization quadrants, not the overhaul/amplify/enhance comparison",
    ),
    (
        "CMD-G3",
        "one-thing-dtd.md",
        0,
        "single-action focus, not the three-way codebase comparison",
    ),
    (
        "CMD-G3B",
        "hadopelagia-deep-dive-dtd.md",
        0,
        "uncapped deep research contradicts the time-pressure constraint; v2 gave deep-dive/hadal 0 here",
    ),
    (
        "DT-G1B",
        "example-conref-conaction-pushbefore.dita",
        0,
        "addressing example, not shell-conformance configuration; follows the pooled conref-range example precedent (0)",
    ),
    (
        "NT-G2B",
        "answers-catalog.nt",
        1,
        "background catalog fragment adjacent to the audit-programme family (cf. spec-deltas judged 1 for this intent)",
    ),
    ("NT-G3", "scaffolds.nt", 0, "scaffold specs, not the DITA plugins/shells census"),
    (
        "NT-G4",
        "lwdita.nt",
        0,
        "LWDITA format detail pass, not an arguments/sigils catalog",
    ),
]


def build_v3() -> int:
    from graded_metrics import load_qrels, load_queries

    v2q = json.loads((HERE / "queries-v2.json").read_text(encoding="utf-8"))
    v2r = json.loads((HERE / "qrels-v2.json").read_text(encoding="utf-8"))
    corpus_of = {q["id"]: q["corpus"] for q in v2q["queries"]}
    have = {(j["query_id"], j["doc_id"]) for j in v2r["judgments"]}
    judgments = list(v2r["judgments"])
    for qid, name, grade, rationale in V3_ADDITIONS:
        doc_id = f"{corpus_of[qid]}/{name}"
        if (qid, doc_id) in have:
            print(
                f"REFUSED v3: {(qid, doc_id)} already labelled — v2 labels never move"
            )
            return 2
        judgments.append(
            {
                "query_id": qid,
                "doc_id": doc_id,
                "grade": grade,
                "rationale": rationale,
                "evidence": "lane-on gap adjudication 2026-10-27: staged title/headings/snippets inspected (v3_inspect.py)",
                "annotator": ANNOTATOR,
                "status": "adjudicated-v3",
            }
        )
    qpayload = {
        "version": V3_VERSION,
        "seed": v2q.get("seed"),
        "queries": v2q["queries"],
    }
    rpayload = {"version": V3_VERSION, "judgments": judgments}
    qpath = HERE / "queries-v3.json"
    rpath = HERE / "qrels-v3.json"
    qpath.write_bytes(json.dumps(qpayload, indent=2).encode("utf-8"))
    rpath.write_bytes(json.dumps(rpayload, indent=2).encode("utf-8"))
    versus = json.loads(
        (ROOT / "eval" / "results" / "versus.json").read_text(encoding="utf-8")
    )
    manifest = {
        c: [row["file"] for row in rows] for c, rows in versus["manifest"].items()
    }
    report = validate_dataset(load_queries(qpath), load_qrels(rpath), manifest)
    print(json.dumps(report, indent=2))
    print(f"wrote {qpath} + {rpath}")
    return 1 if report["errors"] else 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="build_gold")
    ap.add_argument("--v2", action="store_true", help="emit pool-adjudicated v2 files")
    ap.add_argument(
        "--v3",
        action="store_true",
        help="emit additive lane-on-gap v3 files (v1/v2 untouched)",
    )
    args = ap.parse_args()
    if args.v3:
        return build_v3()
    version = "gold-v2-2026-10-26" if args.v2 else VERSION
    versus = json.loads(
        (ROOT / "eval" / "results" / "versus.json").read_text(encoding="utf-8")
    )
    manifest = {
        c: [row["file"] for row in rows] for c, rows in versus["manifest"].items()
    }
    queries, judgments = [], []
    for qid, corpus, taxon, text, intent, grades in INTENTS:
        queries.append(
            {
                "id": qid,
                "corpus": corpus,
                "taxon": taxon,
                "text": text,
                "intent": intent,
                "authoring": "curated from staged title/family inventory before graded scoring",
            }
        )
        merged = {}
        for grade in (3, 2, 1, 0):
            for name in grades.get(grade, []):
                merged[name] = (grade, "judged")
        if args.v2:
            for grade, names in ADJUDICATIONS.get(qid, {}).items():
                for name in names:
                    merged[name] = (grade, "adjudicated")
        for name, (grade, status) in sorted(merged.items()):
            if name not in manifest.get(corpus, []):
                print(f"REFUSED {qid}: {name} not in {corpus} manifest")
                return 2
            judgments.append(
                {
                    "query_id": qid,
                    "doc_id": f"{corpus}/{name}",
                    "grade": grade,
                    "rationale": RATIONALE[grade],
                    "evidence": "staged filename + extracted title in versus manifest inventory"
                    if status == "judged"
                    else "blind pool worksheet: title/headings/snippets inspected",
                    "annotator": ANNOTATOR,
                    "status": status,
                }
            )
    if args.v2:
        judged = {(j["query_id"], j["doc_id"]) for j in judgments}
        pool = json.loads(
            (ROOT / "eval" / "results" / "graded-pool.json").read_text(encoding="utf-8")
        )
        for q in queries:
            for doc_id in pool.get(q["id"], {}).get("blind", []):
                if (q["id"], doc_id) in judged:
                    continue
                judgments.append(
                    {
                        "query_id": q["id"],
                        "doc_id": doc_id,
                        "grade": 0,
                        "rationale": "pooled candidate inspected in blind worksheet: unrelated subject family, no dedicated intent treatment",
                        "evidence": "blind pool worksheet title/headings/snippets",
                        "annotator": ANNOTATOR,
                        "status": "adjudicated",
                    }
                )
    qpayload = {"version": version, "seed": versus.get("seed"), "queries": queries}
    rpayload = {"version": version, "judgments": judgments}
    suffix = "-v2" if args.v2 else ""
    qpath = HERE / f"queries{suffix}.json"
    rpath = HERE / f"qrels{suffix}.json"
    qpath.write_bytes(json.dumps(qpayload, indent=2).encode("utf-8"))
    rpath.write_bytes(json.dumps(rpayload, indent=2).encode("utf-8"))
    from graded_metrics import load_qrels, load_queries

    report = validate_dataset(load_queries(qpath), load_qrels(rpath), manifest)
    print(json.dumps(report, indent=2))
    print(f"wrote {qpath} + {rpath}")
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
