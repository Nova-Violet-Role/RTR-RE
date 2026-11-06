<!-- SPDX-License-Identifier: AGPL-3.0-or-later OR EUPL-1.2 -->
<!-- Copyright 2026 Saimonokuma. -->
# Renovation: RTR-RE:Rolling

- survey: artifacts/geometry/2026-10-26-survey.md (2026-10-26)
- plan: artifacts/geometry/2026-10-26-plan.md (2026-10-26, operator-amended)
- target: C:\RTR
- date: 2026-10-26

## Changes (before -> after)

| verb | file | before | after |
|---|---|---|---|
| 95 consolidation | execution/context_budget.py (new, 5900 B) | no budget owner | RTR-RE:Rolling planner: TRIGGER 200000, TARGET 100000, caps 40 msgs / 20000 summary chars / 4000 restore chars; never mutates input |
| 105 vectorisation | execution/test_context_budget.py (new, 4977 B) | no planner tests | 11 tests incl. no-mutation collision test + verbatim-substance test; RED ModuleNotFoundError -> GREEN OK |
| 106 restructure | execution/memory_mcp_server.py | 19 tools | + memory_context_plan (pure, no ONNX load) |
| 95 consolidation | rolling-context/1.8.0/proxy/compressor.py | summary + tail unbounded, CRLF | cap_summary + kept-message cap (env, defaults 20000/40), LF; proof 108889 -> 19997 chars |
| 107 specification | C:\Users\Saimono\.config\opencode\acp.jsonc (1788 B; backup .bak.20261026, 1721 B) | enabled false, preserve 220000, bash/read protected, reasoning kept, gate floor 4000 | enabled true, max 200000, preserve 100000/40, protected [skill, compress], reasoning.drop true, reserve 32768, gate floor 200 |
| 107 specification | .opencode/acp.jsonc (new, copy of global) | absent | project template, same wiring |
| 108 documentation | directives/context-management.md (new) | absent | RTR-RE:Rolling design note (RTR indexes directives/) |

## Certification (measured)

- `uv run --no-project execution/test_context_budget.py` -> Ran 11 tests, OK.
- Rolling cap check -> in=108889 out=19997 cap=20000, ROLLING-CAP-OK.
- ACP check -> ACP-OK bytes=1788 keys=25 (all keys valid vs config.ts).
- py_compile on all touched .py -> clean. CR check false on all written files.
- Not run: execution/test_memory.py (needs chromadb/fastembed env; memory_engine.py untouched by this renovation — pre-existing local modification, see git status). Live ACP behavior needs OpenCode restart (reasoned, not measured).

## Colophon

Made 2026-10-26 in the main lane, test-first, under AGPL-3.0-or-later OR EUPL-1.2.
Diplomatics: survey and plan predate every change above; bounds in code equal bounds in plan (200000/100000/40/20000/4000).
