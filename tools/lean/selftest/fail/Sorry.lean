-- expect: FAIL +main_claim +non-standard axioms: \[sorryAx\]
-- `main_claim` contains no `sorry` itself; the gate must catch it through `helper`.
theorem helper : 2 + 2 = 5 := sorry
theorem main_claim : 2 + 2 = 5 ∧ True := ⟨helper, trivial⟩
