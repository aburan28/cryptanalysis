import Lean

namespace MixedRadix

abbrev Coeff := Int × Int

def add (x y : Coeff) : Coeff := (x.1 + y.1, x.2 + y.2)
def mul (x y : Coeff) : Coeff :=
  (x.1 * y.1 - x.2 * y.2,
   x.1 * y.2 + x.2 * y.1 - x.2 * y.2)
def norm (x : Coeff) : Int := x.1 * x.1 - x.1 * x.2 + x.2 * x.2

def tau : Coeff := (1, -1)
def rho : Coeff := (2, -1)
def tau4 : Coeff := (-9, -9)

theorem norm_tau (x : Coeff) : norm (mul tau x) = 3 * norm x := by
  cases x
  simp [norm, mul, tau]
  grind

theorem norm_rho (x : Coeff) : norm (mul rho x) = 7 * norm x := by
  cases x
  simp [norm, mul, rho]
  grind

theorem tau_fourth_power : mul (mul tau tau) (mul tau tau) = tau4 := by
  decide

def unitDigit (i : Fin 6) : Coeff :=
  match i.val with
  | 0 => (1, 0)
  | 1 => (-1, 0)
  | 2 => (0, 1)
  | 3 => (0, -1)
  | 4 => (-1, -1)
  | _ => (1, 1)

def tau4Seed (i : Fin 9) : Coeff :=
  match i.val with
  | 0 => (-1, -1)
  | 1 => (-2, -2)
  | 2 => (-3, -2)
  | 3 => (-3, -1)
  | 4 => (-4, -3)
  | 5 => (-4, -1)
  | 6 => (-4, -4)
  | 7 => (-5, -3)
  | _ => (-5, -2)

theorem rho_unit_residue_cover :
    ∀ r : Fin 7, r.val ≠ 0 →
      ∃ u : Fin 6,
        ((unitDigit u).1 + 2 * (unitDigit u).2 - (r.val : Int)) % 7 = 0 := by
  decide

theorem tau4_unit_orbit_cover :
    ∀ a b : Fin 9, (2 * (a.val : Int) - (b.val : Int)) % 3 ≠ 0 →
      ∃ s : Fin 9, ∃ u : Fin 6,
        ((mul (unitDigit u) (tau4Seed s)).1 - (a.val : Int)) % 9 = 0 ∧
        ((mul (unitDigit u) (tau4Seed s)).2 - (b.val : Int)) % 9 = 0 := by
  decide

def eval : List (Coeff × Coeff) → Coeff
  | [] => (0, 0)
  | (radix, digit) :: rest => add (mul radix (eval rest)) digit

theorem recoding_reconstruct (x radix digit quotient : Coeff)
    (h : x = add (mul radix quotient) digit)
    (rest : List (Coeff × Coeff)) (hr : eval rest = quotient) :
    eval ((radix, digit) :: rest) = x := by
  simp [eval, hr, h]

#print axioms norm_tau
#print axioms norm_rho
#print axioms tau_fourth_power
#print axioms rho_unit_residue_cover
#print axioms tau4_unit_orbit_cover
#print axioms recoding_reconstruct
end MixedRadix
