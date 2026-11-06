<!-- SPDX-FileCopyrightText: Nova-Violet Role ORG -->
<!-- SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later -->
# Graded telemetry plates (generated, do not edit)

Dataset gold-v2-2026-10-26 | depth 20 | queries 24 | judgments 773

## Combined

| System | nDCG@3 | nDCG@10 | nDCG@20 | ERR@10 | MAP | unjudged |
|---|---:|---:|---:|---:|---:|---:|
| rag-dense | 0.7481 | 0.7988 | 0.8236 | 0.8182 | 0.6904 | 3 |
| rag-hybrid | 0.7038 | 0.7602 | 0.8006 | 0.7671 | 0.6510 | 1 |
| rag-dense-base | 0.7984 | 0.8167 | 0.8557 | 0.8369 | 0.7243 | 6 |
| rag-hybrid-base | 0.7060 | 0.7632 | 0.7877 | 0.7803 | 0.6509 | 1 |
| rtr-arctic | 0.5791 | 0.6821 | 0.7204 | 0.7039 | 0.5513 | 4 |
| rtr-bge | 0.7060 | 0.7632 | 0.7877 | 0.7803 | 0.6509 | 1 |
| rtr-full | 0.6915 | 0.7798 | 0.8032 | 0.7899 | 0.6584 | 2 |

## Per-query nDCG@10 deltas (rtr-full minus rag-dense-base, worst first)

| Query | Corpus | dense-base | rtr-full | delta | best | lane-on full |
|---|---|---:|---:|---:|---|---:|
| NT-G1C | nt-studies | 0.7346 | 0.4192 | -0.3154 | rag-dense-base | 0.3369 |
| NT-G1 | nt-studies | 0.9273 | 0.6827 | -0.2446 | rag-dense | 0.6839 |
| CMD-G1B | dtd-commands | 0.8029 | 0.6052 | -0.1977 | rag-dense | 0.6833 |
| DT-G1 | dita-spec | 0.9571 | 0.8152 | -0.1419 | rag-dense | 0.8152 |
| NT-G5 | nt-studies | 0.8553 | 0.7273 | -0.1280 | rag-dense-base | 0.7113 |
| NT-G2B | nt-studies | 0.4301 | 0.3162 | -0.1139 | rag-dense | 0.3162 |
| NT-G2 | nt-studies | 0.7585 | 0.6535 | -0.1050 | rag-hybrid-base | 0.7129 |
| CMD-G1 | dtd-commands | 0.9568 | 0.8706 | -0.0862 | rag-dense-base | 0.8738 |
| NT-G4 | nt-studies | 0.8542 | 0.7779 | -0.0763 | rag-dense-base | 0.7779 |
| DT-G3 | dita-spec | 0.9645 | 0.8976 | -0.0669 | rag-dense-base | 0.9220 |
| DT-G2 | dita-spec | 0.7750 | 0.7707 | -0.0043 | rtr-arctic | 0.7705 |
| CMD-G2B | dtd-commands | 0.9221 | 0.9203 | -0.0018 | rag-dense-base | 0.9203 |
| DT-G4 | dita-spec | 0.8828 | 0.8828 | +0.0000 | rag-dense | 0.8688 |
| CMD-G6 | dtd-commands | 0.8843 | 0.8843 | +0.0000 | rag-hybrid-base | 0.8843 |
| CMD-G1C | dtd-commands | 0.8525 | 0.8533 | +0.0008 | rag-dense | 0.8718 |
| DT-G1B | dita-spec | 0.8823 | 0.8872 | +0.0049 | rtr-full | 0.8851 |
| CMD-G3 | dtd-commands | 0.9894 | 0.9960 | +0.0066 | rtr-full | 1.0000 |
| NT-G1B | nt-studies | 0.8926 | 0.9074 | +0.0148 | rag-dense | 0.9140 |
| CMD-G2 | dtd-commands | 0.7183 | 0.7402 | +0.0219 | rtr-full | 0.7402 |
| DT-G6 | dita-spec | 0.9150 | 0.9470 | +0.0320 | rtr-full | 0.9480 |
| DT-G4B | dita-spec | 0.8843 | 0.9263 | +0.0420 | rtr-arctic | 0.9303 |
| DT-G3B | dita-spec | 0.8193 | 0.8846 | +0.0653 | rtr-full | 0.8373 |
| NT-G3 | nt-studies | 0.6236 | 0.8281 | +0.2045 | rag-hybrid-base | 0.8281 |
| CMD-G3B | dtd-commands | 0.3170 | 0.5222 | +0.2052 | rag-dense | 0.5093 |

Formulas and supervision: eval/graded/PROTOCOL.md. Claim basis: artifacts/geometry/2026-10-27-final-freeze.md.
