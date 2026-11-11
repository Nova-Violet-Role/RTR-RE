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

def totalTokens : List Message → Nat
  | [] => 0
  | m :: rest => m.tokens + totalTokens rest

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

/-- Tail-walk model: newest-first accumulation, as context_budget.py
plans it. Messages arrive oldest-first; the walk runs over the reverse
and stops before the next message once the target is reached — so the
crossing message is kept and the planner overshoots by at most one. -/
def maxTokens : List Message → Nat
  | [] => 0
  | m :: rest => Nat.max m.tokens (maxTokens rest)

theorem mem_le_maxTokens (m : Message) (l : List Message) (h : m ∈ l) :
    m.tokens ≤ maxTokens l := by
  induction l with
  | nil => simp at h
  | cons x xs ih =>
      simp only [maxTokens]
      simp at h
      cases h with
      | inl heq => rw [heq]; exact Nat.le_max_left _ _
      | inr hmem => exact Nat.le_trans (ih hmem) (Nat.le_max_right _ _)

def walkAux : List Message → Nat → Nat → List Message
  | [], _, _ => []
  | m :: rest, target, acc =>
      if acc ≥ target then [] else m :: walkAux rest target (acc + m.tokens)

def keepTail (newestFirst : List Message) (target : Nat) : List Message :=
  walkAux newestFirst target 0

theorem walkAux_bounded (l : List Message) (target acc : Nat) :
    totalTokens (walkAux l target acc) ≤ (target - acc) + maxTokens l := by
  induction l generalizing acc with
  | nil => simp [walkAux, totalTokens, maxTokens]
  | cons m rest ih =>
      by_cases h : acc ≥ target
      · simp only [walkAux, if_pos h, totalTokens]
        omega
      · simp only [walkAux, if_neg h, totalTokens]
        by_cases hcross : acc + m.tokens ≥ target
        · have hempty : walkAux rest target (acc + m.tokens) = [] := by
            cases rest with
            | nil => rfl
            | cons x xs => simp only [walkAux, if_pos hcross]
          rw [hempty]
          simp only [totalTokens]
          have hmax1 : m.tokens ≤ maxTokens (m :: rest) := by
            simp only [maxTokens]
            exact Nat.le_max_left _ _
          omega
        · have hrec := ih (acc + m.tokens)
          have hmax2 : maxTokens rest ≤ maxTokens (m :: rest) := by
            simp only [maxTokens]
            exact Nat.le_max_right _ _
          have hlt2 : acc + m.tokens < target := by omega
          omega

/-- The keeper bound, derived from the walk — not assumed: the kept
tail exceeds the target by at most the largest single message. -/
theorem keeper_tail_bounded (messages : List Message) (target : Nat) :
    totalTokens (keepTail messages target)
      ≤ target + maxTokens messages := by
  unfold keepTail
  have h := walkAux_bounded messages target 0
  simpa using h

/-- Cache hit = prefix equality (positional!): the served window must
equal the cached prefix for the cache to apply. -/
def cacheHit (served cached : List Message) : Prop :=
  served = cached

/-- Retrieval hit = content membership (addressed!): the needed content
is in the sunk store regardless of window shape. -/
def retrievalHit (needed : Message) (sunk : List Message) : Prop :=
  needed ∈ sunk

/-- Eviction destroys cache hits: dropping the oldest k changes the
prefix, so equality with the cached window fails. -/
theorem eviction_kills_cache (served : List Message) (k : Nat)
    (h : 0 < k) (hlen : k ≤ served.length) :
    ¬ cacheHit (served.drop k) served := by
  unfold cacheHit
  intro heq
  have hlen2 : (served.drop k).length = served.length := by rw [heq]
  rw [List.length_drop] at hlen2
  omega

/-- Eviction preserves retrieval hits: the sunk store only grows, so
membership is monotone in the evicted prefix. -/
theorem sunk_grows_monotone (needed : Message) (sunk evicted : List Message)
    (h : needed ∈ sunk) : needed ∈ evicted ++ sunk := by
  simp [h]

theorem evicted_enters_store (needed : Message) (sunk evicted : List Message)
    (h : needed ∈ evicted) : needed ∈ evicted ++ sunk := by
  simp [h]

end Symbiose
