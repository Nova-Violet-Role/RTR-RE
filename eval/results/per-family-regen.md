<!-- SPDX-FileCopyrightText: Nova-Violet Role ORG -->
<!-- SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later -->
# RE:Symbiose versus RAG — full scoreboard (generated, do not edit)

Tool: RE:Symbiose versus v2 (isolated, same-size controls) | seed 20260928 | lexikon seeded 38

## dtd-daisy (11 files, 94 queries)

| System | Taxon | n | R@1 | R@3 | MRR |
|---|---|---|---|---|---|
| rtr-full | OVERALL | 94 | 0.8723 | 0.9574 | 0.9113 |
| rtr-full | OVERALL_MACRO | 94 | 0.7985 | 0.9658 | 0.8774 |
| rtr-full | T1 | 10 | 0.7000 | 1.0000 | 0.8333 |
| rtr-full | T11 | 2 | 0.5000 | 1.0000 | 0.7500 |
| rtr-full | T2 | 12 | 1.0000 | 1.0000 | 1.0000 |
| rtr-full | T6 | 6 | 1.0000 | 1.0000 | 1.0000 |
| rtr-full | T7 | 14 | 0.7143 | 0.7857 | 0.7500 |
| rtr-full | T8 | 40 | 0.9750 | 0.9750 | 0.9750 |
| rtr-full | T9 | 10 | 0.7000 | 1.0000 | 0.8333 |
| rag-dense-base | OVERALL | 94 | 0.6596 | 0.8511 | 0.7465 |
| rag-dense-base | OVERALL_MACRO | 94 | 0.5835 | 0.8481 | 0.7061 |
| rag-dense-base | T1 | 10 | 0.7000 | 1.0000 | 0.8333 |
| rag-dense-base | T11 | 2 | 0.5000 | 1.0000 | 0.7500 |
| rag-dense-base | T2 | 12 | 0.4167 | 0.8333 | 0.6111 |
| rag-dense-base | T6 | 6 | 1.0000 | 1.0000 | 1.0000 |
| rag-dense-base | T7 | 14 | 0.1429 | 0.4286 | 0.2857 |
| rag-dense-base | T8 | 40 | 0.9250 | 0.9750 | 0.9458 |
| rag-dense-base | T9 | 10 | 0.4000 | 0.7000 | 0.5167 |

## dtd-xdita (5 files, 43 queries)

| System | Taxon | n | R@1 | R@3 | MRR |
|---|---|---|---|---|---|
| rtr-full | OVERALL | 43 | 0.8605 | 1.0000 | 0.9225 |
| rtr-full | OVERALL_MACRO | 43 | 0.8000 | 1.0000 | 0.8901 |
| rtr-full | T1 | 3 | 0.6667 | 1.0000 | 0.8333 |
| rtr-full | T11 | 4 | 0.5000 | 1.0000 | 0.7083 |
| rtr-full | T2 | 12 | 1.0000 | 1.0000 | 1.0000 |
| rtr-full | T6 | 5 | 0.6000 | 1.0000 | 0.8000 |
| rtr-full | T7 | 6 | 0.8333 | 1.0000 | 0.8889 |
| rtr-full | T8 | 11 | 1.0000 | 1.0000 | 1.0000 |
| rtr-full | T9 | 2 | 1.0000 | 1.0000 | 1.0000 |
| rag-dense-base | OVERALL | 43 | 0.5349 | 0.9302 | 0.7016 |
| rag-dense-base | OVERALL_MACRO | 43 | 0.5781 | 0.9394 | 0.7303 |
| rag-dense-base | T1 | 3 | 0.6667 | 1.0000 | 0.7778 |
| rag-dense-base | T11 | 4 | 0.5000 | 1.0000 | 0.7083 |
| rag-dense-base | T2 | 12 | 0.7500 | 1.0000 | 0.8611 |
| rag-dense-base | T6 | 5 | 0.6000 | 1.0000 | 0.8000 |
| rag-dense-base | T7 | 6 | 0.1667 | 0.6667 | 0.3889 |
| rag-dense-base | T8 | 11 | 0.3636 | 0.9091 | 0.5758 |
| rag-dense-base | T9 | 2 | 1.0000 | 1.0000 | 1.0000 |

## Combined

| System | n | R@1 | R@3 | MRR | mR@1 | p50 ms | errors |
|---|---|---|---|---|---|---|---|
| rtr-full | 137 | 0.8686 | 0.9708 | 0.9148 | 0.7844 | 30.6 | 0 |
| rag-dense-base | 137 | 0.6204 | 0.8759 | 0.7324 | 0.5782 | 7.2 | 0 |
