<!-- SPDX-FileCopyrightText: Nova-Violet Role ORG -->
<!-- SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later -->
# RE:Symbiose versus RAG — full scoreboard (generated, do not edit)

Tool: RE:Symbiose versus v2 (isolated, same-size controls) | seed 20260928 | lexikon seeded 4

## dtd-commands (48 files, 97 queries)

| System | Taxon | n | R@1 | R@3 | MRR |
|---|---|---|---|---|---|
| rag-dense | OVERALL | 97 | 0.2887 | 0.4639 | 0.3677 |
| rag-dense | T1 | 48 | 0.2292 | 0.3958 | 0.3056 |
| rag-dense | T2 | 12 | 0.1667 | 0.2500 | 0.1944 |
| rag-dense | T3 | 12 | 0.2500 | 0.5000 | 0.3750 |
| rag-dense | T4 | 12 | 0.0833 | 0.4167 | 0.2361 |
| rag-dense | T5 | 1 | 0.0000 | 0.0000 | 0.0000 |
| rag-dense | T6 | 12 | 0.9167 | 1.0000 | 0.9444 |
| rtr-bge | OVERALL | 97 | 0.4536 | 0.5361 | 0.4897 |
| rtr-bge | T1 | 48 | 0.3125 | 0.3958 | 0.3472 |
| rtr-bge | T2 | 12 | 0.5000 | 0.5833 | 0.5417 |
| rtr-bge | T3 | 12 | 0.5833 | 0.7500 | 0.6667 |
| rtr-bge | T4 | 12 | 0.3333 | 0.4167 | 0.3611 |
| rtr-bge | T5 | 1 | 0.0000 | 0.0000 | 0.0000 |
| rtr-bge | T6 | 12 | 1.0000 | 1.0000 | 1.0000 |

## Combined

| System | n | R@1 | R@3 | MRR | p50 ms | errors |
|---|---|---|---|---|---|---|
| rag-dense | 97 | 0.2887 | 0.4639 | 0.3677 | 3.3 | 0 |
| rtr-bge | 97 | 0.4536 | 0.5361 | 0.4897 | 14.0 | 0 |
