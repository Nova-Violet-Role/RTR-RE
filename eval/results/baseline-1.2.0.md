# RTR-RE baseline — 1.2.0 (frozen, TODO-29/68)

- Frozen at: 2026-11-10T20:04:10
- Release arc: 1.2.0
- Source manifest (sha256):
  - `versus`: `411b359b5860b48d52a10b69855a6c1a0950210c479d728f02536cf09581c7c7`
  - `engine_beneath`: `130b26df7dc0d150aa1ccb89467c352369831c549f5bf50805320825c94a75a4`
  - `parity_matrix`: `9757cb2154a029f2e8b49464805097c9d9ef36a9b89cf251326979d8336be330`

## Retrieval — overall per corpus × system

| Corpus | System | n | R@1 | R@3 | MRR | p50 ms |
|---|---|---|---|---|---|---|
| dita-spec | rag-dense | 77 | 0.7273 | 0.7922 | 0.7576 | 3.4 |
| dita-spec | rag-dense-base | 77 | 0.7013 | 0.7532 | 0.7273 | 8.7 |
| dita-spec | rag-hybrid | 77 | 0.9351 | 0.9481 | 0.9394 | 5.9 |
| dita-spec | rag-hybrid-base | 77 | 0.8701 | 0.8961 | 0.8788 | 11.3 |
| dita-spec | rtr-arctic | 77 | 0.9091 | 0.9351 | 0.9177 | 15.3 |
| dita-spec | rtr-bge | 77 | 0.8701 | 0.8961 | 0.8788 | 14.3 |
| dita-spec | rtr-full | 77 | 0.9351 | 0.9481 | 0.9394 | 25.5 |
| dtd-commands | rag-dense | 97 | 0.2887 | 0.4639 | 0.3677 | 2.9 |
| dtd-commands | rag-dense-base | 97 | 0.3505 | 0.4742 | 0.4055 | 6.8 |
| dtd-commands | rag-hybrid | 97 | 0.4124 | 0.5258 | 0.4622 | 3.2 |
| dtd-commands | rag-hybrid-base | 97 | 0.4536 | 0.5361 | 0.4897 | 7.7 |
| dtd-commands | rtr-arctic | 97 | 0.4742 | 0.5773 | 0.5189 | 19.3 |
| dtd-commands | rtr-bge | 97 | 0.4536 | 0.5361 | 0.4897 | 13.3 |
| dtd-commands | rtr-full | 97 | 0.4742 | 0.5979 | 0.5275 | 32.8 |
| dtd-family | rag-dense | 243 | 0.2757 | 0.4362 | 0.3409 | 3.1 |
| dtd-family | rag-dense-base | 243 | 0.2716 | 0.4239 | 0.3374 | 7.4 |
| dtd-family | rag-hybrid | 243 | 0.5391 | 0.6914 | 0.6084 | 17.8 |
| dtd-family | rag-hybrid-base | 243 | 0.5144 | 0.6543 | 0.5782 | 21.9 |
| dtd-family | rtr-arctic | 243 | 0.716 | 0.8683 | 0.7819 | 55.8 |
| dtd-family | rtr-bge | 243 | 0.6296 | 0.8148 | 0.714 | 46.2 |
| dtd-family | rtr-full | 243 | 0.6914 | 0.893 | 0.7791 | 78.0 |
| keeper-memory | rag-dense | 40 | 0.05 | 0.45 | 0.25 | 3.7 |
| keeper-memory | rag-dense-base | 40 | 0.2 | 0.525 | 0.3625 | 9.1 |
| keeper-memory | rag-hybrid | 40 | 0.7 | 0.7 | 0.7 | 4.9 |
| keeper-memory | rag-hybrid-base | 40 | 0.9 | 0.9 | 0.9 | 9.9 |
| keeper-memory | rtr-arctic | 40 | 0.85 | 0.85 | 0.85 | 14.3 |
| keeper-memory | rtr-bge | 40 | 0.9 | 0.9 | 0.9 | 12.9 |
| keeper-memory | rtr-full | 40 | 0.975 | 0.975 | 0.975 | 26.0 |
| nt-studies | rag-dense | 87 | 0.3333 | 0.6207 | 0.4579 | 4.1 |
| nt-studies | rag-dense-base | 87 | 0.3678 | 0.5862 | 0.4579 | 9.1 |
| nt-studies | rag-hybrid | 87 | 0.5632 | 0.7241 | 0.6284 | 5.7 |
| nt-studies | rag-hybrid-base | 87 | 0.5172 | 0.6667 | 0.5805 | 11.3 |
| nt-studies | rtr-arctic | 87 | 0.5747 | 0.8046 | 0.6648 | 17.9 |
| nt-studies | rtr-bge | 87 | 0.5287 | 0.6667 | 0.5862 | 16.5 |
| nt-studies | rtr-full | 87 | 0.5747 | 0.8391 | 0.6839 | 31.5 |

## DTD family — rtr-full taxon detail

| Taxon | n | R@1 | R@3 | MRR |
|---|---|---|---|---|
| T1 | 32 | 0.7188 | 0.875 | 0.7917 |
| T10 | 21 | 0.8571 | 1.0 | 0.9127 |
| T11 | 40 | 0.425 | 0.775 | 0.5708 |
| T12 | 40 | 0.725 | 0.95 | 0.8208 |
| T2 | 12 | 0.8333 | 0.9167 | 0.875 |
| T6 | 6 | 0.8333 | 1.0 | 0.9167 |
| T7 | 40 | 0.625 | 0.8 | 0.7 |
| T8 | 40 | 0.8 | 0.975 | 0.8792 |
| T9 | 12 | 0.75 | 0.9167 | 0.8333 |
| OVERALL | 243 | 0.6914 | 0.893 | 0.7791 |
| OVERALL_MACRO | 243 | 0.7297 | 0.912 | 0.8111 |

## Engine Beneath

- Cases: 27 — passed 27, failed 0 (PASS)
- Per-case verdicts and checks: `eval/results/baseline-1.2.0.json`

## Parity

- `eval/results/parity-matrix-1.0.0.md` (four-column matrix, parity on shared retrieval core)
