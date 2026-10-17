import AlternateRadix

namespace SparseTauRadix

abbrev Pair := Int × Int

def pairAdd (x y : Pair) : Pair := (x.1+y.1,x.2+y.2)
def pairSub (x y : Pair) : Pair := (x.1-y.1,x.2-y.2)
def pairScale (n : Int) (x : Pair) : Pair := (n*x.1,n*x.2)

/-- Multiplication by the secp256k1 endomorphism root, with τ²=3τ−3. -/
def tauPair (x : Pair) : Pair := (-3*x.2,x.1+3*x.2)

/-- Multiplication by π=127+128τ in the basis (1,τ). -/
def sparsePair (x : Pair) : Pair :=
  (127*x.1-384*x.2,128*x.1+511*x.2)

/-- The radix action needs seven doublings, two group additions, and one τ. -/
theorem sparse_pair_shortcut (x : Pair) :
    sparsePair x = pairSub (pairScale 128 (pairAdd x (tauPair x))) x := by
  apply Prod.ext
  · simp [sparsePair,pairSub,pairScale,pairAdd,tauPair]
    omega
  · simp [sparsePair,pairSub,pairScale,pairAdd,tauPair]
    omega

theorem sparse_norm : AlternateRadix.pairNorm 127 128 = 114049 := by decide

/-- The residue of τ in the cyclic quotient by the composite-norm radix. -/
theorem tau_residue : 127 + 128*(-892) = -114049 := by decide

theorem tau_residue_polynomial :
    (-892)^2 - 3*(-892) + 3 = 7*114049 := by decide

/-- Every radix multiple has zero residue modulo 114049. -/
theorem sparse_residue_multiple (x : Pair) :
    (sparsePair x).1 - 892*(sparsePair x).2 =
      -114049*(x.1+4*x.2) := by
  simp [sparsePair]
  omega

/-- Exact norm scaling by the sparse radix, including all pairs. -/
theorem sparse_pair_norm (x : Pair) :
    AlternateRadix.pairNorm (sparsePair x).1 (sparsePair x).2 =
      114049 * AlternateRadix.pairNorm x.1 x.2 := by
  simp [AlternateRadix.pairNorm,sparsePair,Int.mul_add,Int.mul_sub,
        Int.add_mul,Int.mul_assoc,Int.mul_comm,Int.mul_left_comm]
  simp only [← Int.mul_assoc]
  omega

/-- The integer quotient formulas invert the exact radix matrix. -/
theorem quotient_step (ra rb u v : Int)
    (hu : 114049*u = 511*ra+384*rb)
    (hv : 114049*v = -128*ra+127*rb) :
    sparsePair (u,v) = (ra,rb) := by
  apply Prod.ext
  · simp only [sparsePair]
    omega
  · simp only [sparsePair]
    omega

/-- A complete exact quotient trace from the original pair to a terminal pair. -/
inductive ValidTrace : Pair → List Pair → Pair → Prop
  | terminal (z : Pair) : ValidTrace z [] z
  | step (z next digit terminal : Pair) (rest : List Pair)
      (equation : z = pairAdd digit (sparsePair next))
      (tail : ValidTrace next rest terminal) :
      ValidTrace z (digit :: rest) terminal

def evaluatePairs (digits : List Pair) (terminal : Pair) : Pair :=
  match digits with
  | [] => terminal
  | digit :: rest => pairAdd digit (sparsePair (evaluatePairs rest terminal))

theorem valid_trace_evaluates (z terminal : Pair) (digits : List Pair)
    (trace : ValidTrace z digits terminal) :
    z = evaluatePairs digits terminal := by
  induction trace with
  | terminal z => rfl
  | step z next digit terminal rest equation tail ih =>
      simp [evaluatePairs,equation,ih]

def evaluatePoints {Point : Type} (add : Point → Point → Point)
    (radix : Point → Point) (digits : List Point) (terminal : Point) : Point :=
  match digits with
  | [] => terminal
  | digit :: rest => add digit (radix (evaluatePoints add radix rest terminal))

theorem map_evaluatePairs {Point : Type} (evaluate : Pair → Point)
    (add : Point → Point → Point) (radix : Point → Point)
    (map_add : ∀ x y, evaluate (pairAdd x y) = add (evaluate x) (evaluate y))
    (map_radix : ∀ x, evaluate (sparsePair x) = radix (evaluate x))
    (digits : List Pair) (terminal : Pair) :
    evaluate (evaluatePairs digits terminal) =
      evaluatePoints add radix (digits.map evaluate) (evaluate terminal) := by
  induction digits with
  | nil => rfl
  | cons digit rest ih =>
      simp [evaluatePairs,evaluatePoints,map_add,map_radix,ih]

/-- Exact digit traces map to point Horner evaluation under explicit group-map
hypotheses. A concrete curve proof must discharge those hypotheses. -/
theorem point_horner_of_valid_trace {Point : Type} (evaluate : Pair → Point)
    (add : Point → Point → Point) (radix : Point → Point)
    (map_add : ∀ x y, evaluate (pairAdd x y) = add (evaluate x) (evaluate y))
    (map_radix : ∀ x, evaluate (sparsePair x) = radix (evaluate x))
    (z terminal : Pair) (digits : List Pair)
    (trace : ValidTrace z digits terminal) :
    evaluate z =
      evaluatePoints add radix (digits.map evaluate) (evaluate terminal) := by
  rw [valid_trace_evaluates z terminal digits trace]
  exact map_evaluatePairs evaluate add radix map_add map_radix digits terminal

#print axioms sparse_pair_shortcut
#print axioms sparse_norm
#print axioms tau_residue
#print axioms tau_residue_polynomial
#print axioms sparse_residue_multiple
#print axioms sparse_pair_norm
#print axioms quotient_step
#print axioms valid_trace_evaluates
#print axioms map_evaluatePairs
#print axioms point_horner_of_valid_trace

end SparseTauRadix
