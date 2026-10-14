import SplitPrimeLatticeCell
import SplitPrimeNormBound
import SplitPrimeDigitChoice

open SplitPrimeRadix SplitPrimeDigitChoice

noncomputable def stateAt (start : Coeff) : Nat → Coeff
  | 0 => start
  | i + 1 => (chooseStep (stateAt start i)).2

noncomputable def digitAt (start : Coeff) (i : Nat) : Coeff :=
  (chooseStep (stateAt start i)).1

theorem trajectory_step (start : Coeff) (i : Nat) :
    norm (digitAt start i) ≤ 1064*1064 ∧
    stateAt start i = add (digitAt start i) (piMul (stateAt start (i+1))) := by
  have h := chooseStep_spec (stateAt start i)
  simpa [digitAt, stateAt] using h.2

theorem trajectory_table_digit (start : Coeff) (i : Nat) :
    ∃ m : Nat, ∃ u : UnitCode,
      (m = 0 ∨ m ∈ SplitPrimeCanonicalSeeds.seeds) ∧
      digitAt start i = digit (m : Int) u := by
  have h := (chooseStep_spec (stateAt start i)).1
  simpa [digitAt] using h

-- Python breaks equal-norm ties using coordinate magnitudes and coordinates.
-- The terminal theorem depends only on the minimum norm, so it covers every
-- candidate selected by that tie policy.
theorem min_norm_scalar_terminal_bound (scalar : Int)
    (state digit : Nat → Int × Int)
    (hstartNorm : nrm (state 0).1 (state 0).2 = selectedNorm scalar)
    (hstep : ∀ i < 21,
      (state i).1 = (digit i).1 + 86*(state (i+1)).1 + 63*(state (i+1)).2 ∧
      (state i).2 = (digit i).2 - 21*(state (i+1)).1 + 23*(state (i+1)).2)
    (hdigit : ∀ i < 21, nrm (digit i).1 (digit i).2 ≤ 1064*1064) :
    nrm (state 21).1 (state 21).2 < 46*46 := by
  have hcell : 3*nrm (state 0).1 (state 0).2 ≤
      115792089237316195423570985008687907852837564279074904382605163141518161494337 := by
    rw [hstartNorm]
    have h := selected_norm_bound scalar
    simpa [order] using h
  exact terminal_bound_from_cell state digit hcell hstep hdigit

theorem selected_candidate_terminal_bound (scalar : Int)
    (state digit : Nat → Int × Int)
    (hstart : state 0 = selectedCandidate scalar)
    (hstep : ∀ i < 21,
      (state i).1 = (digit i).1 + 86*(state (i+1)).1 + 63*(state (i+1)).2 ∧
      (state i).2 = (digit i).2 - 21*(state (i+1)).1 + 23*(state (i+1)).2)
    (hdigit : ∀ i < 21, nrm (digit i).1 (digit i).2 ≤ 1064*1064) :
    nrm (state 21).1 (state 21).2 < 46*46 := by
  apply min_norm_scalar_terminal_bound scalar state digit
  · rw [hstart]
    simpa [nrm, eNorm] using selected_candidate_norm scalar
  · exact hstep
  · exact hdigit

theorem canonical_scheme_terminal_bound (scalar : Int) :
    nrm (stateAt (selectedCandidate scalar) 21).1
      (stateAt (selectedCandidate scalar) 21).2 < 46*46 := by
  let start := selectedCandidate scalar
  apply selected_candidate_terminal_bound scalar (stateAt start) (digitAt start)
  · rfl
  · intro i _
    have h := (trajectory_step start i).2
    dsimp [add, piMul] at h
    have h1 := congrArg Prod.fst h
    have h2 := congrArg Prod.snd h
    constructor <;> omega
  · intro i _
    have h := (trajectory_step start i).1
    simpa [nrm, norm] using h

#print axioms min_norm_scalar_terminal_bound
#print axioms selected_candidate_terminal_bound
#print axioms trajectory_step
#print axioms trajectory_table_digit
#print axioms canonical_scheme_terminal_bound
