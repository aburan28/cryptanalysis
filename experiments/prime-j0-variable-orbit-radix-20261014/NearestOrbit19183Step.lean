import NearestOrbit19183Digits

namespace NearestOrbit19183Step
open NearestOrbit19183Digits NearestOrbit19183Selector SplitPrime12211Nearest

noncomputable def nearestDigit (r : Nat) : Int × Int :=
  if r ≤ 9591 then selectedDigit r
  else let d := selectedDigit (19183-r); (-d.1, -d.2)

theorem neg_norm (a b : Int) : nrm (-a) (-b) = nrm a b := by
  unfold nrm
  grind

theorem digit_valid (r : Nat) (hr : r < 19183) :
    nrm (nearestDigit r).1 (nearestDigit r).2 ≤ 6348 ∧
    ((nearestDigit r).1 + 140*(nearestDigit r).2 - (r : Int)) % 19183 = 0 := by
  by_cases h : r ≤ 9591
  · have hs := selected_digit_valid r (by omega)
    simpa [nearestDigit, h] using hs
  · have hc : 19183-r < 9592 := by omega
    have hs := selected_digit_valid (19183-r) hc
    have hn : nrm (-(selectedDigit (19183-r)).1)
        (-(selectedDigit (19183-r)).2) ≤ 6348 := by
      rw [neg_norm]
      exact hs.1
    have hm :
        (-(selectedDigit (19183-r)).1 -
         140*(selectedDigit (19183-r)).2 - (r : Int)) % 19183 = 0 := by
      omega
    constructor
    · simpa [nearestDigit, h] using hn
    · simp [nearestDigit, h]
      omega

theorem bounded_step (a b : Int) :
    ∃ d next : Int × Int,
      d = nearestDigit (((a+140*b)%19183).toNat) ∧
      nrm d.1 d.2 ≤ 80*80 ∧
      a = d.1 + 140*next.1 + 3*next.2 ∧
      b = d.2 - next.1 + 137*next.2 := by
  let residueWord : Int := (a+140*b)%19183
  let r : Nat := residueWord.toNat
  have hr0 : 0 ≤ residueWord := Int.emod_nonneg _ (by decide)
  have hrmax : residueWord < 19183 := Int.emod_lt _ (by decide)
  have hr : r < 19183 := by dsimp [r]; omega
  have hcast : (r : Int) = residueWord := by
    dsimp [r]
    rw [Int.ofNat_toNat]
    omega
  let d := nearestDigit r
  have hd := digit_valid r hr
  have hdmod : (d.1 + 140*d.2 - residueWord)%19183 = 0 := by
    simpa [d, hcast] using hd.2
  have hmod : ((a-d.1)+140*(b-d.2))%19183 = 0 := by
    dsimp [residueWord] at hdmod
    omega
  obtain ⟨k, hk⟩ := Int.dvd_of_emod_eq_zero hmod
  have hq : 19183*k = (a-d.1)+140*(b-d.2) := by omega
  let next : Int × Int := (137*k-(b-d.2), k)
  refine ⟨d, next, rfl, ?_, ?_, ?_⟩
  · have hn : nrm d.1 d.2 ≤ 6348 := by simpa [d] using hd.1
    omega
  · dsimp [next]
    omega
  · dsimp [next]
    omega

#print axioms neg_norm
#print axioms digit_valid
#print axioms bounded_step
end NearestOrbit19183Step
