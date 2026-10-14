import Lean

namespace SplitPrimeRadix

abbrev Coeff := Int × Int

-- tau² = 3 tau - 3, and pi = 86 - 21 tau has norm 3301.
def add (x y : Coeff) : Coeff := (x.1 + y.1, x.2 + y.2)
def piMul (x : Coeff) : Coeff :=
  (86 * x.1 + 63 * x.2, -21 * x.1 + 23 * x.2)
def norm (x : Coeff) : Int :=
  x.1 * x.1 + 3 * x.1 * x.2 + 3 * x.2 * x.2

theorem pi_norm : norm (86, -21) = 3301 := by decide
theorem norm_pi_mul (z : Coeff) : norm (piMul z) = 3301 * norm z := by
  cases z with
  | mk a b =>
      simp only [norm, piMul]
      grind

theorem coordinate_a_bound (a b : Int) :
    a * a ≤ 4 * norm (a, b) := by
  have h : 0 ≤ (a + 2 * b) * (a + 2 * b) := by
    by_cases hx : 0 ≤ a + 2 * b
    · exact Int.mul_nonneg hx hx
    · have hy : a + 2 * b ≤ 0 := by omega
      exact Int.mul_nonneg_of_nonpos_of_nonpos hy hy
  simp only [norm]
  grind

theorem coordinate_b_bound (a b : Int) :
    3 * b * b ≤ 4 * norm (a, b) := by
  have h : 0 ≤ (2 * a + 3 * b) * (2 * a + 3 * b) := by
    by_cases hx : 0 ≤ 2 * a + 3 * b
    · exact Int.mul_nonneg hx hx
    · have hy : 2 * a + 3 * b ≤ 0 := by omega
      exact Int.mul_nonneg_of_nonpos_of_nonpos hy hy
  simp only [norm]
  grind
theorem tau_residue_root : (1576 * 1576 - 3 * 1576 + 3) % 3301 = 0 := by decide
theorem pi_residue_zero : (86 - 21 * 1576) % 3301 = 0 := by decide

theorem residue_quotient (a b d : Int)
    (h : (a + 1576 * b - d) % 3301 = 0) :
    ∃ k : Int, d = a + 1576 * b - 3301 * k := by
  obtain ⟨k, hk⟩ := Int.dvd_of_emod_eq_zero h
  refine ⟨k, ?_⟩
  omega

-- The exact final rational inequality in the written terminal-bound proof.
-- The geometric contraction and lattice-cell coordinate bounds are recorded
-- separately in split_prime_radix.py and SPLIT_PRIME_RADIX.md.
theorem terminal_numeric :
    2 * (56 * 2252907023369138918423925520396307732351
      + 1650 * 57 ^ 21) < 663 * 56 * 57 ^ 21 := by decide

-- If d is the centered residue of a+1576b modulo 3301, k is its
-- integral quotient. The two formulas below are exactly division by pi.
theorem split_step_identity (a b k : Int) :
    let d := a + 1576 * b - 3301 * k
    let q : Coeff := (23 * k - 11 * b, 21 * k - 10 * b)
    add (d, 0) (piMul q) = (a, b) := by
  dsimp [add, piMul]
  apply Prod.ext <;> dsimp <;> omega

def expand : List Int → Coeff → Coeff
  | [], terminal => terminal
  | d :: ds, terminal => add (d, 0) (piMul (expand ds terminal))

def Valid : Coeff → List Int → Coeff → Prop
  | z, [], terminal => z = terminal
  | z, d :: ds, terminal =>
      ∃ next, z = add (d, 0) (piMul next) ∧ Valid next ds terminal

theorem valid_expand (z terminal : Coeff) (digits : List Int)
    (h : Valid z digits terminal) : z = expand digits terminal := by
  induction digits generalizing z with
  | nil => simpa [Valid, expand] using h
  | cons d ds ih =>
      obtain ⟨next, hz, ht⟩ := h
      simp only [expand]
      rw [hz, ih next ht]

-- The group action theorem exposes the exact bridge required by an
-- elliptic-curve implementation: additivity and compatibility with pi.
theorem action_expand {P : Type} (pointAdd : P → P → P)
    (digitPoint : Int → P) (piPoint : P → P) (act : Coeff → P)
    (act_digit_add : ∀ d z, act (add (d, 0) z) =
      pointAdd (digitPoint d) (act z))
    (act_pi : ∀ z, act (piMul z) = piPoint (act z))
    (digits : List Int) (terminal : Coeff) :
    act (expand digits terminal) =
      digits.foldr (fun d acc => pointAdd (digitPoint d) (piPoint acc))
        (act terminal) := by
  induction digits with
  | nil => rfl
  | cons d ds ih =>
      simp only [expand, List.foldr_cons]
      rw [act_digit_add, act_pi, ih]

#print axioms pi_norm
#print axioms norm_pi_mul
#print axioms coordinate_a_bound
#print axioms coordinate_b_bound
#print axioms tau_residue_root
#print axioms pi_residue_zero
#print axioms residue_quotient
#print axioms terminal_numeric
#print axioms split_step_identity
#print axioms valid_expand
#print axioms action_expand

end SplitPrimeRadix
