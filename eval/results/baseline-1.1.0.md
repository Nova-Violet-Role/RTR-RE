# RTR-RE baseline — 1.1.0 (frozen, TODO-29/68)

- Frozen at: 2026-11-07T20:58:11
- Release arc: 1.1.0
- Source manifest (sha256):
  - `versus`: `6deeb7003d830fd55b2f6a8f0675e6f541fb40c84ebd99539aec12af7fd93286`
  - `engine_beneath`: `34b747e9af4c34af10882c4aaba8a57ce9fac61337f1954cb33a3fb0de8485ff`
  - `parity_matrix`: `9757cb2154a029f2e8b49464805097c9d9ef36a9b89cf251326979d8336be330`

## Retrieval — overall per corpus × system

| Corpus | System | n | R@1 | R@3 | MRR | p50 ms |
|---|---|---|---|---|---|---|
| dita-spec | rag-dense | 77 | 0.7273 | 0.7922 | 0.7576 | 3.3 |
| dita-spec | rag-dense-base | 77 | 0.7013 | 0.7532 | 0.7273 | 8.0 |
| dita-spec | rag-hybrid | 77 | 0.9351 | 0.9481 | 0.9394 | 5.4 |
| dita-spec | rag-hybrid-base | 77 | 0.8701 | 0.8961 | 0.8788 | 10.3 |
| dita-spec | rtr-arctic | 77 | 0.9091 | 0.9351 | 0.9177 | 13.4 |
| dita-spec | rtr-bge | 77 | 0.8701 | 0.8961 | 0.8788 | 12.6 |
| dita-spec | rtr-full | 77 | 0.9351 | 0.9481 | 0.9394 | 24.0 |
| dtd-commands | rag-dense | 97 | 0.2887 | 0.4639 | 0.3677 | 3.0 |
| dtd-commands | rag-dense-base | 97 | 0.3505 | 0.4742 | 0.4055 | 8.0 |
| dtd-commands | rag-hybrid | 97 | 0.4124 | 0.5258 | 0.4622 | 3.4 |
| dtd-commands | rag-hybrid-base | 97 | 0.4536 | 0.5361 | 0.4897 | 8.2 |
| dtd-commands | rtr-arctic | 97 | 0.4742 | 0.5773 | 0.5189 | 19.5 |
| dtd-commands | rtr-bge | 97 | 0.4536 | 0.5361 | 0.4897 | 14.0 |
| dtd-commands | rtr-full | 97 | 0.4845 | 0.6082 | 0.5378 | 31.4 |
| dtd-family | rag-dense | 243 | 0.2716 | 0.4156 | 0.3299 | 3.5 |
| dtd-family | rag-dense-base | 243 | 0.2675 | 0.4156 | 0.332 | 8.0 |
| dtd-family | rag-hybrid | 243 | 0.5185 | 0.6872 | 0.596 | 18.2 |
| dtd-family | rag-hybrid-base | 243 | 0.5021 | 0.6502 | 0.57 | 19.2 |
| dtd-family | rtr-arctic | 243 | 0.6955 | 0.856 | 0.7654 | 45.2 |
| dtd-family | rtr-bge | 243 | 0.6173 | 0.8107 | 0.7058 | 38.2 |
| dtd-family | rtr-full | 243 | 0.6749 | 0.8807 | 0.7641 | 64.6 |
| keeper-memory | rag-dense | 40 | 0.075 | 0.5 | 0.2875 | 3.5 |
| keeper-memory | rag-dense-base | 40 | 0.325 | 0.85 | 0.5875 | 8.3 |
| keeper-memory | rag-hybrid | 40 | 0.85 | 0.85 | 0.85 | 4.3 |
| keeper-memory | rag-hybrid-base | 40 | 0.975 | 0.975 | 0.975 | 8.9 |
| keeper-memory | rtr-arctic | 40 | 0.75 | 0.75 | 0.75 | 12.2 |
| keeper-memory | rtr-bge | 40 | 0.975 | 0.975 | 0.975 | 11.5 |
| keeper-memory | rtr-full | 40 | 1.0 | 1.0 | 1.0 | 23.9 |
| nt-studies | rag-dense | 87 | 0.3333 | 0.6207 | 0.4579 | 4.2 |
| nt-studies | rag-dense-base | 87 | 0.3678 | 0.5862 | 0.4579 | 9.3 |
| nt-studies | rag-hybrid | 87 | 0.5632 | 0.7241 | 0.6284 | 6.0 |
| nt-studies | rag-hybrid-base | 87 | 0.5172 | 0.6667 | 0.5805 | 10.8 |
| nt-studies | rtr-arctic | 87 | 0.5747 | 0.8046 | 0.6648 | 14.9 |
| nt-studies | rtr-bge | 87 | 0.5287 | 0.6667 | 0.5862 | 14.2 |
| nt-studies | rtr-full | 87 | 0.5747 | 0.8506 | 0.6916 | 27.2 |

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
