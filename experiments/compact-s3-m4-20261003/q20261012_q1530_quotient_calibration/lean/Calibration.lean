/-!
Finite checks for the Q1530 conditional quotient-reuse sweep.
The uniform query-success law, sampled W7/W8 base sizes, and rank novelty
are assumptions from the frozen Q1526 protocol, not theorems here.
-/

namespace Q1530

def r : Nat := 680564733841876926932320129493409985129
def baseB (w : Nat) : Nat :=
  if w == 5 then 309633434 else
  if w == 6 then 6559634788 else
  if w == 7 then 118153819312 else 1844590711506
def columns (w : Nat) : Nat :=
  if w == 5 then 1181807 else
  if w == 6 then 25036774 else
  if w == 7 then 450968776 else 7040422563

-- T = 131 K² / 2^j and Q = K 2r 2^j / B².
-- The quotient-reuse cost is T + (263/262) Q.
def costNum (w j : Nat) : Nat :=
  131 * columns w ^ 2 * 262 * baseB w ^ 2 +
    263 * columns w * 2 * r * 2^(2*j)
def costDen (w j : Nat) : Nat := 2^j * 262 * baseB w ^ 2
def matrixEligible (w : Nat) : Bool := 4 * columns w ^ 2 < 2^61

theorem n53_unique_key_coverage_below_descriptor_fraction :
    1418520 * 2743068 < 2000000 * 2730335 := by decide
theorem w8_matrix_exceeds_budget :
    2^61 < 4 * columns 8 ^ 2 := by decide
theorem w7_full_pair_additions_above_budget :
    2^61 * costDen 7 0 < costNum 7 0 := by decide
theorem all_84_cells_have_at_least_w7_full_cost_when_matrix_eligible :
    ([5, 6, 7, 8] : List Nat).all (fun w =>
      (List.range 21).all (fun j =>
        !matrixEligible w ||
          costNum 7 0 * costDen w j ≤ costNum w j * costDen 7 0)) = true := by decide

#print axioms n53_unique_key_coverage_below_descriptor_fraction
#print axioms w8_matrix_exceeds_budget
#print axioms w7_full_pair_additions_above_budget
#print axioms all_84_cells_have_at_least_w7_full_cost_when_matrix_eligible

end Q1530
