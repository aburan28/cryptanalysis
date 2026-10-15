import Lean
import SplitPrime12211DirectBound

namespace SplitPrime12211DirectDigits

def directDigit (r : Nat) : Int :=
  if r ≤ 6105 then (r : Int) else (r : Int) - 12211

theorem direct_digit_bounds (r : Nat) (hr : r < 12211) :
    -6105 ≤ directDigit r ∧ directDigit r ≤ 6105 := by
  by_cases h : r ≤ 6105
  · simp [directDigit, h] <;> omega
  · simp [directDigit, h] <;> omega

theorem direct_digit_residue (r : Nat) (hr : r < 12211) :
    directDigit r % 12211 = (r : Int) := by
  by_cases h : r ≤ 6105
  · simp [directDigit, h] <;> omega
  · simp [directDigit, h] <;> omega

theorem direct_digit_norm (r : Nat) (hr : r < 12211) :
    nrm (directDigit r) 0 ≤ 6105*6105 := by
  have hb := direct_digit_bounds r hr
  simp [nrm]
  exact square_le_abs (directDigit r) 6105 (by decide) hb.1 hb.2

theorem bounded_step (a b : Int) :
    ∃ d : Int, ∃ next : Int × Int,
      d = directDigit (((a+112*b)%12211).toNat) ∧
      nrm d 0 ≤ 6105*6105 ∧
      a = d + 112*next.1 + 3*next.2 ∧
      b = -next.1 + 109*next.2 := by
  let residueWord : Int := (a+112*b)%12211
  let r : Nat := residueWord.toNat
  have hr0 : 0 ≤ residueWord := Int.emod_nonneg _ (by decide)
  have hrmax : residueWord < 12211 := Int.emod_lt _ (by decide)
  have hr : r < 12211 := by dsimp [r]; omega
  have hcast : (r : Int) = residueWord := by
    dsimp [r]
    rw [Int.ofNat_toNat]
    omega
  let d := directDigit r
  have hdmod : d % 12211 = residueWord := by
    dsimp [d]
    rw [direct_digit_residue r hr, hcast]
  have hmod : ((a-d)+112*b)%12211 = 0 := by
    dsimp [residueWord] at hdmod
    omega
  obtain ⟨k, hk⟩ := Int.dvd_of_emod_eq_zero hmod
  have hq : 12211*k = (a-d)+112*b := by omega
  have hq' : 12211*k = (a-d)+112*(b-0) := by omega
  let next : Int × Int := (109*k-b, k)
  refine ⟨d, next, rfl, direct_digit_norm r hr, ?_, ?_⟩
  · have hs := SplitPrime12211Direct.recoding_step_identity a b d 0 k hq'
    simpa [next] using hs.1
  · have hs := SplitPrime12211Direct.recoding_step_identity a b d 0 k hq'
    simpa [next] using hs.2

#print axioms direct_digit_bounds
#print axioms direct_digit_residue
#print axioms direct_digit_norm
#print axioms bounded_step

end SplitPrime12211DirectDigits
