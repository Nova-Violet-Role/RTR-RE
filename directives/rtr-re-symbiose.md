<!-- SPDX-License-Identifier: AGPL-3.0-or-later OR EUPL-1.2 -->
# RTR-RE:Symbiose — declared subset (elevation, verb 11)

Full name: Role-Type-Retrieval-RE:Symbiotized. Short name: RE:Symbiose.
The compression layer lifted into its own declarations with its own laws.
Licence: AGPL-3.0-or-later OR EUPL-1.2, as always.
Code: execution/context_budget.py (bounds), execution/symbiose_worker.py
(background compressor).

- RTRRE.trigger = 400000 tokens (env OPENCODE_MEMORY_RTRRE_TRIGGER)
- RTRRE.target = 200000 tokens (env OPENCODE_MEMORY_RTRRE_TARGET)
- RTRRE.max_keep = 200 messages (env OPENCODE_MEMORY_RTRRE_MAX_KEEP)
- RTRRE.max_summary = 20000 chars (env OPENCODE_MEMORY_RTRRE_MAX_SUMMARY)
- RTRRE.max_restore = 4000 chars (env OPENCODE_MEMORY_RTRRE_MAX_RESTORE)
- RTRRE.lanes = read|written
- RTRRE.dtypes = PCDATA|CDATA|NDATA

- LAW.RTRRE.1 Verbatim until trigger, then cut only to target (50% cut,
  400k to 200k preserved; deployments under a smaller model input cap
  scale both numbers down through the env knobs).
- LAW.RTRRE.2 Three offices, zero overlap: Keeper (native plugin
  rtr-re-keeper.js)
  selects/protects/prunes the host window and sinks evicted spans
  before any eviction; Compressor (symbiose planner + worker) plans
  and records evictions; RTR Manager retrieves. Planner and worker
  never mutate live messages; only the Keeper rewrites the outgoing
  host view, and only after the sink succeeds.
- LAW.RTRRE.3 Compression never pauses the live turn: background worker,
  result applies next turn; submit latency is measured by test.
- LAW.RTRRE.4 Both lanes survive: evicted read + written spans go verbatim
  (NDATA masked) to `.opencode/memory/` as DTD-shaped spans for dual-ONNX
  DTD retrieval.
- LAW.RTRRE.5 Invalid tuning refuses by knob name; defaults never move.
- LAW.RTRRE.6 Protected tools (`todowrite`) and the last user
  message are never evicted; tool pairs never split.
