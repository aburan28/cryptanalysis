import SparseTauRadix

namespace CheckpointedSparse

open SparseTauRadix

theorem pair_add_zero (x : Pair) : pairAdd (0,0) x = x := by
  cases x
  simp [pairAdd]

theorem pair_add_assoc (x y z : Pair) :
    pairAdd x (pairAdd y z) = pairAdd (pairAdd x y) z := by
  cases x; cases y; cases z
  simp [pairAdd,Int.add_assoc]

theorem sparse_add (x y : Pair) :
    sparsePair (pairAdd x y) = pairAdd (sparsePair x) (sparsePair y) := by
  apply Prod.ext
  · simp [sparsePair,pairAdd]
    omega
  · simp [sparsePair,pairAdd]
    omega

/-- Multiplication by the sparse radix raised to a nonnegative power. -/
def power : Nat → Pair → Pair
  | 0, x => x
  | n+1, x => sparsePair (power n x)

theorem power_add (n : Nat) (x y : Pair) :
    power n (pairAdd x y) = pairAdd (power n x) (power n y) := by
  induction n with
  | zero => rfl
  | succ n ih =>
      simp [power,ih,sparse_add]

/-- A block split preserves the ordinary low-digit-first Horner evaluation. -/
theorem evaluate_append (xs ys : List Pair) (terminal : Pair) :
    evaluatePairs (xs ++ ys) terminal =
      pairAdd (evaluatePairs xs (0,0))
        (power xs.length (evaluatePairs ys terminal)) := by
  induction xs with
  | nil =>
      simp [evaluatePairs,power,pair_add_zero]
  | cons digit rest ih =>
      simp only [List.cons_append,List.length_cons,evaluatePairs]
      rw [ih,sparse_add]
      simp only [power]
      exact (pair_add_assoc digit
        (sparsePair (evaluatePairs rest (0,0)))
        (sparsePair (power rest.length (evaluatePairs ys terminal))))

/-- Each checkpoint block is evaluated from one precomputed base π^b G. -/
def evaluateBlocks : List (List Pair) → Pair → Pair
  | [], terminal => terminal
  | block :: rest, terminal =>
      pairAdd (evaluatePairs block (0,0))
        (power block.length (evaluateBlocks rest terminal))

/-- Every partition into checkpoint blocks equals the original full Horner
chain, including its terminal pair. -/
theorem evaluate_blocks_flatten (blocks : List (List Pair)) (terminal : Pair) :
    evaluateBlocks blocks terminal =
      evaluatePairs blocks.flatten terminal := by
  induction blocks with
  | nil => rfl
  | cons block rest ih =>
      simp only [evaluateBlocks,List.flatten_cons]
      rw [ih]
      exact (evaluate_append block rest.flatten terminal).symm

def pointPower {Point : Type} (radix : Point → Point) : Nat → Point → Point
  | 0, x => x
  | n+1, x => radix (pointPower radix n x)

theorem map_power {Point : Type} (evaluate : Pair → Point)
    (radix : Point → Point)
    (map_radix : ∀ x, evaluate (sparsePair x) = radix (evaluate x))
    (n : Nat) (x : Pair) :
    evaluate (power n x) = pointPower radix n (evaluate x) := by
  induction n with
  | zero => rfl
  | succ n ih => simp [power,pointPower,map_radix,ih]

def evaluatePointBlocks {Point : Type} (evaluate : Pair → Point)
    (add : Point → Point → Point) (radix : Point → Point) :
    List (List Pair) → Point → Point
  | [], terminal => terminal
  | block :: rest, terminal =>
      add (evaluatePoints add radix (block.map evaluate) (evaluate (0,0)))
        (pointPower radix block.length
          (evaluatePointBlocks evaluate add radix rest terminal))

/-- The checkpointed point computation maps the exact pair computation,
under explicit addition and endomorphism-map hypotheses. -/
theorem map_evaluate_blocks {Point : Type} (evaluate : Pair → Point)
    (add : Point → Point → Point) (radix : Point → Point)
    (map_add : ∀ x y, evaluate (pairAdd x y) = add (evaluate x) (evaluate y))
    (map_radix : ∀ x, evaluate (sparsePair x) = radix (evaluate x))
    (blocks : List (List Pair)) (terminal : Pair) :
    evaluate (evaluateBlocks blocks terminal) =
      evaluatePointBlocks evaluate add radix blocks (evaluate terminal) := by
  induction blocks with
  | nil => rfl
  | cons block rest ih =>
      simp only [evaluateBlocks,evaluatePointBlocks,map_add]
      rw [SparseTauRadix.map_evaluatePairs evaluate add radix
        map_add map_radix block (0,0)]
      rw [map_power evaluate radix map_radix block.length
        (evaluateBlocks rest terminal)]
      rw [ih]

#print axioms sparse_add
#print axioms power_add
#print axioms evaluate_append
#print axioms evaluate_blocks_flatten
#print axioms map_evaluate_blocks

end CheckpointedSparse
