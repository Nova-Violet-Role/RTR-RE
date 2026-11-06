<!-- SPDX-FileCopyrightText: Nova-Violet Role ORG -->
<!-- SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later -->
# Lean quadruple check: live-control battery (2026-10-27)

Second helping hand, same discipline: core-only, no Mathlib.
`elan run leanprover/lean4:v4.33.0 lake build` in `C:\RTR\formal` AND
`C:\RTR-RE\formal` (a literal `C:\RTR:RE` path is impossible on Windows —
WinError 123, measured): **exit 0, 9 jobs, sorry hits 0**, 20 axiom
records, all in {propext, Classical.choice, Quot.sound} or fewer, both
trees. A from-zero `lake clean` + `lake build` shows every job green
([6/9] Control ✔, [7/9] Checks ℹ info-level records only).
Verbose debug: every module additionally typechecked with
`lake env lean -Ddiagnostics=true` (Planner/Graded/Control/Lane/Worker
all exit 0, zero errors/warnings/sorries; Planner's old binder warning
gone since the `_hasDelta` fix). New file
`formal/Symbiose/Control.lean` (7 new axiom lines in Checks.lean):

| Pass | Theorems | What they pin |
|---|---|---|
| 1 precedence | explicit_option_wins, file_beats_env, env_beats_default, default_when_all_absent | options > file > env > defaults — a bound from the wrong layer is caught |
| 2 reload safety | unchanged_mtime_is_identity, invalid_file_keeps_last_good | no phantom reloads; invalid file keeps last good (fail-open) |
| 3 command totality | verb_total, unknown_always_refuses, status_never_mutates, every_mutation_names_its_field | every /rtr verb in exactly one class; unknown always refuses; only named verbs write |
| 4 presence honesty | absent_is_not_a_verdict, present_needs_evidence | no status file = ABSENT, never "disabled"/"healthy"; presence needs the file |

## Correction 2026-10-27: `native_decide` unbanned (operator-ordered)

An earlier blanket ban confused footprint hygiene with soundness and is
rescinded in the skill (Core Principles + Quality Gate), here, in
`formal/MATHLIB_POLICY.md`, and in the `Graded.lean` header comment.
Measured: `m31_native : Nat.Prime (2^31 - 1) := by native_decide`
discharges via compiled trial division where kernel `decide` would
reduce the same division chain term by term — infeasible in any
practical budget. Axioms recorded exactly as printed:
`[propext, Classical.choice, Quot.sound,
m31_native._native.native_decide.ax_1_1]`.
Rule going forward: native_decide allowed for large computations,
always recorded, kernel-checked tactics win ties. 21 axiom records,
21/21 standard-or-recorded-native.

## Addendum: full Mathlib, operator-mandated (same day)

Policy: `formal/MATHLIB_POLICY.md` — the battery always builds against
full Mathlib (`lakefile.lean` requires mathlib `v4.33.0` @ `db584cd`;
every module opens `import Mathlib`). Proofs use Mathlib idioms where
they fit (`norm_num` for the concrete DCG and fusion drag, `linarith`
for fusion-between-arms, `norm_num` for `laneCap_nonneg`); the rest is
unchanged in statement.

Measured path, no skipping:
- `lake update` pulled the tag + 8690-file cache, exit 0.
- Full `import Mathlib` initially failed on a handful of cached oleans
  (Lie Weights / Eigenspace / Bicones / PushoutI / SesquilinearForm /
  CStarAlgebra-FFC / RootSystem-Finite) while the tactic framework
  (`Mathlib.Tactic`: `norm_num`, `linarith`) loaded fine.
- Root causes found and fixed at their layers: (1) a `lake clean` in the
  standalone tree had wiped dependency build caches, forcing source
  rebuilds that OOMed (`std::bad_alloc`) under full parallelism —
  recovered with `lake update` + sequential per-module builds;
  (2) Mathlib's `rfl`-lemmas close `0 ≤ 0` / `1 ≤ 1` inside `rw`, so two
  trailing `decide`s became "no goals" errors — removed, they were dead.
- Final: `lake build` exit 0, **8713 jobs**, both trees, same 20 axiom
  records (all standard; `invalid_file_keeps_last_good` and
  `fixpoint_repairs_chain_to_call` depend on no axioms at all).
- Verbose debug: all five modules re-elaborated with
  `-Ddiagnostics=true`, exit 0, zero errors/warnings/sorries.
- The core-only era is superseded by decision, not by failure: the old
  grind proofs also passed, but the standing rule is Mathlib-first.

Realizations named in the module docstring: `resolveKeeperConfig`,
`refreshConfig`, `handleRtrCommand`, `rtr_status_payload`. The `succ`/
`some` constructor miss was caught by the build (Option uses `some`),
fixed, rebuilt green.
