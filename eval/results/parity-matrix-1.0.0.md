<!-- SPDX-FileCopyrightText: Nova-Violet Role ORG -->
<!-- SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later -->
# Parity matrix RTR vs RTR-RE — 1.0.0 release arc (measured at 0.5.0 code, 2026-11-06)

Product boundary (operator-defined, governs every classification):

- **RTR = the engine**: retrieval only.
- **RTR-RE = the full car**: retrieval + Compressor + Keeper + installer + TUI surface.
- The only things they share: the evaluations, MCP/no-MCP running through the
  Optimizer, and every retrieval improvement — without compromising that RE
  also contains Compressor and Keeper.
- Engine Beneath differs by design: RE evaluates the full architecture
  (Keeper+Compressor+Manager+retrieval) in richer 3D form; RTR evaluates
  retrieval alone in static SVG/Mermaid. That is RTR-RE-only scope, never a
  defect.

## Four columns

| Surface | RTR MCP | RTR no-MCP | RTR-RE MCP | RTR-RE no-MCP |
|---|---|---|---|---|
| memory_engine.py (retrieval) | identical | identical | identical | identical |
| memory_mcp_server.py (26 tools) | identical | — | identical | — |
| memory_cli.py (rtr-cli) | identical | identical | identical | identical |
| rtr_presets.json (registry) | identical | identical | identical | identical |
| mjs/rtr-core.js (Optimizer) | identical | identical | identical | identical |
| mjs/rtr.mjs (plugin) | identical | identical | identical | identical |
| rtr-re-keeper.test.mjs | identical | identical | identical | identical |
| Keeper plugin (rtr-re-keeper.js) | legacy copy | legacy copy | live (config+status) | live |
| Compressor (context_budget.py) | absent | absent | present | present |
| TUI palette (rtr-re-tui.tsx) | absent | absent | present | present |
| Engine Beneath evaluation | retrieval-only SVG/Mermaid | same | full 3D | full 3D |
| acp.jsonc | legacy leftover | legacy leftover | absent | absent |
| Installer (install_opencode.py) | installs keeper (legacy) | — | installs keeper + registry | — |

## Executed scenarios (measured at 0.5.0 code, 1.0.0 release arc)

1. MCP tool listing via asyncio list_tools: RE 26 / RTR 26, IDENTICAL sets.
2. Byte-identity: memory_engine.py, memory_mcp_server.py, memory_cli.py,
   rtr_presets.json, rtr-re-keeper.test.mjs, mjs/rtr-core.js, mjs/rtr.mjs —
   all identical (sha256).
3. Installer diff: 1 docstring line only (RE lacks the "No ACP plugin" line);
   functionally identical — both install the keeper.
4. Keeper JS diff: 2 comment lines only (RTR still claims "keeper-only
   posture"); functionally identical.
5. Live wiring: RE has .opencode/rtr-re-keeper.json + status (preset
   symbiose-ah, max 200) and the TUI plugin in the live plugin dir; RTR has
   no live keeper config and no TUI plugin.

## Classification

| Asymmetry | Class | Action |
|---|---|---|
| Keeper + Compressor + TUI + full Engine Beneath only in RE | RTR-RE-only (by design) | none — this is the car |
| acp.jsonc in RTR | legacy leftover | remove before RTR ships engine-only (TODO-40) |
| RTR keeper installer/JS still claiming keeper-only posture | legacy leftover | remove or reword before RTR ships engine-only (TODO-40) |
| Engine Beneath 3D vs static | RTR-RE-only (by design) | keep separate, never conflate |
| Retrieval core byte-identical | PARITY | none — verified |

No measured defects found in the shared retrieval core. The only repairs are
the RTR legacy leftovers, which belong to the engine-only release cleanup
(TODO-40), not to parity.
