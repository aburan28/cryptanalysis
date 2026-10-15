import NearestOrbit35533Step

namespace NearestOrbit35533Complete

open NearestOrbit35533Step SplitPrime12211Nearest

private theorem step_pair_exists (z : Int × Int) :
    ∃ pair : (Int × Int) × (Int × Int),
      pair.1 = nearestDigit (((z.1+190*z.2)%35533).toNat) ∧
      nrm pair.1.1 pair.1.2 ≤ 109*109 ∧
      z.1 = pair.1.1 + 190*pair.2.1 + 3*pair.2.2 ∧
      z.2 = pair.1.2 - pair.2.1 + 187*pair.2.2 := by
  obtain ⟨d, next, hd, hnorm, ha, hb⟩ := bounded_step z.1 z.2
  exact ⟨(d, next), hd, hnorm, ha, hb⟩

noncomputable def chooseStep (z : Int × Int) :
    (Int × Int) × (Int × Int) :=
  Classical.choose (step_pair_exists z)

theorem chooseStep_spec (z : Int × Int) :
    (chooseStep z).1 =
      nearestDigit (((z.1+190*z.2)%35533).toNat) ∧
    nrm (chooseStep z).1.1 (chooseStep z).1.2 ≤ 109*109 ∧
    z.1 = (chooseStep z).1.1 + 190*(chooseStep z).2.1 +
      3*(chooseStep z).2.2 ∧
    z.2 = (chooseStep z).1.2 - (chooseStep z).2.1 +
      187*(chooseStep z).2.2 := by
  exact Classical.choose_spec (step_pair_exists z)

noncomputable def stateAt (start : Int × Int) : Nat → Int × Int
  | 0 => start
  | i + 1 => (chooseStep (stateAt start i)).2

noncomputable def digitAt (start : Int × Int) (i : Nat) : Int × Int :=
  (chooseStep (stateAt start i)).1

theorem trajectory_direct_digit (start : Int × Int) (i : Nat) :
    digitAt start i =
      nearestDigit ((((stateAt start i).1 +
        190*(stateAt start i).2)%35533).toNat) := by
  simpa [digitAt] using (chooseStep_spec (stateAt start i)).1

theorem trajectory_step (start : Int × Int) (i : Nat) :
    nrm (digitAt start i).1 (digitAt start i).2 ≤ 109*109 ∧
    (stateAt start i).1 = (digitAt start i).1 +
      190*(stateAt start (i+1)).1 + 3*(stateAt start (i+1)).2 ∧
    (stateAt start i).2 = (digitAt start i).2 -
      (stateAt start (i+1)).1 + 187*(stateAt start (i+1)).2 := by
  simpa [digitAt, stateAt] using (chooseStep_spec (stateAt start i)).2

theorem canonical_scheme_terminal_bound (scalar : Int) :
    nrm (stateAt (selectedCandidate scalar) 16).1
      (stateAt (selectedCandidate scalar) 16).2 < 78*78 := by
  let start := selectedCandidate scalar
  apply NearestOrbit35533.selected_terminal_bound scalar
    (stateAt start) (digitAt start)
  · rfl
  · intro i _
    exact (trajectory_step start i).2
  · intro i _
    exact (trajectory_step start i).1

#print axioms chooseStep_spec
#print axioms trajectory_direct_digit
#print axioms trajectory_step
#print axioms canonical_scheme_terminal_bound

end NearestOrbit35533Complete
