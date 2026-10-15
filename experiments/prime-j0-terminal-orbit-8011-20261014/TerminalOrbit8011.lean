import Lean

namespace TerminalOrbit8011

set_option maxRecDepth 100000

def nrm (a b : Int) : Int := a*a + 3*a*b + 3*b*b
def omega (a b : Int) : Int × Int := (a + 3*b, -a - 2*b)

def unitImage (a b : Int) : Nat → Int × Int
  | 0 => (a, b)
  | 1 => (-a, -b)
  | 2 => omega a b
  | 3 => (-(omega a b).1, -(omega a b).2)
  | 4 => omega (omega a b).1 (omega a b).2
  | 5 => (-(omega (omega a b).1 (omega a b).2).1,
           -(omega (omega a b).1 (omega a b).2).2)
  | _ => (0, 0)

theorem omega_cube (a b : Int) :
    omega (omega (omega a b).1 (omega a b).2).1
      (omega (omega a b).1 (omega a b).2).2 = (a, b) := by
  simp [omega]
  constructor <;> omega

theorem omega_preserves_norm (a b : Int) :
    nrm (omega a b).1 (omega a b).2 = nrm a b := by
  simp [omega, nrm]
  grind

theorem neg_preserves_norm (a b : Int) : nrm (-a) (-b) = nrm a b := by
  simp [nrm]
  grind

theorem unit_preserves_norm (a b : Int) (u : Nat) (hu : u < 6) :
    nrm (unitImage a b u).1 (unitImage a b u).2 = nrm a b := by
  have hc : u = 0 ∨ u = 1 ∨ u = 2 ∨ u = 3 ∨ u = 4 ∨ u = 5 := by omega
  rcases hc with h | h | h | h | h | h <;>
    subst u <;> simp [unitImage, omega_preserves_norm, neg_preserves_norm]

theorem unit_images_distinct (a b : Int) (h : a ≠ 0 ∨ b ≠ 0)
    (u v : Nat) (hu : u < 6) (hv : v < 6) (huv : u ≠ v) :
    unitImage a b u ≠ unitImage a b v := by
  have hc1 : u = 0 ∨ u = 1 ∨ u = 2 ∨ u = 3 ∨ u = 4 ∨ u = 5 := by omega
  have hc2 : v = 0 ∨ v = 1 ∨ v = 2 ∨ v = 3 ∨ v = 4 ∨ v = 5 := by omega
  rcases hc1 with h1 | h1 | h1 | h1 | h1 | h1 <;>
    rcases hc2 with h2 | h2 | h2 | h2 | h2 | h2 <;>
    subst u <;> subst v <;> intro heq <;>
    simp [unitImage, omega, Prod.mk.injEq] at heq <;>
    rcases h with ha | hb <;> omega

#print axioms omega_cube
#print axioms omega_preserves_norm
#print axioms neg_preserves_norm
#print axioms unit_preserves_norm
#print axioms unit_images_distinct

end TerminalOrbit8011
