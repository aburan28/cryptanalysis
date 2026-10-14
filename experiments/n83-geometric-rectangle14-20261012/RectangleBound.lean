/- The exhaustive 2,914,905-rectangle census supplies the bound 8509
   for each rectangle other than the selected one. The finite-field census
   and the orbit-cardinality bridge are independently checked artifacts,
   outside this core Lean module. -/

namespace N83Rectangle14

theorem other_rectangle_below_winner (columns validLifts : Nat)
    (hOrbit : columns ≤ validLifts) (hCensus : validLifts ≤ 8509) :
    columns < 8532 :=
  Nat.lt_of_le_of_lt (Nat.le_trans hOrbit hCensus) (by decide)

theorem winner_exceeds_prior_width14 : 8261 < 8532 := by decide

theorem winner_usable_points : 166 * 8532 = 1416312 := by decide

#print axioms other_rectangle_below_winner
#print axioms winner_exceeds_prior_width14
#print axioms winner_usable_points

end N83Rectangle14
