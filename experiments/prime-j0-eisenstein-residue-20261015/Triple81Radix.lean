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

theorem prime_norm81 : AlternateRadix.norm 82 = 6481 := by decide

/-- The quotient's Eisenstein norm contracts under a bounded digit.
The digit bound is an explicit premise so a selector must establish it. -/
theorem quotient_norm_step (current digit next : Pair)
    (hquot : primePair81 next =
      pairAdd current (-digit.1,-digit.2))
    (hdigit : AlternateRadix.pairNorm digit.1 digit.2 ≤ 6481) :
    100*6481*AlternateRadix.pairNorm next.1 next.2 ≤
      101*AlternateRadix.pairNorm current.1 current.2 +
      10100*6481 := by
  rcases current with ⟨a,b⟩
  rcases digit with ⟨da,db⟩
  rcases next with ⟨u,v⟩
  have hscale := AlternateRadix.multiply_prime_norm 82 u v
  rw [prime_norm81] at hscale
  have hweight := AlternateRadix.pair_norm_weighted a b da db
  simp only [primePair81, pairAdd, Prod.mk.injEq] at hquot
  have heq : AlternateRadix.multiplyPrime 82 u v =
      (a-da,b-db) := by
    simp only [AlternateRadix.multiplyPrime, Prod.mk.injEq]
    constructor <;> omega
  rw [heq] at hscale
  rw [hscale] at hweight
  simp only [Prod.fst, Prod.snd] at hdigit hweight ⊢
  omega

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

/-- Twenty exact norm-6481 quotient steps with bounded digits reach the
declared terminal table, from the certified initial lattice bound. -/
theorem twenty_step_terminal_bound (q : Nat → Nat)
    (hzero : q 0 ≤ 7*2^260)
    (hstep : ∀ i : Nat, i < 20 →
      100*6481*q (i+1) ≤ 101*q i + 10100*6481) :
    q 20 < 5000 := by
  have h0 : q 0 ≤ 7*2^260 := hzero
  have h1 : q 1 ≤ 2021046309909768249701334643447427269921601707356466687878944900937375902720 := by
    have hs : 100*6481*q 1 ≤ 101*q 0 + 10100*6481 := by
      simpa using hstep 0 (by decide)
    omega
  have h2 : q 2 ≤ 314960156304407642678344081142092507733500651817625575491086923306087073 := by
    have hs : 100*6481*q 2 ≤ 101*q 1 + 10100*6481 := by
      simpa using hstep 1 (by decide)
    omega
  have h3 : q 3 ≤ 49083437412043159868095590488121190064933753793519801148896434584139 := by
    have hs : 100*6481*q 3 ≤ 101*q 2 + 10100*6481 := by
      simpa using hstep 2 (by decide)
    omega
  have h4 : q 4 ≤ 7649170156791172884859828173584694023388842976617034278720166577 := by
    have hs : 100*6481*q 4 ≤ 101*q 3 + 10100*6481 := by
      simpa using hstep 3 (by decide)
    omega
  have h5 : q 5 ≤ 1192047810269878817112857036772186539673311434405678849175749 := by
    have hs : 100*6481*q 5 ≤ 101*q 4 + 10100*6481 := by
      simpa using hstep 4 (by decide)
    omega
  have h6 : q 6 ≤ 185768907324884679105691345030073816551464982062912457696 := by
    have hs : 100*6481*q 6 ≤ 101*q 5 + 10100*6481 := by
      simpa using hstep 5 (by decide)
    omega
  have h7 : q 7 ≤ 28950254034583170173854074753953796438355135300654566 := by
    have hs : 100*6481*q 7 ≤ 101*q 6 + 10100*6481 := by
      simpa using hstep 6 (by decide)
    omega
  have h8 : q 8 ≤ 4511611877014195629623918454172710137747058579589 := by
    have hs : 100*6481*q 8 ≤ 101*q 7 + 10100*6481 := by
      simpa using hstep 7 (by decide)
    omega
  have h9 : q 9 ≤ 703090263197706771473562357462496102318242528 := by
    have hs : 100*6481*q 9 ≤ 101*q 8 + 10100*6481 := by
      simpa using hstep 8 (by decide)
    omega
  have h10 : q 10 ≤ 109569690762179268506140716098923169779676 := by
    have hs : 100*6481*q 10 ≤ 101*q 9 + 10100*6481 := by
      simpa using hstep 9 (by decide)
    omega
  have h11 : q 11 ≤ 17075356838420160652862540234518191967 := by
    have hs : 100*6481*q 11 ≤ 101*q 10 + 10100*6481 := by
      simpa using hstep 10 (by decide)
    omega
  have h12 : q 12 ≤ 2661026138991569550901275364428951 := by
    have hs : 100*6481*q 12 ≤ 101*q 11 + 10100*6481 := by
      simpa using hstep 11 (by decide)
    omega
  have h13 : q 13 ≤ 414694707665712890975202610512 := by
    have hs : 100*6481*q 13 ≤ 101*q 12 + 10100*6481 := by
      simpa using hstep 12 (by decide)
    omega
  have h14 : q 14 ≤ 64626084669398244080381931 := by
    have hs : 100*6481*q 14 ≤ 101*q 13 + 10100*6481 := by
      simpa using hstep 13 (by decide)
    omega
  have h15 : q 15 ≤ 10071338607636510804173 := by
    have hs : 100*6481*q 15 ≤ 101*q 14 + 10100*6481 := by
      simpa using hstep 14 (by decide)
    omega
  have h16 : q 16 ≤ 1569518900434018912 := by
    have hs : 100*6481*q 16 ≤ 101*q 15 + 10100*6481 := by
      simpa using hstep 15 (by decide)
    omega
  have h17 : q 17 ≤ 244594057929180 := by
    have hs : 100*6481*q 17 ≤ 101*q 16 + 10100*6481 := by
      simpa using hstep 16 (by decide)
    omega
  have h18 : q 18 ≤ 38117574320 := by
    have hs : 100*6481*q 18 ≤ 101*q 17 + 10100*6481 := by
      simpa using hstep 17 (by decide)
    omega
  have h19 : q 19 ≤ 5940350 := by
    have hs : 100*6481*q 19 ≤ 101*q 18 + 10100*6481 := by
      simpa using hstep 18 (by decide)
    omega
  have h20 : q 20 ≤ 1027 := by
    have hs : 100*6481*q 20 ≤ 101*q 19 + 10100*6481 := by
      simpa using hstep 19 (by decide)
    omega
  omega

/-- The twenty exact quotient equations and per-digit norm bounds suffice
to fit the terminal pair in the native norm-5000 table. -/
theorem twenty_quotients_terminal (state digit : Nat → Pair)
    (hinitial : AlternateRadix.pairNorm (state 0).1 (state 0).2 ≤
      7*2^260)
    (hquot : ∀ i : Nat, i < 20 →
      primePair81 (state (i+1)) =
        pairAdd (state i) (-(digit i).1,-(digit i).2))
    (hdigit : ∀ i : Nat, i < 20 →
      AlternateRadix.pairNorm (digit i).1 (digit i).2 ≤ 6481) :
    AlternateRadix.pairNorm (state 20).1 (state 20).2 < 5000 := by
  let q : Nat → Nat := fun i =>
    (AlternateRadix.pairNorm (state i).1 (state i).2).toNat
  have hq (i : Nat) : (q i : Int) =
      AlternateRadix.pairNorm (state i).1 (state i).2 := by
    have hn := AlternateRadix.pair_norm_nonnegative
      (state i).1 (state i).2
    simp [q, Int.toNat_of_nonneg hn]
  have hzero : q 0 ≤ 7*2^260 := by
    have heq := hq 0
    omega
  have hstep : ∀ i : Nat, i < 20 →
      100*6481*q (i+1) ≤ 101*q i + 10100*6481 := by
    intro i hi
    have hs := quotient_norm_step (state i) (digit i) (state (i+1))
      (hquot i hi) (hdigit i hi)
    have hnow := hq i
    have hnext := hq (i+1)
    omega
  have hterminal := twenty_step_terminal_bound q hzero hstep
  have heq := hq 20
  omega

#print axioms prime_norm81
#print axioms quotient_norm_step
#print axioms twenty_step_terminal_bound
#print axioms twenty_quotients_terminal
#print axioms conjugate_primePair81
#print axioms quotient_step
#print axioms valid_trace_evaluates
#print axioms point_horner81
#print axioms two_scalar_horner81

end Triple81Radix
