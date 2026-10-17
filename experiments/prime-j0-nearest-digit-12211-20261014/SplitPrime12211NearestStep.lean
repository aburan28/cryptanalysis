import SplitPrime12211NearestDigits

namespace SplitPrime12211NearestStep
open SplitPrime12211NearestDigits

noncomputable def nearestDigit (r : Nat) : Int × Int :=
  if r ≤ 6105 then selectedDigit r
  else let d := selectedDigit (12211-r); (-d.1, -d.2)

theorem neg_norm (a b : Int) : nrm (-a) (-b) = nrm a b := by
  unfold nrm
  grind

theorem digit_valid (r : Nat) (hr : r < 12211) :
    nrm (nearestDigit r).1 (nearestDigit r).2 ≤ 3997 ∧
    ((nearestDigit r).1 + 112*(nearestDigit r).2 - (r : Int)) % 12211 = 0 := by
  by_cases h : r ≤ 6105
  · have hs := selected_digit_valid r (by omega)
    simpa [nearestDigit, h] using hs
  · have hc : 12211-r < 6106 := by omega
    have hs := selected_digit_valid (12211-r) hc
    have hn : nrm (-(selectedDigit (12211-r)).1)
        (-(selectedDigit (12211-r)).2) ≤ 3997 := by
      rw [neg_norm]
      exact hs.1
    have hm :
        (-(selectedDigit (12211-r)).1 -
         112*(selectedDigit (12211-r)).2 - (r : Int)) % 12211 = 0 := by
      omega
    constructor
    · simpa [nearestDigit, h] using hn
    · simp [nearestDigit, h]
      omega

theorem bounded_step (a b : Int) :
    ∃ d next : Int × Int,
      d = nearestDigit (((a+112*b)%12211).toNat) ∧
      nrm d.1 d.2 ≤ 64*64 ∧
      a = d.1 + 112*next.1 + 3*next.2 ∧
      b = d.2 - next.1 + 109*next.2 := by
  let residueWord : Int := (a+112*b)%12211
  let r : Nat := residueWord.toNat
  have hr0 : 0 ≤ residueWord := Int.emod_nonneg _ (by decide)
  have hrmax : residueWord < 12211 := Int.emod_lt _ (by decide)
  have hr : r < 12211 := by dsimp [r]; omega
  have hcast : (r : Int) = residueWord := by
    dsimp [r]
    rw [Int.ofNat_toNat]
    omega
  let d := nearestDigit r
  have hd := digit_valid r hr
  have hdmod : (d.1 + 112*d.2 - residueWord)%12211 = 0 := by
    simpa [d, hcast] using hd.2
  have hmod : ((a-d.1)+112*(b-d.2))%12211 = 0 := by
    dsimp [residueWord] at hdmod
    omega
  obtain ⟨k, hk⟩ := Int.dvd_of_emod_eq_zero hmod
  have hq : 12211*k = (a-d.1)+112*(b-d.2) := by omega
  let next : Int × Int := (109*k-(b-d.2), k)
  refine ⟨d, next, rfl, ?_, ?_, ?_⟩
  · have hn : nrm d.1 d.2 ≤ 3997 := by simpa [d] using hd.1
    omega
  · have hs := SplitPrime12211Nearest.recoding_step_identity a b d.1 d.2 k hq
    simpa [next] using hs.1
  · have hs := SplitPrime12211Nearest.recoding_step_identity a b d.1 d.2 k hq
    simpa [next] using hs.2

#print axioms neg_norm
#print axioms digit_valid
#print axioms bounded_step
end SplitPrime12211NearestStep
