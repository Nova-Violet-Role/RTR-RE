-- SPDX-FileCopyrightText: Nova-Violet Role ORG
-- SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
import Mathlib
namespace Symbiose

/- Live-loop contracts (bullet-proof): the writer lock, scoped indexing,
and relay verification as review models. Like the rest of the battery
this proves the model, not the Python: `_acquire_writer_lock`,
`index_files` and `_try_relay_sidecar` in execution/memory_engine.py
and execution/symbiose_worker.py are the realizations these theorems
name. -/

-- The lock is free or held by exactly one pid; losers read the holder
-- from the unlocked sidecar instead of the locked byte.
inductive LockState where
  | free
  | held (pid : Nat)
  deriving DecidableEq, Repr

def holderCount : LockState → Nat
  | .free => 0
  | .held _ => 1

theorem never_two_holders (s : LockState) : holderCount s ≤ 1 := by
  cases s <;> simp [holderCount]

def acquire (s : LockState) (pid : Nat) : Option LockState :=
  match s with
  | .free => some (.held pid)
  | .held _ => none

theorem acquire_succeeds_only_from_free (s : LockState) (pid : Nat)
    (h : (acquire s pid).isSome) : s = .free := by
  cases s with
  | free => rfl
  | held q => simp [acquire] at h

-- Scoped indexing covers a subset of discovery; only a full discovery
-- may purge, because only it sees every active path.
theorem scoped_subset_of_discovered (inner outer : List String)
    (h : ∀ p ∈ inner, p ∈ outer) (p : String) (hp : p ∈ inner) :
    p ∈ outer :=
  h p hp

-- Relay counting: strict opens never exceed loose substring matches, so
-- a loose count can only over-approve. The drain relays on the strict
-- count alone. Measured live 2026-11-10 (sidecar 1cb8575a): 202 loose
-- matches over 195 strict opens and 195 messages.
def looseCount (strict extra : Nat) : Nat :=
  strict + extra

theorem strict_le_loose (strict extra : Nat) :
    strict ≤ looseCount strict extra := by
  simp [looseCount]

example : looseCount 195 7 = 202 := rfl

end Symbiose
