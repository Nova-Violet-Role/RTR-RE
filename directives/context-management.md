<!-- SPDX-License-Identifier: AGPL-3.0-or-later OR EUPL-1.2 -->
# RTR-RE:Symbiose (RE:Symbiose) — Keeper, Compressor, Manager

Full name: Role-Type-Retrieval-RE:Symbiotized. Licence:
AGPL-3.0-or-later OR EUPL-1.2, as always. Three offices, zero overlap.
The Keeper (native plugin `opencode-plugin/rtr-re-keeper.js`; the lab's
legacy ACP wiring ran keeper-only under `permission: deny`) only
selects, protects and prunes the window — it never summarises and never
nudges. The Compressor
keeps everything verbatim until TRIGGER=320000 tokens, then cuts 60%
to a TARGET tail of 128000 tokens / 40 messages, in a background
worker (`execution/symbiose_worker.py`) so the live turn never pauses.
RTR is the Manager replacing RAG: evicted read + written spans go verbatim
(PCDATA/CDATA byte-exact, NDATA masked) into `directives/sessions/` for
the dual-ONNX index (Arctic-m + bge-base, RRF, DTD-typed), so compression
loses position, never substance.

Every Compressor bound is configurable (`OPENCODE_MEMORY_RTRRE_*`,
refused loudly when invalid). Protected tools (`skill`, `compress`) and
the last user message are never evicted. Summaries cap at 20000 chars;
restore at 4000. Declared subset: directives/rtr-re-symbiose.md.
Derivation: artifacts/geometry/2026-10-26-plan.md. Evaluation:
artifacts/geometry/2026-10-26-evaluation.md.
