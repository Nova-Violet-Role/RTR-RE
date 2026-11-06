<!-- SPDX-License-Identifier: AGPL-3.0-or-later OR EUPL-1.2 -->
<!-- Copyright 2026 Saimonokuma. -->
# Dummy3 + dummy4 survey: current code, calibrated profile, native Keeper

Date: 2026-10-27. Instruments: `opencode-dev run --agent muse-code
--format json`, isolated XDG config/data, MCP env trigger 40000 /
target 20000 (dummy3), same calibration for the Keeper plugin (dummy4).
Turn transcripts are the JSONL event files under each dummy root in
Temp (not shipped); every claim below names the tool result inside them,
never the agent's OK marker alone.

## Dummy3 (ACP keeper-only wiring, current engine code)

- T1: index scanned 1/new 1, plan reported env 40000/20000 — but planted
  searches (HELIX-204, UMBRA-618, project `rtrre-dummy3`) returned
  **0 results**. Fronted, not smoothed: direct engine probe with the
  identical env found both facts at 0.9696, and the recorded tool args
  showed the agent passing the root name as the project ref.
  Root cause: `project_filter_key` returned the root name as a metadata
  equality key while index time keyed the file under `project`. Fixed:
  root refs resolve to no-filter in search/list/deltas, absolute refs
  resolve through discovery scopes (red tests first, both measured).
- T2 (same session, fixed code): both searches found the planted file
  (0.9695); plan decisions 20000 keep / 40000 keep / 40001 compress.
- T3 exposed the sibling defect: the eviction sink landed in
  `C:\Users\Saimono\projects\rtrre-dummy3\...` — `resolve_project_dir`
  fell back to a hardcoded home `PROJECTS_DIR`, outside the isolated
  roots, so the sink was never indexed (search missed the marker).
  Fixed: `PROJECTS_DIR` follows the first configured discovery root and
  a bare root name resolves to the root itself. Leaked directory removed.
- T4: submit ready (evicted 21, keep 18010 of 60010), sink inside the
  isolated root, index scanned 2/new 1, search for the evicted marker
  hit the sink file at 0.9700. Full loop through the MCP surface.

## Dummy4 (native Keeper, no ACP plugin, no acp.jsonc)

- Setup: cloned config with `plugin/acp.js` deleted, `acp.jsonc`
  deleted, `plugin/rtr-re-keeper.js` installed from the standalone tree.
- First run failed to load the plugin ("Plugin export is not a
  function" in opencode.log): the legacy loader iterates every export.
  Restructured to a single default export (helpers on `server._test`),
  node tests 9/9 green before and after.
- T1: agent reported `ACP-ABSENT` (no compress/decompress/acp_status/
  search_context tools), index+search worked (FJORD-927 at 0.9700),
  two full-file reads completed.
- T3 (after load fix, cumulative window ≈43.9k est. tokens over the
  40k trigger): Keeper evicted — sink
  `project/directives/sessions/rtrre-269353b1815a1a9a.md`
  (110.46 kB, 10 spans, T1 history verbatim). The agent answered
  NO-EVICTION-NOTE to introspection; the sink file is the instrument
  that counts, not the model's self-report.
- T4: index scanned 2/new 1; search for a phrase only present in the
  evicted T1 read returned the sink file as top candidate (0.9618).
  Host-applied eviction → verbatim sink → RTR indexing → retrieval,
  with no ACP anywhere in the loop. This is the first host-applied
  eviction evidence in the project (dummy2 proved the advisory worker).

## Honest limits

- The Keeper note's visibility to the model is unproven (agent denied
  seeing it while the sink proves eviction happened on that request);
  treat the note as best-effort orientation, retrieval as the contract.
- Dummy token counts are the chars/4 estimator on both sides
  (planner and Keeper mirror it); production model counts will differ.
- Live-session proof still requires the operator restart (TODO-14).
