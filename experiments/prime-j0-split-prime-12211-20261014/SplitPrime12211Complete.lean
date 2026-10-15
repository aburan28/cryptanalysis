import SplitPrime12211Digits

namespace SplitPrime12211Complete

open SplitPrime12211Digits

private theorem step_pair_exists (z : Int × Int) :
    ∃ pair : (Int × Int) × (Int × Int),
      (∃ m u : Nat,
        m = canonicalSeed (((z.1+112*z.2)%12211).toNat) ∧
        u < 6 ∧ pair.1 = digitPair m u) ∧
      nrm pair.1.1 pair.1.2 ≤ 4033*4033 ∧
      z.1 = pair.1.1 + 112*pair.2.1 + 3*pair.2.2 ∧
      z.2 = pair.1.2 - pair.2.1 + 109*pair.2.2 := by
  obtain ⟨m, u, next, hm, _, hu, hnorm, ha, hb⟩ := bounded_step z.1 z.2
  exact ⟨(digitPair m u, next), ⟨m, u, hm, hu, rfl⟩,
    hnorm, ha, hb⟩

noncomputable def chooseStep (z : Int × Int) :
    (Int × Int) × (Int × Int) :=
  Classical.choose (step_pair_exists z)

theorem chooseStep_spec (z : Int × Int) :
    (∃ m u : Nat,
      m = canonicalSeed (((z.1+112*z.2)%12211).toNat) ∧
      u < 6 ∧ (chooseStep z).1 = digitPair m u) ∧
    nrm (chooseStep z).1.1 (chooseStep z).1.2 ≤ 4033*4033 ∧
    z.1 = (chooseStep z).1.1 + 112*(chooseStep z).2.1 + 3*(chooseStep z).2.2 ∧
    z.2 = (chooseStep z).1.2 - (chooseStep z).2.1 + 109*(chooseStep z).2.2 := by
  exact Classical.choose_spec (step_pair_exists z)

noncomputable def stateAt (start : Int × Int) : Nat → Int × Int
  | 0 => start
  | i + 1 => (chooseStep (stateAt start i)).2

noncomputable def digitAt (start : Int × Int) (i : Nat) : Int × Int :=
  (chooseStep (stateAt start i)).1

theorem trajectory_table_digit (start : Int × Int) (i : Nat) :
    ∃ m u : Nat,
      m = canonicalSeed ((((stateAt start i).1 +
        112*(stateAt start i).2)%12211).toNat) ∧
      u < 6 ∧ digitAt start i = digitPair m u := by
  simpa [digitAt] using (chooseStep_spec (stateAt start i)).1

theorem trajectory_step (start : Int × Int) (i : Nat) :
    nrm (digitAt start i).1 (digitAt start i).2 ≤ 4033*4033 ∧
    (stateAt start i).1 = (digitAt start i).1 +
      112*(stateAt start (i+1)).1 + 3*(stateAt start (i+1)).2 ∧
    (stateAt start i).2 = (digitAt start i).2 -
      (stateAt start (i+1)).1 + 109*(stateAt start (i+1)).2 := by
  simpa [digitAt, stateAt] using (chooseStep_spec (stateAt start i)).2

theorem canonical_scheme_terminal_bound (scalar : Int) :
    nrm (stateAt (selectedCandidate scalar) 18).1
      (stateAt (selectedCandidate scalar) 18).2 < 70*70 := by
  let start := selectedCandidate scalar
  apply SplitPrime12211.selected_terminal_bound scalar
    (stateAt start) (digitAt start)
  · rfl
  · intro i _
    exact (trajectory_step start i).2
  · intro i _
    exact (trajectory_step start i).1

#print axioms chooseStep_spec
#print axioms trajectory_table_digit
#print axioms trajectory_step
#print axioms canonical_scheme_terminal_bound

end SplitPrime12211Complete
