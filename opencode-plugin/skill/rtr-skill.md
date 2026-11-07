<!-- SPDX-FileCopyrightText: Nova-Violet Role ORG -->
<!-- SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later -->
# RTR-RE:Symbiose Keeper — shared ruleset

This file is the single source of the Keeper's operating rules. It is
loadable by both hosts: the JS Keeper (`rtr-re-keeper.js`) and the mjs
plugin framework (`mjs/framework/rtr-keeper-framework.mjs`). One body,
two hosts — the cross mjs-js skill (TODO-65 P6).

## Office

The Keeper owns the live window. On every request it estimates the
visible token window; above TRIGGER it keeps a bounded verbatim tail
(TARGET), sinks the evicted spans verbatim (NDATA masked) to
`directives/sessions/` for the RTR memory MCP index, and only then
rewrites the outgoing message list. If the sink fails, nothing is
evicted (fail-open): substance is never lost to a failed write.

## Keep rules

- Newest-first tail: keep the newest messages up to TARGET tokens.
- Tool-pair fixpoint: a tool result is kept with its call.
- Protected tools (`todowrite`) are always kept while protected.
- The last user message is always kept.
- Recency-aware protection: past 1000 cumulative messages, only recent
  protected messages stay hard-protected (TODO-45).

## Live control

- Bounds/enabled/maxKeep come from plugin options > project config file
  (`.opencode/rtr-re-keeper.json`, reloaded when its mtime changes) >
  env > defaults.
- The `/rtr` command family (status, hold, trigger, target, max, preset,
  cpu, modality, threads, parking, enable, disable) writes that file, so
  the next exchange already runs the new bounds. The same verbs work in
  plain chat via the prompt-level parser (P1).
- The registry is reloaded when the registry file changes on disk
  (finding d): newly added presets resolve without a restart.

## Status

Every transform writes a status file (`.opencode/rtr-re-keeper-status.json`)
the MCP viewport reads. A one-line reminder rides the conversation every
10 exchanges; the full status is injected on the first exchange (P2).
