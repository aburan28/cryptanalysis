import Lean

namespace PrimeJ0Radix943Recoding

-- One coordinate of the signed Eisenstein representative. Each recorded
-- digit/quotient step must satisfy this exact integer equation.
inductive Steps (base : Int) : Int → List Int → Int → Prop where
  | done (terminal : Int) : Steps base terminal [] terminal
  | next {state quotient terminal : Int} {tail : List Int}
      (digit : Int) (equation : state = digit + base * quotient)
      (rest : Steps base quotient tail terminal) :
      Steps base state (digit :: tail) terminal

def value (base : Int) : List Int → Int
  | [] => 0
  | digit :: tail => digit + base * value base tail

theorem reconstruct (base start terminal : Int) (digits : List Int)
    (h : Steps base start digits terminal) :
    start = value base digits + base ^ digits.length * terminal := by
  induction h with
  | done terminal => simp [value]
  | next digit equation rest ih =>
      simp only [value, List.length_cons, Int.pow_succ']
      rw [equation, ih]
      simp only [Int.mul_add, Int.mul_assoc, Int.add_assoc]

theorem reconstruct_zero (base start : Int) (digits : List Int)
    (h : Steps base start digits 0) : start = value base digits := by
  have reconstructed := reconstruct base start 0 digits h
  simpa using reconstructed

-- The Rust recoder applies the same radix step to both integer coordinates
-- of a short Eisenstein representative; there is no hidden modular reduction.
theorem reconstruct_pair (first second : Int)
    (firstDigits secondDigits : List Int)
    (firstSteps : Steps 943 first firstDigits 0)
    (secondSteps : Steps 943 second secondDigits 0) :
    first = value 943 firstDigits ∧ second = value 943 secondDigits := by
  exact ⟨reconstruct_zero 943 first firstDigits firstSteps,
    reconstruct_zero 943 second secondDigits secondSteps⟩

#print axioms reconstruct
#print axioms reconstruct_zero
#print axioms reconstruct_pair

end PrimeJ0Radix943Recoding
