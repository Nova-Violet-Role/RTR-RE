<!-- SPDX-FileCopyrightText: Nova-Violet Role ORG -->
<!-- SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later -->
# RE:Symbiose versus RAG — graded scoreboard (generated, do not edit)

Dataset gold-v3-2026-10-27 | depth 20 | queries 24 | judgments 785

| System | nDCG@3 | nDCG@10 | nDCG@20 | ERR@10 | MAP | unjudged |
|---|---:|---:|---:|---:|---:|---:|
| rag-dense | 0.7410 | 0.7900 | 0.8155 | 0.8081 | 0.6784 | 3 |
| rag-hybrid | 0.7147 | 0.7645 | 0.8048 | 0.7826 | 0.6538 | 0 |
| rag-dense-base | 0.7925 | 0.8184 | 0.8572 | 0.8368 | 0.7265 | 2 |
| rag-hybrid-base | 0.7012 | 0.7649 | 0.7898 | 0.7789 | 0.6531 | 0 |
| rtr-arctic | 0.5656 | 0.6728 | 0.7163 | 0.7197 | 0.5396 | 2 |
| rtr-bge | 0.7012 | 0.7649 | 0.7898 | 0.7789 | 0.6531 | 0 |
| rtr-full | 0.7012 | 0.7762 | 0.8015 | 0.7874 | 0.6600 | 1 |

Formulas and supervision: eval/graded/PROTOCOL.md.
