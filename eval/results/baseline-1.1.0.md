# RTR-RE baseline — 1.1.0 (frozen, TODO-29/68)

- Frozen at: 2026-11-07T18:04:37
- Release arc: 1.1.0
- Source manifest (sha256):
  - `versus`: `ee205476e15028defd612ae3d76788038f47c4ace897bf43a5f7ca2fecf0dd3d`
  - `engine_beneath`: `a2a16d27317204e16c95f0a13e0c80a6fa3fead76f6276c3c0a3bcd39456f8c1`
  - `parity_matrix`: `9757cb2154a029f2e8b49464805097c9d9ef36a9b89cf251326979d8336be330`

## Retrieval — overall per corpus × system

| Corpus | System | n | R@1 | R@3 | MRR | p50 ms |
|---|---|---|---|---|---|---|
| dita-spec | rag-dense | 77 | 0.7273 | 0.7922 | 0.7576 | 5.9 |
| dita-spec | rag-dense-base | 77 | 0.7013 | 0.7532 | 0.7273 | 14.1 |
| dita-spec | rag-hybrid | 77 | 0.9351 | 0.9481 | 0.9394 | 9.8 |
| dita-spec | rag-hybrid-base | 77 | 0.8701 | 0.8961 | 0.8788 | 17.2 |
| dita-spec | rtr-arctic | 77 | 0.9091 | 0.9351 | 0.9177 | 23.4 |
| dita-spec | rtr-bge | 77 | 0.8701 | 0.8961 | 0.8788 | 20.6 |
| dita-spec | rtr-full | 77 | 0.9351 | 0.9481 | 0.9394 | 40.1 |
| dtd-commands | rag-dense | 97 | 0.2887 | 0.4639 | 0.3677 | 6.1 |
| dtd-commands | rag-dense-base | 97 | 0.3505 | 0.4742 | 0.4055 | 13.2 |
| dtd-commands | rag-hybrid | 97 | 0.4124 | 0.5258 | 0.4622 | 6.6 |
| dtd-commands | rag-hybrid-base | 97 | 0.4536 | 0.5361 | 0.4897 | 14.7 |
| dtd-commands | rtr-arctic | 97 | 0.4742 | 0.5773 | 0.5189 | 31.5 |
| dtd-commands | rtr-bge | 97 | 0.4536 | 0.5361 | 0.4897 | 23.4 |
| dtd-commands | rtr-full | 97 | 0.4845 | 0.6082 | 0.5378 | 52.5 |
| dtd-family | rag-dense | 243 | 0.2716 | 0.4156 | 0.3299 | 6.2 |
| dtd-family | rag-dense-base | 243 | 0.2675 | 0.4156 | 0.332 | 13.9 |
| dtd-family | rag-hybrid | 243 | 0.5185 | 0.6872 | 0.596 | 31.3 |
| dtd-family | rag-hybrid-base | 243 | 0.5021 | 0.6502 | 0.57 | 30.3 |
| dtd-family | rtr-arctic | 243 | 0.6955 | 0.856 | 0.7654 | 59.8 |
| dtd-family | rtr-bge | 243 | 0.6173 | 0.8107 | 0.7058 | 38.9 |
| dtd-family | rtr-full | 243 | 0.6749 | 0.8807 | 0.7641 | 65.5 |
| nt-studies | rag-dense | 87 | 0.3333 | 0.6207 | 0.4579 | 7.6 |
| nt-studies | rag-dense-base | 87 | 0.3678 | 0.5862 | 0.4579 | 17.9 |
| nt-studies | rag-hybrid | 87 | 0.5632 | 0.7241 | 0.6284 | 10.6 |
| nt-studies | rag-hybrid-base | 87 | 0.5172 | 0.6667 | 0.5805 | 19.2 |
| nt-studies | rtr-arctic | 87 | 0.5747 | 0.8046 | 0.6648 | 26.2 |
| nt-studies | rtr-bge | 87 | 0.5287 | 0.6667 | 0.5862 | 24.0 |
| nt-studies | rtr-full | 87 | 0.5747 | 0.8506 | 0.6916 | 49.8 |

## DTD family — rtr-full taxon detail

| Taxon | n | R@1 | R@3 | MRR |
|---|---|---|---|---|
| T1 | 32 | 0.7188 | 0.875 | 0.7917 |
| T10 | 21 | 0.619 | 0.8571 | 0.7222 |
| T11 | 40 | 0.425 | 0.8 | 0.5792 |
| T12 | 40 | 0.725 | 0.95 | 0.8208 |
| T2 | 12 | 0.8333 | 0.9167 | 0.875 |
| T6 | 6 | 0.8333 | 1.0 | 0.9167 |
| T7 | 40 | 0.675 | 0.8 | 0.7292 |
| T8 | 40 | 0.8 | 0.95 | 0.8667 |
| T9 | 12 | 0.6667 | 0.9167 | 0.7778 |
| OVERALL | 243 | 0.6749 | 0.8807 | 0.7641 |

## Engine Beneath

- Cases: 27 — passed 27, failed 0 (PASS)
- Per-case verdicts and checks: `eval/results/baseline-1.1.0.json`

## Parity

- `eval/results/parity-matrix-1.0.0.md` (four-column matrix, parity on shared retrieval core)
