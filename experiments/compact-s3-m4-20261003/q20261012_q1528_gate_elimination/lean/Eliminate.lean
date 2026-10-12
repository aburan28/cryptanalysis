/-! Local Boolean equivalence and structural elimination for Q1528. -/

namespace Q1528

def gateClauses (a b z : Bool) : Bool :=
  ((!z || a) && (!z || b) && (z || !a || !b))

theorem gate_equivalence (a b z : Bool) :
    gateClauses a b z = true ↔ z = (a && b) := by
  cases a <;> cases b <;> cases z <;> decide

theorem eliminate_gate (a b : Bool) (rest : Bool → Prop) :
    (∃ z : Bool, gateClauses a b z = true ∧ rest z) ↔ rest (a && b) := by
  constructor
  · rintro ⟨z, hz, hr⟩
    have h : z = (a && b) := (gate_equivalence a b z).mp hz
    simpa [h] using hr
  · intro hr
    exact ⟨a && b, (gate_equivalence a b (a && b)).mpr rfl, hr⟩

theorem xor_substitution (a b z rest : Bool) (hz : z = (a && b)) :
    (Bool.xor z rest) = (Bool.xor (a && b) rest) := by
  subst z
  rfl

#print axioms gate_equivalence
#print axioms eliminate_gate
#print axioms xor_substitution

end Q1528
