<!-- SPDX-FileCopyrightText: Nova-Violet Role ORG -->
<!-- SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later -->
# RTR-RE:Symbiose v1.2.1

Role-Type-Retrieval-RE:Symbiotized — the retriever + full context engine.
CPU-first, local-first, zero API cost.

## What's new since 1.2.0

- **Vector reconciliation.** `memory_repair` now diffs registry-vs-Chroma
  per model, reports live files whose chunks are missing (holes the
  incremental path is hash-blind to), and heals them through the normal
  incremental path. Dry run measures without writing.
- **Abort-safe upserts.** Index writes land before stale ids are pruned
  (add-then-purge), so a timeout or kill mid-wave leaves old vectors
  serving instead of holes; a plain re-run resumes cleanly.
- **Measured:** 526 Python + 33 subtests, 129 JS, Lean green zero
  sorry, ship gate 27/27, behavior gate 8/8, versus rtr-full R@1
  0.7227 / R@3 0.8497 / MRR 0.7769 (installed wheel identical).

# RTR-RE:Symbiose v1.2.0

Role-Type-Retrieval-RE:Symbiotized — the retriever + full context engine.
CPU-first, local-first, zero API cost.

## What's new since 1.1.0

- **One-shot evictions.** `/rtr evict-tokens <n>` and `/rtr evict-messages
  <n>` plus matching ctrl+p palette buttons evict an explicit amount
  oldest-first on the next exchange (self-clearing flags); protections,
  last-user, and tool-pair fixpoint still hold.
- **Manual mode.** Installers offer a manual preset with zero automatic
  trigger/target/max; a palette guide ships into the project memory
  folder for professional manual context care.
- **Scoped indexing.** `index --project` and `memory_index` now scope the
  walk (plus purge) to the named projects instead of broadcasting.
- **Honest benches.** Empty guards, T5 skip-on-seed-failure, T10
  expected-sets, macro overall, bootstrap CIs on both benches, recorded
  corpus skips, computed transfer findings.
- **Verbatim proof.** Span bytes equal message bytes (byte-exact tests);
  NDATA masked, never stored; Chroma carries messages contiguously.
- **Measured:** 519 Python + 33 subtests, 129 JS, Lean green zero
  sorry, ship gate 27/27, behavior gate 8/8, versus rtr-full R@1
  0.7227 / R@3 0.8497 / MRR 0.7769 (installed wheel identical).

## Install

- `uvx --from rtr-role-type-retrieval rtr-mcp` (MCP server)
- `uv tool install rtr-role-type-retrieval` (CLI + installer)
- `npm install rtr-re-opencode-plugin` (OpenCode keeper + ctrl+p palette)
- `npm install @saimonokuma/rtr-re-mjs` (no-MCP memory mode)

## License

AGPL-3.0-or-later OR EUPL-1.2.

---

# RTR-RE:Symbiose v1.1.0

Role-Type-Retrieval-RE:Symbiotized — the retriever + full context engine.
CPU-first, local-first, zero API cost.

## What's new since 1.0.0

- **Keeper Memory 2.0 — the Infinite Memory (MUGEN).** Evicted spans are
  re-digitized as DTD-shaped records into `.opencode/memory/` and become a
  first-class retrieval corpus — eviction is never deletion; the
  infinite-memory claim is measured (span retrieval R@1 1.0 on the
  keeper-memory corpus).
- **DTD family signatures.** Lineage, driver/module role, and
  customization-layer switches are extracted into the inventory header;
  new taxons T11 (lineage discrimination) and T12 (customization-layer
  recognition) join the bench.
- **MUGEN is the shipped default preset** — re-symbiose-mugen
  400k/200k/200.
- **Plugin framework (P1–P6).** Prompt-level `/rtr` commands, split context
  injection, subagent brief propagation, modern hook surface, ESM
  capabilities, and a live registry reload.
- **Thread-scaling + parking measured across all 32 threads** on the
  reference host — quality is axis-flat, RAM delta ~1.3%, degradation is
  graceful. First competitive picture of its kind.
- **Optimizer empowerment** — machine-aware recommendations
  (Recommended from Saimonokuma: 8 threads, P40 on ≥24 cores).

## Measurement (frozen 1.1.0 baseline)

- 5 corpora, 35 systems, 10 taxons, Engine Beneath 27/27.
- rtr-full combined R@1 0.6857 vs classic RAG best 0.5901.
- Keeper-memory corpus R@1 1.0.

## Install

- `uvx --from rtr-role-type-retrieval rtr-mcp` (MCP server)
- `uv tool install rtr-role-type-retrieval` (CLI + installer)
- `npm install rtr-re-opencode-plugin` (OpenCode keeper + ctrl+p palette)
- `npm install @saimonokuma/rtr-re-mjs` (no-MCP memory mode)

## License

AGPL-3.0-or-later OR EUPL-1.2.
