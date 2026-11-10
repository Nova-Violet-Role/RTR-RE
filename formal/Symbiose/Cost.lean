-- SPDX-FileCopyrightText: Nova-Violet Role ORG
-- SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
import Mathlib
namespace Symbiose

/- No-cache cost model (TODO-15): a small-window model operates a large
managed context at lesser per-turn cost, because evicted substance lives
in retrieval form instead of being re-sent.

Model: managed tokens M (the whole context RTR-RE tracks), live window
L (what the keeper serves, bounded by the target preset), retrieval
hits R (what a turn pulls back, bounded by the restore budget), model
window W (what the model accepts per turn).

Without RTR (and without prompt caching): every turn re-sends M.
With RTR: every turn sends L + R, with L + R ≤ W < M.

Like the rest of the battery this proves the model, not the Python:
`plan_compression` (live bound), `bounded_restore` (retrieval bound)
and `evaluate_retrieval` (soundness) are the realizations these
theorems name. -/

/-- Per-turn cost without RTR: the whole managed context, re-sent. -/
def costWithout (managed : Nat) : Nat :=
  managed

/-- Per-turn cost with RTR: live window plus retrieved hits. -/
def costWith (live retrieved : Nat) : Nat :=
  live + retrieved

/-- A turn fits the model window. -/
def fitsWindow (live retrieved modelWindow : Nat) : Prop :=
  live + retrieved ≤ modelWindow

theorem rtr_costs_less (managed live retrieved : Nat)
    (h : live + retrieved < managed) :
    costWith live retrieved < costWithout managed := by
  simp [costWith, costWithout, h]

theorem window_fit_is_additive (live retrieved modelWindow : Nat)
    (h : fitsWindow live retrieved modelWindow) :
    live ≤ modelWindow ∧ retrieved ≤ modelWindow := by
  unfold fitsWindow at h
  constructor <;> omega

/-- The live window is bounded by the target preset; retrieved hits are
bounded by the restore budget. When both bounds fit, every turn fits. -/
theorem bounded_turn_fits (live retrieved target restore modelWindow : Nat)
    (hl : live ≤ target) (hr : retrieved ≤ restore)
    (h : target + restore ≤ modelWindow) :
    fitsWindow live retrieved modelWindow := by
  unfold fitsWindow
  omega

/-- Live instance (measured 2026-11-10): 3.43M managed, ~390k served,
restore budget 4k chars (~1k tokens), 700k model window. -/
theorem live_instance_fits :
    fitsWindow 390000 1000 700000 := by
  unfold fitsWindow
  decide

theorem live_instance_costs_less :
    costWith 390000 1000 < costWithout 3430000 := by
  decide

/-- The 4M frontier: even at 4M managed, the served window stays the
target tail, so the cost stays flat while the unmanaged cost grows. -/
theorem cost_flat_in_managed (live retrieved managed : Nat)
    (h : live + retrieved < managed) :
    costWith live retrieved < costWithout managed ∧
      costWith live retrieved = live + retrieved := by
  constructor
  · simp [costWith, costWithout, h]
  · rfl

/-- Savings ratio: the fraction of the managed context NOT re-sent. -/
def savings (managed live retrieved : Nat) : Rat :=
  if managed = 0 then 0
  else 1 - ((live + retrieved : Nat) : Rat) / (managed : Rat)

theorem savings_positive (managed live retrieved : Nat)
    (hm : 0 < managed) (h : live + retrieved < managed) :
    0 < savings managed live retrieved := by
  unfold savings
  have hne : (managed : Nat) ≠ 0 := by omega
  rw [if_neg hne]
  have hcast : ((live + retrieved : Nat) : Rat) < (managed : Rat) := by
    exact_mod_cast h
  have hpos : (0 : Rat) < (managed : Rat) := by exact_mod_cast hm
  have hfrac : ((live + retrieved : Nat) : Rat) / (managed : Rat) < 1 := by
    rw [div_lt_one hpos]
    exact hcast
  linarith

theorem live_instance_savings :
    savings 3430000 390000 1000 > 4 / 5 := by
  norm_num [savings]

end Symbiose
