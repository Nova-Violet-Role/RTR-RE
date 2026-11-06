-- SPDX-FileCopyrightText: Nova-Violet Role ORG
-- SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
import Mathlib
namespace Symbiose

/-- Ticket states exposed by execution/symbiose_worker.py. -/
inductive TicketState where
  | pending
  | ready
  | failed
  | cached
  | cooldown
  | overflow
  | unknown
  deriving DecidableEq, Repr

/-- Legal background transitions. There is deliberately no transition that
rewrites a live message list: the worker contract is ticket-only. -/
inductive Step : TicketState → TicketState → Prop where
  | finish : Step .pending .ready
  | fail : Step .pending .failed

theorem ready_only_from_pending {a : TicketState} (h : Step a .ready) :
    a = .pending := by
  cases h
  rfl

theorem failed_only_from_pending {a : TicketState} (h : Step a .failed) :
    a = .pending := by
  cases h
  rfl

/-- If every accepted submission is retained, the ticket store grows without
bound. This is a formal hinter for an explicit retention policy. -/
def retainedTickets : Nat → Nat
  | 0 => 0
  | n + 1 => retainedTickets n + 1

theorem retained_tickets_eq (n : Nat) : retainedTickets n = n := by
  induction n with
  | zero => rfl
  | succ n ih => simp [retainedTickets, ih]

/-- Caller-visible submit work is hash plus enqueue; sink work is a separate
term. Addition commutes in arithmetic, so architecture must be enforced by
the event order/implementation, not by a numeric identity. This theorem only
pins the accounting decomposition used on tickets. -/
theorem elapsed_decomposes (queue plan sink : Nat) :
    queue + plan + sink = queue + (plan + sink) := by
  omega

/-- A bounded completed-ticket store with capacity c never exceeds c if its
retention operation explicitly truncates to c. Python does not implement
this yet; this is the intended contract for the retention amelioration. -/
def retainBounded (capacity current : Nat) : Nat :=
  min capacity current

theorem retain_bounded_le (capacity current : Nat) :
    retainBounded capacity current ≤ capacity :=
  Nat.min_le_left _ _

end Symbiose
