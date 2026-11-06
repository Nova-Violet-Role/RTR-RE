# RTR-RE baseline — 0.5.0 (frozen, TODO-29)

- Frozen at: 2026-11-06T13:22:59
- Release arc: 1.0.0
- Source manifest (sha256):
  - `versus`: `1e6f90761fc3c253d3911ca61a88fe0112e8e631633b7816dd8550db96c4aebe`
  - `engine_beneath`: `bb5aa806f20207d801b6ad83d9b6378cc0b19c21724ba6fe039e3617dd44de74`
  - `parity_matrix`: `9757cb2154a029f2e8b49464805097c9d9ef36a9b89cf251326979d8336be330`

## Retrieval — overall per corpus × system

| Corpus | System | n | R@1 | R@3 | MRR | p50 ms |
|---|---|---|---|---|---|---|
| dita-spec | rag-dense | 77 | 0.7143 | 0.7792 | 0.7403 | 2.8 |
| dita-spec | rag-dense-base | 77 | 0.7013 | 0.7922 | 0.7424 | 8.0 |
| dita-spec | rag-hybrid | 77 | 0.9091 | 0.9351 | 0.9199 | 4.9 |
| dita-spec | rag-hybrid-base | 77 | 0.8961 | 0.9221 | 0.9048 | 9.9 |
| dita-spec | rtr-arctic | 77 | 0.8961 | 0.9351 | 0.9156 | 12.2 |
| dita-spec | rtr-bge | 77 | 0.8961 | 0.9221 | 0.9048 | 12.2 |
| dita-spec | rtr-full | 77 | 0.9221 | 0.974 | 0.9459 | 22.5 |
| dtd-commands | rag-dense | 97 | 0.3196 | 0.4742 | 0.3883 | 2.6 |
| dtd-commands | rag-dense-base | 97 | 0.3711 | 0.4639 | 0.4124 | 7.7 |
| dtd-commands | rag-hybrid | 97 | 0.4124 | 0.5052 | 0.4536 | 2.9 |
| dtd-commands | rag-hybrid-base | 97 | 0.4639 | 0.5464 | 0.4983 | 8.8 |
| dtd-commands | rtr-arctic | 97 | 0.1649 | 0.1959 | 0.177 | 13.8 |
| dtd-commands | rtr-bge | 97 | 0.4536 | 0.5361 | 0.488 | 13.5 |
| dtd-commands | rtr-full | 97 | 0.3918 | 0.4948 | 0.4364 | 25.2 |
| dtd-family | rag-dense | 92 | 0.2826 | 0.413 | 0.3388 | 3.6 |
| dtd-family | rag-dense-base | 92 | 0.3913 | 0.4674 | 0.4239 | 8.1 |
| dtd-family | rag-hybrid | 92 | 0.4891 | 0.587 | 0.5308 | 13.1 |
| dtd-family | rag-hybrid-base | 92 | 0.5543 | 0.6196 | 0.5851 | 20.3 |
| dtd-family | rtr-arctic | 92 | 0.413 | 0.5 | 0.4529 | 23.1 |
| dtd-family | rtr-bge | 92 | 0.5543 | 0.6196 | 0.5851 | 26.1 |
| dtd-family | rtr-full | 92 | 0.5652 | 0.6848 | 0.6196 | 41.6 |
| nt-studies | rag-dense | 87 | 0.3333 | 0.5747 | 0.4387 | 4.0 |
| nt-studies | rag-dense-base | 87 | 0.3448 | 0.5977 | 0.4483 | 9.7 |
| nt-studies | rag-hybrid | 87 | 0.5747 | 0.8161 | 0.6705 | 5.9 |
| nt-studies | rag-hybrid-base | 87 | 0.5287 | 0.6782 | 0.5881 | 11.6 |
| nt-studies | rtr-arctic | 87 | 0.4483 | 0.6207 | 0.5134 | 15.0 |
| nt-studies | rtr-bge | 87 | 0.5402 | 0.6897 | 0.5996 | 14.6 |
| nt-studies | rtr-full | 87 | 0.5402 | 0.7586 | 0.6284 | 27.6 |

## DTD family — rtr-full taxon detail

| Taxon | n | R@1 | R@3 | MRR |
|---|---|---|---|---|
| T1 | 32 | 0.5625 | 0.75 | 0.6406 |
| T10 | 12 | 0.5 | 0.5 | 0.5 |
| T2 | 12 | 0.5833 | 0.6667 | 0.625 |
| T6 | 6 | 0.8333 | 1.0 | 0.9167 |
| T7 | 12 | 0.5 | 0.5 | 0.5 |
| T8 | 12 | 0.5 | 0.5833 | 0.5417 |
| T9 | 6 | 0.6667 | 1.0 | 0.8333 |
| OVERALL | 92 | 0.5652 | 0.6848 | 0.6196 |

## Engine Beneath

- Cases: 14 — passed 14, failed 0 (PASS)
- Per-case verdicts and checks: `eval/results/baseline-0.5.0.json`

## Parity

- `eval/results/parity-matrix-1.0.0.md` (four-column matrix, parity on shared retrieval core)
