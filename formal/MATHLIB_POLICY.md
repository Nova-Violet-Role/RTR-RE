<!-- SPDX-FileCopyrightText: Nova-Violet Role ORG -->
<!-- SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later -->
# Standing policy: full Mathlib, always (operator-mandated 2026-10-27)

The formal battery builds against full Mathlib, no exceptions.

- `formal/lakefile.lean` requires `mathlib` at the pinned tag
  (`v4.33.0`, commit `db584cd`). Every `Symbiose/*` module opens with
  `import Mathlib`.
- Proofs use Mathlib idioms where they fit (`norm_num`, `linarith`);
  `grind`/`decide`/`simp`/`omega` remain for what they already close.
- `native_decide` is allowed for large computations where kernel
  `decide` is infeasible (measured: `Nat.Prime (2^31-1)` discharges via
  compiled trial division while the kernel would reduce the same
  division chain term by term). Its native-code axiom
  (`*.native_decide.ax_*`) is legitimate and must appear in the
  recorded `#print axioms` output; kernel-checked tactics win ties.
  An earlier blanket ban confused footprint hygiene with soundness
  and is rescinded here and in the lean4 skill (Core Principles +
  Quality Gate, same day, operator-ordered).
- The bar: `lake build` exit 0, sorry hits 0, every `#print axioms`
  record inside {propext, Classical.choice, Quot.sound}, or those plus
  a recorded native axiom where a large computation earned it.
- History: the original 2026-10-27 battery was core-only by author call
  (documented in the first battery record), never by skill mandate —
  the lean4 skill prioritises LSP inspection and Mathlib search, and
  forbids nothing. Operator overrode to full Mathlib the same day;
  the core-only note in `Graded.lean` records the supersession.
- The global lean4 skill file carries the same two rules now (full
  Mathlib always; native_decide carve-out with recorded axioms),
  added by explicit operator order — a global default, not a side
  effect.
