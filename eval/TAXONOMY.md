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
follow this convention. `eval/dtd_extractor.py` (the DTD structural feature
extractor) is the instrument behind the DTD corpus queries and is covered by
`execution/test_dtd_extractor.py`.

## Corpora (both real, both local)

| Corpus | Files | Nature | Queries (intense) |
|---|---|---|---|
| `nt-studies` | 36 NestedText research notes | keyword-dense, overlapping vocab | 191 |
| `dita-spec` | 30 DITA 2.0 spec topics (XML) | long structured prose, element names | 169 |
| `dtd-commands` | 48 real *-dtd command files | huge generated DTD prose, identifiers | 213 |
| `dtd-family` | 60 DTD/module/entity files across 15 families | real DTD grammars (JATS, DocBook, DITA, TEI, MathML, XHTML, SVG, Office, daisy, …) | 285 |
| `keeper-memory` | 40 generated DTD-shaped evicted spans | infinite-memory retrievability (T13) | 40 |

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
| T7 attribute-semantic | rare attribute name (df==1) → its file | attribute-semantic recall (DTD) |
| T8 entity-lane | rare entity/parameter-entity name (df==1) → its file | entity-lane recall (DTD) |
| T9 content-model | distinctive sequence/choice content-model fragment → its file | content-model recall (DTD) |
| T10 cross-family | term occurring in exactly two files from different families → one of them | cross-family vocabulary discrimination (DTD) |
| T11 lineage | family keyword/owner from a file's PUBLIC lineage → that file | lineage discrimination (DTD, TODO-64) |
| T12 customization-layer | module-switch name from a driver's customization layer → that driver | customization-layer recognition (DTD, TODO-64) |
| T13 keeper-memory | distinctive evicted-span marker → its span file | infinite-memory retrievability (TODO-70) |

Metrics per taxon: recall@1, recall@3, MRR. Queries auto-derived (seed 20260928),
T5 pairs runtime-validated (source present, synonym absent, single owner).

## Scoreboard (`results/versus.json`, `results/versus.md`, `versus.mmd`)

Official tool v2, fully isolated (DB/registry/roots/lexikon),
sha256 corpus manifest in the JSON. 898 queries, 5 real corpora,
**0 query errors** on every system. Freeze 2026-11-11 at 1.2.0,
intense caps (`results/versus.json`; 1.1.0 preserved in
`results/versus-1.1.0.json`; STRUCT-lane-on run archived in
`results/versus-lane-on.json`, within noise). The 1.2.0 non-intense
544-query run reproduced the prior record exactly (R@1 bit-identical
on 4 of 5 corpora), proving the engine changes bench-neutral; the
freeze moved to intense because this taxonomy specifies intense
counts and the record must match its spec. Cross-run absolutes move ±~0.02 (register R-15) — read
within-run comparisons only.

| System | R@1 | R@3 | MRR |
|---|---|---|---|
| **rtr-full** | **0.723** | **0.850** | **0.777** |
| rtr-arctic | 0.713 | 0.824 | 0.760 |
| rtr-bge | 0.659 | 0.755 | 0.702 |
| rag-hybrid | 0.638 | 0.736 | 0.681 |
| rag-hybrid-base | 0.626 | 0.712 | 0.664 |
| rag-dense-base | 0.404 | 0.549 | 0.469 |
| rag-dense | 0.394 | 0.571 | 0.473 |

rtr-full leads every column. keeper-memory (T13): rtr-full R@1/R@3/MRR
0.975 — evicted spans are retrievable at high score through the real
engine. Historical 2026-10-27 freeze (3 corpora): rtr-full
0.642/0.756/0.689; precedent leak-aided 164-query run (superseded):
0.738/0.854/0.785.

### DTD-corpus run (2026-11-06, 4 corpora, 353 queries, T7–T10 taxons)

Full 4×7 run with the DTD family corpus and the new structural taxons.
rtr-full leads the DTD corpus (R@1=0.565, R@3=0.685, MRR=0.620) and
holds overall MRR leadership (0.643 vs rag-hybrid-base 0.632). On the
DTD corpus, rtr-full beats every classic RAG arm on the same model size
(rag-hybrid-base: R@1=0.554, MRR=0.585). DTD taxon detail (rtr-full):
T7 attribute-semantic R@1=0.500, T8 entity-lane R@1=0.500, T9
content-model R@1=0.667/R@3=1.000, T10 cross-family R@1=0.500. The
cross-family taxon is the hardest lane — shared vocabulary across
families (e.g. `appendix` in DocBook and DITA) collapses on the
strongest family match; this is the measured target for amplification.

rtr-full leads R@3 and sits at R@1/MRR parity (−0.014/−0.007 vs the best
RAG arm); dense-only RAG is not close anywhere. The graded companion
(`bench_graded.py`, frozen gold-v2, 773 judgments) is the stricter
instrument and same-size dense leads it combined — published in full in
`results/graded.md` and scoped in
`artifacts/geometry/2026-10-27-graded-fortification.md`. Gold v1 (155
judgments, 370 unjudged returned) vs v2 (773 judgments, 4 unjudged):
rtr-full nDCG@10 0.7960 → 0.7944, drift 0.0016 (noise) — the residual
is pool coverage, and v2 strictly dominates as the claim basis. On
dtd-commands Arctic collapses (binary R@1 0.160 in the TODO-6 run);
vote truncation + standout lane weights mitigate fusion drag but do not
make Arctic a solo model there. T5 stays small-n; cross-encoder rerank
remains tracked future work, not a claim.

Historical (precedent, leak-aided, superseded): 164 queries gave
rtr-full 0.738/0.854/0.785. Isolation removed live-root leakage
(36 staged → 66 indexed) and the numbers narrowed — we publish the
isolated ones.

### DTD cross-family transfer matrix (TODO-35)

`results/transfer-matrix.json` measures vocabulary transfer between the
15 DTD families (Jaccard + asymmetric containment per kind: elements,
attributes, entities, notations). Findings:

1. **Transfer is kind-specific.** DITA v1.2 → v1.3 elements transfer at
   0.998 containment (535/536) but entities do not (34 vs 2174): version
   pairs share structure, not entity vocabulary.
2. **High overlap is mostly module inclusion.** xhtml11 embeds MathML
   (mathml|xhtml11 Jaccard 0.861); JATS and DITA v1.3 distributions bundle
   mathml3.dtd. The near-duplicate band is inclusion, not coincidence.
3. **The moderate band is where T10 binds.** JATS↔DocBook (0.280),
   DocBook↔DITA v1.3 (0.232), DITA v1.2↔v1.3 (0.183): shared vocabulary
   exists, but each side has substantial unique structure — exactly the
   cross-family discrimination failure T10 measures.
4. **Most pairs are independent** (92/105 below 0.15): no transfer, no
   discrimination risk.

Lane decision: unified lanes for near-duplicate pairs (Jaccard ≥ 0.5,
7 pairs); family-tagged lanes for moderate-overlap pairs (0.15–0.5,
6 pairs), where cross-family discrimination (T10) is the binding
constraint; independent lanes below 0.15 (92 pairs). The DTD corpus is
therefore a **family-tagged lane**.

### DTD per-family suites (TODO-36)

14 families wired via `PER_FAMILY_CORPORA`/`ALL_CORPORA`; full 14×7 run,
zero query errors. rtr-full leads 9 families, ties 2, loses 3
(`dita-spec11`, `xhtml`, `xhtml11`) — all three losses are sibling-family
bleed (DITA vs DITA-spec etc.), the exact failure the family-tagged lane
addresses. Per-family boards: `results/per-family-scoreboard.md`.

### The amplification — 1.0.0 (TODO-30/37)

The frozen no-seed floor (above) vs the current architecture (structural
inventory header + lexikon seeded from DTD vocabulary, 3800 terms):

| dtd-family rtr-full | frozen floor | current | delta |
|---|---|---|---|
| R@1 | 0.5460 | 0.7239 | **+0.1779** |
| R@3 | 0.6503 | 0.8896 | **+0.2393** |
| MRR | 0.5930 | 0.7996 | **+0.2066** |
| T7 (attribute-semantic) | 0.2500 | 0.6750 | **+0.4250** |
| T8 (entity-lane) | 0.4750 | 0.7750 | **+0.3000** |
| T9 (content-model) | 0.6667 | 0.6667 | 0.0000 (parity) |
| T10 (cross-family) | 0.6190 | 0.6190 | 0.0000 (parity) |
| T1/T2/T6 | — | — | at parity |

No regression anywhere; the other three corpora hold exactly at the
floor. The amplification is architecture, not bench-only: the inventory
header and the lexikon seeding are shipped in the engine.

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

- Four corpora, 353 queries (standard caps), file-level self-supervision, no
  human labels. Measures retrieval mechanics, not graded relevance depth.
- Margins on nt-studies/dtd-commands are narrow queries-wide; dita-spec is decisive.
- The DTD-family corpus is the hardest: 60 real grammar files across 15 families,
  with T7–T10 structural taxons. T7/T8 were amplified (see above); T10 remains
  the hardest lane, held at parity with the floor.
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
