import Lean

namespace StreamFixture

-- A sequence starts at one scalar or point and adds the same step each pass.
def progression {α : Type} (add : α → α → α) (start step : α) : Nat → α
  | 0 => start
  | j+1 => add (progression add start step j) step

-- The scalar-to-point homomorphism carries the entire deterministic stream.
-- For the fixture, addA is addition modulo the subgroup order and addB is
-- curve-point addition. The concrete secp256k1 computations are replayed by
-- generate_stream_fixture.py rather than assumed by this declaration.
theorem hom_progression {α β : Type}
    (addA : α → α → α) (addB : β → β → β) (f : α → β)
    (hom : ∀ x y, f (addA x y) = addB (f x) (f y))
    (start step : α) (j : Nat) :
    f (progression addA start step j) =
      progression addB (f start) (f step) j := by
  induction j with
  | zero => rfl
  | succ j ih =>
      change f (addA (progression addA start step j) step) =
        addB (progression addB (f start) (f step) j) (f step)
      rw [hom, ih]

#print axioms hom_progression
end StreamFixture
