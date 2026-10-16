import JointHorner

namespace Triple81Radix

open HornerRadix

/-- Multiplication by `81 + omega = 82 - tau` in the `(1,tau)` basis. -/
def primePair81 (x : Pair) : Pair :=
  (82*x.1 + 3*x.2, -x.1 + 79*x.2)

/-- Multiplication by the conjugate `79 + tau`. -/
def conjugatePair81 (x : Pair) : Pair :=
  (79*x.1 - 3*x.2, x.1 + 82*x.2)

/-- The exact integer quotient numerators in the native recoder. -/
theorem conjugate_primePair81 (x : Pair) :
    conjugatePair81 (primePair81 x) =
      (6481*x.1, 6481*x.2) := by
  rcases x with ⟨a,b⟩
  simp only [conjugatePair81, primePair81,
             Prod.mk.injEq]
  constructor <;> omega

/-- One exact division step preserves the represented scalar pair. -/
theorem quotient_step (current digit next : Pair)
    (quotient : conjugatePair81 (pairAdd current
      (-digit.1,-digit.2)) = (6481*next.1,6481*next.2)) :
    current = pairAdd digit (primePair81 next) := by
  rcases current with ⟨a,b⟩
  rcases digit with ⟨d,e⟩
  rcases next with ⟨u,v⟩
  simp only [conjugatePair81, primePair81, pairAdd,
             Prod.mk.injEq] at quotient ⊢
  rcases quotient with ⟨h₁,h₂⟩
  constructor <;> omega

def evaluatePairs81 (digits : List Pair) (terminal : Pair) : Pair :=
  match digits with
  | [] => terminal
  | digit :: rest => pairAdd digit (primePair81 (evaluatePairs81 rest terminal))

/-- The input and each quotient are explicit, so a trace cannot assert its
own final result without the exact division equations. -/
inductive ValidTrace81 : Pair → List Pair → Pair → Prop
  | terminal (z : Pair) : ValidTrace81 z [] z
  | step (z next digit terminal : Pair) (rest : List Pair)
      (equation : z = pairAdd digit (primePair81 next))
      (tail : ValidTrace81 next rest terminal) :
      ValidTrace81 z (digit :: rest) terminal

theorem valid_trace_evaluates (z terminal : Pair) (digits : List Pair)
    (trace : ValidTrace81 z digits terminal) :
    z = evaluatePairs81 digits terminal := by
  induction trace with
  | terminal z => rfl
  | step z next digit terminal rest equation tail ih =>
      simp [evaluatePairs81, equation, ih]

private theorem map_evaluate81 {Point : Type} (evaluate : Pair → Point)
    (add : Point → Point → Point) (prime : Point → Point)
    (map_add : ∀ x y, evaluate (pairAdd x y) = add (evaluate x) (evaluate y))
    (map_prime : ∀ x, evaluate (primePair81 x) = prime (evaluate x))
    (digits : List Pair) (terminal : Pair) :
    evaluate (evaluatePairs81 digits terminal) =
      evaluatePoints add prime (digits.map evaluate)
      (evaluate terminal) := by
  induction digits with
  | nil => rfl
  | cons digit rest ih =>
      simp [evaluatePairs81, evaluatePoints, map_add, map_prime, ih]

theorem point_horner81 {Point : Type} (evaluate : Pair → Point)
    (add : Point → Point → Point) (prime : Point → Point)
    (map_add : ∀ x y, evaluate (pairAdd x y) = add (evaluate x) (evaluate y))
    (map_prime : ∀ x, evaluate (primePair81 x) = prime (evaluate x))
    (z terminal : Pair) (digits : List Pair)
    (trace : ValidTrace81 z digits terminal) :
    evaluate z = evaluatePoints add prime (digits.map evaluate)
      (evaluate terminal) := by
  rw [valid_trace_evaluates z terminal digits trace]
  exact map_evaluate81 evaluate add prime map_add map_prime digits terminal

/-- Two scalar traces share the same `81 + omega` point recurrence. -/
theorem two_scalar_horner81 {Point : Type}
    (add : Point → Point → Point) (prime : Point → Point)
    (g q : Pair → Point)
    (assoc : ∀ x y z, add (add x y) z = add x (add y z))
    (comm : ∀ x y, add x y = add y x)
    (prime_add : ∀ x y, prime (add x y) = add (prime x) (prime y))
    (g_add : ∀ x y, g (pairAdd x y) = add (g x) (g y))
    (q_add : ∀ x y, q (pairAdd x y) = add (q x) (q y))
    (g_prime : ∀ x, g (primePair81 x) = prime (g x))
    (q_prime : ∀ x, q (primePair81 x) = prime (q x))
    (scalarG scalarQ terminalG terminalQ : Pair)
    (digits : List (Pair × Pair))
    (traceG : ValidTrace81 scalarG (digits.map Prod.fst) terminalG)
    (traceQ : ValidTrace81 scalarQ (digits.map Prod.snd) terminalQ) :
    add (g scalarG) (q scalarQ) =
      evaluatePoints add prime
        (digits.map (fun d => add (g d.1) (q d.2)))
        (add (g terminalG) (q terminalQ)) := by
  rw [point_horner81 g add prime g_add g_prime
      scalarG terminalG (digits.map Prod.fst) traceG]
  rw [point_horner81 q add prime q_add q_prime
      scalarQ terminalQ (digits.map Prod.snd) traceQ]
  simpa only [List.map_map, Function.comp_def] using
    (JointHorner.combine_horner add prime assoc comm prime_add g q
      digits terminalG terminalQ)

#print axioms conjugate_primePair81
#print axioms quotient_step
#print axioms valid_trace_evaluates
#print axioms point_horner81
#print axioms two_scalar_horner81

end Triple81Radix
