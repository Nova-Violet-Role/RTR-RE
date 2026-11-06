-- SPDX-FileCopyrightText: Nova-Violet Role ORG
-- SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
import Mathlib
import Symbiose.Planner
import Symbiose.Worker
import Symbiose.Graded
import Symbiose.Lane
import Symbiose.Control

namespace Symbiose

-- Executable review checks: these are examples, not extra assumptions.
example : repairFix 3 [2] [1, 2] = [2, 1, 0] := rfl
example : retainedTickets 4 = 4 := rfl
example : gain 3 = 7 := rfl
example : lookupGrade [("judged", 0)] "missing" = none := rfl
example : laneOf .code = .structural := rfl
example : countLane .exact [.plain, .opaque, .code, .opaque] = 2 := rfl
example : resolveBound (some 1) (some 2) (some 3) 4 = 1 := rfl
example : verbClass .unknown = .refuse := rfl
example : presenceOf none = .absent := rfl

/-- Capability probe, not a model claim: large decidable goals that kernel
`decide` cannot reduce in any practical budget discharge via compiled
evaluation. The native axiom below is the price, recorded on purpose. -/
theorem m31_native : Nat.Prime (2 ^ 31 - 1) := by native_decide

#print axioms protected_message_can_exceed_any_smaller_target
#print axioms fixpoint_repairs_chain_to_call
#print axioms fused_calls_new_never_more
#print axioms retained_tickets_eq
#print axioms dcg_nonneg
#print axioms dcg_perfect_concrete
#print axioms weak_arm_can_drag_fusion
#print axioms fusion_between_arms
#print axioms lane_never_both
#print axioms partition_counts
#print axioms bonus_bounded
#print axioms lane_off_identity
#print axioms final_le_base_add_cap
#print axioms explicit_option_wins
#print axioms unchanged_mtime_is_identity
#print axioms invalid_file_keeps_last_good
#print axioms verb_total
#print axioms every_mutation_names_its_field
#print axioms absent_is_not_a_verdict
#print axioms present_needs_evidence
#print axioms m31_native

end Symbiose
