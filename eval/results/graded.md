<!-- SPDX-FileCopyrightText: Nova-Violet Role ORG -->
<!-- SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later -->
# RE:Symbiose versus RAG — graded scoreboard (generated, do not edit)

Dataset gold-v2-2026-10-26 | depth 20 | queries 24 | judgments 773

| System | nDCG@3 | nDCG@10 | nDCG@20 | ERR@10 | MAP | unjudged |
|---|---:|---:|---:|---:|---:|---:|
| rag-dense | 0.7703 | 0.8040 | 0.8336 | 0.8274 | 0.7014 | 6 |
| rag-hybrid | 0.7020 | 0.7635 | 0.8045 | 0.7820 | 0.6568 | 2 |
| rag-dense-base | 0.7942 | 0.8094 | 0.8482 | 0.8311 | 0.7138 | 6 |
| rag-hybrid-base | 0.7292 | 0.7793 | 0.8037 | 0.8039 | 0.6653 | 1 |
| rtr-arctic | 0.7197 | 0.7877 | 0.8125 | 0.8134 | 0.6573 | 9 |
| rtr-bge | 0.7292 | 0.7793 | 0.8037 | 0.8039 | 0.6653 | 1 |
| rtr-full | 0.7216 | 0.7944 | 0.8176 | 0.8153 | 0.6672 | 4 |

Formulas and supervision: eval/graded/PROTOCOL.md.
