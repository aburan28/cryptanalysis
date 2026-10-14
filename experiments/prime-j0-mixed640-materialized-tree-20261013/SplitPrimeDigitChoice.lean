import SplitPrimeCanonicalCover
import SplitPrimeRadix
import SplitPrimeLatticeCell

namespace SplitPrimeDigitChoice
open SplitPrimeCanonicalSeeds SplitPrimeCanonicalCover SplitPrimeRadix

inductive UnitCode where
  | pos0 | neg0 | pos1 | neg1 | pos2 | neg2

def multiplier : UnitCode → Nat
  | .pos0 => 1
  | .neg0 => 3300
  | .pos1 => 1726
  | .neg1 => 1575
  | .pos2 => 1574
  | .neg2 => 1727

def digit (m : Int) : UnitCode → Coeff
  | .pos0 => (m, 0)
  | .neg0 => (-m, 0)
  | .pos1 => omegaMul (m, 0)
  | .neg1 => (-(omegaMul (m, 0)).1, -(omegaMul (m, 0)).2)
  | .pos2 => omegaMul (omegaMul (m, 0))
  | .neg2 => (-(omegaMul (omegaMul (m, 0))).1,
              -(omegaMul (omegaMul (m, 0))).2)

theorem digit_norm (m : Int) (u : UnitCode) :
    norm (digit m u) = m*m := by
  have h := unit_seed_norm m
  cases u with
  | pos0 => simpa [digit] using h.1
  | neg0 => simp [digit, norm]; grind
  | pos1 => simpa [digit] using h.2.1
  | neg1 => simpa [digit, norm_neg] using h.2.1
  | pos2 => simpa [digit] using h.2.2
  | neg2 => simpa [digit, norm_neg] using h.2.2

theorem digit_residue (m : Int) (u : UnitCode) :
    unitResidue (digit m u) = ((multiplier u : Nat) : Int)*m % 3301 := by
  have h := unit_seed_residue_forms m
  cases u with
  | pos0 => simpa [digit, multiplier] using h.1
  | neg0 => simpa [digit, multiplier] using h.2.1
  | pos1 => simpa [digit, multiplier] using h.2.2.1
  | neg1 => simpa [digit, multiplier] using h.2.2.2.1
  | pos2 => simpa [digit, multiplier] using h.2.2.2.2.1
  | neg2 => simpa [digit, multiplier] using h.2.2.2.2.2

theorem cast_mod (c r m : Nat) (h : r = (c*m)%3301) :
    (r : Int) = ((c : Int)*(m : Int))%3301 := by
  have hh := congrArg (fun x : Nat => (x : Int)) h
  simp only [Int.natCast_emod, Int.natCast_mul] at hh
  have h3301 : ((3301 : Nat) : Int) = (3301 : Int) := by decide
  rw [h3301] at hh
  exact hh

theorem code_of_form (r m : Nat) (hm : m ≤ 1064)
    (h : r = m ∨ r = (3300*m)%3301 ∨ r = (1726*m)%3301 ∨
      r = (1575*m)%3301 ∨ r = (1574*m)%3301 ∨ r = (1727*m)%3301) :
    ∃ u : UnitCode, r = (multiplier u*m)%3301 := by
  rcases h with h | h | h | h | h | h
  · refine ⟨.pos0, ?_⟩
    simp [multiplier]
    omega
  · exact ⟨.neg0, by simpa [multiplier] using h⟩
  · exact ⟨.pos1, by simpa [multiplier] using h⟩
  · exact ⟨.neg1, by simpa [multiplier] using h⟩
  · exact ⟨.pos2, by simpa [multiplier] using h⟩
  · exact ⟨.neg2, by simpa [multiplier] using h⟩

theorem bounded_canonical_digit (r : Nat) (hr : r < 3301) :
    ∃ m : Nat, ∃ u : UnitCode,
      (m = 0 ∨ m ∈ seeds) ∧
      norm (digit (m : Int) u) ≤ 1064*1064 ∧
      unitResidue (digit (m : Int) u) = (r : Int) := by
  obtain ⟨m, hm, hc, hform⟩ := all_residues_covered r hr
  obtain ⟨u, hu⟩ := code_of_form r m hm hform
  refine ⟨m, u, ?_, ?_, ?_⟩
  · rcases hc with hz | hcanon
    · exact Or.inl hz
    · exact Or.inr (canonical_mem m hm hcanon)
  · rw [digit_norm]
    have hm0 : 0 ≤ (m : Int) := by omega
    have hmi : (m : Int) ≤ 1064 := by omega
    exact square_le_abs (m : Int) 1064 (by decide) (by omega) hmi
  · rw [digit_residue]
    exact (cast_mod (multiplier u) r m hu).symm

theorem bounded_unit_step (a b : Int) :
    ∃ m : Nat, ∃ u : UnitCode, ∃ next : Coeff,
      (m = 0 ∨ m ∈ seeds) ∧
      norm (digit (m : Int) u) ≤ 1064*1064 ∧
      (a, b) = add (digit (m : Int) u) (piMul next) := by
  let residue : Int := (a+1576*b)%3301
  let r : Nat := residue.toNat
  have hr0 : 0 ≤ residue := Int.emod_nonneg _ (by decide)
  have hrmax : residue < 3301 := Int.emod_lt _ (by decide)
  have hr : r < 3301 := by dsimp [r]; omega
  have hcast : (r : Int) = residue := by
    dsimp [r]
    rw [Int.ofNat_toNat]
    omega
  obtain ⟨m, u, hmem, hnorm, hres⟩ := bounded_canonical_digit r hr
  let d := digit (m : Int) u
  have hres' : (d.1+1576*d.2)%3301 = residue := by
    change (d.1+1576*d.2)%3301 = (r : Int) at hres
    rw [hcast] at hres
    exact hres
  have hmod : ((a-d.1)+1576*(b-d.2))%3301 = 0 := by
    dsimp [residue] at hres'
    omega
  obtain ⟨k, hk⟩ := Int.dvd_of_emod_eq_zero hmod
  have hq : 3301*k = (a-d.1)+1576*(b-d.2) := by omega
  let next : Coeff := (23*k-11*(b-d.2), 21*k-10*(b-d.2))
  refine ⟨m, u, next, hmem, hnorm, ?_⟩
  have hs := unit_digit_step_identity a b d.1 d.2 k hq
  simpa [d, next] using hs.symm

theorem step_pair_exists (z : Coeff) :
    ∃ p : Coeff × Coeff,
      (∃ m : Nat, ∃ u : UnitCode,
        (m = 0 ∨ m ∈ seeds) ∧ p.1 = digit (m : Int) u) ∧
      norm p.1 ≤ 1064*1064 ∧ z = add p.1 (piMul p.2) := by
  obtain ⟨m, u, next, hmem, hn, hz⟩ := bounded_unit_step z.1 z.2
  exact ⟨(digit (m : Int) u, next), ⟨m, u, hmem, rfl⟩, hn, hz⟩

noncomputable def chooseStep (z : Coeff) : Coeff × Coeff :=
  Classical.choose (step_pair_exists z)

theorem chooseStep_spec (z : Coeff) :
    (∃ m : Nat, ∃ u : UnitCode,
      (m = 0 ∨ m ∈ seeds) ∧
      (chooseStep z).1 = digit (m : Int) u) ∧
    norm (chooseStep z).1 ≤ 1064*1064 ∧
    z = add (chooseStep z).1 (piMul (chooseStep z).2) :=
  Classical.choose_spec (step_pair_exists z)

#print axioms digit_norm
#print axioms digit_residue
#print axioms bounded_canonical_digit
#print axioms bounded_unit_step
#print axioms chooseStep_spec

end SplitPrimeDigitChoice
