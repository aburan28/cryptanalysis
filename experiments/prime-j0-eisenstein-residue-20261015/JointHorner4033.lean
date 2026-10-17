import HornerRadix

namespace JointHorner4033

open HornerRadix

/-- The implementation interleaves the G and Q digits and applies the
norm-4033 endomorphism only once at each shared Horner step. -/
def jointPoints {Point : Type} (add : Point → Point → Point)
    (prime : Point → Point) (digits : List (Point × Point))
    (gTerminal qTerminal : Point) : Point :=
  match digits with
  | [] => add gTerminal qTerminal
  | (g, q) :: rest =>
      add (add g q) (prime (jointPoints add prime rest gTerminal qTerminal))

/-- For equal-length streams, shared Horner evaluation is the sum of the two
independent evaluations. These are exactly the algebraic laws required of
projective group addition and the norm-4033 curve endomorphism. -/
theorem joint_eq_sum {Point : Type} (add : Point → Point → Point)
    (prime : Point → Point)
    (add_assoc : ∀ x y z, add (add x y) z = add x (add y z))
    (add_comm : ∀ x y, add x y = add y x)
    (prime_add : ∀ x y, prime (add x y) = add (prime x) (prime y))
    (digits : List (Point × Point)) (gTerminal qTerminal : Point) :
    jointPoints add prime digits gTerminal qTerminal =
      add (evaluatePoints add prime (digits.map Prod.fst) gTerminal)
          (evaluatePoints add prime (digits.map Prod.snd) qTerminal) := by
  induction digits with
  | nil => rfl
  | cons pair rest ih =>
      cases pair with
      | mk g q =>
          simp only [jointPoints, List.map_cons,
                     evaluatePoints, ih, prime_add]
          calc
            add (add g q)
                (add (prime (evaluatePoints add prime (rest.map Prod.fst) gTerminal))
                     (prime (evaluatePoints add prime (rest.map Prod.snd) qTerminal)))
                = add (add g (prime (evaluatePoints add prime (rest.map Prod.fst) gTerminal)))
                      (add q (prime (evaluatePoints add prime (rest.map Prod.snd) qTerminal))) := by
                        rw [add_assoc g q, ← add_assoc q, add_comm q,
                            add_assoc, ← add_assoc g, add_assoc]

/-- Exact independent recoder traces produce the shared two-base point.
The two evaluation maps represent scalar-lattice pairs at G and Q. -/
theorem joint_of_valid_traces {Point : Type} (add : Point → Point → Point)
    (prime : Point → Point) (evaluateG evaluateQ : Pair → Point)
    (add_assoc : ∀ x y z, add (add x y) z = add x (add y z))
    (add_comm : ∀ x y, add x y = add y x)
    (prime_add : ∀ x y, prime (add x y) = add (prime x) (prime y))
    (map_addG : ∀ x y, evaluateG (pairAdd x y) = add (evaluateG x) (evaluateG y))
    (map_primeG : ∀ x, evaluateG (primePair x) = prime (evaluateG x))
    (map_addQ : ∀ x y, evaluateQ (pairAdd x y) = add (evaluateQ x) (evaluateQ y))
    (map_primeQ : ∀ x, evaluateQ (primePair x) = prime (evaluateQ x))
    (digits : List (Pair × Pair)) (gTerminal qTerminal gScalar qScalar : Pair)
    (gTrace : ValidTrace gScalar (digits.map Prod.fst) gTerminal)
    (qTrace : ValidTrace qScalar (digits.map Prod.snd) qTerminal) :
    jointPoints add prime
      (digits.map fun pair => (evaluateG pair.1, evaluateQ pair.2))
      (evaluateG gTerminal) (evaluateQ qTerminal) =
        add (evaluateG gScalar) (evaluateQ qScalar) := by
  rw [joint_eq_sum add prime add_assoc add_comm prime_add]
  simp only [List.map_map]
  have gEq := point_horner_of_valid_trace evaluateG add prime
    map_addG map_primeG gScalar gTerminal (digits.map Prod.fst) gTrace
  have qEq := point_horner_of_valid_trace evaluateQ add prime
    map_addQ map_primeQ qScalar qTerminal (digits.map Prod.snd) qTrace
  simpa only [List.map_map, Function.comp_def] using
    (calc
      add (evaluatePoints add prime
            ((digits.map Prod.fst).map evaluateG) (evaluateG gTerminal))
          (evaluatePoints add prime
            ((digits.map Prod.snd).map evaluateQ) (evaluateQ qTerminal))
          = add (evaluateG gScalar)
                (evaluatePoints add prime
                  ((digits.map Prod.snd).map evaluateQ) (evaluateQ qTerminal)) := by rw [← gEq]
      _ = add (evaluateG gScalar) (evaluateQ qScalar) := by rw [← qEq])

#print axioms joint_eq_sum
#print axioms joint_of_valid_traces

end JointHorner4033
