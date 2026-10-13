/- Every factor-base orbit needs at least one usable lifted seed. The finite
   census supplies valid <= 1094 for each losing two-bit offset. -/

namespace N83TwoShift

theorem losing_shift_below_winner (columns validLifts : Nat)
    (hOrbit : columns ≤ validLifts) (hCensus : validLifts ≤ 1094) :
    columns < 1109 :=
  Nat.lt_of_le_of_lt (Nat.le_trans hOrbit hCensus) (by decide)

#print axioms losing_shift_below_winner

end N83TwoShift
