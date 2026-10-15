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

/-- Conditional 20-step terminal norm certificate for the radix `31+32τ`.
The quotient recurrence and uniform digit cap remain explicit hypotheses. -/
theorem radix32_terminal_from_norm_step (q : Nat → Nat)
    (hzero : q 0 ≤ 7*2^260)
    (hstep : ∀ i : Nat, i < 20 →
      100*7009*q (i+1) ≤ 101*q i + 10100*2284) :
    q 20 < 5000 := by
  have h1 : q 1 ≤ 1868797422531774579300092712823908708283906500981204252267576245252551465986 := by
    have hs : 100*7009*q 1 ≤ 101*q 0 + 10100*2284 := by
      simpa using hstep 0 (by decide)
    omega
  have h2 : q 2 ≤ 269294535134411802695547672985040347462797198743189655413076331531613241 := by
    have hs : 100*7009*q 2 ≤ 101*q 1 + 10100*2284 := by
      simpa using hstep 1 (by decide)
    omega
  have h3 : q 3 ≤ 38805461618741035914182215681964724060126290587904344694993165194344 := by
    have hs : 100*7009*q 3 ≤ 101*q 2 + 10100*2284 := by
      simpa using hstep 2 (by decide)
    omega
  have h4 : q 4 ≤ 5591884182469460161695539711625677172310964972718417483513068494 := by
    have hs : 100*7009*q 4 ≤ 101*q 3 + 10100*2284 := by
      simpa using hstep 3 (by decide)
    omega
  have h5 : q 5 ≤ 805792983919839458312526053465820223146536541938308126458614 := by
    have hs : 100*7009*q 5 ≤ 101*q 4 + 10100*2284 := by
      simpa using hstep 4 (by decide)
    omega
  have h6 : q 6 ≤ 116115125375807940204829692395559769635896976367198060772 := by
    have hs : 100*7009*q 6 ≤ 101*q 5 + 10100*2284 := by
      simpa using hstep 5 (by decide)
    omega
  have h7 : q 7 ≤ 16732240923036955287042087219220340609538585551558035 := by
    have hs : 100*7009*q 7 ≤ 101*q 6 + 10100*2284 := by
      simpa using hstep 6 (by decide)
    omega
  have h8 : q 8 ≤ 2411123317487134375790056797176850337513763933129 := by
    have hs : 100*7009*q 8 ≤ 101*q 7 + 10100*2284 := by
      simpa using hstep 7 (by decide)
    omega
  have h9 : q 9 ≤ 347443936461978273583672045248768560549137081 := by
    have hs : 100*7009*q 9 ≤ 101*q 8 + 10100*2284 := by
      simpa using hstep 8 (by decide)
    omega
  have h10 : q 10 ≤ 50066824914623777474605331103046974768848 := by
    have hs : 100*7009*q 10 ≤ 101*q 9 + 10100*2284 := by
      simpa using hstep 9 (by decide)
    omega
  have h11 : q 11 ≤ 7214651614177488264995203939802745719 := by
    have hs : 100*7009*q 11 ≤ 101*q 10 + 10100*2284 := by
      simpa using hstep 10 (by decide)
    omega
  have h12 : q 12 ≤ 1039634488560317184711821369553574 := by
    have hs : 100*7009*q 12 ≤ 101*q 11 + 10100*2284 := by
      simpa using hstep 11 (by decide)
    omega
  have h13 : q 13 ≤ 149811789619905886226129202950 := by
    have hs : 100*7009*q 13 ≤ 101*q 12 + 10100*2284 := by
      simpa using hstep 12 (by decide)
    omega
  have h14 : q 14 ≤ 21587945144258088898329394 := by
    have hs : 100*7009*q 14 ≤ 101*q 13 + 10100*2284 := by
      simpa using hstep 13 (by decide)
    omega
  have h15 : q 15 ≤ 3110832443387169323376 := by
    have hs : 100*7009*q 15 ≤ 101*q 14 + 10100*2284 := by
      simpa using hstep 14 (by decide)
    omega
  have h16 : q 16 ≤ 448272330977463439 := by
    have hs : 100*7009*q 16 ≤ 101*q 15 + 10100*2284 := by
      simpa using hstep 15 (by decide)
    omega
  have h17 : q 17 ≤ 64596241159576 := by
    have hs : 100*7009*q 17 ≤ 101*q 16 + 10100*2284 := by
      simpa using hstep 16 (by decide)
    omega
  have h18 : q 18 ≤ 9308346954 := by
    have hs : 100*7009*q 18 ≤ 101*q 17 + 10100*2284 := by
      simpa using hstep 17 (by decide)
    omega
  have h19 : q 19 ≤ 1341369 := by
    have hs : 100*7009*q 19 ≤ 101*q 18 + 10100*2284 := by
      simpa using hstep 18 (by decide)
    omega
  have h20 : q 20 ≤ 226 := by
    have hs : 100*7009*q 20 ≤ 101*q 19 + 10100*2284 := by
      simpa using hstep 19 (by decide)
    omega
  omega

#print axioms family_shortcut
#print axioms family_norm
#print axioms family_residue
#print axioms family_residue_polynomial
#print axioms family_norm_scaling
#print axioms radix64_terminal_from_norm_step
#print axioms radix32_terminal_from_norm_step

end SparseRadixFamily
