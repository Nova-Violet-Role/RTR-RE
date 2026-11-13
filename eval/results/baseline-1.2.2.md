# RTR-RE baseline — 1.2.2 (frozen, TODO-29/68)

- Frozen at: 2026-11-13T04:44:26
- Release arc: 1.2.2
- Source manifest (sha256):
  - `versus`: `1c086472b7ccd8af31da1a32397594e36dd695edca22071dc8474563b538d596`
  - `engine_beneath`: `e8964a9ca74856d5d8d1431e33b9208c7864afd538da3dcdc5b2aeb80dde865a`
  - `parity_matrix`: `9757cb2154a029f2e8b49464805097c9d9ef36a9b89cf251326979d8336be330`

## Retrieval — overall per corpus × system

| Corpus | System | n | R@1 | R@3 | MRR | p50 ms |
|---|---|---|---|---|---|---|
| dita-spec | rag-dense | 169 | 0.6568 | 0.7574 | 0.7022 | 3.1 |
| dita-spec | rag-dense-base | 169 | 0.6391 | 0.7278 | 0.6795 | 9.3 |
| dita-spec | rag-hybrid | 169 | 0.929 | 0.9467 | 0.9359 | 5.6 |
| dita-spec | rag-hybrid-base | 169 | 0.8698 | 0.8935 | 0.8787 | 11.3 |
| dita-spec | rtr-arctic | 169 | 0.929 | 0.9586 | 0.9398 | 14.5 |
| dita-spec | rtr-bge | 169 | 0.8698 | 0.8935 | 0.8787 | 13.3 |
| dita-spec | rtr-full | 169 | 0.9467 | 0.9645 | 0.9536 | 24.8 |
| dtd-commands | rag-dense | 213 | 0.3803 | 0.5164 | 0.4413 | 3.3 |
| dtd-commands | rag-dense-base | 213 | 0.3897 | 0.5258 | 0.4523 | 9.2 |
| dtd-commands | rag-hybrid | 213 | 0.4836 | 0.5775 | 0.5235 | 4.1 |
| dtd-commands | rag-hybrid-base | 213 | 0.4883 | 0.5728 | 0.5266 | 10.0 |
| dtd-commands | rtr-arctic | 213 | 0.5587 | 0.6385 | 0.5915 | 23.3 |
| dtd-commands | rtr-bge | 213 | 0.4883 | 0.5728 | 0.5266 | 15.8 |
| dtd-commands | rtr-full | 213 | 0.5446 | 0.6573 | 0.5939 | 35.5 |
| dtd-family | rag-dense | 285 | 0.3228 | 0.4842 | 0.3895 | 3.5 |
| dtd-family | rag-dense-base | 285 | 0.3053 | 0.4351 | 0.3614 | 9.0 |
| dtd-family | rag-hybrid | 285 | 0.593 | 0.7263 | 0.6538 | 18.5 |
| dtd-family | rag-hybrid-base | 285 | 0.5509 | 0.6737 | 0.6064 | 20.7 |
| dtd-family | rtr-arctic | 285 | 0.7333 | 0.8667 | 0.7912 | 46.3 |
| dtd-family | rtr-bge | 285 | 0.6491 | 0.8105 | 0.7222 | 38.5 |
| dtd-family | rtr-full | 285 | 0.7193 | 0.8947 | 0.7959 | 65.8 |
| keeper-memory | rag-dense | 40 | 0.1 | 0.475 | 0.2875 | 4.0 |
| keeper-memory | rag-dense-base | 40 | 0.025 | 0.5 | 0.2625 | 8.4 |
| keeper-memory | rag-hybrid | 40 | 0.675 | 0.675 | 0.675 | 4.4 |
| keeper-memory | rag-hybrid-base | 40 | 0.8 | 0.8 | 0.8 | 9.5 |
| keeper-memory | rtr-arctic | 40 | 0.875 | 0.875 | 0.875 | 14.1 |
| keeper-memory | rtr-bge | 40 | 0.8 | 0.8 | 0.8 | 12.8 |
| keeper-memory | rtr-full | 40 | 0.95 | 0.95 | 0.95 | 22.8 |
| nt-studies | rag-dense | 191 | 0.3508 | 0.6126 | 0.4703 | 3.2 |
| nt-studies | rag-dense-base | 191 | 0.4136 | 0.5916 | 0.4904 | 9.0 |
| nt-studies | rag-hybrid | 191 | 0.6073 | 0.7487 | 0.6667 | 5.2 |
| nt-studies | rag-hybrid-base | 191 | 0.623 | 0.7277 | 0.6693 | 11.0 |
| nt-studies | rtr-arctic | 191 | 0.6492 | 0.8377 | 0.7277 | 15.1 |
| nt-studies | rtr-bge | 191 | 0.6283 | 0.7277 | 0.6719 | 13.9 |
| nt-studies | rtr-full | 191 | 0.6649 | 0.8586 | 0.7469 | 25.9 |

## DTD family — rtr-full taxon detail

| Taxon | n | R@1 | R@3 | MRR |
|---|---|---|---|---|
| T1 | 32 | 0.7188 | 0.875 | 0.7917 |
| T10 | 21 | 0.8571 | 1.0 | 0.9127 |
| T11 | 40 | 0.425 | 0.775 | 0.5708 |
| T12 | 40 | 0.725 | 0.95 | 0.8208 |
| T2 | 40 | 0.85 | 0.875 | 0.8625 |
| T6 | 20 | 0.9 | 1.0 | 0.95 |
| T7 | 40 | 0.625 | 0.8 | 0.7 |
| T8 | 40 | 0.8 | 0.975 | 0.8792 |
| T9 | 12 | 0.75 | 0.9167 | 0.8333 |
| OVERALL | 285 | 0.7193 | 0.8947 | 0.7959 |
| OVERALL_MACRO | 285 | 0.739 | 0.9074 | 0.8134 |

## Engine Beneath

- Cases: 27 — passed 27, failed 0 (PASS)
- Per-case verdicts and checks: `eval/results/baseline-1.2.2.json`

## Parity

- `eval/results/parity-matrix-1.0.0.md` (four-column matrix, parity on shared retrieval core)
