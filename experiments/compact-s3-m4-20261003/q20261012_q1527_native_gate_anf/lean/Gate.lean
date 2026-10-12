/-! The exact local Boolean identity used by Q1527's native ANF conversion. -/

namespace Q1527

theorem and_gate_equivalence (a b z : Bool) :
    ((!z || a) && (!z || b) && (z || !a || !b)) =
      (z == (a && b)) := by
  cases a <;> cases b <;> cases z <;> decide

theorem replace_gate_in_context (context a b z : Bool) :
    (context && ((!z || a) && (!z || b) && (z || !a || !b))) =
      (context && (z == (a && b))) := by
  rw [and_gate_equivalence]

#print axioms and_gate_equivalence
#print axioms replace_gate_in_context

end Q1527
