# RTR-RE baseline — 0.5.0 (frozen, TODO-29)

- Frozen at: 2026-11-06T14:48:27
- Release arc: 1.0.0
- Source manifest (sha256):
  - `versus`: `0a7511551b77e280c0ff11f87d3978b669aa589b83c6cd5cc1c3562d9c169933`
  - `engine_beneath`: `bb5aa806f20207d801b6ad83d9b6378cc0b19c21724ba6fe039e3617dd44de74`
  - `parity_matrix`: `9757cb2154a029f2e8b49464805097c9d9ef36a9b89cf251326979d8336be330`

## Retrieval — overall per corpus × system

| Corpus | System | n | R@1 | R@3 | MRR | p50 ms |
|---|---|---|---|---|---|---|
| dita-spec | rag-dense | 77 | 0.7143 | 0.7662 | 0.7359 | 3.6 |
| dita-spec | rag-dense-base | 77 | 0.6883 | 0.7792 | 0.7294 | 8.9 |
| dita-spec | rag-hybrid | 77 | 0.9351 | 0.961 | 0.9459 | 6.1 |
| dita-spec | rag-hybrid-base | 77 | 0.8961 | 0.9091 | 0.9004 | 11.7 |
| dita-spec | rtr-arctic | 77 | 0.8961 | 0.9221 | 0.9091 | 14.0 |
| dita-spec | rtr-bge | 77 | 0.8961 | 0.9091 | 0.9004 | 14.0 |
| dita-spec | rtr-full | 77 | 0.9351 | 0.974 | 0.9524 | 23.9 |
| dtd-commands | rag-dense | 97 | 0.3093 | 0.4536 | 0.3763 | 3.2 |
| dtd-commands | rag-dense-base | 97 | 0.3505 | 0.4742 | 0.4055 | 8.2 |
| dtd-commands | rag-hybrid | 97 | 0.4021 | 0.5155 | 0.4519 | 3.7 |
| dtd-commands | rag-hybrid-base | 97 | 0.4536 | 0.5155 | 0.4811 | 8.8 |
| dtd-commands | rtr-arctic | 97 | 0.1649 | 0.2062 | 0.1821 | 15.1 |
| dtd-commands | rtr-bge | 97 | 0.4536 | 0.5258 | 0.4845 | 15.1 |
| dtd-commands | rtr-full | 97 | 0.433 | 0.5155 | 0.4691 | 26.1 |
| dtd-family | rag-dense | 163 | 0.2515 | 0.3436 | 0.2924 | 3.6 |
| dtd-family | rag-dense-base | 163 | 0.2822 | 0.3742 | 0.3221 | 8.6 |
| dtd-family | rag-hybrid | 163 | 0.4908 | 0.5767 | 0.5286 | 17.7 |
| dtd-family | rag-hybrid-base | 163 | 0.4785 | 0.5215 | 0.498 | 23.6 |
| dtd-family | rtr-arctic | 163 | 0.4417 | 0.4969 | 0.4673 | 37.0 |
| dtd-family | rtr-bge | 163 | 0.4785 | 0.5215 | 0.498 | 29.9 |
| dtd-family | rtr-full | 163 | 0.5337 | 0.6319 | 0.5757 | 54.2 |
| nt-studies | rag-dense | 87 | 0.3218 | 0.5632 | 0.431 | 5.3 |
| nt-studies | rag-dense-base | 87 | 0.3678 | 0.5747 | 0.4502 | 13.4 |
| nt-studies | rag-hybrid | 87 | 0.5632 | 0.8046 | 0.659 | 7.3 |
| nt-studies | rag-hybrid-base | 87 | 0.5287 | 0.6897 | 0.59 | 15.1 |
| nt-studies | rtr-arctic | 87 | 0.4368 | 0.6092 | 0.5019 | 19.2 |
| nt-studies | rtr-bge | 87 | 0.5287 | 0.7011 | 0.5958 | 19.7 |
| nt-studies | rtr-full | 87 | 0.5402 | 0.7586 | 0.6264 | 32.2 |

## DTD family — rtr-full taxon detail

| Taxon | n | R@1 | R@3 | MRR |
|---|---|---|---|---|
| T1 | 32 | 0.5625 | 0.7188 | 0.6198 |
| T10 | 21 | 0.619 | 0.7143 | 0.6587 |
| T2 | 12 | 0.5833 | 0.6667 | 0.625 |
| T6 | 6 | 0.8333 | 1.0 | 0.9167 |
| T7 | 40 | 0.525 | 0.55 | 0.5375 |
| T8 | 40 | 0.4 | 0.5 | 0.4417 |
| T9 | 12 | 0.5833 | 0.75 | 0.6667 |
| OVERALL | 163 | 0.5337 | 0.6319 | 0.5757 |

## Engine Beneath

- Cases: 14 — passed 14, failed 0 (PASS)
- Per-case verdicts and checks: `eval/results/baseline-0.5.0.json`

## Parity

- `eval/results/parity-matrix-1.0.0.md` (four-column matrix, parity on shared retrieval core)
