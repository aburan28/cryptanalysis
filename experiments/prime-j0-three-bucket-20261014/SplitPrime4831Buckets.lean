import SplitPrimeRadix

namespace SplitPrime4831Buckets
open SplitPrimeRadix

private theorem add_zero_left (x : Coeff) : add (0, 0) x = x := by
  cases x <;> simp [add]

private theorem add_zero_right (x : Coeff) : add x (0, 0) = x := by
  cases x <;> simp [add]

private theorem add_assoc (x y z : Coeff) :
    add (add x y) z = add x (add y z) := by
  cases x; cases y; cases z
  simp [add, Int.add_assoc]

private theorem omega_add (x y : Coeff) :
    omegaMul (add x y) = add (omegaMul x) (omegaMul y) := by
  cases x; cases y
  simp [omegaMul, add]
  constructor <;> omega

private theorem omega_zero : omegaMul (0, 0) = (0, 0) := by
  decide

def sum (xs : List Coeff) : Coeff := xs.foldl add (0, 0)

private theorem foldl_start (xs : List Coeff) (start : Coeff) :
    xs.foldl add start = add start (sum xs) := by
  induction xs generalizing start with
  | nil => simp [sum, add_zero_right]
  | cons x xs ih =>
      rw [List.foldl_cons, ih]
      have hsum : sum (x :: xs) = add x (sum xs) := by
        change xs.foldl add (add (0, 0) x) = add x (sum xs)
        rw [add_zero_left]
        exact ih x
      rw [hsum, add_assoc]

private theorem sum_append (xs ys : List Coeff) :
    sum (xs ++ ys) = add (sum xs) (sum ys) := by
  simp only [sum, List.foldl_append]
  exact foldl_start ys (xs.foldl add (0, 0))

private theorem sum_cons (x : Coeff) (xs : List Coeff) :
    sum (x :: xs) = add x (sum xs) := by
  change xs.foldl add (add (0, 0) x) = add x (sum xs)
  rw [add_zero_left]
  exact foldl_start xs x

private theorem sum_map_omega (xs : List Coeff) :
    sum (xs.map omegaMul) = omegaMul (sum xs) := by
  induction xs with
  | nil => simp [sum, omega_zero]
  | cons x xs ih =>
      simp only [List.map_cons, sum_cons, ih]
      rw [omega_add]

theorem three_bucket_recombination
    (plain first second : List Coeff) :
    sum (plain ++ first.map omegaMul ++
        second.map (fun x => omegaMul (omegaMul x))) =
      add (add (sum plain) (omegaMul (sum first)))
          (omegaMul (omegaMul (sum second))) := by
  rw [List.append_assoc, sum_append, sum_append]
  rw [sum_map_omega]
  have h : second.map (fun x => omegaMul (omegaMul x)) =
      (second.map omegaMul).map omegaMul := by
    simp [List.map_map, Function.comp_def]
  rw [h, sum_map_omega, sum_map_omega]
  exact (add_assoc _ _ _).symm

#print axioms three_bucket_recombination
end SplitPrime4831Buckets
