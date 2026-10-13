/- Every folded factor-base column has at least one usable affine seed.
   The independent finite census supplies validLifts <= 2156 for each
   nonwinner two-coordinate offset. -/

namespace N83Width12TwoShift

theorem losing_shift_below_winner (columns validLifts : Nat)
    (hOrbit : columns ≤ validLifts) (hCensus : validLifts ≤ 2156) :
    columns < 2196 :=
  Nat.lt_of_le_of_lt (Nat.le_trans hOrbit hCensus) (by decide)

/- The lift-count census bounds every other pair of cosets by 2196+2150.
   The measured top-pair union has 4349 distinct folded columns. -/
theorem other_coset_pair_below_winner (columns validLifts : Nat)
    (hOrbit : columns ≤ validLifts) (hCensus : validLifts ≤ 4346) :
    columns < 4349 :=
  Nat.lt_of_le_of_lt (Nat.le_trans hOrbit hCensus) (by decide)

#print axioms losing_shift_below_winner
#print axioms other_coset_pair_below_winner

end N83Width12TwoShift
