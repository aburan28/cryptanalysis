import Lean

namespace EisensteinResidue

-- Coordinates represent u + v*omega, with omega^2 + omega + 1 = 0.
def rotate (z : Int × Int) : Int × Int := (-z.2, z.1-z.2)

theorem rotate_three (z : Int × Int) :
    rotate (rotate (rotate z)) = z := by
  rcases z with ⟨u, v⟩
  simp [rotate]
  omega

def prime : Int := 2^256 - 2^32 - 977
def beta : Int :=
  0x7ae96a2b657c07106e64479eac3434e99cf0497512f58995c1396c28719501ee
def piA : Int := -367917413016453100223835821029139468249
def piB : Int := -64502973549206556628585045361533709078
def norm (a b : Int) : Int := a*a-a*b+b*b

theorem pi_norm_eq_prime : norm piA piB = prime := by decide

theorem beta_cubic : (beta*beta+beta+1) % prime = 0 := by decide

theorem pi_in_kernel : (piA+piB*beta) % prime = 0 := by decide

theorem basis_x_width :
    Int.natAbs piA + Int.natAbs piB < 2^129 := by decide

theorem basis_y_width :
    Int.natAbs piB + Int.natAbs (piA-piB) < 2^129 := by decide

#print axioms rotate_three
#print axioms pi_norm_eq_prime
#print axioms beta_cubic
#print axioms pi_in_kernel
#print axioms basis_x_width
#print axioms basis_y_width
end EisensteinResidue
