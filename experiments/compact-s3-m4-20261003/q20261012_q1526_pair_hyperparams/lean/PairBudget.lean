/-!
Finite integer checks for Q1526's frozen conditional pair-index inputs.
The query-floor inequality is cross-multiplied by the positive integer B².
The probabilistic input law and the pair-index success model remain explicit
assumptions in protocol.json; these theorems check its numerical consequences.
-/

namespace Q1526

def r : Nat := 680564733841876926932320129493409985129

theorem w5_query_addition_floor :
    2^61 * 309633434 * 309633434 < 4 * 1181807 * r := by decide

theorem w6_query_addition_floor :
    2^61 * 6559634788 * 6559634788 < 4 * 25036774 * r := by decide

theorem w7_query_addition_floor :
    2^61 * 118153819312 * 118153819312 < 4 * 450968776 * r := by decide

theorem w8_query_addition_floor :
    2^61 * 1844590711506 * 1844590711506 < 4 * 7040422563 * r := by decide

theorem w7_matrix_proxy_below_budget :
    4 * 450968776 * 450968776 < 2^61 := by decide

theorem w8_matrix_proxy_above_budget :
    2^61 < 4 * 7040422563 * 7040422563 := by decide

#print axioms w5_query_addition_floor
#print axioms w6_query_addition_floor
#print axioms w7_query_addition_floor
#print axioms w8_query_addition_floor
#print axioms w7_matrix_proxy_below_budget
#print axioms w8_matrix_proxy_above_budget

end Q1526
