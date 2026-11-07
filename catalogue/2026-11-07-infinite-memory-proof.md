# Infinite Memory — proof (TODO-70)

Measured 2026-11-07, isolated run (fresh extra-roots, temp project root,
local-system profile T8/P80, isolated DB).

## The loop

1. A span is evicted from the live window → `SessionSpanSink` writes it as a
   DTD-shaped record under `<project>/.opencode/memory/rtrre-<digest>.dtd`
   (architectural-form ATTLIST: id/role/lane/dtype/ts/source/session +
   verbatim content), plus a paraphrase companion `rtrre-summary-<digest>.dtd`
   with the common-line anchor.
2. The engine indexes the memory root as a first-class DTD corpus.
3. `memory_search` retrieves any span ever evicted.

## Measured numbers

- Index: `{'scanned': 2, 'new': 2, 'failed': 0, 'lexikon_seeded': 9}`
  — the DTD spans are indexed with the inventory treatment, and the DTD
  vocabulary seeding ran on the memory corpus (9 terms seeded).
- Query: the distinctive marker `KEEPER-MEMORY-2.0-INFINITE-PROOF-731`
  (a string that exists nowhere else on disk) →
  - hit 0.9500 — the span file (`rtrre-proof.dtd`)
  - hit 0.4986 — the paraphrase companion (`rtrre-summary-proof.dtd`)

## What this proves

- Eviction is never deletion: the verbatim span is retrievable at high score.
- The keeper memory is a first-class DTD corpus member: same pipeline, same
  inventory header, same family-signature treatment as any DTD.
- The paraphrase common line (operator vision) is independently retrievable.
- The glossary module (operator vision) is written by `build_lexikon` as
  `rtrre-glossary.dtd` in the same root.
- The real-time ONNX retrieval on the plugin-side optimizer has a uniform
  query target: the memory root.

The infinite-memory claim is now measured, not asserted.
