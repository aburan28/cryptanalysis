/-!
Q1529 checks finite arithmetic after the Q1462/Q1526 conditional query law.
It does not prove the probabilistic query law, rank novelty, or N131 base size.
Integer cross-products avoid rounded floating-point comparisons.
-/

namespace Q1529

def r83 : Nat := 2417851639230796216685689
def b83 : Nat := 30977592
def k83 : Nat := 186612
def t83 : Nat := 2^18
def d83 : Nat := 83 * k83 * (k83 - 1)
def repNum83 : Nat := 2 * r83 * d83
def repDen83 : Nat := b83 * b83 * t83 * 166

theorem n83_domain : d83 = 2890379710356 := by decide
theorem n83_representatives_between :
    2^48 * repDen83 < repNum83 ∧
    repNum83 < 2^49 * repDen83 := by decide
theorem n83_prefix_below_expectation :
    2^20 * repDen83 < repNum83 := by decide

def r131 : Nat := 680564733841876926932320129493409985129
def b7 : Nat := 118153819312
def k7 : Nat := 450968776
def table7 : Nat := 131 * k7 * k7
def oldNum7 : Nat := table7 * b7 * b7 + 4 * k7 * r131
def oldDen7 : Nat := b7 * b7
def reuseNum7 : Nat := table7 * 262 * b7 * b7 + 263 * k7 * 2 * r131
def reuseDen7 : Nat := 262 * b7 * b7

theorem quotient_reuse_saves_pair_additions :
    reuseNum7 * oldDen7 < oldNum7 * reuseDen7 := by decide
theorem quotient_reuse_between_exponents :
    2^85 * reuseDen7 < reuseNum7 ∧
    reuseNum7 < 2^86 * reuseDen7 := by decide
theorem quotient_reuse_above_challenge_pair_add_budget :
    2^61 * reuseDen7 < reuseNum7 := by decide

#print axioms n83_domain
#print axioms n83_representatives_between
#print axioms n83_prefix_below_expectation
#print axioms quotient_reuse_saves_pair_additions
#print axioms quotient_reuse_between_exponents
#print axioms quotient_reuse_above_challenge_pair_add_budget

end Q1529
