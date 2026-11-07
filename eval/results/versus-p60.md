<!-- SPDX-FileCopyrightText: Nova-Violet Role ORG -->
<!-- SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later -->
# RE:Symbiose versus RAG — full scoreboard (generated, do not edit)

Tool: RE:Symbiose versus v2 (isolated, same-size controls) | seed 20260928 | lexikon seeded 3800

## dtd-family (60 files, 243 queries)

| System | Taxon | n | R@1 | R@3 | MRR |
|---|---|---|---|---|---|
| rtr-full | OVERALL | 243 | 0.6749 | 0.8807 | 0.7641 |
| rtr-full | T1 | 32 | 0.7188 | 0.8750 | 0.7917 |
| rtr-full | T10 | 21 | 0.6190 | 0.8571 | 0.7222 |
| rtr-full | T11 | 40 | 0.4250 | 0.8000 | 0.5792 |
| rtr-full | T12 | 40 | 0.7250 | 0.9500 | 0.8208 |
| rtr-full | T2 | 12 | 0.8333 | 0.9167 | 0.8750 |
| rtr-full | T6 | 6 | 0.8333 | 1.0000 | 0.9167 |
| rtr-full | T7 | 40 | 0.6750 | 0.8000 | 0.7292 |
| rtr-full | T8 | 40 | 0.8000 | 0.9500 | 0.8667 |
| rtr-full | T9 | 12 | 0.6667 | 0.9167 | 0.7778 |
| rag-hybrid-base | OVERALL | 243 | 0.5021 | 0.6502 | 0.5700 |
| rag-hybrid-base | T1 | 32 | 0.7188 | 0.8750 | 0.7917 |
| rag-hybrid-base | T10 | 21 | 0.6190 | 0.8571 | 0.7222 |
| rag-hybrid-base | T11 | 40 | 0.3500 | 0.5500 | 0.4292 |
| rag-hybrid-base | T12 | 40 | 0.6000 | 0.8000 | 0.7000 |
| rag-hybrid-base | T2 | 12 | 0.7500 | 0.8333 | 0.7917 |
| rag-hybrid-base | T6 | 6 | 0.8333 | 1.0000 | 0.9167 |
| rag-hybrid-base | T7 | 40 | 0.2250 | 0.2500 | 0.2375 |
| rag-hybrid-base | T8 | 40 | 0.4250 | 0.5250 | 0.4708 |
| rag-hybrid-base | T9 | 12 | 0.6667 | 0.9167 | 0.7917 |

## keeper-memory (40 files, 40 queries)

| System | Taxon | n | R@1 | R@3 | MRR |
|---|---|---|---|---|---|
| rtr-full | OVERALL | 40 | 1.0000 | 1.0000 | 1.0000 |
| rtr-full | T13 | 40 | 1.0000 | 1.0000 | 1.0000 |
| rag-hybrid-base | OVERALL | 40 | 0.9750 | 0.9750 | 0.9750 |
| rag-hybrid-base | T13 | 40 | 0.9750 | 0.9750 | 0.9750 |

## Combined

| System | n | R@1 | R@3 | MRR | p50 ms | errors |
|---|---|---|---|---|---|---|
| rtr-full | 283 | 0.7208 | 0.8975 | 0.7974 | 69.5 | 0 |
| rag-hybrid-base | 283 | 0.5689 | 0.6961 | 0.6272 | 21.2 | 0 |
