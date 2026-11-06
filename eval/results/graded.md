<!-- SPDX-FileCopyrightText: Nova-Violet Role ORG -->
<!-- SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later -->
# RE:Symbiose versus RAG — graded scoreboard (generated, do not edit)

Dataset gold-v2-2026-10-26 | depth 20 | queries 24 | judgments 773

| System | nDCG@3 | nDCG@10 | nDCG@20 | ERR@10 | MAP | unjudged |
|---|---:|---:|---:|---:|---:|---:|
| rag-dense | 0.7481 | 0.7988 | 0.8236 | 0.8182 | 0.6904 | 3 |
| rag-hybrid | 0.7038 | 0.7602 | 0.8006 | 0.7671 | 0.6510 | 1 |
| rag-dense-base | 0.7984 | 0.8167 | 0.8557 | 0.8369 | 0.7243 | 6 |
| rag-hybrid-base | 0.7060 | 0.7632 | 0.7877 | 0.7803 | 0.6509 | 1 |
| rtr-arctic | 0.5791 | 0.6821 | 0.7204 | 0.7039 | 0.5513 | 4 |
| rtr-bge | 0.7060 | 0.7632 | 0.7877 | 0.7803 | 0.6509 | 1 |
| rtr-full | 0.6915 | 0.7798 | 0.8032 | 0.7899 | 0.6584 | 2 |

Formulas and supervision: eval/graded/PROTOCOL.md.
