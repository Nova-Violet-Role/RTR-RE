<!-- SPDX-FileCopyrightText: Nova-Violet Role ORG -->
<!-- SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later -->
# RTR versus RAG — taxionometry

How we measure, what each taxon means, and what the numbers honestly say.
Methodology first, scoreboard second. Reality is the judge.

## Probe placement

Evaluation probes (`engine_beneath.py`, `calibrate_symbiose.py`, benches)
live in `eval/` and are never shipped in the wheel; their tests live in
`execution/test_*.py` and load the probe by path, so they run in the
standard suite while the probe itself stays out of the package.
`execution/test_engine_beneath.py` and `execution/test_calibrate_symbiose.py`
follow this convention.

## Corpora (both real, both local)

| Corpus | Files | Nature | Queries (intense) |
|---|---|---|---|
| `nt-studies` | 36 NestedText research notes | keyword-dense, overlapping vocab | 191 |
| `dita-spec` | 30 DITA 2.0 spec topics (XML) | long structured prose, element names | 169 |
| `dtd-commands` | 48 real *-dtd command files | huge generated DTD prose, identifiers | 213 |

Same index per run for every system — the ablation is purely on the retrieval
path. Each bench run uses an **isolated temp vector DB**
(`OPENCODE_MEMORY_DB_DIR`) so no run contaminates another.

## Systems

| System | Models | Hybrid | Expansion | Notes |
|---|---|---|---|---|
| `rag-dense` | bge-small, dense-only | no | no | classic single-vector RAG |
| `rag-hybrid` | bge-small + BM25 | yes | no | classic hybrid baseline |
| `rag-dense-base` | bge-base, dense-only | no | no | same-size control (768d) |
| `rag-hybrid-base` | bge-base + BM25 | yes | no | same-size control (768d) |
| `rtr-arctic` | arctic-m + BM25 | yes | yes | ablation: arctic alone in RTR plumbing |
| `rtr-bge` | bge-base + BM25 | yes | yes | ablation: bge-base alone in RTR plumbing |
| `rtr-full` | arctic-m + bge-base, confidence-weighted RRF (top-10 vote truncation) | yes | yes | RE:Symbiose dual ensemble (default ship) |

## Taxons

| Taxon | Construction | What it isolates |
|---|---|---|
| T1 title-self | file's own distinctive title → file | general retrieval health |
| T2 rare-term | df==1 term → its file | exact/BM25 discrimination |
| T3 concept | mid-df keyword pair → file, top-3 | multi-term conceptual recall |
| T4 scoped | T1 subset under project filter | isolation (no cross-project bleed) |
| T5 paraphrase | true synonym phrase, absent corpus-wide (BM25 blind) + seeded lexikon | lexikon lane / semantic reach |
| T6 ident | filename stems + opaque digit/underscore ids | exact-match lane |

Metrics per taxon: recall@1, recall@3, MRR. Queries auto-derived (seed 20260928),
T5 pairs runtime-validated (source present, synonym absent, single owner).

## Scoreboard (`results/versus.json`, `results/versus.md`, `versus.mmd`)

Official tool v2, `--intense`, fully isolated (DB/registry/roots/lexikon),
sha256 corpus manifest in the JSON. 573 queries, 3 real corpora,
**0 query errors** on every system. Final freeze 2026-10-27 (lane-off
claim basis in `results/versus.json`; STRUCT-lane-on run archived in
`results/versus-lane-on.json`, within noise). Cross-run absolutes move
±~0.02 (register R-15) — read within-run comparisons only.

| System | R@1 | R@3 | MRR |
|---|---|---|---|
| rag-hybrid | 0.656 | 0.752 | 0.696 |
| **rtr-full** | 0.642 | **0.756** | 0.689 |
| rtr-bge | 0.647 | 0.730 | 0.682 |
| rag-hybrid-base | 0.646 | 0.728 | 0.681 |
| rag-dense-base | 0.469 | 0.614 | 0.534 |
| rtr-arctic | 0.497 | 0.564 | 0.524 |
| rag-dense | 0.452 | 0.607 | 0.522 |

rtr-full leads R@3 and sits at R@1/MRR parity (−0.014/−0.007 vs the best
RAG arm); dense-only RAG is not close anywhere. The graded companion
(`bench_graded.py`, frozen gold-v2, 773 judgments) is the stricter
instrument and same-size dense leads it combined — published in full in
`results/graded.md` and scoped in
`artifacts/geometry/2026-10-27-graded-fortification.md`. On
dtd-commands Arctic collapses (binary R@1 0.160 in the TODO-6 run);
vote truncation + standout lane weights mitigate fusion drag but do not
make Arctic a solo model there. T5 stays small-n; cross-encoder rerank
remains tracked future work, not a claim.

Historical (precedent, leak-aided, superseded): 164 queries gave
rtr-full 0.738/0.854/0.785. Isolation removed live-root leakage
(36 staged → 66 indexed) and the numbers narrowed — we publish the
isolated ones.

## Incident log (why you can trust these numbers)

Mid-campaign the bench caught itself lying: hundreds of
`Error finding id` failures on Arctic queries and run-to-run swings.
Root causes found and fixed in-product:
- Repeated delete/add churn across many short-lived ChromaDB clients desyncs
  the persistent HNSW segment → single shared client per DB path.
- Purge covered only configured models (105 orphan chunks accumulated in the
  bge-small collection) → purge fans out over all existing RTR collections,
  verifies each delete, plus a `janitor` command and `OPENCODE_MEMORY_DB_DIR`
  override. The live DB was janitored back to zero.
- Earlier dual/arctic numbers from contaminated runs were invalidated, not
  explained away. The scoreboard above is the clean re-run.
- Second campaign (2026-10-26): one shared DB across corpora zeroed every
  bge-base arm after corpus 1 in full sequence while subset runs passed —
  delete/add churn again. Fix: one fresh DB + registry per corpus, no purge
  between corpora. The contaminated full run was discarded whole.

## Limits (read before quoting us)

- Three corpora, 573 queries (intense), file-level self-supervision, no
  human labels. Measures retrieval mechanics, not graded relevance depth.
- Margins on nt-studies/dtd-commands are narrow queries-wide; dita-spec is decisive.
- Latency: RTR-full ~42–47ms p50 vs 5–20ms classic arms (in-process; MCP adds transport).
- Dual-ensemble value concentrates in identifiers and cross-corpus robustness;
  per-model ablations ship in the same table so anyone can check our work.

## Reproduce

```
uv run python eval/bench_versus.py   # needs installed rtr wheel for deps
```

Outputs `results/versus.json` + `versus.mmd`; render with
`npx -y @mermaid-js/mermaid-cli -i eval/versus.mmd -o eval/versus.svg`.
The release gate (`uv run python -m execution.rtr_eval`) is separate and must stay
green: no ship on regression.
