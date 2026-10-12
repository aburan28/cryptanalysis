import TerminalUnit

namespace PrimeJ0Radix919DigitCover

open PrimeJ0Radix919TerminalUnit

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
  let x := u - m * 919
  let y := v - n * 919
  ((x+y, -y), (m+n, -n))

theorem corner_equation (z : Pair) (m n : Int) :
    z = add (corner z m n).1 (scale 919 (corner z m n).2) := by
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
    (hOld : z = add old.1 (scale 919 old.2))
    (hNext : z = add next.1 (scale 919 next.2)) :
    z = add (choose old next).1 (scale 919 (choose old next).2) := by
  unfold choose
  split
  · exact hNext
  · exact hOld

def nearestStep (z : Pair) : Candidate :=
  let u := z.1 + z.2
  let v := -z.2
  let fu := u / 919
  let fv := v / 919
  choose (choose (choose (corner z fu fv) (corner z fu (fv+1)))
    (corner z (fu+1) fv)) (corner z (fu+1) (fv+1))

theorem nearest_step_equation (z : Pair) :
    z = add (nearestStep z).1 (scale 919 (nearestStep z).2) := by
  unfold nearestStep
  exact choose_equation z _ _
    (choose_equation z _ _
      (choose_equation z _ _ (corner_equation z _ _) (corner_equation z _ _))
      (corner_equation z _ _))
    (corner_equation z _ _)

private theorem corner_digit_00 (z : Pair) :
    (corner z ((z.1+z.2)/919) ((-z.2)/919)).1 =
      ((z.1+z.2)%919 + (-z.2)%919, -((-z.2)%919)) := by
  rcases z with ⟨a,b⟩
  apply Prod.ext <;> simp only [corner] <;> omega

private theorem corner_digit_01 (z : Pair) :
    (corner z ((z.1+z.2)/919) (((-z.2)/919)+1)).1 =
      ((z.1+z.2)%919 + ((-z.2)%919-919), -(((-z.2)%919)-919)) := by
  rcases z with ⟨a,b⟩
  apply Prod.ext <;> simp only [corner] <;> omega

private theorem corner_digit_10 (z : Pair) :
    (corner z (((z.1+z.2)/919)+1) ((-z.2)/919)).1 =
      (((z.1+z.2)%919-919) + (-z.2)%919, -((-z.2)%919)) := by
  rcases z with ⟨a,b⟩
  apply Prod.ext <;> simp only [corner] <;> omega

private theorem corner_digit_11 (z : Pair) :
    (corner z (((z.1+z.2)/919)+1) (((-z.2)/919)+1)).1 =
      (((z.1+z.2)%919-919) + ((-z.2)%919-919), -(((-z.2)%919)-919)) := by
  rcases z with ⟨a,b⟩
  apply Prod.ext <;> simp only [corner] <;> omega

theorem nearest_digit_bound (z : Pair) :
    3 * norm (nearestStep z).1 ≤ (919 : Int)^2 := by
  let u := z.1+z.2
  let v := -z.2
  let r := u % 919
  let s := v % 919
  have hr0 : 0 ≤ r := by dsimp [r]; omega
  have hs0 : 0 ≤ s := by dsimp [s]; omega
  have hrR : r ≤ (919 : Int) := by dsimp [r]; omega
  have hsR : s ≤ (919 : Int) := by dsimp [s]; omega
  have hCover := four_corner_cover r s 919 hr0 hs0 hrR hsR
  let c00 := corner z (u/919) (v/919)
  let c01 := corner z (u/919) (v/919+1)
  let c10 := corner z (u/919+1) (v/919)
  let c11 := corner z (u/919+1) (v/919+1)
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
  · have hb := hex_digit_bound r s 919 h₀
    have hc : c00.1 = (r+s,-s) := by simpa [c00, r, s, u, v] using corner_digit_00 z
    rw [hc] at h00
    have hs := Int.mul_le_mul_of_nonneg_left h00 (by decide : (0:Int) ≤ 3)
    omega
  · have hb := hex_digit_bound (r-919) s 919 h₁
    have hc : c10.1 = ((r-919)+s,-s) := by simpa [c10, r, s, u, v] using corner_digit_10 z
    rw [hc] at h10
    have hs := Int.mul_le_mul_of_nonneg_left h10 (by decide : (0:Int) ≤ 3)
    omega
  · have hb := hex_digit_bound r (s-919) 919 h₂
    have hc : c01.1 = (r+(s-919),-(s-919)) := by simpa [c01, r, s, u, v] using corner_digit_01 z
    rw [hc] at h01
    have hs := Int.mul_le_mul_of_nonneg_left h01 (by decide : (0:Int) ≤ 3)
    omega
  · have hb := hex_digit_bound (r-919) (s-919) 919 h₃
    have hc : c11.1 = ((r-919)+(s-919),-(s-919)) := by simpa [c11, r, s, u, v] using corner_digit_11 z
    rw [hc] at h11
    have hs := Int.mul_le_mul_of_nonneg_left h11 (by decide : (0:Int) ≤ 3)
    omega

-- This recursion records the same digit and quotient used by the concrete
-- four-corner chooser at each window. The first component is least-significant
-- digit first, as in the Rust and Python implementations.
def recode : Nat → Pair → List Pair × Pair
  | 0, z => ([], z)
  | n+1, z =>
      let step := nearestStep z
      let tail := recode n step.2
      (step.1 :: tail.1, tail.2)

theorem recode_length (n : Nat) (z : Pair) : (recode n z).1.length = n := by
  induction n generalizing z with
  | zero => rfl
  | succ n ih =>
      simp only [recode, List.length_cons]
      exact congrArg Nat.succ (ih (nearestStep z).2)

theorem recode_digit_bounds (n : Nat) (z : Pair) :
    ∀ digit ∈ (recode n z).1, 3 * norm digit ≤ (919 : Int)^2 := by
  induction n generalizing z with
  | zero => simp [recode]
  | succ n ih =>
      simp only [recode, List.mem_cons]
      intro digit h
      rcases h with h | h
      · rw [h]
        exact nearest_digit_bound z
      · exact ih (nearestStep z).2 digit h

theorem recode_steps (n : Nat) (z : Pair) :
    Recodes z (recode n z).1 (recode n z).2 := by
  induction n generalizing z with
  | zero => exact Recodes.done z
  | succ n ih =>
      simp only [recode]
      exact Recodes.next (nearestStep z).1 (nearest_step_equation z)
        (ih (nearestStep z).2)

theorem nearest_thirteen_terminal_unit (z : Pair)
    (hInitial : 3 * norm z ≤ subgroupOrder) :
    (recode 13 z).2 = (0, 0) ∨ (recode 13 z).2 = (1, 0) ∨
    (recode 13 z).2 = (-1, 0) ∨ (recode 13 z).2 = (1, -1) ∨
    (recode 13 z).2 = (2, -1) ∨ (recode 13 z).2 = (-1, 1) ∨
    (recode 13 z).2 = (-2, 1) := by
  exact thirteen_steps_terminal_unit z (recode 13 z).2 (recode 13 z).1
    (recode_length 13 z) hInitial (recode_digit_bounds 13 z) (recode_steps 13 z)

private def form (x y : Int) : Int := x*x - x*y + y*y

private theorem hex_form_bound (x y R : Int) (h : hex x y R) :
    3 * form x y ≤ R*R := by
  have hb := hex_digit_bound x y R h
  have hid : norm (x+y,-y) = form x y := by
    simp only [norm, form]
    grind +ring
  rw [hid] at hb
  exact hb

def basisU : Pair :=
  (193508920647619669885755136084601127231,
   238911465918039986966665730306072050094)

def basisV : Pair :=
  (-basisU.2, 303414439467246543595250775667605759171)

def basisW : Pair := sub basisU (scale 2 basisV)

theorem basis_determinant :
    basisW.1 * basisV.2 - basisW.2 * basisV.1 = subgroupOrder := by decide

theorem basis_norms :
    norm basisW = subgroupOrder ∧
    norm basisV = subgroupOrder ∧
    norm (add basisW basisV) = subgroupOrder := by decide

private theorem basis_gram (W V : Pair) (N x y : Int)
    (hW : norm W = N) (hV : norm V = N)
    (hSum : norm (add W V) = N) :
    norm (add (scale x W) (scale y V)) = N * form x y := by
  have hCross : cross W V = -N := by
    have h := norm_add W V
    rw [hW, hV, hSum] at h
    omega
  have hc : cross (scale x W) (scale y V) = x*y*cross W V := by
    rcases W with ⟨a,b⟩
    rcases V with ⟨c,d⟩
    simp only [cross, scale]
    grind +ring
  have h := norm_add (scale x W) (scale y V)
  rw [norm_scale, norm_scale, hc, hCross, hW, hV] at h
  dsimp [form]
  grind +ring

def representativeCorner (scalar m n : Int) (W V : Pair) : Pair :=
  sub (sub (scalar,0) (scale m W)) (scale n V)

private theorem scaled_representative_corner (scalar m n N : Int) (W V : Pair)
    (hDet : W.1 * V.2 - W.2 * V.1 = N) :
    scale N (representativeCorner scalar m n W V) =
      add (scale (scalar*V.2-m*N) W) (scale (-scalar*W.2-n*N) V) := by
  rcases W with ⟨a,b⟩
  rcases V with ⟨c,d⟩
  apply Prod.ext
  · simp only [representativeCorner, sub, scale, add] at hDet ⊢
    grind +ring
  · simp only [representativeCorner, sub, scale, add] at hDet ⊢
    grind +ring

private theorem representative_corner_bound (scalar m n N : Int) (W V : Pair)
    (hN : 0 < N) (hDet : W.1*V.2-W.2*V.1=N)
    (hW : norm W=N) (hV : norm V=N) (hSum : norm (add W V)=N)
    (hHex : 3*form (scalar*V.2-m*N) (-scalar*W.2-n*N) ≤ N*N) :
    3*norm (representativeCorner scalar m n W V) ≤ N := by
  let x := scalar*V.2-m*N
  let y := -scalar*W.2-n*N
  have hs := scaled_representative_corner scalar m n N W V hDet
  have hg := basis_gram W V N x y hW hV hSum
  have hn := norm_scale N (representativeCorner scalar m n W V)
  rw [hs, hg] at hn
  have heq : N*N*norm (representativeCorner scalar m n W V) = N*form x y := by
    simpa [x,y] using hn.symm
  have hmul := Int.mul_le_mul_of_nonneg_left hHex (Int.le_of_lt hN)
  have hbound : N*N*(3*norm (representativeCorner scalar m n W V)) ≤ N*N*N := by
    calc
      N*N*(3*norm (representativeCorner scalar m n W V)) = N*(3*form x y) := by
        grind +ring
      _ ≤ N*(N*N) := by simpa [x,y] using hmul
      _ = N*N*N := by grind +ring
  have hN2 : 0 < N*N := Int.mul_pos hN hN
  by_cases hgoal : 3*norm (representativeCorner scalar m n W V) ≤ N
  · exact hgoal
  · have hgt : N < 3*norm (representativeCorner scalar m n W V) := by omega
    have hstrict := Int.mul_lt_mul_of_pos_left hgt hN2
    omega

private def maxAbs (z : Pair) : Nat := max z.1.natAbs z.2.natAbs

private def representativeScoreLt (a b : Pair) : Prop :=
  norm a < norm b ∨
  (norm a = norm b ∧
    (maxAbs a < maxAbs b ∨
     (maxAbs a = maxAbs b ∧
      (a.1 < b.1 ∨ (a.1 = b.1 ∧ a.2 < b.2)))))

private instance (a b : Pair) : Decidable (representativeScoreLt a b) := by
  unfold representativeScoreLt
  infer_instance

private def chooseRepresentative (old next : Pair) : Pair :=
  if representativeScoreLt next old then next else old

private theorem choose_representative_le_left (old next : Pair) :
    norm (chooseRepresentative old next) ≤ norm old := by
  unfold chooseRepresentative
  split
  · rename_i h
    dsimp [representativeScoreLt] at h
    omega
  · omega

private theorem choose_representative_le_right (old next : Pair) :
    norm (chooseRepresentative old next) ≤ norm next := by
  unfold chooseRepresentative
  split
  · omega
  · rename_i h
    have hNoLess : ¬ norm next < norm old := by
      intro hlt
      exact h (Or.inl hlt)
    omega

def nearestRepresentative (scalar : Int) : Pair :=
  let W := basisW
  let V := basisV
  let N := subgroupOrder
  let fw := (scalar*V.2)/N
  let fv := (-scalar*W.2)/N
  chooseRepresentative
    (chooseRepresentative
      (chooseRepresentative
        (representativeCorner scalar fw fv W V)
        (representativeCorner scalar fw (fv+1) W V))
      (representativeCorner scalar (fw+1) fv W V))
    (representativeCorner scalar (fw+1) (fv+1) W V)

theorem nearest_representative_bound (scalar : Int) :
    3 * norm (nearestRepresentative scalar) ≤ subgroupOrder := by
  let W := basisW
  let V := basisV
  let N := subgroupOrder
  have hN : 0 < N := by decide
  have hDet : W.1*V.2-W.2*V.1=N := by simpa [W,V,N] using basis_determinant
  have hW : norm W=N := by simpa [W,N] using basis_norms.1
  have hV : norm V=N := by simpa [V,N] using basis_norms.2.1
  have hSum : norm (add W V)=N := by simpa [W,V,N] using basis_norms.2.2
  let t := scalar*V.2
  let w := -scalar*W.2
  let fw := t/N
  let fv := w/N
  let r := t%N
  let s := w%N
  have hr0 : 0 ≤ r := Int.emod_nonneg t (Int.ne_of_gt hN)
  have hs0 : 0 ≤ s := Int.emod_nonneg w (Int.ne_of_gt hN)
  have hrN : r ≤ N := Int.le_of_lt (Int.emod_lt_of_pos t hN)
  have hsN : s ≤ N := Int.le_of_lt (Int.emod_lt_of_pos w hN)
  have hx0 : t-fw*N=r := by
    have h := Int.ediv_mul_add_emod t N
    dsimp [fw,r]
    omega
  have hx1 : t-(fw+1)*N=r-N := by
    have h := Int.ediv_mul_add_emod t N
    dsimp [fw,r]
    grind +ring
  have hy0 : w-fv*N=s := by
    have h := Int.ediv_mul_add_emod w N
    dsimp [fv,s]
    omega
  have hy1 : w-(fv+1)*N=s-N := by
    have h := Int.ediv_mul_add_emod w N
    dsimp [fv,s]
    grind +ring
  let c00 := representativeCorner scalar fw fv W V
  let c01 := representativeCorner scalar fw (fv+1) W V
  let c10 := representativeCorner scalar (fw+1) fv W V
  let c11 := representativeCorner scalar (fw+1) (fv+1) W V
  have h00 : norm (nearestRepresentative scalar) ≤ norm c00 := by
    dsimp [nearestRepresentative, c00,c01,c10,c11,fw,fv,t,w,W,V,N]
    exact Int.le_trans (choose_representative_le_left _ _)
      (Int.le_trans (choose_representative_le_left _ _)
        (choose_representative_le_left _ _))
  have h01 : norm (nearestRepresentative scalar) ≤ norm c01 := by
    dsimp [nearestRepresentative, c00,c01,c10,c11,fw,fv,t,w,W,V,N]
    exact Int.le_trans (choose_representative_le_left _ _)
      (Int.le_trans (choose_representative_le_left _ _)
        (choose_representative_le_right _ _))
  have h10 : norm (nearestRepresentative scalar) ≤ norm c10 := by
    dsimp [nearestRepresentative, c00,c01,c10,c11,fw,fv,t,w,W,V,N]
    exact Int.le_trans (choose_representative_le_left _ _)
      (choose_representative_le_right _ _)
  have h11 : norm (nearestRepresentative scalar) ≤ norm c11 := by
    dsimp [nearestRepresentative, c00,c01,c10,c11,fw,fv,t,w,W,V,N]
    exact choose_representative_le_right _ _
  rcases four_corner_cover r s N hr0 hs0 hrN hsN with h₀ | h₁ | h₂ | h₃
  · have hf := hex_form_bound r s N h₀
    have hb : 3*form (scalar*V.2-fw*N) (-scalar*W.2-fv*N) ≤ N*N := by
      change 3*form (t-fw*N) (w-fv*N) ≤ N*N
      rw [hx0,hy0]
      exact hf
    have hc := representative_corner_bound scalar fw fv N W V hN hDet hW hV hSum hb
    have hm := Int.mul_le_mul_of_nonneg_left h00 (by decide : (0:Int) ≤ 3)
    dsimp [c00] at hm
    omega
  · have hf := hex_form_bound (r-N) s N h₁
    have hb : 3*form (scalar*V.2-(fw+1)*N) (-scalar*W.2-fv*N) ≤ N*N := by
      change 3*form (t-(fw+1)*N) (w-fv*N) ≤ N*N
      rw [hx1,hy0]
      exact hf
    have hc := representative_corner_bound scalar (fw+1) fv N W V hN hDet hW hV hSum hb
    have hm := Int.mul_le_mul_of_nonneg_left h10 (by decide : (0:Int) ≤ 3)
    dsimp [c10] at hm
    omega
  · have hf := hex_form_bound r (s-N) N h₂
    have hb : 3*form (scalar*V.2-fw*N) (-scalar*W.2-(fv+1)*N) ≤ N*N := by
      change 3*form (t-fw*N) (w-(fv+1)*N) ≤ N*N
      rw [hx0,hy1]
      exact hf
    have hc := representative_corner_bound scalar fw (fv+1) N W V hN hDet hW hV hSum hb
    have hm := Int.mul_le_mul_of_nonneg_left h01 (by decide : (0:Int) ≤ 3)
    dsimp [c01] at hm
    omega
  · have hf := hex_form_bound (r-N) (s-N) N h₃
    have hb : 3*form (scalar*V.2-(fw+1)*N) (-scalar*W.2-(fv+1)*N) ≤ N*N := by
      change 3*form (t-(fw+1)*N) (w-(fv+1)*N) ≤ N*N
      rw [hx1,hy1]
      exact hf
    have hc := representative_corner_bound scalar (fw+1) (fv+1) N W V hN hDet hW hV hSum hb
    have hm := Int.mul_le_mul_of_nonneg_left h11 (by decide : (0:Int) ≤ 3)
    dsimp [c11] at hm
    omega

theorem scalar_recode_terminal_unit (scalar : Int) :
    (recode 13 (nearestRepresentative scalar)).2 = (0, 0) ∨
    (recode 13 (nearestRepresentative scalar)).2 = (1, 0) ∨
    (recode 13 (nearestRepresentative scalar)).2 = (-1, 0) ∨
    (recode 13 (nearestRepresentative scalar)).2 = (1, -1) ∨
    (recode 13 (nearestRepresentative scalar)).2 = (2, -1) ∨
    (recode 13 (nearestRepresentative scalar)).2 = (-1, 1) ∨
    (recode 13 (nearestRepresentative scalar)).2 = (-2, 1) :=
  nearest_thirteen_terminal_unit (nearestRepresentative scalar)
    (nearest_representative_bound scalar)

def lambdaTau : Int :=
  0xac9c52b33fa3cf1f5ad9e3fd77ed9ba4a880b9fc8ec739c2e0cfc810b51283d0

def scalarMap (z : Pair) : Int := z.1 + lambdaTau*z.2

private def kernelV : Int := 204580311103670717363538375293302872898
private def kernelW : Int := -248072105426244568656964927078881993893

theorem basis_kernel :
    scalarMap basisV = subgroupOrder*kernelV ∧
    scalarMap basisW = subgroupOrder*kernelW := by decide

private theorem representative_corner_congruence (scalar m n : Int) :
    (scalarMap (representativeCorner scalar m n basisW basisV)-scalar) %
      subgroupOrder = 0 := by
  have hV := basis_kernel.1
  have hW := basis_kernel.2
  have heq : scalarMap (representativeCorner scalar m n basisW basisV)-scalar =
      subgroupOrder * (-(m*kernelW+n*kernelV)) := by
    dsimp [scalarMap, representativeCorner, sub, scale] at hV hW ⊢
    grind +ring
  have hdvd : subgroupOrder ∣
      scalarMap (representativeCorner scalar m n basisW basisV)-scalar :=
    ⟨-(m*kernelW+n*kernelV), heq⟩
  exact Int.emod_eq_zero_of_dvd hdvd

private theorem choose_representative_congruence (scalar : Int) (old next : Pair)
    (hOld : (scalarMap old-scalar)%subgroupOrder=0)
    (hNext : (scalarMap next-scalar)%subgroupOrder=0) :
    (scalarMap (chooseRepresentative old next)-scalar)%subgroupOrder=0 := by
  unfold chooseRepresentative
  split
  · exact hNext
  · exact hOld

theorem nearest_representative_congruence (scalar : Int) :
    (scalarMap (nearestRepresentative scalar)-scalar)%subgroupOrder=0 := by
  unfold nearestRepresentative
  exact choose_representative_congruence scalar _ _
    (choose_representative_congruence scalar _ _
      (choose_representative_congruence scalar _ _
        (representative_corner_congruence scalar _ _)
        (representative_corner_congruence scalar _ _))
      (representative_corner_congruence scalar _ _))
    (representative_corner_congruence scalar _ _)

theorem scalar_recode_reconstruct (scalar : Int) :
    nearestRepresentative scalar =
      add (decode (recode 13 (nearestRepresentative scalar)).1)
        (scale ((919 : Int)^13) (recode 13 (nearestRepresentative scalar)).2) := by
  have h := recodes_reconstruct (nearestRepresentative scalar)
    (recode 13 (nearestRepresentative scalar)).2
    (recode 13 (nearestRepresentative scalar)).1
    (recode_steps 13 (nearestRepresentative scalar))
  rw [recode_length] at h
  exact h

theorem scalar_recode_congruence (scalar : Int) :
    (scalarMap (add (decode (recode 13 (nearestRepresentative scalar)).1)
      (scale ((919 : Int)^13) (recode 13 (nearestRepresentative scalar)).2))
      - scalar) % subgroupOrder = 0 := by
  rw [← scalar_recode_reconstruct]
  exact nearest_representative_congruence scalar

#print axioms nearest_step_equation
#print axioms nearest_digit_bound
#print axioms recode_length
#print axioms recode_digit_bounds
#print axioms recode_steps
#print axioms nearest_thirteen_terminal_unit
#print axioms basis_determinant
#print axioms basis_norms
#print axioms nearest_representative_bound
#print axioms scalar_recode_terminal_unit
#print axioms basis_kernel
#print axioms nearest_representative_congruence
#print axioms scalar_recode_reconstruct
#print axioms scalar_recode_congruence

end PrimeJ0Radix919DigitCover
