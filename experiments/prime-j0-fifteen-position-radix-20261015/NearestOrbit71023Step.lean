import NearestOrbit71023Digits

namespace NearestOrbit71023Step
open NearestOrbit71023Digits NearestOrbit71023Selector SplitPrime12211Nearest

noncomputable def nearestDigit (r : Nat) : Int × Int :=
  if r ≤ 35511 then selectedDigit r
  else let d := selectedDigit (71023-r); (-d.1, -d.2)

theorem neg_norm (a b : Int) : nrm (-a) (-b) = nrm a b := by
  unfold nrm
  grind

theorem digit_valid (r : Nat) (hr : r < 71023) :
    nrm (nearestDigit r).1 (nearestDigit r).2 ≤ 23497 ∧
    ((nearestDigit r).1 + 268*(nearestDigit r).2 - (r : Int)) % 71023 = 0 := by
  by_cases h : r ≤ 35511
  · have hs := selected_digit_valid r (by omega)
    simpa [nearestDigit, h] using hs
  · have hc : 71023-r < 35512 := by omega
    have hs := selected_digit_valid (71023-r) hc
    have hn : nrm (-(selectedDigit (71023-r)).1)
        (-(selectedDigit (71023-r)).2) ≤ 23497 := by
      rw [neg_norm]
      exact hs.1
    have hm :
        (-(selectedDigit (71023-r)).1 -
         268*(selectedDigit (71023-r)).2 - (r : Int)) % 71023 = 0 := by
      omega
    constructor
    · simpa [nearestDigit, h] using hn
    · simp [nearestDigit, h]
      omega

theorem bounded_step (a b : Int) :
    ∃ d next : Int × Int,
      d = nearestDigit (((a+268*b)%71023).toNat) ∧
      nrm d.1 d.2 ≤ 154*154 ∧
      a = d.1 + 268*next.1 + 3*next.2 ∧
      b = d.2 - next.1 + 265*next.2 := by
  let residueWord : Int := (a+268*b)%71023
  let r : Nat := residueWord.toNat
  have hr0 : 0 ≤ residueWord := Int.emod_nonneg _ (by decide)
  have hrmax : residueWord < 71023 := Int.emod_lt _ (by decide)
  have hr : r < 71023 := by dsimp [r]; omega
  have hcast : (r : Int) = residueWord := by
    dsimp [r]
    rw [Int.ofNat_toNat]
    omega
  let d := nearestDigit r
  have hd := digit_valid r hr
  have hdmod : (d.1 + 268*d.2 - residueWord)%71023 = 0 := by
    simpa [d, hcast] using hd.2
  have hmod : ((a-d.1)+268*(b-d.2))%71023 = 0 := by
    dsimp [residueWord] at hdmod
    omega
  obtain ⟨k, hk⟩ := Int.dvd_of_emod_eq_zero hmod
  have hq : 71023*k = (a-d.1)+268*(b-d.2) := by omega
  let next : Int × Int := (265*k-(b-d.2), k)
  refine ⟨d, next, rfl, ?_, ?_, ?_⟩
  · have hn : nrm d.1 d.2 ≤ 23497 := by simpa [d] using hd.1
    omega
  · dsimp [next]
    omega
  · dsimp [next]
    omega

#print axioms neg_norm
#print axioms digit_valid
#print axioms bounded_step
end NearestOrbit71023Step
