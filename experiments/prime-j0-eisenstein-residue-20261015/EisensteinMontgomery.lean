import Lean

namespace EisensteinMontgomery

def norm (a b : Int) : Int := a*a-a*b+b*b
def adjX (a b x y : Int) : Int := (a-b)*x+b*y
def adjY (a b x y : Int) : Int := -b*x+a*y

theorem adjugate_x (a b x y : Int) :
    adjX a b x y*a-adjY a b x y*b=norm a b*x := by
  simp only [adjX,adjY,norm,Int.mul_add,Int.mul_sub,Int.add_mul,
             Int.sub_mul,Int.mul_neg,Int.neg_mul,Int.mul_assoc,
             Int.mul_comm,Int.mul_left_comm]
  omega

theorem adjugate_y (a b x y : Int) :
    adjX a b x y*b+adjY a b x y*(a-b)=norm a b*y := by
  simp only [adjX,adjY,norm,Int.mul_add,Int.mul_sub,Int.add_mul,
             Int.sub_mul,Int.mul_neg,Int.neg_mul,Int.mul_assoc,
             Int.mul_comm,Int.mul_left_comm]
  omega

theorem inverse_mod_witness (p inv R : Int)
    (h : (p*inv)%R=1) : ∃ k : Int, p*inv=1+R*k := by
  have heq := Int.emod_add_mul_ediv (p*inv) R
  rw [h] at heq
  refine ⟨(p*inv)/R,?_⟩
  omega

theorem quotient_mod_witness (n inv R q : Int)
    (h : q%R=(-(n*inv))%R) :
    ∃ k : Int, q=-(n*inv)+R*k := by
  have hzero : (q-(-(n*inv)))%R=0 :=
    (Int.emod_eq_emod_iff_emod_sub_eq_zero).mp h
  have hdvd : R∣q-(-(n*inv)) :=
    (Int.dvd_iff_emod_eq_zero).mpr hzero
  rcases hdvd with ⟨k,hk⟩
  refine ⟨k,?_⟩
  omega

-- The q hypotheses are exactly the coefficientwise congruences computed
-- by multiplying the adjugate pair by -p^{-1} modulo the power-of-two radix.
theorem montgomery_numerators_divisible
    (a b x y p inv R q₁ q₂ k k₁ k₂ : Int)
    (hnorm : p=norm a b)
    (hinv : p*inv=1+R*k)
    (hq₁ : q₁=-(adjX a b x y*inv)+R*k₁)
    (hq₂ : q₂=-(adjY a b x y*inv)+R*k₂) :
    R ∣ x+q₁*a-q₂*b ∧ R ∣ y+q₁*b+q₂*(a-b) := by
  have hn₁ : adjX a b x y*a-adjY a b x y*b=p*x := by
    simpa only [hnorm] using adjugate_x a b x y
  have hn₂ : adjX a b x y*b+adjY a b x y*(a-b)=p*y := by
    simpa only [hnorm] using adjugate_y a b x y
  constructor
  · apply (Int.dvd_iff_emod_eq_zero).2
    have hnx : a*(adjX a b x y*inv)-b*(adjY a b x y*inv)=x*(p*inv) := by
      calc
        a*(adjX a b x y*inv)-b*(adjY a b x y*inv)
            = (adjX a b x y*a-adjY a b x y*b)*inv := by
              rw [Int.sub_mul]
              congr 1 <;> ac_rfl
        _ = (p*x)*inv := by rw [hn₁]
        _ = x*(p*inv) := by ac_rfl
    have hix : x*(p*inv)=x+x*(R*k) := by
      have h := congrArg (fun z : Int => x*z) hinv
      simpa only [Int.mul_add,Int.mul_one] using h
    have heq : x+q₁*a-q₂*b=R*(k₁*a-k₂*b-k*x) := by
      rw [hq₁,hq₂]
      simp only [Int.mul_add,Int.mul_sub,Int.add_mul,Int.sub_mul,
                 Int.mul_neg,Int.neg_mul,Int.mul_assoc,Int.mul_comm,
                 Int.mul_left_comm,Int.mul_one,Int.one_mul] at hnx hix ⊢
      omega
    rw [heq]
    simp

  · apply (Int.dvd_iff_emod_eq_zero).2
    have hny : b*(adjX a b x y*inv)+(a-b)*(adjY a b x y*inv)=y*(p*inv) := by
      calc
        b*(adjX a b x y*inv)+(a-b)*(adjY a b x y*inv)
            = (adjX a b x y*b+adjY a b x y*(a-b))*inv := by
              rw [Int.add_mul]
              congr 1 <;> ac_rfl
        _ = (p*y)*inv := by rw [hn₂]
        _ = y*(p*inv) := by ac_rfl
    have hiy : y*(p*inv)=y+y*(R*k) := by
      have h := congrArg (fun z : Int => y*z) hinv
      simpa only [Int.mul_add,Int.mul_one] using h
    have hdist : (a-b)*(adjY a b x y*inv)
        = a*(adjY a b x y*inv)-b*(adjY a b x y*inv) :=
      Int.sub_mul a b (adjY a b x y*inv)
    have heq : y+q₁*b+q₂*(a-b)=R*(k₁*b+k₂*(a-b)-k*y) := by
      rw [hq₁,hq₂]
      simp only [Int.mul_add,Int.mul_sub,Int.add_mul,Int.sub_mul,
                 Int.mul_neg,Int.neg_mul,Int.mul_assoc,Int.mul_comm,
                 Int.mul_left_comm,Int.mul_one,Int.one_mul] at hny hiy hdist ⊢
      omega
    rw [heq]
    simp

theorem montgomery_divisible_from_congruences
    (a b x y p inv R q₁ q₂ : Int)
    (hnorm : p=norm a b)
    (hinv : (p*inv)%R=1)
    (hq₁ : q₁%R=(-(adjX a b x y*inv))%R)
    (hq₂ : q₂%R=(-(adjY a b x y*inv))%R) :
    R ∣ x+q₁*a-q₂*b ∧ R ∣ y+q₁*b+q₂*(a-b) := by
  obtain ⟨k,hk⟩ := inverse_mod_witness p inv R hinv
  obtain ⟨k₁,hk₁⟩ := quotient_mod_witness (adjX a b x y) inv R q₁ hq₁
  obtain ⟨k₂,hk₂⟩ := quotient_mod_witness (adjY a b x y) inv R q₂ hq₂
  exact montgomery_numerators_divisible a b x y p inv R q₁ q₂
    k k₁ k₂ hnorm hk hk₁ hk₂

-- The numerator divided by R has the intended field residue: any added
-- ideal multiple vanishes under evaluation at the cube root beta.
theorem montgomery_field_semantics
    (x y q₁ q₂ a b beta p R z₁ z₂ : Int)
    (hx : x+q₁*a-q₂*b=R*z₁)
    (hy : y+q₁*b+q₂*(a-b)=R*z₂)
    (hpi : p ∣ a+beta*b)
    (homegaPi : p ∣ -b+beta*(a-b)) :
    (R*(z₁+beta*z₂))%p=(x+beta*y)%p := by
  apply (Int.emod_eq_emod_iff_emod_sub_eq_zero).2
  have hdiff : R*(z₁+beta*z₂)-(x+beta*y) =
      q₁*(a+beta*b)+q₂*(-b+beta*(a-b)) := by
    have hhy := congrArg (fun t : Int => beta*t) hy
    simp only [Int.mul_add,Int.mul_sub,Int.add_mul,Int.sub_mul,
               Int.mul_neg,Int.neg_mul,Int.mul_assoc,Int.mul_comm,
               Int.mul_left_comm] at hhy ⊢
    omega
  rw [hdiff]
  have hm₁ : (a+beta*b)%p=0 := (Int.dvd_iff_emod_eq_zero).mp hpi
  have hm₂ : (-b+beta*(a-b))%p=0 :=
    (Int.dvd_iff_emod_eq_zero).mp homegaPi
  simp [Int.add_emod,Int.mul_emod,hm₁,hm₂]

def prime : Int := 2^256-2^32-977
def radix : Int := 2^128
def inversePrime : Int := 0x434ddc0123db5fa627c7f6e22ddacacf
def piA : Int := -367917413016453100223835821029139468249
def piB : Int := -64502973549206556628585045361533709078
def beta : Int :=
  0x7ae96a2b657c07106e64479eac3434e99cf0497512f58995c1396c28719501ee

theorem norm_pi : norm piA piB=prime := by decide
theorem prime_inverse_radix : (prime*inversePrime)%radix=1 := by decide
theorem pi_kernel : (piA+beta*piB)%prime=0 := by decide
theorem omega_pi_kernel : (-piB+beta*(piA-piB))%prime=0 := by decide

theorem secp_montgomery_divisible (x y q₁ q₂ : Int)
    (hq₁ : q₁%radix=(-(adjX piA piB x y*inversePrime))%radix)
    (hq₂ : q₂%radix=(-(adjY piA piB x y*inversePrime))%radix) :
    radix ∣ x+q₁*piA-q₂*piB ∧
    radix ∣ y+q₁*piB+q₂*(piA-piB) := by
  exact montgomery_divisible_from_congruences
    piA piB x y prime inversePrime radix q₁ q₂
    norm_pi prime_inverse_radix hq₁ hq₂

#print axioms adjugate_x
#print axioms adjugate_y
#print axioms montgomery_numerators_divisible
#print axioms inverse_mod_witness
#print axioms quotient_mod_witness
#print axioms montgomery_divisible_from_congruences
#print axioms montgomery_field_semantics
#print axioms norm_pi
#print axioms prime_inverse_radix
#print axioms pi_kernel
#print axioms omega_pi_kernel
#print axioms secp_montgomery_divisible

end EisensteinMontgomery
