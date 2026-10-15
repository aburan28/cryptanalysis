import NearestOrbit35533Digits

namespace NearestOrbit35533Step
open NearestOrbit35533Digits NearestOrbit35533Selector SplitPrime12211Nearest

noncomputable def nearestDigit (r : Nat) : Int × Int :=
  if r ≤ 17766 then selectedDigit r
  else let d := selectedDigit (35533-r); (-d.1, -d.2)

theorem neg_norm (a b : Int) : nrm (-a) (-b) = nrm a b := by
  unfold nrm
  grind

theorem digit_valid (r : Nat) (hr : r < 35533) :
    nrm (nearestDigit r).1 (nearestDigit r).2 ≤ 11719 ∧
    ((nearestDigit r).1 + 190*(nearestDigit r).2 - (r : Int)) % 35533 = 0 := by
  by_cases h : r ≤ 17766
  · have hs := selected_digit_valid r (by omega)
    simpa [nearestDigit, h] using hs
  · have hc : 35533-r < 17767 := by omega
    have hs := selected_digit_valid (35533-r) hc
    have hn : nrm (-(selectedDigit (35533-r)).1)
        (-(selectedDigit (35533-r)).2) ≤ 11719 := by
      rw [neg_norm]
      exact hs.1
    have hm :
        (-(selectedDigit (35533-r)).1 -
         190*(selectedDigit (35533-r)).2 - (r : Int)) % 35533 = 0 := by
      omega
    constructor
    · simpa [nearestDigit, h] using hn
    · simp [nearestDigit, h]
      omega

theorem bounded_step (a b : Int) :
    ∃ d next : Int × Int,
      d = nearestDigit (((a+190*b)%35533).toNat) ∧
      nrm d.1 d.2 ≤ 109*109 ∧
      a = d.1 + 190*next.1 + 3*next.2 ∧
      b = d.2 - next.1 + 187*next.2 := by
  let residueWord : Int := (a+190*b)%35533
  let r : Nat := residueWord.toNat
  have hr0 : 0 ≤ residueWord := Int.emod_nonneg _ (by decide)
  have hrmax : residueWord < 35533 := Int.emod_lt _ (by decide)
  have hr : r < 35533 := by dsimp [r]; omega
  have hcast : (r : Int) = residueWord := by
    dsimp [r]
    rw [Int.ofNat_toNat]
    omega
  let d := nearestDigit r
  have hd := digit_valid r hr
  have hdmod : (d.1 + 190*d.2 - residueWord)%35533 = 0 := by
    simpa [d, hcast] using hd.2
  have hmod : ((a-d.1)+190*(b-d.2))%35533 = 0 := by
    dsimp [residueWord] at hdmod
    omega
  obtain ⟨k, hk⟩ := Int.dvd_of_emod_eq_zero hmod
  have hq : 35533*k = (a-d.1)+190*(b-d.2) := by omega
  let next : Int × Int := (187*k-(b-d.2), k)
  refine ⟨d, next, rfl, ?_, ?_, ?_⟩
  · have hn : nrm d.1 d.2 ≤ 11719 := by simpa [d] using hd.1
    omega
  · dsimp [next]
    omega
  · dsimp [next]
    omega

#print axioms neg_norm
#print axioms digit_valid
#print axioms bounded_step
end NearestOrbit35533Step
