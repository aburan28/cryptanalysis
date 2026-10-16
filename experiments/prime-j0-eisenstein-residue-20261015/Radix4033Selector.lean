import Radix4033Bounds

namespace Radix4033Selector

open HornerRadix AlternateRadix Radix4033 Radix4033Bounds

/-- The exact five-by-five lift and coordinate window in the native selector. -/
def candidate (r : Int) (liftIndex offsetIndex : Nat) : Pair := Id.run do
  let lift := r + ((liftIndex : Int)-2)*4033
  let center := (127*lift) / 8066
  let b := center + (offsetIndex : Int)-2
  return (lift-65*b,b)

def candidates (r : Int) : List Pair :=
  (List.range 5).flatMap fun i =>
    (List.range 5).map fun j => candidate r i j

theorem rounded_in_center_window (r : Int) :
    let center := (127*r) / 8066
    nearestB r = center ∨ nearestB r = center+1 := by
  dsimp [nearestB]
  omega

/-- The rounded candidate used in the norm proof is one of the native loop's
25 candidates, at lift index two and offset index two or three. -/
theorem rounded_candidate_mem (r : Int) :
    (r-65*nearestB r,nearestB r) ∈ candidates r := by
  have hwindow := rounded_in_center_window r
  unfold candidates
  apply List.mem_flatMap.mpr
  refine ⟨2, by decide, ?_⟩
  apply List.mem_map.mpr
  rcases hwindow with hzero | hone
  · refine ⟨2, by decide, ?_⟩
    simp [candidate, hzero]
  · refine ⟨3, by decide, ?_⟩
    simp [candidate, hone]
    omega

/-- Retain a candidate when it lowers the primary norm score. The native
selector also uses deterministic tie breakers, which leave this norm result
unchanged. -/
def choose (best next : Pair) : Pair :=
  if pairNorm next.1 next.2 < pairNorm best.1 best.2 then next else best

theorem choose_le_best (best next : Pair) :
    pairNorm (choose best next).1 (choose best next).2 ≤
      pairNorm best.1 best.2 := by
  by_cases h : pairNorm next.1 next.2 < pairNorm best.1 best.2
  · simp [choose, h]
    omega
  · simp [choose, h]

theorem choose_le_next (best next : Pair) :
    pairNorm (choose best next).1 (choose best next).2 ≤
      pairNorm next.1 next.2 := by
  by_cases h : pairNorm next.1 next.2 < pairNorm best.1 best.2
  · simp [choose, h]
  · simp [choose, h]
    omega

theorem foldl_choose_le_seed (xs : List Pair) (seed : Pair) :
    pairNorm (xs.foldl choose seed).1 (xs.foldl choose seed).2 ≤
      pairNorm seed.1 seed.2 := by
  induction xs generalizing seed with
  | nil => simp
  | cons x xs ih =>
    simp only [List.foldl_cons]
    exact Int.le_trans (ih (choose seed x)) (choose_le_best seed x)

theorem foldl_choose_le_member (xs : List Pair) (seed x : Pair)
    (h : x ∈ xs) :
    pairNorm (xs.foldl choose seed).1 (xs.foldl choose seed).2 ≤
      pairNorm x.1 x.2 := by
  induction xs generalizing seed with
  | nil => simp at h
  | cons y ys ih =>
    simp only [List.mem_cons] at h
    simp only [List.foldl_cons]
    rcases h with hxy | htail
    · subst x
      exact Int.le_trans (foldl_choose_le_seed ys (choose seed y))
        (choose_le_next seed y)
    · exact ih (choose seed y) htail

def selectedPair (r : Int) : Pair :=
  (candidates r).foldl choose (r,0)

def congruent (r : Int) (x : Pair) : Prop :=
  ∃ k : Int, x.1+65*x.2 = r+4033*k

theorem candidate_congruent (r : Int) (i j : Nat) :
    congruent r (candidate r i j) := by
  refine ⟨(i : Int)-2, ?_⟩
  simp [candidate]
  omega

theorem candidates_congruent (r : Int) (x : Pair)
    (h : x ∈ candidates r) : congruent r x := by
  unfold candidates at h
  obtain ⟨i, _, hi⟩ := List.mem_flatMap.mp h
  obtain ⟨j, _, hj⟩ := List.mem_map.mp hi
  subst x
  exact candidate_congruent r i j

theorem choose_preserves_congruence (r : Int) (best next : Pair)
    (hbest : congruent r best) (hnext : congruent r next) :
    congruent r (choose best next) := by
  by_cases h : pairNorm next.1 next.2 < pairNorm best.1 best.2
  · simpa [choose, h] using hnext
  · simpa [choose, h] using hbest

theorem foldl_choose_congruent (r : Int) (xs : List Pair) (seed : Pair)
    (hseed : congruent r seed)
    (hall : ∀ x, x ∈ xs → congruent r x) :
    congruent r (xs.foldl choose seed) := by
  induction xs generalizing seed with
  | nil => simpa using hseed
  | cons x xs ih =>
    simp only [List.foldl_cons]
    have hx : congruent r x := hall x (by simp)
    have hrest : ∀ y, y ∈ xs → congruent r y := by
      intro y hy
      exact hall y (by simp [hy])
    exact ih (choose seed x)
      (choose_preserves_congruence r seed x hseed hx) hrest

theorem selected_pair_congruent (r : Int) :
    congruent r (selectedPair r) := by
  apply foldl_choose_congruent r (candidates r) (r,0)
  · exact ⟨0, by simp⟩
  · intro x hx
    exact candidates_congruent r x hx

/-- Once the centered residue of the current lattice state is known, the
finite selector supplies a digit admitting an exact next quotient. -/
theorem selected_exact_quotient (r a b m : Int)
    (hresidue : a+65*b = r+4033*m) :
    ∃ next : Pair,
      mulRadix next =
        (a-(selectedPair r).1,b-(selectedPair r).2) := by
  obtain ⟨n,hn⟩ := selected_pair_congruent r
  let k := m-n
  have hshift :
      (a-(selectedPair r).1)+65*(b-(selectedPair r).2) = 4033*k := by
    dsimp [k]
    omega
  exact ⟨(62*k-(b-(selectedPair r).2),k),
    exact_quotient (a-(selectedPair r).1)
      (b-(selectedPair r).2) k hshift⟩

/-- The actual finite search window contains a uniformly bounded digit. -/
theorem selected_norm_below_radix (r : Int)
    (hr : 0 ≤ r ∧ r ≤ 2016) :
    pairNorm (selectedPair r).1 (selectedPair r).2 < 4033 := by
  have hmember := rounded_candidate_mem r
  have hselect := foldl_choose_le_member (candidates r) (r,0)
    (r-65*nearestB r,nearestB r) hmember
  exact selected_digit_norm_below_radix r
    (selectedPair r).1 (selectedPair r).2 hr hselect

def negPair (x : Pair) : Pair := (-x.1,-x.2)

theorem neg_pair_norm (x : Pair) :
    pairNorm (negPair x).1 (negPair x).2 = pairNorm x.1 x.2 := by
  simp [negPair,pairNorm,Int.neg_mul,Int.mul_neg]

/-- The native high-residue branch uses the negative of the low-residue
candidate, covering all 4033 quotient classes. -/
def signedSelected (residue : Int) : Pair :=
  if residue ≤ 2016 then selectedPair residue
  else negPair (selectedPair (4033-residue))

theorem signed_selected_norm (residue : Int)
    (hr : 0 ≤ residue ∧ residue < 4033) :
    pairNorm (signedSelected residue).1 (signedSelected residue).2 < 4033 := by
  by_cases hlow : residue ≤ 2016
  · simpa [signedSelected, hlow] using
      selected_norm_below_radix residue ⟨hr.1,hlow⟩
  · have hcenter : 0 ≤ 4033-residue ∧ 4033-residue ≤ 2016 := by omega
    simpa [signedSelected, hlow, neg_pair_norm] using
      selected_norm_below_radix (4033-residue) hcenter

theorem signed_selected_congruent (residue : Int)
    : congruent residue (signedSelected residue) := by
  by_cases hlow : residue ≤ 2016
  · simpa [signedSelected, hlow] using selected_pair_congruent residue
  · obtain ⟨n,hn⟩ := selected_pair_congruent (4033-residue)
    refine ⟨-n-1, ?_⟩
    simp [signedSelected, hlow, negPair]
    omega

theorem signed_exact_quotient (residue a b m : Int)
    (hresidue : a+65*b = residue+4033*m) :
    ∃ next : Pair,
      mulRadix next =
        (a-(signedSelected residue).1,b-(signedSelected residue).2) := by
  obtain ⟨n,hn⟩ := signed_selected_congruent residue
  let k := m-n
  have hshift :
      (a-(signedSelected residue).1)+65*(b-(signedSelected residue).2) = 4033*k := by
    dsimp [k]
    omega
  exact ⟨(62*k-(b-(signedSelected residue).2),k),
    exact_quotient (a-(signedSelected residue).1)
      (b-(signedSelected residue).2) k hshift⟩

/-- The finite selector model has a bounded digit and an exact next quotient
for every integer-pair state, with the residue computed modulo 4033. -/
theorem total_selected_step (a b : Int) :
    let residue := (a+65*b) % 4033
    pairNorm (signedSelected residue).1 (signedSelected residue).2 < 4033 ∧
      ∃ next : Pair,
        mulRadix next =
          (a-(signedSelected residue).1,b-(signedSelected residue).2) := by
  let residue := (a+65*b) % 4033
  have hr : 0 ≤ residue ∧ residue < 4033 := by
    dsimp [residue]
    omega
  have hresidue :
      a+65*b = residue+4033*((a+65*b)/4033) := by
    dsimp [residue]
    omega
  exact ⟨signed_selected_norm residue hr,
    signed_exact_quotient residue a b ((a+65*b)/4033) hresidue⟩

#print axioms rounded_in_center_window
#print axioms rounded_candidate_mem
#print axioms choose_le_best
#print axioms choose_le_next
#print axioms foldl_choose_le_member
#print axioms selected_norm_below_radix
#print axioms selected_pair_congruent
#print axioms selected_exact_quotient
#print axioms signed_selected_norm
#print axioms signed_selected_congruent
#print axioms signed_exact_quotient
#print axioms total_selected_step

end Radix4033Selector
