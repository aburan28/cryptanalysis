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

def evalPair (z : Int × Int) : Int := z.1 + beta*z.2

def mulPair (z w : Int × Int) : Int × Int :=
  let a := z.1*w.1
  let b := z.2*w.2
  let c := (z.1+z.2)*(w.1+w.2)
  (a-b,c-a-b-b)

theorem eval_rotate_mod (z : Int × Int) :
    evalPair (rotate z) % prime = (beta*evalPair z) % prime := by
  apply (Int.emod_eq_emod_iff_emod_sub_eq_zero).2
  have hdiff : evalPair (rotate z) - beta*evalPair z =
      -z.2*(beta*beta+beta+1) := by
    rcases z with ⟨u,v⟩
    simp only [evalPair,rotate]
    simp only [Int.mul_add,Int.mul_sub,Int.mul_neg,Int.neg_mul,
               Int.add_mul,Int.sub_mul,Int.mul_assoc,Int.mul_comm,
               Int.mul_left_comm,Int.mul_one]
    omega
  rw [hdiff, Int.mul_emod, beta_cubic]
  simp

theorem eval_mul_mod (z w : Int × Int) :
    evalPair (mulPair z w) % prime = (evalPair z*evalPair w) % prime := by
  apply (Int.emod_eq_emod_iff_emod_sub_eq_zero).2
  have hdiff : evalPair (mulPair z w) - evalPair z*evalPair w =
      -(z.2*w.2)*(beta*beta+beta+1) := by
    rcases z with ⟨u,v⟩
    rcases w with ⟨s,t⟩
    simp only [evalPair,mulPair]
    simp only [Int.mul_add,Int.mul_sub,Int.mul_neg,Int.neg_mul,
               Int.add_mul,Int.sub_mul,Int.mul_assoc,Int.mul_comm,
               Int.mul_left_comm,Int.mul_one]
    omega
  rw [hdiff, Int.mul_emod, beta_cubic]
  simp

-- A general quotient correction for a pseudo-Mersenne modulus. The native
-- reducer uses k=2^256 and c=2^32+977; its asserted bound is the hypothesis
-- that makes exactly one correction sufficient.
theorem solinas_one_correction
    (shifted q₀ low correction k c p : Int)
    (hk : 0 < k) (hc : 0 < c) (hp : p = k-c) (hpc : c < p)
    (hq : q₀ = shifted / k) (hlow : low = shifted % k)
    (hcorrection : correction = q₀*c)
    (hbound : -(p-c) < correction ∧ correction < p-c) :
    shifted / p =
      if low + correction < 0 then q₀-1
      else if p ≤ low + correction then q₀+1
      else q₀ := by
  have hpositive : 0 < p := by omega
  have hmod_nonneg : 0 ≤ low := by
    rw [hlow]
    exact Int.emod_nonneg _ (Int.ne_of_gt hk)
  have hmod_lt : low < k := by
    rw [hlow]
    exact Int.emod_lt_of_pos _ hk
  have hdecomp : shifted = q₀*p + (low+correction) := by
    have h := Int.emod_add_mul_ediv shifted k
    rw [← hq, ← hlow] at h
    have hkpc : k = p+c := by omega
    calc
      shifted = low + k*q₀ := h.symm
      _ = low + (p+c)*q₀ := by rw [hkpc]
      _ = q₀*p + (low+correction) := by
        rw [Int.add_mul, Int.mul_comm p q₀, Int.mul_comm c q₀, ← hcorrection]
        omega
  have hrange : -p < low+correction ∧ low+correction < 2*p := by
    omega
  by_cases hneg : low+correction < 0
  · simp only [if_pos hneg]
    apply (Int.ediv_eq_iff_of_pos hpositive).2
    constructor <;> simp only [Int.sub_mul, Int.one_mul] <;> omega
  · by_cases hhigh : p ≤ low+correction
    · simp only [if_neg hneg, if_pos hhigh]
      apply (Int.ediv_eq_iff_of_pos hpositive).2
      constructor <;> simp only [Int.add_mul, Int.one_mul] <;> omega
    · simp only [if_neg hneg, if_neg hhigh]
      apply (Int.ediv_eq_iff_of_pos hpositive).2
      constructor <;> omega

#print axioms rotate_three
#print axioms pi_norm_eq_prime
#print axioms beta_cubic
#print axioms pi_in_kernel
#print axioms basis_x_width
#print axioms basis_y_width
#print axioms eval_rotate_mod
#print axioms eval_mul_mod
#print axioms solinas_one_correction
end EisensteinResidue
