-- SPDX-FileCopyrightText: Nova-Violet Role ORG
-- SPDX-License-Identifier: EUPL-1.2 OR AGPL-3.0-or-later
import Mathlib
namespace Symbiose

/- Installer contracts (prover-worthy installation): preset totality,
manual purity (no automatic bounds), bounds validity, required
components, and the manual guide. Like the rest of the battery this
proves the model, not the launchers: planFor/executePlan in
installer/launchers plus install_opencode are the realizations these
theorems name. -/

/-- Installer preset choice. -/
inductive InstallPreset where
  | quick
  | custom
  | hardcore
  | manual
  deriving DecidableEq, Repr

/-- What an install writes: automatic bounds or manual-no-bounds. -/
inductive InstallConfig where
  | auto (trigger target maxKeep : Nat)
  | manual
  deriving DecidableEq, Repr

def presetConfig : InstallPreset → InstallConfig
  | .quick => .auto 400000 200000 200
  | .custom => .auto 400000 200000 200
  | .hardcore => .auto 400000 200000 200
  | .manual => .manual

theorem manual_carries_no_bounds : presetConfig .manual = .manual := rfl

theorem every_preset_installs (p : InstallPreset) :
    presetConfig p = .manual ∨ ∃ t g m, presetConfig p = .auto t g m := by
  cases p with
  | manual => exact Or.inl rfl
  | quick => exact Or.inr ⟨400000, 200000, 200, rfl⟩
  | custom => exact Or.inr ⟨400000, 200000, 200, rfl⟩
  | hardcore => exact Or.inr ⟨400000, 200000, 200, rfl⟩

/-- Bounds gate: target positive and strictly below trigger. -/
def boundsValid (trigger target : Nat) : Bool :=
  decide (target > 0 ∧ trigger > target)

theorem valid_bounds_accepted : boundsValid 400000 200000 = true := rfl

theorem inverted_bounds_refused : boundsValid 200000 400000 = false := rfl

theorem zero_target_refused : boundsValid 400000 0 = false := rfl

/-- Required components can never be deselected. -/
def requiredKept (selected required : List String) : Bool :=
  required.all (fun r => selected.contains r)

theorem required_subset_accepted :
    requiredKept ["keeper", "engine"] ["keeper"] = true := rfl

theorem dropped_required_refused :
    requiredKept ["engine"] ["keeper"] = false := rfl

/-- Only the manual preset installs the palette guide. -/
def installsGuide : InstallPreset → Bool
  | .manual => true
  | _ => false

theorem manual_installs_guide : installsGuide .manual = true := rfl

theorem quick_skips_guide : installsGuide .quick = false := rfl

end Symbiose
