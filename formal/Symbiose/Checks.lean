-- SPDX-FileCopyrightText: Nova-Violet Role ORG
-- SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
import Mathlib
import Symbiose.Planner
import Symbiose.Worker
import Symbiose.Graded
import Symbiose.Lane
import Symbiose.Control
import Symbiose.Live
import Symbiose.Install
import Symbiose.Cost

namespace Symbiose

-- Executable review checks: these are examples, not extra assumptions.
example : repairFix 3 [2] [1, 2] = [2, 1, 0] := rfl
example : retainedTickets 4 = 4 := rfl
example : gain 3 = 7 := rfl
example : lookupGrade [("judged", 0)] "missing" = none := rfl
example : laneOf .code = .structural := rfl
example : countLane .exact [.plain, .opaque, .code, .opaque] = 2 := rfl
example : resolveBound (some 1) (some 2) (some 3) 4 = 1 := rfl
example : costWith 390000 1000 < costWithout 3430000 := by decide
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
#print axioms manual_blocks_auto
#print axioms oneshot_overrides_manual
#print axioms auto_fires_over_trigger
#print axioms manual_carries_no_bounds
#print axioms every_preset_installs
#print axioms valid_bounds_accepted
#print axioms required_subset_accepted
#print axioms manual_installs_guide
#print axioms never_two_holders
#print axioms acquire_succeeds_only_from_free
#print axioms scoped_subset_of_discovered
#print axioms strict_le_loose
#print axioms rtr_costs_less
#print axioms savings_positive
#print axioms live_instance_fits
#print axioms m31_native

end Symbiose
