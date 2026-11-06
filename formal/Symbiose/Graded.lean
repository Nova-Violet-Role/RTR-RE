-- SPDX-FileCopyrightText: Nova-Violet Role ORG
-- SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
import Mathlib
namespace Symbiose

-- Dependency decision (2026-10-27, superseded same day): core-only was
-- the original call; operator standing policy is full Mathlib always
-- (lakefile requires mathlib `v4.33.0` @ `db584cd`; every module imports
-- it). The Rat proofs below now close with Mathlib `norm_num` /
-- `linarith`; the rest is unchanged in statement. `native_decide` is
-- allowed for large computations (see Checks `m31_native`); an earlier
-- blanket rejection confused footprint hygiene with soundness.

/-- Frozen gain mapping from eval/graded/PROTOCOL.md. Inputs above grade 3
are outside the protocol; Python refuses them. This total model clamps
only to keep the review function executable. -/
def gain : Nat → Nat
  | 0 => 0
  | 1 => 1
  | 2 => 3
  | _ => 7

theorem gain_table : gain 0 = 0 ∧ gain 1 = 1 ∧ gain 2 = 3 ∧ gain 3 = 7 := by
  decide

/-- DCG with caller-supplied positive rational discounts. Pinning discounts
as data keeps this core model independent of real logarithm libraries. -/
def dcg : List Nat → List Rat → Rat
  | [], _ => 0
  | _, [] => 0
  | g :: gs, d :: ds => (gain g : Rat) * d + dcg gs ds

theorem dcg_empty (discounts : List Rat) : dcg [] discounts = 0 := rfl

theorem dcg_nonneg (grades : List Nat) (discounts : List Rat)
    (h : ∀ d ∈ discounts, 0 ≤ d) : 0 ≤ dcg grades discounts := by
  induction grades generalizing discounts with
  | nil => simp [dcg]
  | cons g gs ih =>
      cases discounts with
      | nil => simp [dcg]
      | cons d ds =>
          have hd : 0 ≤ d := h d (by simp)
          have hds : ∀ x ∈ ds, 0 ≤ x := by
            intro x hx
            exact h x (List.mem_cons_of_mem d hx)
          have htail := ih ds hds
          have hgain : (0 : Rat) ≤ (gain g : Rat) := by
            exact_mod_cast Nat.zero_le _
          simp [dcg, Rat.add_nonneg (Rat.mul_nonneg hgain hd) htail]

/-- A concrete perfect ranking normalized by its own DCG is one. Division
is intentionally not hidden: a zero ideal is a separate protocol state. -/
theorem dcg_perfect_concrete :
    dcg [3, 2, 1] [1, 1 / 2, 1 / 4] = 35 / 4 := by
  norm_num [dcg, gain]

/-- Simple equal-weight fusion model. A confident weak arm can reduce the
margin of a strong arm; fusion is not inherently superior. This concrete
counterexample is the formal hinter behind same-size ablation arms. -/
def fuse2 (strong weak : Rat) : Rat :=
  (strong + weak) / 2

theorem weak_arm_can_drag_fusion : fuse2 1 0 < 1 := by
  norm_num [fuse2]

theorem fusion_between_arms (strong weak : Rat) (h : weak ≤ strong) :
    weak ≤ fuse2 strong weak ∧ fuse2 strong weak ≤ strong := by
  unfold fuse2
  constructor <;> linarith

/-- Association-list qrel lookup: absent means unjudged in the data model,
while metric code separately counts it. It must never silently become a
judged zero in provenance reports. -/
def lookupGrade (qrels : List (String × Nat)) (doc : String) : Option Nat :=
  (qrels.find? (fun p => p.1 == doc)).map Prod.snd

theorem absent_is_unjudged_not_zero :
    lookupGrade [("judged", 0)] "missing" = none := rfl

theorem judged_zero_is_some_zero :
    lookupGrade [("judged", 0)] "judged" = some 0 := rfl

end Symbiose
