<!-- SPDX-License-Identifier: AGPL-3.0-or-later OR EUPL-1.2 -->
# Amplify ledger: C:\RTR (2026-10-26, autonomous, band amplify 1-5)

Instruments first: ruff (7 F541 found), uv unit runs, git log. Gaps before ideas.

## Gaps (measured)

- gap args-mcp-f541 verb 1 tweak confidence measured verdict done: 7 placeholder-free f-strings in execution/memory_mcp_server.py (ruff F541). Evidence: ruff check output. Cost: 1 file, risk low. Fixed by ruff --fix, re-check clean.
- gap generic-compressor-host verb 3 ameliorate confidence measured verdict done: _SUMMARIZER_HOST could be None for host-less URL (LSP + read compressor.py). Guard added with upstream default host. Cost: 1 file, risk low.
- gap record-vendored-provenance verb 2 enrich confidence measured verdict done: rolling-context/ and opencode-acp/ untracked with no pin record (git status ??). VENDORED.md added with commits 6fc6407 / 98a16d5b and local-change list. Cost: 1 file, risk low.
- gap args-search-optional verb 3 ameliorate confidence measured verdict exposed: LSP: engine.search(project: str) called with None at memory_mcp_server.py:91,251,570. Real fix touches memory_engine.py signatures (pre-existing local modification in tree); deferred to evaluation to avoid colliding with unreviewed local edits. Cost: 2 files, risk medium.

## Ideas (reasoned; adds named)

- idea generic-rtrre-config verb 4 amplification confidence reasoned verdict done: adds rolling_config() + OPENCODE_MEMORY_RTRRE_* knobs in execution/context_budget.py.
- idea generic-rtrre-worker verb 5 magnify confidence reasoned verdict done: adds execution/rolling_worker.py (background, hash cache, cooldown, bounded queue).
- idea record-span-sink verb 4 amplification confidence reasoned verdict done: adds SessionSpanSink writing directives/sessions/rtrre-*.md, both lanes verbatim typed.
- idea report-context-plan-config verb 2 enrich confidence reasoned verdict done: memory_context_plan now prints effective config + source per knob.

## Above band (never silently kept)

- next_verb 6 heighten command enhance-codebase-dtd: live percentile measurement of context under the worker after restart.
- next_verb 14 overhaul command overhaul-codebase-dtd: replace synchronous index_all with the async worker pipeline end-to-end.

Release (recognizer): class minor, from 0.3.0 to 0.3.1, taken no. Kept verbs 1-5 move no segment above minor; "major" in scale is not major in version until an overhaul verb is kept.
