import JointHorner

namespace Triple243Radix

open HornerRadix

/-- Multiplication by `243 + omega = 244 - tau` in the `(1,tau)` basis. -/
def primePair243 (x : Pair) : Pair :=
  (244*x.1 + 3*x.2, -x.1 + 241*x.2)

/-- Multiplication by the conjugate `241 + tau`. -/
def conjugatePair243 (x : Pair) : Pair :=
  (241*x.1 - 3*x.2, x.1 + 244*x.2)

/-- The exact integer quotient numerators for the proposed recoder. -/
theorem conjugate_primePair243 (x : Pair) :
    conjugatePair243 (primePair243 x) =
      (58807*x.1, 58807*x.2) := by
  rcases x with ⟨a,b⟩
  simp only [conjugatePair243, primePair243,
             Prod.mk.injEq]
  constructor <;> omega

theorem prime_norm243 : AlternateRadix.norm 244 = 58807 := by decide

/-- The quotient's Eisenstein norm contracts under a bounded digit.
The digit bound is an explicit premise so a selector must establish it. -/
theorem quotient_norm_step (current digit next : Pair)
    (hquot : primePair243 next =
      pairAdd current (-digit.1,-digit.2))
    (hdigit : AlternateRadix.pairNorm digit.1 digit.2 ≤ 58807) :
    100*58807*AlternateRadix.pairNorm next.1 next.2 ≤
      101*AlternateRadix.pairNorm current.1 current.2 +
      10100*58807 := by
  rcases current with ⟨a,b⟩
  rcases digit with ⟨da,db⟩
  rcases next with ⟨u,v⟩
  have hscale := AlternateRadix.multiply_prime_norm 244 u v
  rw [prime_norm243] at hscale
  have hweight := AlternateRadix.pair_norm_weighted a b da db
  simp only [primePair243, pairAdd, Prod.mk.injEq] at hquot
  have heq : AlternateRadix.multiplyPrime 244 u v =
      (a-da,b-db) := by
    simp only [AlternateRadix.multiplyPrime, Prod.mk.injEq]
    constructor <;> omega
  rw [heq] at hscale
  rw [hscale] at hweight
  simp only [Prod.fst, Prod.snd] at hdigit hweight ⊢
  omega

/-- One exact division step preserves the represented scalar pair. -/
theorem quotient_step (current digit next : Pair)
    (quotient : conjugatePair243 (pairAdd current
      (-digit.1,-digit.2)) = (58807*next.1,58807*next.2)) :
    current = pairAdd digit (primePair243 next) := by
  rcases current with ⟨a,b⟩
  rcases digit with ⟨d,e⟩
  rcases next with ⟨u,v⟩
  simp only [conjugatePair243, primePair243, pairAdd,
             Prod.mk.injEq] at quotient ⊢
  rcases quotient with ⟨h₁,h₂⟩
  constructor <;> omega

def evaluatePairs243 (digits : List Pair) (terminal : Pair) : Pair :=
  match digits with
  | [] => terminal
  | digit :: rest => pairAdd digit (primePair243 (evaluatePairs243 rest terminal))

/-- The input and each quotient are explicit, so a trace cannot assert its
own final result without the exact division equations. -/
inductive ValidTrace243 : Pair → List Pair → Pair → Prop
  | terminal (z : Pair) : ValidTrace243 z [] z
  | step (z next digit terminal : Pair) (rest : List Pair)
      (equation : z = pairAdd digit (primePair243 next))
      (tail : ValidTrace243 next rest terminal) :
      ValidTrace243 z (digit :: rest) terminal

theorem valid_trace_evaluates (z terminal : Pair) (digits : List Pair)
    (trace : ValidTrace243 z digits terminal) :
    z = evaluatePairs243 digits terminal := by
  induction trace with
  | terminal z => rfl
  | step z next digit terminal rest equation tail ih =>
      simp [evaluatePairs243, equation, ih]

private theorem map_evaluate243 {Point : Type} (evaluate : Pair → Point)
    (add : Point → Point → Point) (prime : Point → Point)
    (map_add : ∀ x y, evaluate (pairAdd x y) = add (evaluate x) (evaluate y))
    (map_prime : ∀ x, evaluate (primePair243 x) = prime (evaluate x))
    (digits : List Pair) (terminal : Pair) :
    evaluate (evaluatePairs243 digits terminal) =
      evaluatePoints add prime (digits.map evaluate)
      (evaluate terminal) := by
  induction digits with
  | nil => rfl
  | cons digit rest ih =>
      simp [evaluatePairs243, evaluatePoints, map_add, map_prime, ih]

theorem point_horner243 {Point : Type} (evaluate : Pair → Point)
    (add : Point → Point → Point) (prime : Point → Point)
    (map_add : ∀ x y, evaluate (pairAdd x y) = add (evaluate x) (evaluate y))
    (map_prime : ∀ x, evaluate (primePair243 x) = prime (evaluate x))
    (z terminal : Pair) (digits : List Pair)
    (trace : ValidTrace243 z digits terminal) :
    evaluate z = evaluatePoints add prime (digits.map evaluate)
      (evaluate terminal) := by
  rw [valid_trace_evaluates z terminal digits trace]
  exact map_evaluate243 evaluate add prime map_add map_prime digits terminal

/-- Two scalar traces share the same `243 + omega` point recurrence. -/
theorem two_scalar_horner243 {Point : Type}
    (add : Point → Point → Point) (prime : Point → Point)
    (g q : Pair → Point)
    (assoc : ∀ x y z, add (add x y) z = add x (add y z))
    (comm : ∀ x y, add x y = add y x)
    (prime_add : ∀ x y, prime (add x y) = add (prime x) (prime y))
    (g_add : ∀ x y, g (pairAdd x y) = add (g x) (g y))
    (q_add : ∀ x y, q (pairAdd x y) = add (q x) (q y))
    (g_prime : ∀ x, g (primePair243 x) = prime (g x))
    (q_prime : ∀ x, q (primePair243 x) = prime (q x))
    (scalarG scalarQ terminalG terminalQ : Pair)
    (digits : List (Pair × Pair))
    (traceG : ValidTrace243 scalarG (digits.map Prod.fst) terminalG)
    (traceQ : ValidTrace243 scalarQ (digits.map Prod.snd) terminalQ) :
    add (g scalarG) (q scalarQ) =
      evaluatePoints add prime
        (digits.map (fun d => add (g d.1) (q d.2)))
        (add (g terminalG) (q terminalQ)) := by
  rw [point_horner243 g add prime g_add g_prime
      scalarG terminalG (digits.map Prod.fst) traceG]
  rw [point_horner243 q add prime q_add q_prime
      scalarQ terminalQ (digits.map Prod.snd) traceQ]
  simpa only [List.map_map, Function.comp_def] using
    (JointHorner.combine_horner add prime assoc comm prime_add g q
      digits terminalG terminalQ)

/-- Sixteen exact norm-58807 quotient steps with bounded digits reach the
terminal norm-5000 table from the certified initial lattice bound. -/
theorem sixteen_step_terminal_bound (q : Nat → Nat)
    (hzero : q 0 ≤ 7*2^260)
    (hstep : ∀ i : Nat, i < 16 →
      100*58807*q (i+1) ≤ 101*q i + 10100*58807) :
    q 16 < 5000 := by
  have h0 : q 0 ≤ 7*2^260 := hzero
  have h1 : q 1 ≤ 222735407936558709444697907123008759779650393071866624792005065774059775720 := by
    have hs : 100*58807*q 1 ≤ 101*q 0 + 10100*58807 := by
      simpa using hstep 0 (by decide)
    omega
  have h2 : q 2 ≤ 3825441903445581249496571601922200543769396449446244342338924217045697 := by
    have hs : 100*58807*q 2 ≤ 101*q 1 + 10100*58807 := by
      simpa using hstep 1 (by decide)
    omega
  have h3 : q 3 ≤ 65701299547333430747896293263411201884250011290164551596958074126 := by
    have hs : 100*58807*q 3 ≤ 101*q 2 + 10100*58807 := by
      simpa using hstep 2 (by decide)
    omega
  have h4 : q 4 ≤ 1128408395986987349386556977843544372321194949632972216112598 := by
    have hs : 100*58807*q 4 ≤ 101*q 3 + 10100*58807 := by
      simpa using hstep 3 (by decide)
    omega
  have h5 : q 5 ≤ 19380218000354672451926174564626316867794767614897919366 := by
    have hs : 100*58807*q 5 ≤ 101*q 4 + 10100*58807 := by
      simpa using hstep 4 (by decide)
    omega
  have h6 : q 6 ≤ 332851874442808155091153031276422535352470204075243 := by
    have hs : 100*58807*q 6 ≤ 101*q 5 + 10100*58807 := by
      simpa using hstep 5 (by decide)
    omega
  have h7 : q 7 ≤ 5716673069315493676638232890458393740643034197 := by
    have hs : 100*58807*q 7 ≤ 101*q 6 + 10100*58807 := by
      simpa using hstep 6 (by decide)
    omega
  have h8 : q 8 ≤ 98182865985488948822497580549304975224980 := by
    have hs : 100*58807*q 8 ≤ 101*q 7 + 10100*58807 := by
      simpa using hstep 7 (by decide)
    omega
  have h9 : q 9 ≤ 1686273651867019883869650829914772576 := by
    have hs : 100*58807*q 9 ≤ 101*q 8 + 10100*58807 := by
      simpa using hstep 8 (by decide)
    omega
  have h10 : q 10 ≤ 28961456771909638014323929774004 := by
    have hs : 100*58807*q 10 ≤ 101*q 9 + 10100*58807 := by
      simpa using hstep 9 (by decide)
    omega
  have h11 : q 11 ≤ 497407984417309748745339415 := by
    have hs : 100*58807*q 11 ≤ 101*q 10 + 10100*58807 := by
      simpa using hstep 10 (by decide)
    omega
  have h12 : q 12 ≤ 8542895646121768603035 := by
    have hs : 100*58807*q 12 ≤ 101*q 11 + 10100*58807 := by
      simpa using hstep 11 (by decide)
    omega
  have h13 : q 13 ≤ 146722747335912259 := by
    have hs : 100*58807*q 13 ≤ 101*q 12 + 10100*58807 := by
      simpa using hstep 12 (by decide)
    omega
  have h14 : q 14 ≤ 2519937674345 := by
    have hs : 100*58807*q 14 ≤ 101*q 13 + 10100*58807 := by
      simpa using hstep 13 (by decide)
    omega
  have h15 : q 15 ≤ 43279592 := by
    have hs : 100*58807*q 15 ≤ 101*q 14 + 10100*58807 := by
      simpa using hstep 14 (by decide)
    omega
  have h16 : q 16 ≤ 844 := by
    have hs : 100*58807*q 16 ≤ 101*q 15 + 10100*58807 := by
      simpa using hstep 15 (by decide)
    omega
  omega

/-- The sixteen exact quotient equations and per-digit norm bounds suffice
to fit the terminal pair in the native norm-5000 table. -/
theorem sixteen_quotients_terminal (state digit : Nat → Pair)
    (hinitial : AlternateRadix.pairNorm (state 0).1 (state 0).2 ≤
      7*2^260)
    (hquot : ∀ i : Nat, i < 16 →
      primePair243 (state (i+1)) =
        pairAdd (state i) (-(digit i).1,-(digit i).2))
    (hdigit : ∀ i : Nat, i < 16 →
      AlternateRadix.pairNorm (digit i).1 (digit i).2 ≤ 58807) :
    AlternateRadix.pairNorm (state 16).1 (state 16).2 < 5000 := by
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
  have hstep : ∀ i : Nat, i < 16 →
      100*58807*q (i+1) ≤ 101*q i + 10100*58807 := by
    intro i hi
    have hs := quotient_norm_step (state i) (digit i) (state (i+1))
      (hquot i hi) (hdigit i hi)
    have hnow := hq i
    have hnext := hq (i+1)
    omega
  have hterminal := sixteen_step_terminal_bound q hzero hstep
  have heq := hq 16
  omega

#print axioms prime_norm243
#print axioms quotient_norm_step
#print axioms sixteen_step_terminal_bound
#print axioms sixteen_quotients_terminal
#print axioms conjugate_primePair243
#print axioms quotient_step
#print axioms valid_trace_evaluates
#print axioms point_horner243
#print axioms two_scalar_horner243

end Triple243Radix
