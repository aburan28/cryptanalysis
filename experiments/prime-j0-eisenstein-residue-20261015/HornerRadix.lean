import AlternateRadix

namespace HornerRadix

abbrev Pair := Int × Int

def pairAdd (x y : Pair) : Pair := (x.1 + y.1, x.2 + y.2)

def primePair (x : Pair) : Pair :=
  AlternateRadix.multiplyPrime 334 x.1 x.2

/-- Reconstruct the scalar-lattice pair from low-to-high digits. -/
def evaluatePairs (digits : List Pair) (terminal : Pair) : Pair :=
  match digits with
  | [] => terminal
  | digit :: rest =>
      pairAdd digit (primePair (evaluatePairs rest terminal))

/-- A trace records every exact quotient step, including its final pair. -/
inductive ValidTrace : Pair → List Pair → Pair → Prop
  | terminal (z : Pair) : ValidTrace z [] z
  | step (z next digit terminal : Pair) (rest : List Pair)
      (equation : z = pairAdd digit (primePair next))
      (tail : ValidTrace next rest terminal) :
      ValidTrace z (digit :: rest) terminal

theorem valid_trace_evaluates (z terminal : Pair) (digits : List Pair)
    (trace : ValidTrace z digits terminal) :
    z = evaluatePairs digits terminal := by
  induction trace with
  | terminal z => rfl
  | step z next digit terminal rest equation tail ih =>
      simp [evaluatePairs, equation, ih]

/-- Horner evaluation in an arbitrary point representation. -/
def evaluatePoints {Point : Type} (add : Point → Point → Point)
    (prime : Point → Point) (digits : List Point) (terminal : Point) : Point :=
  match digits with
  | [] => terminal
  | digit :: rest => add digit (prime (evaluatePoints add prime rest terminal))

/-- Pair evaluation commutes with the entire Horner chain when it preserves
addition and multiplication by the exact digit prime. -/
theorem map_evaluatePairs {Point : Type} (evaluate : Pair → Point)
    (add : Point → Point → Point) (prime : Point → Point)
    (map_add : ∀ x y, evaluate (pairAdd x y) = add (evaluate x) (evaluate y))
    (map_prime : ∀ x, evaluate (primePair x) =
      prime (evaluate x))
    (digits : List Pair) (terminal : Pair) :
    evaluate (evaluatePairs digits terminal) =
      evaluatePoints add prime (digits.map evaluate) (evaluate terminal) := by
  induction digits with
  | nil => rfl
  | cons digit rest ih =>
      simp [evaluatePairs, evaluatePoints, map_add, map_prime, ih]

/-- Exact recoder steps and an evaluation map imply equality of the original
pair's point with the point Horner recurrence. The map premises expose the
curve and endomorphism bridge needed by a concrete implementation. -/
theorem point_horner_of_valid_trace {Point : Type} (evaluate : Pair → Point)
    (add : Point → Point → Point) (prime : Point → Point)
    (map_add : ∀ x y, evaluate (pairAdd x y) = add (evaluate x) (evaluate y))
    (map_prime : ∀ x, evaluate (primePair x) =
      prime (evaluate x))
    (z terminal : Pair) (digits : List Pair)
    (trace : ValidTrace z digits terminal) :
    evaluate z =
      evaluatePoints add prime (digits.map evaluate) (evaluate terminal) := by
  rw [valid_trace_evaluates z terminal digits trace]
  exact map_evaluatePairs evaluate add prime map_add map_prime digits terminal

#print axioms valid_trace_evaluates
#print axioms map_evaluatePairs
#print axioms point_horner_of_valid_trace

end HornerRadix
