-- SPDX-FileCopyrightText: Nova-Violet Role ORG
-- SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
import Mathlib
namespace Symbiose

/- STRUCT lane contract (TODO-15), defined before its Python realization.

The query router classifies every opaque query term by shape. This model
pins the three properties the implementation must not violate, whatever
backend answers (rg, ccc, or none):

1. Total and disjoint: every term lands in exactly one lane, so no term
   can vote in both the exact lane and the structural lane (the collision
   constraint). The partition count is the list-level form.
2. Bounded influence: exact + structural bonuses share the one
   EXACT_LANE_WEIGHT cap, so lane evidence can lift a candidate by at
   most the cap and can never bury a dense winner the way an unbounded
   lane could.
3. Fallback identity: with the structural lane off or unavailable, the
   fused bonus is exactly the legacy exact-lane bonus, so every frozen
   bench stays reproducible with the lane disabled.

Like the rest of the battery this proves the model, not the Python:
`classify_query_terms` and `structural_hits` in execution/memory_engine.py
are the realizations these theorems name. -/

/-- Shape of one opaque query term, as the router sees it. -/
inductive TokenShape where
  | plain
  | opaque
  | code
  deriving DecidableEq, Repr

/-- The lane a term votes in. -/
inductive Lane where
  | none
  | exact
  | structural
  deriving DecidableEq, Repr

/-- Router: plain prose votes nowhere extra, opaque tokens (urls, hex,
paths) take the exact lane, code-shaped tokens take the structural lane. -/
def laneOf : TokenShape → Lane
  | .plain => .none
  | .opaque => .exact
  | .code => .structural

theorem lane_total (s : TokenShape) :
    laneOf s = .none ∨ laneOf s = .exact ∨ laneOf s = .structural := by
  cases s <;> simp [laneOf]

theorem lane_never_both (s : TokenShape) :
    ¬ (laneOf s = .exact ∧ laneOf s = .structural) := by
  cases s <;> simp [laneOf]

/-- Terms of one lane in a classified query. -/
def countLane (l : Lane) : List TokenShape → Nat
  | [] => 0
  | s :: rest => (if laneOf s = l then 1 else 0) + countLane l rest

/-- No double counting, list level: the three lanes partition the query. -/
theorem partition_counts (ts : List TokenShape) :
    countLane .none ts + countLane .exact ts + countLane .structural ts
      = ts.length := by
  induction ts with
  | nil => rfl
  | cons s rest ih =>
      cases s <;> simp [countLane, laneOf] <;> omega

/-- The shared bonus cap: EXACT_LANE_WEIGHT = 0.15 in the engine. -/
def laneCap : Rat := 3 / 20

theorem laneCap_nonneg : (0 : Rat) ≤ laneCap := by
  norm_num [laneCap]

/-- Combined exact+structural bonus over `total` opaque terms, of which
`exactHits` matched in the exact lane and `structHits` in the structural
lane. Disjointness of the lanes is the hypothesis `exactHits +
structHits ≤ total` wherever a bound is claimed. -/
def fusedBonus (exactHits structHits total : Nat) : Rat :=
  if total = 0 then 0
  else laneCap * ((exactHits + structHits : Nat) : Rat) / (total : Rat)

theorem bonus_nonneg (e s n : Nat) : 0 ≤ fusedBonus e s n := by
  by_cases hz : n = 0
  · unfold fusedBonus
    rw [if_pos hz]
  · have hn : (0 : Rat) < (n : Rat) := by exact_mod_cast Nat.pos_of_ne_zero hz
    unfold fusedBonus
    rw [if_neg hz, Rat.div_def]
    exact Rat.mul_nonneg
      (Rat.mul_nonneg laneCap_nonneg (by exact_mod_cast Nat.zero_le _))
      (Rat.le_of_lt (Rat.inv_pos.mpr hn))

theorem bonus_bounded (e s n : Nat) (h : e + s ≤ n) :
    fusedBonus e s n ≤ laneCap := by
  by_cases hz : n = 0
  · unfold fusedBonus
    rw [if_pos hz]
    exact laneCap_nonneg
  · have hn : (0 : Rat) < (n : Rat) := by exact_mod_cast Nat.pos_of_ne_zero hz
    have hcast : ((e + s : Nat) : Rat) ≤ (n : Rat) := by exact_mod_cast h
    have hne : (n : Rat) ≠ 0 := by
      intro hh
      rw [hh] at hn
      exact (by decide : ¬ ((0 : Rat) < 0)) hn
    unfold fusedBonus
    rw [if_neg hz, Rat.div_def]
    have step1 : laneCap * ((e + s : Nat) : Rat) * (n : Rat)⁻¹
        ≤ laneCap * (n : Rat) * (n : Rat)⁻¹ :=
      Rat.mul_le_mul_of_nonneg_right
        (Rat.mul_le_mul_of_nonneg_left hcast laneCap_nonneg)
        (Rat.le_of_lt (Rat.inv_pos.mpr hn))
    have step2 : laneCap * (n : Rat) * (n : Rat)⁻¹ = laneCap := by
      rw [Rat.mul_assoc, Rat.mul_inv_cancel _ hne, Rat.mul_one]
    rwa [step2] at step1

/-- Legacy exact-lane bonus (pre-lane engine behaviour). -/
def legacyBonus (exactHits total : Nat) : Rat :=
  if total = 0 then 0 else laneCap * (exactHits : Rat) / (total : Rat)

/-- Fallback identity: structural lane off (zero structural hits, every
term routed exact as before) reproduces the legacy bonus exactly. -/
theorem lane_off_identity (e n : Nat) :
    fusedBonus e 0 n = legacyBonus e n := by
  by_cases hz : n = 0 <;> simp [fusedBonus, legacyBonus, hz]

/-- Score after lanes: bounded bonus, then the same 1.0 clamp the engine
applies. Stated with an if, because Rat has no core `min` in this model. -/
def finalScore (base : Rat) (e s n : Nat) : Rat :=
  if base + fusedBonus e s n ≤ 1 then base + fusedBonus e s n else 1

theorem final_le_one (base : Rat) (e s n : Nat) : finalScore base e s n ≤ 1 := by
  by_cases hle : base + fusedBonus e s n ≤ 1
  · unfold finalScore
    rw [if_pos hle]
    exact hle
  · unfold finalScore
    rw [if_neg hle]

theorem final_le_base_add_cap (base : Rat) (e s n : Nat) (h : e + s ≤ n) :
    finalScore base e s n ≤ base + laneCap := by
  have key : base + fusedBonus e s n ≤ base + laneCap := by
    have h1 : fusedBonus e s n + base ≤ laneCap + base :=
      Rat.add_le_add_right.mpr (bonus_bounded e s n h)
    rwa [Rat.add_comm (fusedBonus e s n) base, Rat.add_comm laneCap base] at h1
  by_cases hle : base + fusedBonus e s n ≤ 1
  · unfold finalScore
    rw [if_pos hle]
    exact key
  · unfold finalScore
    rw [if_neg hle]
    cases (Rat.le_total (a := (1 : Rat)) (b := base + fusedBonus e s n)) with
    | inl h1 => exact Rat.le_trans h1 key
    | inr h1 => exact absurd h1 hle

end Symbiose
