<!-- SPDX-FileCopyrightText: Nova-Violet Role ORG -->
<!-- SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later -->
# Graded telemetry plates (generated, do not edit)

Dataset gold-v2-2026-10-26 | depth 20 | queries 24 | judgments 773

## Combined

| System | nDCG@3 | nDCG@10 | nDCG@20 | ERR@10 | MAP | unjudged |
|---|---:|---:|---:|---:|---:|---:|
| rag-dense | 0.7703 | 0.8040 | 0.8336 | 0.8274 | 0.7014 | 6 |
| rag-hybrid | 0.7020 | 0.7635 | 0.8045 | 0.7820 | 0.6568 | 2 |
| rag-dense-base | 0.7942 | 0.8094 | 0.8482 | 0.8311 | 0.7138 | 6 |
| rag-hybrid-base | 0.7292 | 0.7793 | 0.8037 | 0.8039 | 0.6653 | 1 |
| rtr-arctic | 0.7197 | 0.7877 | 0.8125 | 0.8134 | 0.6573 | 9 |
| rtr-bge | 0.7292 | 0.7793 | 0.8037 | 0.8039 | 0.6653 | 1 |
| rtr-full | 0.7216 | 0.7944 | 0.8176 | 0.8153 | 0.6672 | 4 |

## Per-query nDCG@10 deltas (rtr-full minus rag-dense-base, worst first)

| Query | Corpus | dense-base | rtr-full | delta | best | lane-on full |
|---|---|---:|---:|---:|---|---:|
| NT-G1 | nt-studies | 0.9358 | 0.6567 | -0.2791 | rag-dense | 0.6839 |
| CMD-G1 | dtd-commands | 0.9568 | 0.7980 | -0.1588 | rag-dense-base | 0.8738 |
| DT-G1 | dita-spec | 0.9571 | 0.8152 | -0.1419 | rag-dense | 0.8152 |
| NT-G2B | nt-studies | 0.4574 | 0.3256 | -0.1318 | rag-dense | 0.3162 |
| NT-G5 | nt-studies | 0.8553 | 0.7273 | -0.1280 | rag-dense-base | 0.7113 |
| CMD-G1B | dtd-commands | 0.7177 | 0.6424 | -0.0753 | rag-dense | 0.6833 |
| NT-G4 | nt-studies | 0.8748 | 0.8032 | -0.0716 | rag-dense-base | 0.7779 |
| DT-G3 | dita-spec | 0.9645 | 0.8976 | -0.0669 | rag-dense-base | 0.9220 |
| DT-G4B | dita-spec | 0.8820 | 0.8553 | -0.0267 | rag-dense-base | 0.9303 |
| DT-G1B | dita-spec | 0.8785 | 0.8589 | -0.0196 | rag-dense-base | 0.8851 |
| DT-G4 | dita-spec | 0.8828 | 0.8688 | -0.0140 | rag-dense | 0.8688 |
| CMD-G6 | dtd-commands | 0.8843 | 0.8820 | -0.0023 | rag-hybrid-base | 0.8843 |
| CMD-G2B | dtd-commands | 0.9221 | 0.9203 | -0.0018 | rag-dense-base | 0.9203 |
| CMD-G2 | dtd-commands | 0.7183 | 0.7206 | +0.0023 | rag-hybrid-base | 0.7402 |
| CMD-G3 | dtd-commands | 0.9960 | 1.0000 | +0.0040 | rtr-arctic | 1.0000 |
| NT-G1B | nt-studies | 0.9019 | 0.9066 | +0.0047 | rag-dense | 0.9140 |
| DT-G6 | dita-spec | 0.8980 | 0.9163 | +0.0183 | rtr-arctic | 0.9480 |
| DT-G2 | dita-spec | 0.8179 | 0.8466 | +0.0287 | rtr-full | 0.7705 |
| CMD-G1C | dtd-commands | 0.8718 | 0.9011 | +0.0293 | rag-hybrid | 0.8718 |
| NT-G2 | nt-studies | 0.7425 | 0.7815 | +0.0390 | rag-hybrid-base | 0.7129 |
| NT-G1C | nt-studies | 0.3821 | 0.4222 | +0.0401 | rag-dense | 0.3369 |
| NT-G3 | nt-studies | 0.7715 | 0.8674 | +0.0959 | rtr-arctic | 0.8281 |
| DT-G3B | dita-spec | 0.8215 | 0.9622 | +0.1407 | rtr-arctic | 0.8373 |
| CMD-G3B | dtd-commands | 0.3356 | 0.6898 | +0.3542 | rtr-arctic | 0.5093 |

Formulas and supervision: eval/graded/PROTOCOL.md. Claim basis: artifacts/geometry/2026-10-27-final-freeze.md.
