import TopBound
import LegacyDigitCover

namespace PrimeJ0Power2DirectTerminalDigitCover

open PrimeJ0Radix919TerminalUnit
open PrimeJ0Power2DirectTerminalTopBound

-- Coordinates (x,y) encode the Eisenstein digit (x+y,-y).
private def hex (x y R : Int) : Prop :=
  -R ≤ 2*x-y ∧ 2*x-y ≤ R ∧ -R ≤ 2*y-x ∧ 2*y-x ≤ R ∧
  -R ≤ x+y ∧ x+y ≤ R

private theorem hex_energy (p q R : Int)
    (hpL : -R ≤ p) (hpU : p ≤ R)
    (hqL : -R ≤ q) (hqU : q ≤ R)
    (hsL : -R ≤ p + q) (hsU : p + q ≤ R) :
    p*p + p*q + q*q ≤ R*R := by
  by_cases hp : 0 ≤ p
  · by_cases hq : 0 ≤ q
    · have hpq := Int.mul_nonneg hp hq
      have hs0 : 0 ≤ p+q := by omega
      have hsq := Int.mul_self_le_mul_self hs0 hsU
      have hid : p*p+p*q+q*q = (p+q)*(p+q)-p*q := by grind +ring
      omega
    · have hq' : q ≤ 0 := by omega
      by_cases hs : 0 ≤ p+q
      · have hqp := Int.mul_nonpos_of_nonpos_of_nonneg hq' hs
        have hsq := Int.mul_self_le_mul_self hp hpU
        have hid : p*p+p*q+q*q = p*p+q*(p+q) := by grind +ring
        omega
      · have hs' : p+q ≤ 0 := by omega
        have hps := Int.mul_nonpos_of_nonneg_of_nonpos hp hs'
        have hq0 : 0 ≤ -q := by omega
        have hqu : -q ≤ R := by omega
        have hsq := Int.mul_self_le_mul_self hq0 hqu
        have hid : p*p+p*q+q*q = q*q+p*(p+q) := by grind +ring
        have heq : (-q)*(-q)=q*q := by grind +ring
        omega
  · have hp' : p ≤ 0 := by omega
    by_cases hq : 0 ≤ q
    · by_cases hs : 0 ≤ p+q
      · have hps := Int.mul_nonpos_of_nonpos_of_nonneg hp' hs
        have hsq := Int.mul_self_le_mul_self hq hqU
        have hid : p*p+p*q+q*q = q*q+p*(p+q) := by grind +ring
        omega
      · have hs' : p+q ≤ 0 := by omega
        have hqs := Int.mul_nonpos_of_nonneg_of_nonpos hq hs'
        have hp0 : 0 ≤ -p := by omega
        have hpu : -p ≤ R := by omega
        have hsq := Int.mul_self_le_mul_self hp0 hpu
        have hid : p*p+p*q+q*q = p*p+q*(p+q) := by grind +ring
        have heq : (-p)*(-p)=p*p := by grind +ring
        omega
    · have hq' : q ≤ 0 := by omega
      have hp0 : 0 ≤ -p := by omega
      have hq0 : 0 ≤ -q := by omega
      have hs0 : 0 ≤ -(p+q) := by omega
      have hsu : -(p+q) ≤ R := by omega
      have hpq := Int.mul_nonneg hp0 hq0
      have hsq := Int.mul_self_le_mul_self hs0 hsu
      have hid : p*p+p*q+q*q = (-(p+q))*(-(p+q))-(-p)*(-q) := by grind +ring
      omega

private theorem hex_digit_bound (x y R : Int) (h : hex x y R) :
    3 * norm (x+y, -y) ≤ R*R := by
  rcases h with ⟨hpL, hpU, hqL, hqU, hsL, hsU⟩
  have he := hex_energy (2*x-y) (2*y-x) R hpL hpU hqL hqU
    (by omega) (by omega)
  have hid : (2*x-y)*(2*x-y) + (2*x-y)*(2*y-x) +
      (2*y-x)*(2*y-x) = 3 * norm (x+y, -y) := by
    simp only [norm]
    grind +ring
  omega

private theorem upper_cover (u v R : Int)
    (hu : 0 ≤ u) (hv : 0 ≤ v) (huR : u ≤ R) (hvR : v ≤ R) (hvu : v ≤ u) :
    hex u v R ∨ hex (u-R) v R ∨ hex (u-R) (v-R) R := by
  by_cases hOrigin : 2*u-v ≤ R ∧ u+v ≤ R
  · left
    dsimp [hex]
    omega
  · by_cases hMiddle : 2*v ≤ u
    · right; left
      dsimp [hex]
      omega
    · right; right
      dsimp [hex]
      omega

private theorem hex_swap (x y R : Int) (h : hex x y R) : hex y x R := by
  dsimp [hex] at h ⊢
  omega

private theorem four_corner_cover (u v R : Int)
    (hu : 0 ≤ u) (hv : 0 ≤ v) (huR : u ≤ R) (hvR : v ≤ R) :
    hex u v R ∨ hex (u-R) v R ∨ hex u (v-R) R ∨ hex (u-R) (v-R) R := by
  by_cases h : v ≤ u
  · rcases upper_cover u v R hu hv huR hvR h with h₀ | h₁ | h₂
    · exact Or.inl h₀
    · exact Or.inr (Or.inl h₁)
    · exact Or.inr (Or.inr (Or.inr h₂))
  · have h' : u ≤ v := by omega
    rcases upper_cover v u R hv hu hvR huR h' with h₀ | h₁ | h₂
    · exact Or.inl (hex_swap v u R h₀)
    · exact Or.inr (Or.inr (Or.inl (hex_swap (v-R) u R h₁)))
    · exact Or.inr (Or.inr (Or.inr (hex_swap (v-R) (u-R) R h₂)))

abbrev Candidate := Pair × Pair

def corner (z : Pair) (m n : Int) : Candidate :=
  let u := z.1 + z.2
  let v := -z.2
  let x := u - m * 256
  let y := v - n * 256
  ((x+y, -y), (m+n, -n))

theorem corner_equation (z : Pair) (m n : Int) :
    z = add (corner z m n).1 (scale 256 (corner z m n).2) := by
  rcases z with ⟨a,b⟩
  apply Prod.ext
  · simp only [corner, add, scale]
    omega
  · simp only [corner, add, scale]
    omega

private def scoreLt (a b : Pair) : Prop :=
  norm a < norm b ∨
  (norm a = norm b ∧ (a.1 < b.1 ∨ (a.1 = b.1 ∧ a.2 < b.2)))

private instance (a b : Pair) : Decidable (scoreLt a b) := by
  unfold scoreLt
  infer_instance

private def choose (old next : Candidate) : Candidate :=
  if scoreLt next.1 old.1 then next else old

private theorem choose_norm_le_left (old next : Candidate) :
    norm (choose old next).1 ≤ norm old.1 := by
  unfold choose
  split
  · rename_i h
    dsimp [scoreLt] at h
    omega
  · omega

private theorem choose_norm_le_right (old next : Candidate) :
    norm (choose old next).1 ≤ norm next.1 := by
  unfold choose
  split
  · omega
  · rename_i h
    have hNoLess : ¬ norm next.1 < norm old.1 := by
      intro hlt
      exact h (Or.inl hlt)
    omega

private theorem choose_equation (z : Pair) (old next : Candidate)
    (hOld : z = add old.1 (scale 256 old.2))
    (hNext : z = add next.1 (scale 256 next.2)) :
    z = add (choose old next).1 (scale 256 (choose old next).2) := by
  unfold choose
  split
  · exact hNext
  · exact hOld

def nearestStep (z : Pair) : Candidate :=
  let u := z.1 + z.2
  let v := -z.2
  let fu := u / 256
  let fv := v / 256
  choose (choose (choose (corner z fu fv) (corner z fu (fv+1)))
    (corner z (fu+1) fv)) (corner z (fu+1) (fv+1))

theorem nearest_step_equation (z : Pair) :
    z = add (nearestStep z).1 (scale 256 (nearestStep z).2) := by
  unfold nearestStep
  exact choose_equation z _ _
    (choose_equation z _ _
      (choose_equation z _ _ (corner_equation z _ _) (corner_equation z _ _))
      (corner_equation z _ _))
    (corner_equation z _ _)

private theorem corner_digit_00 (z : Pair) :
    (corner z ((z.1+z.2)/256) ((-z.2)/256)).1 =
      ((z.1+z.2)%256 + (-z.2)%256, -((-z.2)%256)) := by
  rcases z with ⟨a,b⟩
  apply Prod.ext <;> simp only [corner] <;> omega

private theorem corner_digit_01 (z : Pair) :
    (corner z ((z.1+z.2)/256) (((-z.2)/256)+1)).1 =
      ((z.1+z.2)%256 + ((-z.2)%256-256), -(((-z.2)%256)-256)) := by
  rcases z with ⟨a,b⟩
  apply Prod.ext <;> simp only [corner] <;> omega

private theorem corner_digit_10 (z : Pair) :
    (corner z (((z.1+z.2)/256)+1) ((-z.2)/256)).1 =
      (((z.1+z.2)%256-256) + (-z.2)%256, -((-z.2)%256)) := by
  rcases z with ⟨a,b⟩
  apply Prod.ext <;> simp only [corner] <;> omega

private theorem corner_digit_11 (z : Pair) :
    (corner z (((z.1+z.2)/256)+1) (((-z.2)/256)+1)).1 =
      (((z.1+z.2)%256-256) + ((-z.2)%256-256), -(((-z.2)%256)-256)) := by
  rcases z with ⟨a,b⟩
  apply Prod.ext <;> simp only [corner] <;> omega

theorem nearest_digit_bound (z : Pair) :
    3 * norm (nearestStep z).1 ≤ (256 : Int)^2 := by
  let u := z.1+z.2
  let v := -z.2
  let r := u % 256
  let s := v % 256
  have hr0 : 0 ≤ r := by dsimp [r]; omega
  have hs0 : 0 ≤ s := by dsimp [s]; omega
  have hrR : r ≤ (256 : Int) := by dsimp [r]; omega
  have hsR : s ≤ (256 : Int) := by dsimp [s]; omega
  have hCover := four_corner_cover r s 256 hr0 hs0 hrR hsR
  let c00 := corner z (u/256) (v/256)
  let c01 := corner z (u/256) (v/256+1)
  let c10 := corner z (u/256+1) (v/256)
  let c11 := corner z (u/256+1) (v/256+1)
  have h00 : norm (nearestStep z).1 ≤ norm c00.1 := by
    dsimp [nearestStep, c00, c01, c10, c11, u, v]
    exact Int.le_trans (choose_norm_le_left _ _)
      (Int.le_trans (choose_norm_le_left _ _) (choose_norm_le_left _ _))
  have h01 : norm (nearestStep z).1 ≤ norm c01.1 := by
    dsimp [nearestStep, c00, c01, c10, c11, u, v]
    exact Int.le_trans (choose_norm_le_left _ _)
      (Int.le_trans (choose_norm_le_left _ _) (choose_norm_le_right _ _))
  have h10 : norm (nearestStep z).1 ≤ norm c10.1 := by
    dsimp [nearestStep, c00, c01, c10, c11, u, v]
    exact Int.le_trans (choose_norm_le_left _ _) (choose_norm_le_right _ _)
  have h11 : norm (nearestStep z).1 ≤ norm c11.1 := by
    dsimp [nearestStep, c00, c01, c10, c11, u, v]
    exact choose_norm_le_right _ _
  rcases hCover with h₀ | h₁ | h₂ | h₃
  · have hb := hex_digit_bound r s 256 h₀
    have hc : c00.1 = (r+s,-s) := by simpa [c00, r, s, u, v] using corner_digit_00 z
    rw [hc] at h00
    have hs := Int.mul_le_mul_of_nonneg_left h00 (by decide : (0:Int) ≤ 3)
    omega
  · have hb := hex_digit_bound (r-256) s 256 h₁
    have hc : c10.1 = ((r-256)+s,-s) := by simpa [c10, r, s, u, v] using corner_digit_10 z
    rw [hc] at h10
    have hs := Int.mul_le_mul_of_nonneg_left h10 (by decide : (0:Int) ≤ 3)
    omega
  · have hb := hex_digit_bound r (s-256) 256 h₂
    have hc : c01.1 = (r+(s-256),-(s-256)) := by simpa [c01, r, s, u, v] using corner_digit_01 z
    rw [hc] at h01
    have hs := Int.mul_le_mul_of_nonneg_left h01 (by decide : (0:Int) ≤ 3)
    omega
  · have hb := hex_digit_bound (r-256) (s-256) 256 h₃
    have hc : c11.1 = ((r-256)+(s-256),-(s-256)) := by simpa [c11, r, s, u, v] using corner_digit_11 z
    rw [hc] at h11
    have hs := Int.mul_le_mul_of_nonneg_left h11 (by decide : (0:Int) ≤ 3)
    omega

def recode256 : Nat → Pair → List Pair × Pair
  | 0, z => ([], z)
  | n+1, z =>
      let step := nearestStep z
      let tail := recode256 n step.2
      (step.1 :: tail.1, tail.2)

theorem recode256_length (n : Nat) (z : Pair) :
    (recode256 n z).1.length = n := by
  induction n generalizing z with
  | zero => rfl
  | succ n ih =>
      simp only [recode256, List.length_cons]
      exact congrArg Nat.succ (ih (nearestStep z).2)

theorem recode256_digit_bounds (n : Nat) (z : Pair) :
    ∀ digit ∈ (recode256 n z).1, 3 * norm digit ≤ (256 : Int)^2 := by
  induction n generalizing z with
  | zero => simp [recode256]
  | succ n ih =>
      simp only [recode256, List.mem_cons]
      intro digit h
      rcases h with h | h
      · rw [h]
        exact nearest_digit_bound z
      · exact ih (nearestStep z).2 digit h

theorem recode256_steps (n : Nat) (z : Pair) :
    Recodes256 z (recode256 n z).1 (recode256 n z).2 := by
  induction n generalizing z with
  | zero => exact Recodes256.done z
  | succ n ih =>
      simp only [recode256]
      exact Recodes256.next (nearestStep z).1 (nearest_step_equation z)
        (ih (nearestStep z).2)

theorem nearest_fifteen_top_bound (z : Pair)
    (hInitial : 3 * norm z ≤ subgroupOrder) :
    3 * norm (recode256 15 z).2 ≤ topCap := by
  exact fifteen_steps_top_bound z (recode256 15 z).2 (recode256 15 z).1
    (recode256_length 15 z) hInitial (recode256_digit_bounds 15 z)
    (recode256_steps 15 z)

def initial (scalar : Int) : Pair :=
  PrimeJ0Radix919DigitCover.nearestRepresentative scalar

theorem scalar_top_bound (scalar : Int) :
    3 * norm (recode256 15 (initial scalar)).2 ≤ topCap :=
  nearest_fifteen_top_bound (initial scalar)
    (PrimeJ0Radix919DigitCover.nearest_representative_bound scalar)

theorem scalar_recode_reconstruct (scalar : Int) :
    initial scalar =
      add (decode256 (recode256 15 (initial scalar)).1)
        (scale ((256 : Int)^15) (recode256 15 (initial scalar)).2) := by
  have h := recodes256_reconstruct (initial scalar)
    (recode256 15 (initial scalar)).2 (recode256 15 (initial scalar)).1
    (recode256_steps 15 (initial scalar))
  rw [recode256_length] at h
  exact h

theorem scalar_recode_congruence (scalar : Int) :
    (PrimeJ0Radix919DigitCover.scalarMap
      (add (decode256 (recode256 15 (initial scalar)).1)
        (scale ((256 : Int)^15) (recode256 15 (initial scalar)).2))
      - scalar) % subgroupOrder = 0 := by
  rw [← scalar_recode_reconstruct]
  exact PrimeJ0Radix919DigitCover.nearest_representative_congruence scalar

#print axioms nearest_step_equation
#print axioms nearest_digit_bound
#print axioms recode256_length
#print axioms recode256_digit_bounds
#print axioms recode256_steps
#print axioms nearest_fifteen_top_bound
#print axioms scalar_top_bound
#print axioms scalar_recode_reconstruct
#print axioms scalar_recode_congruence

end PrimeJ0Power2DirectTerminalDigitCover
