import SparseTauRadix

namespace SparseRadixFamily

open SparseTauRadix

def familyNorm (t : Int) : Int := 7*t*t - 5*t + 1

/-- Multiplication by `(t-1)+tτ` in the basis `(1,τ)`, where `τ²=3τ-3`. -/
def familyPair (t : Int) (x : Pair) : Pair :=
  ((t-1)*x.1-3*t*x.2,t*x.1+(4*t-1)*x.2)

/-- A power-of-two `t` makes the point action one `τ`, `log₂(t)` doublings,
two additions, and one negation. -/
theorem family_shortcut (t : Int) (x : Pair) :
    familyPair t x = pairSub (pairScale t (pairAdd x (tauPair x))) x := by
  apply Prod.ext
  · simp only [familyPair,pairSub,pairScale,pairAdd,tauPair,
               Int.mul_add, Int.mul_sub, Int.add_mul, Int.sub_mul,
               Int.mul_assoc, Int.mul_comm, Int.mul_left_comm]
    grind
  · simp only [familyPair,pairSub,pairScale,pairAdd,tauPair,
               Int.mul_add, Int.mul_sub, Int.add_mul, Int.sub_mul,
               Int.mul_assoc, Int.mul_comm, Int.mul_left_comm]
    grind

theorem family_norm (t : Int) :
    AlternateRadix.pairNorm (t-1) t = familyNorm t := by
  simp only [AlternateRadix.pairNorm,familyNorm,
             Int.mul_add, Int.mul_sub, Int.add_mul, Int.sub_mul,
             Int.mul_assoc, Int.mul_comm, Int.mul_left_comm]
  grind

/-- The quotient by `(t-1)+tτ` has the explicit root `τ = 4-7t`. -/
theorem family_residue (t : Int) :
    (t-1)+t*(4-7*t) = -familyNorm t := by
  simp only [familyNorm,Int.mul_add,Int.mul_sub,Int.add_mul,Int.sub_mul,
             Int.mul_assoc,Int.mul_comm,Int.mul_left_comm]
  grind

theorem family_residue_polynomial (t : Int) :
    (4-7*t)*(4-7*t) - 3*(4-7*t) + 3 = 7*familyNorm t := by
  simp only [familyNorm,Int.mul_add,Int.mul_sub,Int.add_mul,Int.sub_mul,
             Int.mul_assoc,Int.mul_comm,Int.mul_left_comm]
  grind

theorem family_norm_scaling (t : Int) (x : Pair) :
    AlternateRadix.pairNorm (familyPair t x).1 (familyPair t x).2 =
      familyNorm t * AlternateRadix.pairNorm x.1 x.2 := by
  simp only [familyPair,familyNorm,AlternateRadix.pairNorm,
             Int.mul_add,Int.mul_sub,Int.add_mul,Int.sub_mul,
             Int.mul_assoc,Int.mul_comm,Int.mul_left_comm]
  grind

/-- Conditional 17-step terminal norm certificate for the radix `63+64τ`.
The quotient recurrence and digit cap remain explicit hypotheses. -/
theorem radix64_terminal_from_norm_step (q : Nat → Nat)
    (hzero : q 0 ≤ 7*2^260)
    (hstep : ∀ i : Nat, i < 17 →
      100*28353*q (i+1) ≤ 101*q i + 10100*9451) :
    q 17 < 5000 := by
  have h1 : q 1 ≤ 461975845043741686111323310555594686148270047803663125741312802982934194823 := by
    have hs : 100*28353*q 1 ≤ 101*q 0 + 10100*9451 := by
      simpa using hstep 0 (by decide)
    omega
  have h2 : q 2 ≤ 16456657267103273127091896577475069058291988441494718618796103798990036 := by
    have hs : 100*28353*q 2 ≤ 101*q 1 + 10100*9451 := by
      simpa using hstep 1 (by decide)
    omega
  have h3 : q 3 ≤ 586224520854029762577604329109788020628325338620592734630693924379 := by
    have hs : 100*28353*q 3 ≤ 101*q 2 + 10100*9451 := by
      simpa using hstep 2 (by decide)
    omega
  have h4 : q 4 ≤ 20882684938545129623086811709550520256572799774514113567417974 := by
    have hs : 100*28353*q 4 ≤ 101*q 3 + 10100*9451 := by
      simpa using hstep 3 (by decide)
    omega
  have h5 : q 5 ≤ 743889951254914150859439206667584575146846110544184202872 := by
    have hs : 100*28353*q 5 ≤ 101*q 4 + 10100*9451 := by
      simpa using hstep 4 (by decide)
    omega
  have h6 : q 6 ≤ 26499095360895259491695185649993313614020194393878143 := by
    have hs : 100*28353*q 6 ≤ 101*q 5 + 10100*9451 := by
      simpa using hstep 5 (by decide)
    omega
  have h7 : q 7 ≤ 943959592089169120961172980160591357181264640030 := by
    have hs : 100*28353*q 7 ≤ 101*q 6 + 10100*9451 := by
      simpa using hstep 6 (by decide)
    omega
  have h8 : q 8 ≤ 33626042676614848946170941697957791794627666 := by
    have hs : 100*28353*q 8 ≤ 101*q 7 + 10100*9451 := by
      simpa using hstep 7 (by decide)
    omega
  have h9 : q 9 ≤ 1197838080745635292054902518778872419621 := by
    have hs : 100*28353*q 9 ≤ 101*q 8 + 10100*9451 := by
      simpa using hstep 8 (by decide)
    omega
  have h10 : q 10 ≤ 42669786673476938771045446477150992 := by
    have hs : 100*28353*q 10 ≤ 101*q 9 + 10100*9451 := by
      simpa using hstep 9 (by decide)
    omega
  have h11 : q 11 ≤ 1519997338560706385876482239723 := by
    have hs : 100*28353*q 11 ≤ 101*q 10 + 10100*9451 := by
      simpa using hstep 10 (by decide)
    omega
  have h12 : q 12 ≤ 54145850948623195067021056 := by
    have hs : 100*28353*q 12 ≤ 101*q 11 + 10100*9451 := by
      simpa using hstep 11 (by decide)
    omega
  have h13 : q 13 ≤ 1928801518643862272727 := by
    have hs : 100*28353*q 13 ≤ 101*q 12 + 10100*9451 := by
      simpa using hstep 12 (by decide)
    omega
  have h14 : q 14 ≤ 68708409474493064 := by
    have hs : 100*28353*q 14 ≤ 101*q 13 + 10100*9451 := by
      simpa using hstep 13 (by decide)
    omega
  have h15 : q 15 ≤ 2447553823940 := by
    have hs : 100*28353*q 15 ≤ 101*q 14 + 10100*9451 := by
      simpa using hstep 14 (by decide)
    omega
  have h16 : q 16 ≤ 87187610 := by
    have hs : 100*28353*q 16 ≤ 101*q 15 + 10100*9451 := by
      simpa using hstep 15 (by decide)
    omega
  have h17 : q 17 ≤ 3139 := by
    have hs : 100*28353*q 17 ≤ 101*q 16 + 10100*9451 := by
      simpa using hstep 16 (by decide)
    omega
  omega

#print axioms family_shortcut
#print axioms family_norm
#print axioms family_residue
#print axioms family_residue_polynomial
#print axioms family_norm_scaling
#print axioms radix64_terminal_from_norm_step

end SparseRadixFamily
