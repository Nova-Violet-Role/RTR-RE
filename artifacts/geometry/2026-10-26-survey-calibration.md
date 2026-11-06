<!-- SPDX-License-Identifier: AGPL-3.0-or-later OR EUPL-1.2 -->
<!-- Copyright 2026 Saimonokuma. -->
# Calibrated dummy survey: 40k trigger -> 20k target

Instrument: `opencode-dev` (D:/OPENCODE-SRC/bin/opencode-dev.cmd), agent
muse-code (meta/muse-spark-1.3-contributor), isolated dummy2 config/data/
vector DB/state. Calibration env: OPENCODE_MEMORY_RTRRE_TRIGGER=40000,
OPENCODE_MEMORY_RTRRE_TARGET=20000; Keeper acp.jsonc max=40000,
preserve=20000, permission=deny.

## Local pipeline calibration (eval/calibrate_symbiose.py)

Four sizes x four repetitions, file sink, varied synthetic text. Caller
submit and background completion medians:

| Context | Submit | Complete | Plan | Sink |
|---:|---:|---:|---:|---:|
| 40k | 0.1 ms | 2.1 ms | 1.5 ms | 0.4 ms |
| 100k | 0.2 ms | 4.2 ms | 3.4 ms | 0.5 ms |
| 200k | 0.4 ms | 7.7 ms | 6.7 ms | 0.7 ms |
| 400k | 0.7 ms | 14.9 ms | 13.2 ms | 1.1 ms |

Deployment profile (80k workload, trigger 40k, target 20k): submit
0.2 ms, complete 4.8 ms median (4/4 ready). Tokens/s in generated tables
is a synthetic pipeline upper bound; ONNX indexing is excluded and timed
separately by index/search tools. Generated artifacts are LF bytes.

## Dummy long-session turns 8-12

- T8: plan at 45k = compress; ticket ready but evicted 0. Root cause found
  by debugging: MCP worker singleton ignored calibrated env (library 200k
  default). Fixed by constructing it with `symbiose_config()`.
- T9: token-budgeted 55,010-token submit returned in 0.055 ms; still old
  worker behavior in that server process.
- T10: after fix, submit 0.043 ms, elapsed 0.782 ms, evicted 8 spans /
  40,000 tokens, kept 15,010, sink file written. Compression did not pause
  or rewrite the live conversation.
- T11: facts planted outside the dummy conversation, then index
  (2 new files, 1.30 s) and four searches all recalled exactly:
  ORBIT-117 violet relay; MIRROR-339 blue glass harbor; VELVET-551 amber
  signal bell; XENON-773 three copper moons.
- T12: thresholds verified 20k keep, 40k keep, 40,001 compress, 100k
  compress; four more hidden facts recalled; tiny control submit
  0.034 ms / elapsed 0.075 ms / evicted 0.

## Fortifications discovered during survey

1. Worker now returns ticket timing by stage (hash/submit/queue/plan/sink/
   elapsed + human duration + token/char accounting).
2. MCP worker now consumes deployment `symbiose_config()` instead of silent
   library defaults.
3. SessionSpanSink writes UTF-8 bytes (LF), not Windows-translated CRLF.
4. Engine state paths (registry, extra roots, global lexikon) gained env
   overrides; dummy registry proved isolated and live files untouched.
5. Versus/graded generated artifacts and staged corpora are byte-explicit.

## Honest limits

- The dummy model still sees its own tool arguments in T9/T10; T11 hidden
  facts are the retrieval-only proof. A host-applied window eviction cycle
  remains post-restart live evidence (todo 19), because the worker is
  advisory by collision law.
- Synthetic calibration timings exclude summarizer/LLM and ONNX indexing.
- Rolling tickets are process-scoped; a new MCP process polls old tickets
  as unknown and can resubmit by content hash cheaply.
