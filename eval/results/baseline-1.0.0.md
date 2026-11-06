# RTR-RE baseline — 0.5.0 (frozen, TODO-29)

- Frozen at: 2026-11-06T18:55:03
- Release arc: 1.0.0
- Source manifest (sha256):
  - `versus`: `b2b334339d0e43ec3f44379efa116aadb76883c71dc29146feab193106a7744a`
  - `engine_beneath`: `bb5aa806f20207d801b6ad83d9b6378cc0b19c21724ba6fe039e3617dd44de74`
  - `parity_matrix`: `9757cb2154a029f2e8b49464805097c9d9ef36a9b89cf251326979d8336be330`

## Retrieval — overall per corpus × system

| Corpus | System | n | R@1 | R@3 | MRR | p50 ms |
|---|---|---|---|---|---|---|
| dita-spec | rag-dense | 77 | 0.7273 | 0.7922 | 0.7576 | 2.9 |
| dita-spec | rag-dense-base | 77 | 0.7013 | 0.7532 | 0.7273 | 7.8 |
| dita-spec | rag-hybrid | 77 | 0.9351 | 0.9481 | 0.9394 | 5.0 |
| dita-spec | rag-hybrid-base | 77 | 0.8701 | 0.8961 | 0.8788 | 10.0 |
| dita-spec | rtr-arctic | 77 | 0.9091 | 0.9351 | 0.9177 | 12.8 |
| dita-spec | rtr-bge | 77 | 0.8701 | 0.8961 | 0.8788 | 12.2 |
| dita-spec | rtr-full | 77 | 0.9351 | 0.9481 | 0.9394 | 23.9 |
| dtd-commands | rag-dense | 97 | 0.2887 | 0.4639 | 0.3677 | 3.4 |
| dtd-commands | rag-dense-base | 97 | 0.3505 | 0.4742 | 0.4055 | 8.4 |
| dtd-commands | rag-hybrid | 97 | 0.4124 | 0.5258 | 0.4622 | 3.8 |
| dtd-commands | rag-hybrid-base | 97 | 0.4536 | 0.5361 | 0.4897 | 9.3 |
| dtd-commands | rtr-arctic | 97 | 0.4742 | 0.5773 | 0.5189 | 21.8 |
| dtd-commands | rtr-bge | 97 | 0.4536 | 0.5361 | 0.4897 | 15.3 |
| dtd-commands | rtr-full | 97 | 0.4845 | 0.6082 | 0.5378 | 35.7 |
| dtd-family | rag-dense | 163 | 0.3252 | 0.4172 | 0.362 | 3.7 |
| dtd-family | rag-dense-base | 163 | 0.2945 | 0.3926 | 0.3354 | 8.6 |
| dtd-family | rag-hybrid | 163 | 0.5215 | 0.6074 | 0.5593 | 18.4 |
| dtd-family | rag-hybrid-base | 163 | 0.4908 | 0.6196 | 0.5501 | 20.7 |
| dtd-family | rtr-arctic | 163 | 0.5092 | 0.6135 | 0.5573 | 33.6 |
| dtd-family | rtr-bge | 163 | 0.4908 | 0.6196 | 0.5501 | 27.4 |
| dtd-family | rtr-full | 163 | 0.5399 | 0.6626 | 0.593 | 52.9 |
| nt-studies | rag-dense | 87 | 0.3333 | 0.6207 | 0.4579 | 4.2 |
| nt-studies | rag-dense-base | 87 | 0.3678 | 0.5862 | 0.4579 | 9.9 |
| nt-studies | rag-hybrid | 87 | 0.5632 | 0.7241 | 0.6284 | 5.8 |
| nt-studies | rag-hybrid-base | 87 | 0.5172 | 0.6667 | 0.5805 | 11.6 |
| nt-studies | rtr-arctic | 87 | 0.5747 | 0.8046 | 0.6648 | 15.6 |
| nt-studies | rtr-bge | 87 | 0.5287 | 0.6667 | 0.5862 | 14.8 |
| nt-studies | rtr-full | 87 | 0.5747 | 0.8506 | 0.6916 | 29.7 |

## DTD family — rtr-full taxon detail

| Taxon | n | R@1 | R@3 | MRR |
|---|---|---|---|---|
| T1 | 32 | 0.75 | 0.9062 | 0.8229 |
| T10 | 21 | 0.619 | 0.8571 | 0.7143 |
| T2 | 12 | 0.8333 | 0.9167 | 0.875 |
| T6 | 6 | 0.8333 | 1.0 | 0.9167 |
| T7 | 40 | 0.275 | 0.3 | 0.2833 |
| T8 | 40 | 0.425 | 0.525 | 0.4667 |
| T9 | 12 | 0.6667 | 0.9167 | 0.7778 |
| OVERALL | 163 | 0.5399 | 0.6626 | 0.593 |

## Engine Beneath

- Cases: 14 — passed 14, failed 0 (PASS)
- Per-case verdicts and checks: `eval/results/baseline-0.5.0.json`

## Parity

- `eval/results/parity-matrix-1.0.0.md` (four-column matrix, parity on shared retrieval core)
