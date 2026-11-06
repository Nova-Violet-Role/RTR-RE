import Lake
open Lake DSL

-- Standing operator policy (2026-10-27): this battery always builds
-- against full Mathlib. Core-only fallbacks are forbidden without
-- explicit operator sign-off; the decision is recorded in
-- artifacts/geometry/2026-10-27-lean-control.md.
package «rtr-re-symbiose-formal» where
  leanOptions := #[]

require mathlib from git
  "https://github.com/leanprover-community/mathlib4"@"v4.33.0"

@[default_target]
lean_lib Symbiose where
  roots := #[`Symbiose]
