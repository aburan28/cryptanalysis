-- expect: FAIL +uses_it +non-standard axioms: \[research_claim\]
-- A user axiom standing in for a claim.
axiom research_claim : ∀ n : Nat, n + 0 = n
theorem uses_it : (7 : Nat) + 0 = 7 := research_claim 7
