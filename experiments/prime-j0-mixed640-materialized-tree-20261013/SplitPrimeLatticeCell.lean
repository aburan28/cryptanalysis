import Lean

def q (x y : Int) : Int := x*x-x*y+y*y

theorem square_le_abs (x y : Int) (_hy : 0 ≤ y) (hlo : -y ≤ x) (hhi : x ≤ y) :
    x*x ≤ y*y := by
  have h1 : 0 ≤ y-x := by omega
  have h2 : 0 ≤ y+x := by omega
  have hm := Int.mul_nonneg h1 h2
  grind

theorem local_cell_bound (n x y : Int)
    (hn : 0 ≤ n) (hx : 0 ≤ x) (hy : 0 ≤ y)
    (hs : x+y ≤ n) (h1 : 2*x-y ≤ n) (h2 : 2*y-x ≤ n) :
    3*q x y ≤ n*n := by
  let s := x+y
  let d := x-y
  have hs0 : 0 ≤ s := by dsimp [s]; omega
  have hdlo : -s ≤ d := by dsimp [s,d]; omega
  have hdhi : d ≤ s := by dsimp [s,d]; omega
  have hds : d*d ≤ s*s := square_le_abs d s hs0 hdlo hdhi
  have hform : 4*q x y = s*s+3*d*d := by dsimp [q,s,d]; grind
  have hform2 : 4*q x y = s*s+3*(d*d) := by grind
  by_cases hsmall : 2*s ≤ n
  · have hsq : (2*s)*(2*s) ≤ n*n :=
      square_le_abs (2*s) n hn (by omega) hsmall
    have hring : (2*s)*(2*s) = 4*(s*s) := by grind
    have hq : 4*q x y ≤ 4*(s*s) := by omega
    have hn2 : 0 ≤ n*n := by
      exact Int.mul_nonneg hn hn
    omega
  · have hlo : -(2*n-s) ≤ 3*d := by dsimp [s,d] at *; omega
    have hhi : 3*d ≤ 2*n-s := by dsimp [s,d] at *; omega
    have hns : 0 ≤ 2*n-s := by omega
    have hsq : (3*d)*(3*d) ≤ (2*n-s)*(2*n-s) :=
      square_le_abs (3*d) (2*n-s) hns hlo hhi
    have hprod : s*(n-s) ≥ 0 := Int.mul_nonneg hs0 (by omega)
    have hring1 : (3*d)*(3*d) = 9*(d*d) := by grind
    have hring2 : 3*(s*s)+(2*n-s)*(2*n-s)+4*s*(n-s) = 4*(n*n) := by grind
    have hring3 : 4*s*(n-s) = 4*(s*(n-s)) := by grind
    omega

theorem adjacent_corner_bound (n u v : Int)
    (hn : 0 ≤ n) (hu : 0 ≤ u) (hv : 0 ≤ v)
    (h1 : 2*u+v ≤ n) (h2 : u+2*v ≤ n) :
    3*(u*u+u*v+v*v) ≤ n*n := by
  by_cases huv : v ≤ u
  · have hpos : 0 ≤ 2*u+v := by omega
    have hsq : (2*u+v)*(2*u+v) ≤ n*n :=
      square_le_abs (2*u+v) n hn (by omega) h1
    have hm : 0 ≤ (u-v)*(u+2*v) :=
      Int.mul_nonneg (by omega) (by omega)
    have hid : (2*u+v)*(2*u+v) - 3*(u*u+u*v+v*v) =
        (u-v)*(u+2*v) := by grind
    omega
  · have hpos : 0 ≤ u+2*v := by omega
    have hsq : (u+2*v)*(u+2*v) ≤ n*n :=
      square_le_abs (u+2*v) n hn (by omega) h2
    have hm : 0 ≤ (v-u)*(2*u+v) :=
      Int.mul_nonneg (by omega) (by omega)
    have hid : (u+2*v)*(u+2*v) - 3*(u*u+u*v+v*v) =
        (v-u)*(2*u+v) := by grind
    omega

theorem lower_triangle_cover (n x y : Int)
    (hn : 0 ≤ n) (hx : 0 ≤ x) (hy : 0 ≤ y)
    (hs : x+y ≤ n) :
    3*q x y ≤ n*n ∨
    3*q (x-n) y ≤ n*n ∨
    3*q x (y-n) ≤ n*n := by
  by_cases h1 : 2*x-y ≤ n
  · by_cases h2 : 2*y-x ≤ n
    · exact Or.inl (local_cell_bound n x y hn hx hy hs h1 h2)
    · have hv : 0 ≤ n-y := by omega
      have hc1 : 2*x+(n-y) ≤ n := by omega
      have hc2 : x+2*(n-y) ≤ n := by omega
      have h := adjacent_corner_bound n x (n-y) hn hx hv hc1 hc2
      have heq : q x (y-n) = x*x+x*(n-y)+(n-y)*(n-y) := by
        unfold q
        grind
      rw [heq]
      exact Or.inr (Or.inr h)
  · have hu : 0 ≤ n-x := by omega
    have hc1 : 2*(n-x)+y ≤ n := by omega
    have hc2 : (n-x)+2*y ≤ n := by omega
    have h := adjacent_corner_bound n (n-x) y hn hu hy hc1 hc2
    have heq : q (x-n) y = (n-x)*(n-x)+(n-x)*y+y*y := by
      unfold q
      grind
    rw [heq]
    exact Or.inr (Or.inl h)

theorem four_corner_cover (n x y : Int)
    (hn : 0 ≤ n) (hx : 0 ≤ x) (hy : 0 ≤ y)
    (hxn : x ≤ n) (hyn : y ≤ n) :
    3*q x y ≤ n*n ∨
    3*q (x-n) y ≤ n*n ∨
    3*q x (y-n) ≤ n*n ∨
    3*q (x-n) (y-n) ≤ n*n := by
  by_cases hs : x+y ≤ n
  · rcases lower_triangle_cover n x y hn hx hy hs with h | h | h
    · exact Or.inl h
    · exact Or.inr (Or.inl h)
    · exact Or.inr (Or.inr (Or.inl h))
  · have hu : 0 ≤ n-x := by omega
    have hv : 0 ≤ n-y := by omega
    have hs' : (n-x)+(n-y) ≤ n := by omega
    rcases lower_triangle_cover n (n-x) (n-y) hn hu hv hs' with h | h | h
    · have heq : q (n-x) (n-y) = q (x-n) (y-n) := by
        unfold q
        grind
      rw [heq] at h
      exact Or.inr (Or.inr (Or.inr h))
    · have heq : q ((n-x)-n) (n-y) = q x (y-n) := by
        unfold q
        grind
      rw [heq] at h
      exact Or.inr (Or.inr (Or.inl h))
    · have heq : q (n-x) ((n-y)-n) = q (x-n) y := by
        unfold q
        grind
      rw [heq] at h
      exact Or.inr (Or.inl h)

def order : Int :=
  115792089237316195423570985008687907852837564279074904382605163141518161494337
def W : Int × Int :=
  (671331852483699643819086596696745227419,
   -367917413016453100223835821029139468248)
def V : Int × Int :=
  (-238911465918039986966665730306072050094,
   303414439467246543595250775667605759171)
def eNorm (a b : Int) : Int := a*a+3*a*b+3*b*b

theorem basis_det : W.1*V.2-W.2*V.1 = order := by decide
theorem basis_norm_W : eNorm W.1 W.2 = order := by decide
theorem basis_norm_V : eNorm V.1 V.2 = order := by decide
theorem basis_norm_sum : eNorm (W.1+V.1) (W.2+V.2) = order := by decide

theorem basis_gram (x y : Int) :
    eNorm (x*W.1+y*V.1) (x*W.2+y*V.2) = order*q x y := by
  have hw := basis_norm_W
  have hv := basis_norm_V
  have hsum := basis_norm_sum
  dsimp [eNorm,q,W,V,order] at *
  grind

theorem candidate_coordinates (s fw fv rw rv a b : Int)
    (hw : s*V.2 = order*fw+rw)
    (hv : -(s*W.2) = order*fv+rv)
    (ha : a = s-fw*W.1-fv*V.1)
    (hb : b = -fw*W.2-fv*V.2) :
    order*a = rw*W.1+rv*V.1 ∧
    order*b = rw*W.2+rv*V.2 := by
  have hd := basis_det
  dsimp [W,V,order] at *
  constructor <;> grind

theorem candidate_norm_formula (a b rw rv : Int)
    (ha : order*a = rw*W.1+rv*V.1)
    (hb : order*b = rw*W.2+rv*V.2) :
    order*eNorm a b = q rw rv := by
  have hg := basis_gram rw rv
  rw [← ha, ← hb] at hg
  have hs : eNorm (order*a) (order*b) = order*order*eNorm a b := by
    unfold eNorm
    grind
  rw [hs] at hg
  have hnonzero : order ≠ 0 := by decide
  have hfactor : order*(order*eNorm a b) = order*(q rw rv) := by
    grind
  exact Int.eq_of_mul_eq_mul_left hnonzero hfactor

def candidate (s fw fv i j : Int) : Int × Int :=
  (s-(fw+i)*W.1-(fv+j)*V.1,
   -(fw+i)*W.2-(fv+j)*V.2)

theorem shifted_candidate_norm (s fw fv rw rv i j : Int)
    (hw : s*V.2 = order*fw+rw)
    (hv : -(s*W.2) = order*fv+rv) :
    order*eNorm (candidate s fw fv i j).1 (candidate s fw fv i j).2 =
      q (rw-i*order) (rv-j*order) := by
  have hw' : s*V.2 = order*(fw+i)+(rw-i*order) := by grind
  have hv' : -(s*W.2) = order*(fv+j)+(rv-j*order) := by grind
  have hc := candidate_coordinates s (fw+i) (fv+j)
    (rw-i*order) (rv-j*order)
    (candidate s fw fv i j).1 (candidate s fw fv i j).2
    hw' hv' (by rfl) (by rfl)
  exact candidate_norm_formula _ _ _ _ hc.1 hc.2

theorem candidate_bound (s fw fv rw rv i j : Int)
    (hw : s*V.2 = order*fw+rw)
    (hv : -(s*W.2) = order*fv+rv)
    (hq : 3*q (rw-i*order) (rv-j*order) ≤ order*order) :
    3*eNorm (candidate s fw fv i j).1 (candidate s fw fv i j).2 ≤ order := by
  have hf := shifted_candidate_norm s fw fv rw rv i j hw hv
  have hn : 0 < order := by decide
  have hm : order*(3*eNorm (candidate s fw fv i j).1
      (candidate s fw fv i j).2) ≤ order*order := by
    grind
  exact (Int.mul_le_mul_left hn).mp hm

def floorW (s : Int) : Int := (s*V.2)/order
def floorV (s : Int) : Int := (-(s*W.2))/order
def remW (s : Int) : Int := (s*V.2)%order
def remV (s : Int) : Int := (-(s*W.2))%order

theorem floor_division (s : Int) :
    s*V.2 = order*floorW s+remW s ∧
    -(s*W.2) = order*floorV s+remV s ∧
    0 ≤ remW s ∧ remW s < order ∧
    0 ≤ remV s ∧ remV s < order := by
  have hn : 0 < order := by decide
  have hnz : order ≠ 0 := by decide
  dsimp [floorW,floorV,remW,remV]
  constructor
  · exact (Int.mul_ediv_add_emod (s*V.2) order).symm
  constructor
  · exact (Int.mul_ediv_add_emod (-(s*W.2)) order).symm
  exact ⟨Int.emod_nonneg _ hnz, Int.emod_lt _ hnz,
    Int.emod_nonneg _ hnz, Int.emod_lt _ hnz⟩

theorem four_candidate_bound (s : Int) :
    3*eNorm (candidate s (floorW s) (floorV s) 0 0).1
      (candidate s (floorW s) (floorV s) 0 0).2 ≤ order ∨
    3*eNorm (candidate s (floorW s) (floorV s) 1 0).1
      (candidate s (floorW s) (floorV s) 1 0).2 ≤ order ∨
    3*eNorm (candidate s (floorW s) (floorV s) 0 1).1
      (candidate s (floorW s) (floorV s) 0 1).2 ≤ order ∨
    3*eNorm (candidate s (floorW s) (floorV s) 1 1).1
      (candidate s (floorW s) (floorV s) 1 1).2 ≤ order := by
  obtain ⟨hw,hv,hrw0,hrwn,hrv0,hrvn⟩ := floor_division s
  have hn : 0 ≤ order := by decide
  rcases four_corner_cover order (remW s) (remV s)
      hn hrw0 hrv0 (by omega) (by omega) with h | h | h | h
  · exact Or.inl (candidate_bound s _ _ _ _ 0 0 hw hv (by simpa using h))
  · exact Or.inr (Or.inl (candidate_bound s _ _ _ _ 1 0 hw hv (by simpa using h)))
  · exact Or.inr (Or.inr (Or.inl
      (candidate_bound s _ _ _ _ 0 1 hw hv (by simpa using h))))
  · exact Or.inr (Or.inr (Or.inr
      (candidate_bound s _ _ _ _ 1 1 hw hv (by simpa using h))))

def candidateNorm (s i j : Int) : Int :=
  eNorm (candidate s (floorW s) (floorV s) i j).1
    (candidate s (floorW s) (floorV s) i j).2

def selectedNorm (s : Int) : Int :=
  min (min (candidateNorm s 0 0) (candidateNorm s 1 0))
      (min (candidateNorm s 0 1) (candidateNorm s 1 1))

theorem selected_norm_bound (s : Int) : 3*selectedNorm s ≤ order := by
  rcases four_candidate_bound s with h | h | h | h
  · have hm : selectedNorm s ≤ candidateNorm s 0 0 := by
      dsimp [selectedNorm]
      exact Int.le_trans (Int.min_le_left ..) (Int.min_le_left ..)
    dsimp [candidateNorm] at hm
    omega
  · have hm : selectedNorm s ≤ candidateNorm s 1 0 := by
      dsimp [selectedNorm]
      exact Int.le_trans (Int.min_le_left ..) (Int.min_le_right ..)
    dsimp [candidateNorm] at hm
    omega
  · have hm : selectedNorm s ≤ candidateNorm s 0 1 := by
      dsimp [selectedNorm]
      exact Int.le_trans (Int.min_le_right ..) (Int.min_le_left ..)
    dsimp [candidateNorm] at hm
    omega
  · have hm : selectedNorm s ≤ candidateNorm s 1 1 := by
      dsimp [selectedNorm]
      exact Int.le_trans (Int.min_le_right ..) (Int.min_le_right ..)
    dsimp [candidateNorm] at hm
    omega

def minByNorm (p r : Int × Int) : Int × Int :=
  if eNorm p.1 p.2 ≤ eNorm r.1 r.2 then p else r

theorem norm_minByNorm (p r : Int × Int) :
    eNorm (minByNorm p r).1 (minByNorm p r).2 =
      min (eNorm p.1 p.2) (eNorm r.1 r.2) := by
  unfold minByNorm
  by_cases h : eNorm p.1 p.2 ≤ eNorm r.1 r.2
  · simp [h, Int.min_eq_left h]
  · have hr : eNorm r.1 r.2 ≤ eNorm p.1 p.2 := by omega
    simp [h, Int.min_eq_right hr]

def selectedCandidate (s : Int) : Int × Int :=
  minByNorm
    (minByNorm (candidate s (floorW s) (floorV s) 0 0)
      (candidate s (floorW s) (floorV s) 1 0))
    (minByNorm (candidate s (floorW s) (floorV s) 0 1)
      (candidate s (floorW s) (floorV s) 1 1))

theorem selected_candidate_norm (s : Int) :
    eNorm (selectedCandidate s).1 (selectedCandidate s).2 = selectedNorm s := by
  unfold selectedCandidate selectedNorm candidateNorm
  rw [norm_minByNorm, norm_minByNorm, norm_minByNorm]

theorem selected_candidate_bound (s : Int) :
    3*eNorm (selectedCandidate s).1 (selectedCandidate s).2 ≤ order := by
  rw [selected_candidate_norm]
  exact selected_norm_bound s

#print axioms local_cell_bound
#print axioms adjacent_corner_bound
#print axioms lower_triangle_cover
#print axioms four_corner_cover
#print axioms basis_det
#print axioms basis_gram
#print axioms candidate_coordinates
#print axioms candidate_norm_formula
#print axioms shifted_candidate_norm
#print axioms floor_division
#print axioms four_candidate_bound
#print axioms selected_norm_bound
#print axioms selected_candidate_norm
#print axioms selected_candidate_bound
