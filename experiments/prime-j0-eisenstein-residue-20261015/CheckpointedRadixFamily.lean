import CheckpointedSparse
import SparseRadixFamily

namespace CheckpointedRadixFamily

open SparseTauRadix
open SparseRadixFamily

theorem family_add (t : Int) (x y : Pair) :
    familyPair t (pairAdd x y) =
      pairAdd (familyPair t x) (familyPair t y) := by
  cases x with
  | mk x₁ x₂ =>
    cases y with
    | mk y₁ y₂ =>
      simp [familyPair, pairAdd, Int.mul_add, Int.sub_mul,
            Int.add_mul, Int.mul_comm, Int.mul_left_comm,
            Int.mul_assoc]
      constructor <;> grind

def power (t : Int) : Nat → Pair → Pair
  | 0, x => x
  | n+1, x => familyPair t (power t n x)

theorem power_add (t : Int) (n : Nat) (x y : Pair) :
    power t n (pairAdd x y) =
      pairAdd (power t n x) (power t n y) := by
  induction n with
  | zero => rfl
  | succ n ih => simp [power, ih, family_add]

def evaluate (t : Int) : List Pair → Pair → Pair
  | [], terminal => terminal
  | digit :: rest, terminal =>
      pairAdd digit (familyPair t (evaluate t rest terminal))

theorem evaluate_append (t : Int) (xs ys : List Pair) (terminal : Pair) :
    evaluate t (xs ++ ys) terminal =
      pairAdd (evaluate t xs (0,0))
        (power t xs.length (evaluate t ys terminal)) := by
  induction xs with
  | nil => simp [evaluate, power, CheckpointedSparse.pair_add_zero]
  | cons digit rest ih =>
      simp only [List.cons_append, List.length_cons, evaluate]
      rw [ih, family_add]
      simp only [power]
      exact (CheckpointedSparse.pair_add_assoc digit
        (familyPair t (evaluate t rest (0,0)))
        (familyPair t (power t rest.length (evaluate t ys terminal))))

def evaluateBlocks (t : Int) : List (List Pair) → Pair → Pair
  | [], terminal => terminal
  | block :: rest, terminal =>
      pairAdd (evaluate t block (0,0))
        (power t block.length (evaluateBlocks t rest terminal))

theorem evaluate_blocks_flatten (t : Int) (blocks : List (List Pair))
    (terminal : Pair) :
    evaluateBlocks t blocks terminal =
      evaluate t blocks.flatten terminal := by
  induction blocks with
  | nil => rfl
  | cons block rest ih =>
      simp only [evaluateBlocks, List.flatten_cons]
      rw [ih]
      exact (evaluate_append t block rest.flatten terminal).symm

def pointPower {Point : Type} (radix : Point → Point) : Nat → Point → Point
  | 0, x => x
  | n+1, x => radix (pointPower radix n x)

def evaluatePoint {Point : Type} (evaluatePair : Pair → Point)
    (add : Point → Point → Point) (radix : Point → Point) :
    List Pair → Point → Point
  | [], terminal => terminal
  | digit :: rest, terminal =>
      add (evaluatePair digit) (radix (evaluatePoint evaluatePair add radix rest terminal))

theorem map_evaluate {Point : Type} (t : Int) (evaluatePair : Pair → Point)
    (add : Point → Point → Point) (radix : Point → Point)
    (map_add : ∀ x y, evaluatePair (pairAdd x y) =
      add (evaluatePair x) (evaluatePair y))
    (map_radix : ∀ x, evaluatePair (familyPair t x) = radix (evaluatePair x))
    (digits : List Pair) (terminal : Pair) :
    evaluatePair (evaluate t digits terminal) =
      evaluatePoint evaluatePair add radix digits (evaluatePair terminal) := by
  induction digits with
  | nil => rfl
  | cons digit rest ih =>
      simp only [evaluate, evaluatePoint, map_add, map_radix]
      rw [ih]

theorem map_power {Point : Type} (t : Int) (evaluatePair : Pair → Point)
    (radix : Point → Point)
    (map_radix : ∀ x, evaluatePair (familyPair t x) = radix (evaluatePair x))
    (n : Nat) (x : Pair) :
    evaluatePair (power t n x) = pointPower radix n (evaluatePair x) := by
  induction n with
  | zero => rfl
  | succ n ih => simp [power, pointPower, map_radix, ih]

def evaluatePointBlocks {Point : Type} (evaluatePair : Pair → Point)
    (add : Point → Point → Point) (radix : Point → Point) :
    List (List Pair) → Point → Point
  | [], terminal => terminal
  | block :: rest, terminal =>
      add (evaluatePoint evaluatePair add radix block (evaluatePair (0,0)))
        (pointPower radix block.length
          (evaluatePointBlocks evaluatePair add radix rest terminal))

theorem map_evaluate_blocks {Point : Type} (t : Int)
    (evaluatePair : Pair → Point) (add : Point → Point → Point)
    (radix : Point → Point)
    (map_add : ∀ x y, evaluatePair (pairAdd x y) =
      add (evaluatePair x) (evaluatePair y))
    (map_radix : ∀ x, evaluatePair (familyPair t x) = radix (evaluatePair x))
    (blocks : List (List Pair)) (terminal : Pair) :
    evaluatePair (evaluateBlocks t blocks terminal) =
      evaluatePointBlocks evaluatePair add radix blocks (evaluatePair terminal) := by
  induction blocks with
  | nil => rfl
  | cons block rest ih =>
      simp only [evaluateBlocks, evaluatePointBlocks, map_add]
      rw [map_evaluate t evaluatePair add radix map_add map_radix block (0,0)]
      rw [map_power t evaluatePair radix map_radix block.length
        (evaluateBlocks t rest terminal)]
      rw [ih]

#print axioms family_add
#print axioms power_add
#print axioms evaluate_append
#print axioms evaluate_blocks_flatten
#print axioms map_evaluate
#print axioms map_evaluate_blocks

end CheckpointedRadixFamily
