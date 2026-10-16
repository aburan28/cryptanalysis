import JointSeedGraph

namespace JointHorner

open HornerRadix

private theorem interchange {Point : Type} (add : Point → Point → Point)
    (assoc : ∀ x y z, add (add x y) z = add x (add y z))
    (comm : ∀ x y, add x y = add y x)
    (a b c d : Point) :
    add (add a b) (add c d) = add (add a c) (add b d) := by
  calc
    add (add a b) (add c d) = add a (add b (add c d)) := assoc a b (add c d)
    _ = add a (add (add b c) d) := by rw [← assoc b c d]
    _ = add a (add (add c b) d) := by rw [comm b c]
    _ = add a (add c (add b d)) := by rw [assoc c b d]
    _ = add (add a c) (add b d) := (assoc a c (add b d)).symm

/-- Two synchronized Horner chains can share one prime step and one addition
of their two digit points per position. -/
theorem combine_horner {Point : Type} (add : Point → Point → Point)
    (prime : Point → Point)
    (assoc : ∀ x y z, add (add x y) z = add x (add y z))
    (comm : ∀ x y, add x y = add y x)
    (prime_add : ∀ x y, prime (add x y) = add (prime x) (prime y))
    (g q : Pair → Point) (digits : List (Pair × Pair))
    (terminalG terminalQ : Pair) :
    add (evaluatePoints add prime (digits.map (fun d => g d.1)) (g terminalG))
        (evaluatePoints add prime (digits.map (fun d => q d.2)) (q terminalQ)) =
      evaluatePoints add prime
        (digits.map (fun d => add (g d.1) (q d.2)))
        (add (g terminalG) (q terminalQ)) := by
  induction digits with
  | nil => rfl
  | cons digit rest ih =>
      simp only [List.map_cons, evaluatePoints]
      rw [interchange add assoc comm, ← prime_add, ih]

/-- Exact recoder traces for both scalars give the point produced by a
single shared Horner chain. The group and endomorphism laws are explicit. -/
theorem two_scalar_horner {Point : Type} (add : Point → Point → Point)
    (prime : Point → Point) (g q : Pair → Point)
    (assoc : ∀ x y z, add (add x y) z = add x (add y z))
    (comm : ∀ x y, add x y = add y x)
    (prime_add : ∀ x y, prime (add x y) = add (prime x) (prime y))
    (g_add : ∀ x y, g (pairAdd x y) = add (g x) (g y))
    (q_add : ∀ x y, q (pairAdd x y) = add (q x) (q y))
    (g_prime : ∀ x, g (primePair x) = prime (g x))
    (q_prime : ∀ x, q (primePair x) = prime (q x))
    (scalarG scalarQ terminalG terminalQ : Pair)
    (digits : List (Pair × Pair))
    (traceG : ValidTrace scalarG (digits.map Prod.fst) terminalG)
    (traceQ : ValidTrace scalarQ (digits.map Prod.snd) terminalQ) :
    add (g scalarG) (q scalarQ) =
      evaluatePoints add prime
        (digits.map (fun d => add (g d.1) (q d.2)))
        (add (g terminalG) (q terminalQ)) := by
  rw [point_horner_of_valid_trace g add prime g_add g_prime
      scalarG terminalG (digits.map Prod.fst) traceG]
  rw [point_horner_of_valid_trace q add prime q_add q_prime
      scalarQ terminalQ (digits.map Prod.snd) traceQ]
  simpa only [List.map_map, Function.comp_def] using
    (combine_horner add prime assoc comm prime_add g q digits terminalG terminalQ)

/-- A certified Q-seed schedule supplies the exact Q digit and terminal
points used by the shared two-scalar Horner evaluation. The coverage premises
identify the concrete lookup entries used by this scalar stream. -/
theorem two_scalar_horner_from_graph {Point : Type}
    (add : Point → Point → Point) (prime : Point → Point)
    (g q lookup : Pair → Point)
    (assoc : ∀ x y z, add (add x y) z = add x (add y z))
    (comm : ∀ x y, add x y = add y x)
    (prime_add : ∀ x y, prime (add x y) = add (prime x) (prime y))
    (g_add : ∀ x y, g (pairAdd x y) = add (g x) (g y))
    (q_add : ∀ x y, q (pairAdd x y) = add (q x) (q y))
    (g_prime : ∀ x, g (primePair x) = prime (g x))
    (q_prime : ∀ x, q (primePair x) = prime (q x))
    (scalarG scalarQ terminalG terminalQ : Pair)
    (digits : List (Pair × Pair))
    (traceG : ValidTrace scalarG (digits.map Prod.fst) terminalG)
    (traceQ : ValidTrace scalarQ (digits.map Prod.snd) terminalQ)
    (vertices : List (Pair × Point))
    (graph : JointSeedGraph.CertifiedTrace q add q_add vertices)
    (digit_covered : ∀ digit, digit ∈ digits →
      (digit.2, lookup digit.2) ∈ vertices)
    (terminal_covered : (terminalQ, lookup terminalQ) ∈ vertices) :
    add (g scalarG) (q scalarQ) =
      evaluatePoints add prime
        (digits.map (fun d => add (g d.1) (lookup d.2)))
        (add (g terminalG) (lookup terminalQ)) := by
  have valid := JointSeedGraph.certifiedTrace_valid q add q_add graph
  have hdigits :
      digits.map (fun d => add (g d.1) (lookup d.2)) =
      digits.map (fun d => add (g d.1) (q d.2)) := by
    apply List.map_congr_left
    intro digit member
    rw [valid digit.2 (lookup digit.2) (digit_covered digit member)]
  have hterminal : lookup terminalQ = q terminalQ :=
    valid terminalQ (lookup terminalQ) terminal_covered
  simpa only [hdigits, hterminal] using
    (two_scalar_horner add prime g q assoc comm prime_add g_add q_add
      g_prime q_prime scalarG scalarQ terminalG terminalQ digits traceG traceQ)

#print axioms combine_horner
#print axioms two_scalar_horner
#print axioms two_scalar_horner_from_graph

end JointHorner
