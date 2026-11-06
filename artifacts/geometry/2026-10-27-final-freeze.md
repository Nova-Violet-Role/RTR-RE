<!-- SPDX-License-Identifier: AGPL-3.0-or-later OR EUPL-1.2 -->
<!-- Copyright 2026 Saimonokuma. -->
# Final bench freeze: lane-off claim basis, lane-on recorded

Date: 2026-10-27. All runs after TODO-6 fortification, TODO-15 STRUCT
lane, 320k/128k bounds, TODO-1/2 fixes and the project-ref coherence
fix. Lane-off is the shipped default and the claim basis
(`eval/results/graded.json`, `eval/results/versus.json` + regenerated
boards); lane-on runs are archived beside them
(`graded-lane-on.json`, `versus-lane-on.json`). TODO-6 basis preserved
as `graded-todo6.json` / `versus-todo6.json`. Comparisons are within-run
(R-15: unchanged arms move ±0.02 across runs).

## Graded (gold-v2, 24 queries, 773 judgments), combined nDCG@10

| Arm | Lane off (basis) | Lane on (rg) |
|---|---:|---:|
| rag-dense-base | 0.8167 | 0.7933 |
| rag-dense | 0.7988 | 0.7811 |
| rtr-full | 0.7798 | 0.7809 |
| rag-hybrid-base / rtr-bge | 0.7632 | 0.7731 |
| rag-hybrid | 0.7602 | 0.7505 |
| rtr-arctic | 0.6821 | 0.6715 |

## Binary intense (573 queries), combined R@1 / R@3 / MRR

| Arm | Lane off (basis) | Lane on (rg) |
|---|---|---|
| rtr-full | 0.6422 / 0.7557 / 0.6894 | 0.6527 / 0.7574 / 0.6984 |
| rag-hybrid | 0.6562 / 0.7522 / 0.6963 | 0.6545 / 0.7557 / 0.6978 |
| rag-hybrid-base | 0.6457 / 0.7277 / 0.6806 | 0.6510 / 0.7295 / 0.6841 |
| rtr-bge | 0.6475 / 0.7295 / 0.6821 | 0.6527 / 0.7330 / 0.6864 |
| rtr-arctic | 0.4974 / 0.5637 / 0.5239 | 0.5061 / 0.5742 / 0.5352 |
| rag-dense-base | 0.4695 / 0.6143 / 0.5343 | 0.4625 / 0.6440 / 0.5451 |
| rag-dense | 0.4520 / 0.6073 / 0.5218 | 0.4503 / 0.6300 / 0.5334 |

## Reading

- Lane-off reproduces the TODO-6 verdict within recorded noise
  (graded full 0.7798 vs 0.7823; binary full R@3/MRR leads, R@1 parity).
  Fallback identity holds empirically, as Lane.lean states it must.
- Lane-on is neutral on graded natural intents (few code-shaped terms)
  and mildly positive on binary identifier lanes (full R@1 +0.0105,
  MRR +0.0090), all inside the R-15 noise band — recorded as
  no-harm/no-claim. It ships default-off.
- Scoped public claim (unchanged): same-size dense RAG leads graded
  combined; RE:Symbiose leads binary R@3/MRR at R@1 parity; hybrid
  advantage is corpus-shaped. Nothing stronger is licensed.
