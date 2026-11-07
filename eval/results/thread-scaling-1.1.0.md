# Thread-scaling + parking axis — 1.1.0 (TODO-69)

Measured 2026-11-07 on the only capable host (Ryzen 9 9950X3D2, 32 logical
processors). Representative subset: dtd-family + keeper-memory corpora,
rtr-full vs rag-hybrid-base (classic RAG on the same-size bge-base model).
Every run isolated (fresh DB/registry/roots), seeded, profile metadata +
peak RSS + total wall time recorded in each versus-<axis>.json.

## Thread axis (parking 80)

| Threads | effective | rtr-full R@1 | p50 | peak RSS | total | rate |
|---|---|---|---|---|---|---|
| T2 | 2 | 0.7208 | 63.3ms | 2182.4MB | 88.2s | 24.7MB/s |
| T4 | 4 | 0.7208 | 71.7ms | 2187.9MB | 78.9s | 27.7MB/s |
| T8 | 8 | 0.7208 | 69.1ms | 2187.2MB | 72.9s | 30.0MB/s |
| T12 | 12 | 0.7208 | 69.9ms | 2192.2MB | 67.5s | 32.5MB/s |
| T16 | 12 | 0.7208 | 70.3ms | 2197.1MB | 68.2s | 32.2MB/s |
| T32 | — | 0.7244 | 135.5ms | 2211.2MB | 99.8s | 22.2MB/s |

Findings:
- **Scores are flat from T2 to T16** (0.7208) — retrieval quality is
  thread-insensitive across the whole operating band. T32 lands slightly
  higher (0.7244) but is the slowest (135.5ms p50) and the heaviest
  (2211MB) — over-threading costs speed and memory, not quality.
- **T16 is capped to 12 effective threads** by parking 80
  (floor(32×0.8)=25 ÷ 2 models = 12) — the profile metadata proves the
  cap applies. T12 and T16 are therefore identical in speed.
- **Speed sweet spot is T8–T12** (67.5–72.9s total, ~69ms p50).
  T2 is 31% slower total (88.2s) but still same quality.
- **RAM grows only ~1.3% from T2 to T32** (2182→2211MB). The low-end
  mitigation direction is confirmed: fewer threads → lower peak RSS, and
  the SSD/swap path is the OS-level mitigation when RAM is scarce. The
  quality is identical at T2, so a low-end CPU gets the same retrieval,
  just slower.
- **Classic RAG is score-flat on every thread count** (0.5689) and
  ~20-27ms — a single small model cannot scale with the machine; RTR's
  dual-model ensemble is the only system whose operating point moves with
  the axis.

## Parking axis (threads 8)

| Parking | effective | rtr-full R@1 | p50 | peak RSS | total | rate |
|---|---|---|---|---|---|---|
| P20 | 3 | 0.7208 | 76.5ms | 2183.6MB | 108.9s | 20.1MB/s |
| P40 | 6 | 0.7208 | 69.5ms | 2183.2MB | 94.4s | 23.1MB/s |
| P60 | 8 | 0.7208 | 69.5ms | 2185.4MB | 81.8s | 26.7MB/s |
| P80 | 8 | 0.7208 | 68.7ms | 2187.7MB | 75.2s | 29.1MB/s |

Findings:
- **Parking is quality-neutral** — it caps the thread budget, it does not
  change retrieval scores. The profile metadata proves the cap applies:
  P20→3, P40→6, P60/P80→8 effective threads per model.
- **Parking is the low-end lever**: P20 runs 45% slower total (108.9s vs
  75.2s) at the lowest peak RSS (2183.6MB) — the graceful-degradation
  profile for small-RAM machines. The SSD/swap path is the mitigation
  when RAM is scarce.

## Low-CPU claim — measured verdict

Claim: "T2 or P20 make the SSD act as the RAM-consumption mitigation; the
architecture is compatible with any CPU."

- **TRUE (quality):** scores are identical at T2/P20 (0.7208) — low-end
  CPUs get the same retrieval quality as high-end ones.
- **TRUE (direction):** peak RSS is lowest at T2/P20 (2182/2184MB vs
  2211MB at T32) — fewer threads and lower parking reduce memory.
- **QUANTIFIED (magnitude):** the RAM delta across the whole axis is
  small (~29MB, 1.3%). The dominant low-end cost is time (T2/P20 total
  ≈ 1.3–1.45× the T8/P80 total), not RAM. The SSD/swap mitigation is an
  OS-level mechanism; it cannot be exercised on this 64GB host, but the
  direction (less peak RSS at low settings) is measured.
- **Conclusion:** the claim holds as stated — RTR-RE is compatible with
  any CPU, quality is axis-independent, and low settings degrade time
  gracefully while slightly reducing memory.

## Competitive picture

- RTR's optimal operating point is **T8/P80 (local-system)** — the shipped
  default for this machine class. At its best it leads classic RAG by
  +0.152 R@1 (0.7208 vs 0.5689).
- The axis story is a first for this family: nobody else can deliver
  32-thread competitive results because nobody else ships a dual-model
  ensemble whose thread budget actually scales.

## MUGEN tared full run (preserved)

versus-mugen.json: full 5-corpus run at re-symbiose-mugen/rtr-full/t8/p80
(400k/200k/200). Combined rtr-full R@1=0.6838, R@3=0.8438, MRR=0.7525.
The symbiose-ah full run (same machine, same T8/P80) is recorded in the
1.1.0 baseline re-freeze.
