# RTR-RE baseline — 1.2.0 (frozen, TODO-29/68)

- Frozen at: 2026-11-11T18:34:47
- Release arc: 1.2.0
- Source manifest (sha256):
  - `versus`: `d3dd96c63284f329490ab081e70ddf074ad08b2b211dc6f134e1c9b2f125ea2e`
  - `engine_beneath`: `aff3e4593073dd31c64784505cecef17f179307e0c51a9168fe23c32bcb44b55`
  - `parity_matrix`: `9757cb2154a029f2e8b49464805097c9d9ef36a9b89cf251326979d8336be330`

## Retrieval — overall per corpus × system

| Corpus | System | n | R@1 | R@3 | MRR | p50 ms |
|---|---|---|---|---|---|---|
| dita-spec | rag-dense | 169 | 0.6568 | 0.7574 | 0.7022 | 2.9 |
| dita-spec | rag-dense-base | 169 | 0.6391 | 0.7278 | 0.6795 | 8.0 |
| dita-spec | rag-hybrid | 169 | 0.929 | 0.9467 | 0.9359 | 5.0 |
| dita-spec | rag-hybrid-base | 169 | 0.8698 | 0.8935 | 0.8787 | 10.0 |
| dita-spec | rtr-arctic | 169 | 0.929 | 0.9586 | 0.9398 | 13.1 |
| dita-spec | rtr-bge | 169 | 0.8698 | 0.8935 | 0.8787 | 12.4 |
| dita-spec | rtr-full | 169 | 0.9467 | 0.9645 | 0.9536 | 23.3 |
| dtd-commands | rag-dense | 213 | 0.3803 | 0.5164 | 0.4413 | 2.6 |
| dtd-commands | rag-dense-base | 213 | 0.3897 | 0.5258 | 0.4523 | 7.6 |
| dtd-commands | rag-hybrid | 213 | 0.4836 | 0.5775 | 0.5235 | 3.4 |
| dtd-commands | rag-hybrid-base | 213 | 0.4883 | 0.5728 | 0.5266 | 9.4 |
| dtd-commands | rtr-arctic | 213 | 0.5587 | 0.6385 | 0.5915 | 21.6 |
| dtd-commands | rtr-bge | 213 | 0.4883 | 0.5728 | 0.5266 | 13.9 |
| dtd-commands | rtr-full | 213 | 0.5446 | 0.6573 | 0.5923 | 32.7 |
| dtd-family | rag-dense | 285 | 0.3263 | 0.4912 | 0.3947 | 3.3 |
| dtd-family | rag-dense-base | 285 | 0.2982 | 0.4351 | 0.3567 | 8.1 |
| dtd-family | rag-hybrid | 285 | 0.593 | 0.7263 | 0.6538 | 18.4 |
| dtd-family | rag-hybrid-base | 285 | 0.5474 | 0.6702 | 0.6029 | 18.7 |
| dtd-family | rtr-arctic | 285 | 0.7228 | 0.8702 | 0.7871 | 39.7 |
| dtd-family | rtr-bge | 285 | 0.6491 | 0.807 | 0.7205 | 35.3 |
| dtd-family | rtr-full | 285 | 0.7263 | 0.9018 | 0.8023 | 57.2 |
| keeper-memory | rag-dense | 40 | 0.05 | 0.45 | 0.25 | 3.3 |
| keeper-memory | rag-dense-base | 40 | 0.2 | 0.525 | 0.3625 | 8.5 |
| keeper-memory | rag-hybrid | 40 | 0.7 | 0.7 | 0.7 | 4.0 |
| keeper-memory | rag-hybrid-base | 40 | 0.9 | 0.9 | 0.9 | 9.1 |
| keeper-memory | rtr-arctic | 40 | 0.85 | 0.85 | 0.85 | 12.6 |
| keeper-memory | rtr-bge | 40 | 0.9 | 0.9 | 0.9 | 11.3 |
| keeper-memory | rtr-full | 40 | 0.975 | 0.975 | 0.975 | 23.3 |
| nt-studies | rag-dense | 191 | 0.3508 | 0.6126 | 0.4703 | 2.6 |
| nt-studies | rag-dense-base | 191 | 0.4136 | 0.5916 | 0.4904 | 7.4 |
| nt-studies | rag-hybrid | 191 | 0.6073 | 0.7487 | 0.6667 | 4.3 |
| nt-studies | rag-hybrid-base | 191 | 0.623 | 0.7277 | 0.6693 | 9.9 |
| nt-studies | rtr-arctic | 191 | 0.6492 | 0.8377 | 0.7277 | 13.3 |
| nt-studies | rtr-bge | 191 | 0.6283 | 0.7277 | 0.6719 | 12.7 |
| nt-studies | rtr-full | 191 | 0.6649 | 0.8586 | 0.7469 | 23.6 |

## DTD family — rtr-full taxon detail

| Taxon | n | R@1 | R@3 | MRR |
|---|---|---|---|---|
| T1 | 32 | 0.7188 | 0.875 | 0.7917 |
| T10 | 21 | 0.8571 | 1.0 | 0.9127 |
| T11 | 40 | 0.475 | 0.8 | 0.6083 |
| T12 | 40 | 0.725 | 0.95 | 0.8208 |
| T2 | 40 | 0.85 | 0.875 | 0.8625 |
| T6 | 20 | 0.9 | 1.0 | 0.95 |
| T7 | 40 | 0.65 | 0.825 | 0.725 |
| T8 | 40 | 0.775 | 0.975 | 0.8625 |
| T9 | 12 | 0.75 | 0.9167 | 0.8333 |
| OVERALL | 285 | 0.7263 | 0.9018 | 0.8023 |
| OVERALL_MACRO | 285 | 0.7445 | 0.913 | 0.8185 |

## Engine Beneath

- Cases: 27 — passed 27, failed 0 (PASS)
- Per-case verdicts and checks: `eval/results/baseline-1.2.0.json`

## Parity

- `eval/results/parity-matrix-1.0.0.md` (four-column matrix, parity on shared retrieval core)
