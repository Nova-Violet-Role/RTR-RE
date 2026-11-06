-- SPDX-FileCopyrightText: Nova-Violet Role ORG
-- SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
import Mathlib
namespace Symbiose

/-- Minimal message model for execution/context_budget.py.

Only fields that affect planning/cache identity are modeled. This is a
review model, not a claim that Lean verifies the Python implementation. -/
structure Message where
  role : String
  text : String
  tokens : Nat
  tool : String := ""
  isProtected : Bool := false
  isUser : Bool := false
  toolResult : Bool := false
  deriving DecidableEq, Repr

def totalTokens (messages : List Message) : Nat :=
  messages.foldl (fun acc m => acc + m.tokens) 0

/-- Legacy cache identity: role and text only (pre-audit Python behavior). -/
def legacyKey (m : Message) : String × String :=
  (m.role, m.text)

/-- Canonical cache identity: the whole modeled message participates. -/
def canonicalKey (m : Message) : Message :=
  m

theorem legacy_hash_ignores_tokens :
    legacyKey { role := "assistant", text := "same", tokens := 1 }
      = legacyKey { role := "assistant", text := "same", tokens := 9999 } := rfl

theorem legacy_hash_ignores_tool :
    legacyKey { role := "assistant", text := "same", tokens := 10 }
      = legacyKey { role := "assistant", text := "same", tokens := 10, tool := "skill" } :=
  rfl

theorem canonical_key_distinguishes_tokens :
    canonicalKey { role := "assistant", text := "same", tokens := 1 }
      ≠ canonicalKey { role := "assistant", text := "same", tokens := 2 } := by
  intro h
  have htok := congrArg Message.tokens h
  exact absurd htok (by decide)

/-- A target cannot be a hard cap when protected messages bypass the walk. -/
theorem protected_message_can_exceed_any_smaller_target :
    ¬ ∀ (m : Message) (target : Nat), m.isProtected = true → m.tokens ≤ target := by
  intro h
  have hle := h
    { role := "assistant", text := "protected", tokens := 50000, isProtected := true }
    20000
    rfl
  change 50000 ≤ 20000 at hle
  omega

def dedupNat : List Nat → List Nat
  | [] => []
  | x :: xs => if xs.contains x then dedupNat xs else x :: dedupNat xs

/-- One repair pass over a snapshot, as the pre-audit Python did. -/
def repairOnce (keep tools : List Nat) : List Nat :=
  dedupNat
    (keep ++ (keep.filter (fun i => tools.contains i ∧ 0 < i)).map (fun i => i - 1))

/-- Fuel-bounded fixpoint repair used as the intended contract. -/
def repairFix : Nat → List Nat → List Nat → List Nat
  | 0, keep, _ => keep
  | fuel + 1, keep, tools =>
      let next := repairOnce keep tools
      if next.length = keep.length then keep else repairFix fuel next tools

theorem one_pass_leaves_chain_gap :
    repairOnce [2] [1, 2] = [2, 1] := rfl

theorem fixpoint_repairs_chain_to_call :
    repairFix 3 [2] [1, 2] = [2, 1, 0] := rfl

/-- Abstract fused-search call counts before and after removing an unused
original-query gate pass. The Python regression is
test_search_skips_unused_gate_pass. -/
def fusedCallsOld (_hasDelta prf : Bool) : Nat :=
  1 + (if prf then 1 else 0) + 1

def fusedCallsNew (hasDelta prf : Bool) : Nat :=
  (if hasDelta then 1 else 0) + (if prf then 1 else 0) + 1

theorem fused_calls_no_delta_no_prf :
    fusedCallsNew false false = 1 ∧ fusedCallsOld false false = 2 := by
  constructor <;> rfl

theorem fused_calls_new_never_more (hasDelta prf : Bool) :
    fusedCallsNew hasDelta prf ≤ fusedCallsOld hasDelta prf := by
  cases hasDelta <;> cases prf <;> decide

end Symbiose
