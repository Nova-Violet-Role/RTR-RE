# RTR-RE baseline — 1.0.0 (frozen, TODO-29)

- Frozen at: 2026-11-07T02:17:31
- Release arc: 1.0.0
- Source manifest (sha256):
  - `versus`: `4bf24b7f34e45ff4afb9b67545e72d5f418fcf1cb96e85306c0b7a8cd6da9f73`
  - `engine_beneath`: `1707421cc79063136aa38cfe88120af5680385ba44a784ce7cbd361dcf77313b`
  - `parity_matrix`: `9757cb2154a029f2e8b49464805097c9d9ef36a9b89cf251326979d8336be330`

## Retrieval — overall per corpus × system

| Corpus | System | n | R@1 | R@3 | MRR | p50 ms |
|---|---|---|---|---|---|---|
| dita-spec | rag-dense | 77 | 0.7273 | 0.7922 | 0.7576 | 3.8 |
| dita-spec | rag-dense-base | 77 | 0.7013 | 0.7532 | 0.7273 | 8.6 |
| dita-spec | rag-hybrid | 77 | 0.9351 | 0.9481 | 0.9394 | 6.9 |
| dita-spec | rag-hybrid-base | 77 | 0.8701 | 0.8961 | 0.8788 | 12.0 |
| dita-spec | rtr-arctic | 77 | 0.9091 | 0.9351 | 0.9177 | 17.1 |
| dita-spec | rtr-bge | 77 | 0.8701 | 0.8961 | 0.8788 | 14.3 |
| dita-spec | rtr-full | 77 | 0.9351 | 0.9481 | 0.9394 | 28.2 |
| dtd-commands | rag-dense | 97 | 0.2887 | 0.4639 | 0.3677 | 4.1 |
| dtd-commands | rag-dense-base | 97 | 0.3505 | 0.4742 | 0.4055 | 8.1 |
| dtd-commands | rag-hybrid | 97 | 0.4124 | 0.5258 | 0.4622 | 4.6 |
| dtd-commands | rag-hybrid-base | 97 | 0.4536 | 0.5361 | 0.4897 | 9.2 |
| dtd-commands | rtr-arctic | 97 | 0.4742 | 0.5773 | 0.5189 | 22.6 |
| dtd-commands | rtr-bge | 97 | 0.4536 | 0.5361 | 0.4897 | 15.7 |
| dtd-commands | rtr-full | 97 | 0.4845 | 0.6082 | 0.5378 | 37.2 |
| dtd-family | rag-dense | 163 | 0.3006 | 0.4356 | 0.3558 | 4.6 |
| dtd-family | rag-dense-base | 163 | 0.2883 | 0.3988 | 0.3364 | 8.8 |
| dtd-family | rag-hybrid | 163 | 0.546 | 0.638 | 0.5879 | 22.0 |
| dtd-family | rag-hybrid-base | 163 | 0.4969 | 0.6135 | 0.5511 | 25.8 |
| dtd-family | rtr-arctic | 163 | 0.6871 | 0.8221 | 0.7464 | 60.4 |
| dtd-family | rtr-bge | 163 | 0.6871 | 0.8282 | 0.7515 | 48.4 |
| dtd-family | rtr-full | 163 | 0.7239 | 0.8896 | 0.7996 | 88.6 |
| nt-studies | rag-dense | 87 | 0.3333 | 0.6207 | 0.4579 | 5.7 |
| nt-studies | rag-dense-base | 87 | 0.3678 | 0.5862 | 0.4579 | 13.9 |
| nt-studies | rag-hybrid | 87 | 0.5632 | 0.7241 | 0.6284 | 7.9 |
| nt-studies | rag-hybrid-base | 87 | 0.5172 | 0.6667 | 0.5805 | 15.2 |
| nt-studies | rtr-arctic | 87 | 0.5747 | 0.8046 | 0.6648 | 23.4 |
| nt-studies | rtr-bge | 87 | 0.5287 | 0.6667 | 0.5862 | 20.1 |
| nt-studies | rtr-full | 87 | 0.5747 | 0.8506 | 0.6916 | 35.5 |

## DTD family — rtr-full taxon detail

| Taxon | n | R@1 | R@3 | MRR |
|---|---|---|---|---|
| T1 | 32 | 0.7188 | 0.875 | 0.7917 |
| T10 | 21 | 0.619 | 0.8095 | 0.7063 |
| T2 | 12 | 0.9167 | 0.9167 | 0.9167 |
| T6 | 6 | 0.8333 | 1.0 | 0.9167 |
| T7 | 40 | 0.675 | 0.825 | 0.7417 |
| T8 | 40 | 0.775 | 0.975 | 0.8667 |
| T9 | 12 | 0.6667 | 0.9167 | 0.7778 |
| OVERALL | 163 | 0.7239 | 0.8896 | 0.7996 |

## Engine Beneath

- Cases: 27 — passed 27, failed 0 (PASS)
- Per-case verdicts and checks: `eval/results/baseline-1.0.0.json`

## Parity

- `eval/results/parity-matrix-1.0.0.md` (four-column matrix, parity on shared retrieval core)
