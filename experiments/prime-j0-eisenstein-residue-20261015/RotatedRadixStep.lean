import HornerRadix

namespace RotatedRadixStep

open HornerRadix

def pairSub (x y : Pair) : Pair := (x.1 - y.1, x.2 - y.2)
def pairScale (n : Int) (x : Pair) : Pair := (n*x.1, n*x.2)

/-- Multiplication by τ, using τ² = 3τ - 3. -/
def tauPair (x : Pair) : Pair := (-3*x.2, x.1 + 3*x.2)

/-- Multiplication by ω = 1 - τ. -/
def omegaPair (x : Pair) : Pair :=
  (x.1 + 3*x.2, -x.1 - 2*x.2)

theorem tau_is_one_minus_omega (x : Pair) :
    tauPair x = pairSub x (omegaPair x) := by
  apply Prod.ext
  · simp [tauPair, pairSub, omegaPair]
    omega
  · simp [tauPair, pairSub, omegaPair]
    omega

/-- The native rotation schedule evaluates exactly the radix 31 + 32τ. -/
theorem rotated_radix_identity (x : Pair) :
    pairSub (pairScale 63 x) (pairScale 32 (omegaPair x)) =
      pairAdd (pairScale 31 x) (pairScale 32 (tauPair x)) := by
  apply Prod.ext
  · simp [pairSub, pairScale, omegaPair, tauPair, pairAdd]
    omega
  · simp [pairSub, pairScale, omegaPair, tauPair, pairAdd]
    omega

/-- The same identity holds under a point map when the implementation
respects the pair-field operations used in the native schedule. -/
theorem mapped_rotated_radix_identity {Point : Type}
    (evaluate : Pair → Point) (add sub : Point → Point → Point)
    (scale : Int → Point → Point) (omega tau : Point → Point)
    (map_add : ∀ x y, evaluate (pairAdd x y) = add (evaluate x) (evaluate y))
    (map_sub : ∀ x y, evaluate (pairSub x y) = sub (evaluate x) (evaluate y))
    (map_scale : ∀ n x, evaluate (pairScale n x) = scale n (evaluate x))
    (map_omega : ∀ x, evaluate (omegaPair x) = omega (evaluate x))
    (map_tau : ∀ x, evaluate (tauPair x) = tau (evaluate x))
    (x : Pair) :
    sub (scale 63 (evaluate x)) (scale 32 (omega (evaluate x))) =
      add (scale 31 (evaluate x)) (scale 32 (tau (evaluate x))) := by
  have h := congrArg evaluate (rotated_radix_identity x)
  simpa only [map_sub, map_scale, map_omega, map_add, map_tau] using h

#print axioms tau_is_one_minus_omega
#print axioms rotated_radix_identity
#print axioms mapped_rotated_radix_identity

end RotatedRadixStep
