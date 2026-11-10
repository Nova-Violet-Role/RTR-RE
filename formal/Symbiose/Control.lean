-- SPDX-FileCopyrightText: Nova-Violet Role ORG
-- SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
import Mathlib
namespace Symbiose

/- Live-control contract (TODO-17), the Lean quadruple check.

While Lane.lean pins what the STRUCT lane may do to a ranking, this file
pins what the live Keeper control layer may do to the window — before
any Python runs. Four passes, matching the architecture audit:

1. Keeper bounds precedence: plugin options beat the watched project
   file, which beats env, which beats the operator defaults. A bound
   taken from the wrong layer is a misconfiguration the model catches.
2. Reload safety: an unchanged file mtime leaves the config identical
   (no phantom reloads), and an invalid file keeps the last good config
   (fail-open, never a crash into defaults that would evict wrongly).
3. Command totality: every /rtr verb lands in exactly one class, and
   only the mutating class writes the config file. Unknown input is
   always a refusal, never a silent no-op and never a write.
4. Presence honesty: no status file means ABSENT, never "disabled" and
   never "healthy". The MCP viewport may only repeat what the file
   says; absence is a fact, not a default.

Like the rest of the battery this proves the model, not the JavaScript:
`resolveKeeperConfig`, `refreshConfig`, `handleRtrCommand` and
`rtr_status_payload` in the two codebases are the realizations these
theorems name. -/

-- Pass 1: precedence. `none` = layer absent; `d` = operator default. -/
def resolveBound (o f e : Option Nat) (d : Nat) : Nat :=
  match o with
  | some v => v
  | none =>
    match f with
    | some v => v
    | none =>
      match e with
      | some v => v
      | none => d

theorem explicit_option_wins (f e : Option Nat) (d v : Nat) :
    resolveBound (some v) f e d = v := by
  simp [resolveBound]

theorem file_beats_env (e : Option Nat) (d v : Nat) :
    resolveBound none (some v) e d = v := by
  simp [resolveBound]

theorem env_beats_default (d v : Nat) :
    resolveBound none none (some v) d = v := by
  simp [resolveBound]

theorem default_when_all_absent (d : Nat) :
    resolveBound none none none d = d := by
  simp [resolveBound]

-- Pass 2: reload safety. Config is bounds plus the mtime it was read at. -/
structure KeeperCfg where
  trigger : Nat
  target : Nat
  deriving DecidableEq, Repr

def reloadKeeper (old : KeeperCfg) (mtime oldMtime : Nat)
    (fileVals : Option KeeperCfg) : KeeperCfg :=
  if mtime = oldMtime then old
  else match fileVals with
    | some v => v
    | none => old

theorem unchanged_mtime_is_identity (old : KeeperCfg) (m : Nat)
    (fv : Option KeeperCfg) : reloadKeeper old m m fv = old := by
  simp [reloadKeeper]

theorem invalid_file_keeps_last_good (old : KeeperCfg) (m m' : Nat) :
    reloadKeeper old m' m none = old := by
  unfold reloadKeeper
  split
  · rfl
  · rfl

-- Pass 3: command totality. Every verb in exactly one class. -/
inductive RtrVerb where
  | status | help | enable | disable | preset
  | hold | trigger | target | max | cpu | modality | threads | parking
  | unknown
  deriving DecidableEq, Repr

inductive VerbClass where
  | report | mutate | refuse
  deriving DecidableEq, Repr

def verbClass : RtrVerb → VerbClass
  | .status => .report
  | .help => .report
  | .enable => .mutate
  | .disable => .mutate
  | .preset => .mutate
  | .hold => .mutate
  | .trigger => .mutate
  | .target => .mutate
  | .max => .mutate
  | .cpu => .mutate
  | .modality => .mutate
  | .threads => .mutate
  | .parking => .mutate
  | .unknown => .refuse

theorem verb_total (v : RtrVerb) :
    verbClass v = .report ∨ verbClass v = .mutate ∨ verbClass v = .refuse := by
  cases v <;> simp [verbClass]

theorem unknown_always_refuses : verbClass .unknown = .refuse := rfl

theorem status_never_mutates : verbClass .status ≠ .mutate := by
  simp [verbClass]

theorem every_mutation_names_its_field (v : RtrVerb) (h : verbClass v = .mutate) :
    v = .enable ∨ v = .disable ∨ v = .preset ∨ v = .hold ∨
      v = .trigger ∨ v = .target ∨ v = .max ∨ v = .cpu ∨
      v = .modality ∨ v = .threads ∨ v = .parking := by
  cases v <;> simp_all [verbClass]

-- Pass 4: presence honesty. Absence is absence, never a verdict. -/
inductive KeeperPresence where
  | absent
  | present
  deriving DecidableEq, Repr

def presenceOf : Option Nat → KeeperPresence
  | none => .absent
  | some _ => .present

theorem absent_is_not_a_verdict (o : Option Nat) (h : presenceOf o = .absent) :
    o = none := by
  cases o with
  | none => rfl
  | some v =>
    simp [presenceOf] at h

theorem present_needs_evidence (o : Option Nat) (h : presenceOf o = .present) :
    ∃ v, o = some v := by
  cases o with
  | none =>
    simp [presenceOf] at h
  | some v =>
    exact ⟨v, rfl⟩

end Symbiose
