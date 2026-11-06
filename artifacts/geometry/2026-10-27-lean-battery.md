<!-- SPDX-License-Identifier: AGPL-3.0-or-later OR EUPL-1.2 -->
<!-- Copyright 2026 Saimonokuma. -->
# Lean 4 battery: build record and dependency decision

Date: 2026-10-27. Instrument: `elan run leanprover/lean4:v4.33.0 lake build`
in `C:\RTR\formal`, foreground, exit code read directly from the completed
process record. The LSP snapshot shown during editing was stale (it quoted
pre-edit file contents, including a Planner field name removed earlier);
the build below is the measured state and was rerun after the last edit.

## Decision: core-only, no Mathlib

`norm_num`, `linarith` and `ring` are Mathlib tactics and are unknown in a
core-only project; `rfl` and `decide` cannot reduce concrete Rat arithmetic
because Rat normalization goes through well-founded gcd recursion that the
kernel does not unfold. Probes on 2026-10-27 (temp files under
`C:\Users\Saimono\AppData\Local\Temp\opencode\lean_probe3.lean` and
`lean_probe4.lean`, both with `set_option diagnostics true`) measured:

- `native_decide` closes the concrete goals but depends on a per-theorem
  native-code axiom (`_native.native_decide.ax_1_1`). Rejected: the battery
  admits only the standard axioms.
- The Lean-core `grind` tactic (CommRing + Linarith modules visible in its
  diagnostics) closes all three blocked goals and depends only on
  `propext`, `Classical.choice`, `Quot.sound`. Adopted.
- Core Rat order lemmas that exist for manual fallback: `Rat.add_le_add_left`,
  `Rat.add_le_add_right` (both iff), `Rat.mul_le_mul_of_nonneg_left`,
  `Rat.mul_le_mul_of_nonneg_right`, `Rat.mul_pos`, `Rat.inv_pos`,
  `Rat.div_mul_cancel`, `Rat.mul_inv_cancel`, `Rat.add_nonneg`,
  `Rat.mul_nonneg`. Absent in core: `Rat.div_nonneg`, `Rat.div_pos`,
  `Rat.inv_nonneg`, `Rat.sub_nonneg`, `Rat.add_div`, `Rat.le_div_iff_mul_le`,
  `Rat.div_le_iff_le_mul`, `Rat.mul_le_mul_left`, `Rat.mul_le_mul_right`.

The decision is also recorded as a comment at the top of
`formal/Symbiose/Graded.lean`. No Mathlib dependency is added; `lakefile.lean`
has no `require` lines and `lean-toolchain` stays `leanprover/lean4:v4.33.0`.

## Changes that closed the build

- `formal/Symbiose/Graded.lean`: `dcg_perfect_concrete` proved by `show`
  (definitional unfolding of `dcg`/`gain` on the concrete lists) then
  `grind`; `weak_arm_can_drag_fusion` and `fusion_between_arms` proved by
  `unfold fuse2` then `grind`.
- `formal/Symbiose/Planner.lean`: unused binder in `fusedCallsOld` renamed
  to `_hasDelta` (the old call shape ignores the delta flag by design; that
  is the behavior being modeled). Linter warning gone.
- `formal/Symbiose/Checks.lean`: axiom records extended with
  `dcg_perfect_concrete` and `weak_arm_can_drag_fusion`.

## Build result

```
[3/7] Built Symbiose.Planner
[4/7] Built Symbiose.Graded
[5/7] Built Symbiose.Checks
[6/7] Built Symbiose
Build completed successfully (7 jobs).
exit=0
```

Axiom records printed by `Checks.lean` at build time:

| Theorem | Axioms |
|---|---|
| `protected_message_can_exceed_any_smaller_target` | propext, Quot.sound |
| `fixpoint_repairs_chain_to_call` | none |
| `fused_calls_new_never_more` | none |
| `retained_tickets_eq` | propext |
| `dcg_nonneg` | propext, Classical.choice, Quot.sound |
| `dcg_perfect_concrete` | propext, Classical.choice, Quot.sound |
| `weak_arm_can_drag_fusion` | propext, Classical.choice, Quot.sound |
| `fusion_between_arms` | propext, Classical.choice, Quot.sound |

Sorry scan over `formal/Symbiose.lean` and `formal/Symbiose/*.lean`:
23 theorem lines read (instrument control), `sorry` hits 0, `axiom `
declarations 0, `native_decide` textual hits 1 (the rejection comment in
`Graded.lean`; the axiom records above prove no native axiom is depended on).

Encoding: CR absent from all three edited files; the CR detector was
tripped on a deliberate `"a<char cr>b"` control first and fired.

## What the battery proves, and what it does not

The battery proves properties of the review models in `formal/Symbiose/`:
cache-identity counterexamples, the protected-message target counterexample,
one-pass vs fixpoint tool-chain repair, fused-call counts, ticket retention
growth and its bounded contract, the graded gain table, DCG non-negativity
and one concrete DCG value, fusion drag and between-arms bounds, and
unjudged-vs-judged-zero lookup separation. It does not prove anything about
the Python implementation, Chroma, or the ONNX models; those are decided by
the test suites and benches. The models exist to hint failures cheaply: two
of their counterexamples (legacy cache hash, one-pass repair) correspond to
real defects already fixed in `execution/` during the limits audit.
