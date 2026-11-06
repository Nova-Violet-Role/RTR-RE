<!-- SPDX-License-Identifier: AGPL-3.0-or-later OR EUPL-1.2 -->
<!-- Copyright 2026 Saimonokuma. -->
# Graded-loss fortification: mechanism, fix, measured trade, scoped verdict

Date: 2026-10-27. Closes TODO-6. Gold labels were never touched after the
v2 freeze (`eval/graded/qrels-v2.json`, 773 judgments); every number below
is a bench output, compared **within run** only, because unchanged arms
move across runs (rag-dense-base on nt-studies: 0.7656 pre-fix run vs
0.7187 post-fix run — embedding/index nondeterminism sets the noise floor).

## Mechanism (measured, not inferred)

The hybrid lane weights in `_fused_multi` were computed from a BM25
"decisiveness" gap: top score minus median over **all** candidates, on
max-normalized BM25 (`execution/memory_engine.py:1113` normalizes so the
top is 1.0 whenever anything matches). The median sits in the zero/weak
mass, so the gap measured 0.9014 on NT-G1C and near-maximal generally:
the shift saturated, BM25 took weight 0.57–0.60 against dense 0.15–0.18
on nearly every query, and the declared "a flat field keeps default
weights" branch was dead code in practice. Instrumented probe
(`probe_ntg1c.py`, staged nt-studies, bge-base): the grade-3 doc
`jats.duo.nt` was dense rank 1 (normalized 1.0000) but hybrid rank 12,
below eight candidates dense had not voted for at all (dense 0.0000 after
vote truncation) whose chunks matched generic query terms
("distribution", "tag", "suite") shared across the census corpus.

## Fix (test-first)

`hybrid_lane_weights` (`execution/memory_engine.py:278`) now measures
standout as top-vs-runner-up among **positive** BM25 scores:
a lone standout still takes the lead (exact-term behaviour preserved),
a generic field keeps the dense-lead defaults (0.45/0.30). Contract tests
in `execution/test_memory.py` (`TestHybridLaneWeights`, 4 tests) were red
first (AttributeError, exit 1), green after; full `test_memory` 19 tests
OK. On NT-G1C the hybrid rank of `jats.duo.nt` moved 12 → 4, and every
dense-unvoted BM25 leader fell below the dense-voted head.

## Measured trade (within-run, gold v2 graded / intense binary)

Graded combined nDCG@10 (final column is the frozen claim basis; the
middle post-fix run exposed a hardcoded `gold-v1` dataset label in
`bench_graded.py`, fixed to read the queries-file version, then rerun):

| Arm | Pre-fix run | Final post-fix run |
|---|---:|---:|
| rag-dense-base | 0.8187 | 0.8057 |
| rtr-full | 0.7712 | 0.7823 |
| rag-dense | 0.7898 | 0.7815 |
| rag-hybrid-base / rtr-bge | 0.7703 | 0.7647 |
| rag-hybrid | 0.7532 | 0.7422 |
| rtr-arctic | 0.7440 | 0.6929 |

Per-corpus within-run gaps, final run (hybrid-base minus dense-base,
nDCG@10): nt-studies −0.046 (pre-fix run −0.117: the fix recovers most
of the NT loss); dita-spec −0.039 (unchanged; rtr-full 0.8766 vs
dense-base 0.8854, within noise); dtd-commands −0.038 (pre-fix +0.009:
the fix costs CMD, concentrated in CMD-G2/G3B across all hybrid arms
and in arctic-only drops on G1/G1C/G6; rtr-full 0.8033 ties dense-base
0.8031 there through the arctic+bge fusion).

Binary intense combined (573 queries): rtr-full R@1 0.679 → 0.6492,
R@3 0.763 → 0.7504, MRR 0.715 → 0.6926; rag-hybrid-base R@1 0.6545 now
edges full on R@1 while full keeps the R@3 and MRR leads. Pre-fix result
preserved at `eval/results/versus-prefix.json`, graded pre-fix at
`eval/results/graded-v2-prefix.json`.

A second-iteration candidate — compensate BM25 lead by dense
indecisiveness — was measured before implementation (`probe_spreads.py`):
dense relative sim spreads are 0.06–0.27 everywhere and do **not**
separate the cases (NT-G1C bge is the flattest at 0.0637 yet its dense
top-1 is exactly right; arctic on dtd-commands spreads like bge while
ranking far worse). Spread-based compensation would misfire; it was
rejected on that evidence rather than tuned blind.

## Verdict

Keep the standout fix. It restores the declared semantics, removes a
measured burial mechanism for semantic intents over generic-vocabulary
prose (the production shape: session notes and wikis), and its costs fall
where lexical ordering genuinely beats a weak dense model
(dtd-commands/arctic), which the same-size bge arm does not suffer.
Scoped claims for TODO-11 to carry verbatim-grade honesty:

- On frozen gold-v2 graded intents, same-size dense RAG (bge-base)
  **leads combined** (0.8057 vs rtr-full 0.7823 nDCG@10, final frozen
  run in `eval/results/graded.json`, dataset `gold-v2-2026-10-26`).
  No universal "RAG eradicated" claim is licensed by graded evidence.
- On the intense binary Versus, rtr-full leads R@3 (0.7504) and MRR
  (0.6926) with R@1 at parity (−0.005 vs rag-hybrid-base).
- The hybrid advantage is corpus-shaped: lexical-lead helps
  term-dense, cross-referenced command docs; dense-lead helps
  generic-vocabulary census/prose corpora. The lane now chooses by
  standout, and the residual CMD cost is recorded, not hidden.
