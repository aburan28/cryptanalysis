import Lean
import NearestOrbit35533Bound

namespace NearestOrbit35533Selector
open SplitPrime12211Nearest

def candidate (lift b : Int) : Int × Int := (lift - 190*b, b)

def candidates (r : Nat) : List (Int × Int) := Id.run do
  let x : Int := r
  let y : Int := x - 35533
  let bx := (377*x + 35533) / 71066
  let by0 : Int := (377*y + 35533) / 71066
  return [candidate x (bx-1), candidate x bx, candidate x (bx+1),
          candidate y (by0-1), candidate y by0, candidate y (by0+1)]

def boundCheck (r : Nat) : Bool :=
  (candidates r).any (fun p => nrm p.1 p.2 ≤ 11719)

def pick (p q : Int × Int) : Int × Int :=
  if nrm p.1 p.2 ≤ nrm q.1 q.2 then p else q

def selectedDigit (r : Nat) : Int × Int :=
  match candidates r with
  | [] => (0, 0)
  | p :: ps => ps.foldl pick p

def selectedCheck (r : Nat) : Bool :=
  let d := selectedDigit r
  decide (nrm d.1 d.2 ≤ 11719) &&
  decide ((d.1 + 190*d.2 - (r : Int)) % 35533 = 0)

private theorem pick_le_left (p q : Int × Int) :
    nrm (pick p q).1 (pick p q).2 ≤ nrm p.1 p.2 := by
  by_cases h : nrm p.1 p.2 ≤ nrm q.1 q.2
  · simp [pick, h]
  · simp [pick, h]
    omega

private theorem pick_le_right (p q : Int × Int) :
    nrm (pick p q).1 (pick p q).2 ≤ nrm q.1 q.2 := by
  by_cases h : nrm p.1 p.2 ≤ nrm q.1 q.2
  · simp [pick, h]
  · simp [pick, h]

private theorem fold_le_init (p : Int × Int) (ps : List (Int × Int)) :
    nrm (ps.foldl pick p).1 (ps.foldl pick p).2 ≤ nrm p.1 p.2 := by
  induction ps generalizing p with
  | nil => simp
  | cons q qs ih =>
      simp only [List.foldl_cons]
      calc
        nrm (qs.foldl pick (pick p q)).1 (qs.foldl pick (pick p q)).2 ≤ nrm (pick p q).1 (pick p q).2 := ih (pick p q)
        _ ≤ nrm p.1 p.2 := pick_le_left p q

private theorem fold_le_member (p q : Int × Int) (ps : List (Int × Int))
    (hq : q ∈ ps) :
    nrm (ps.foldl pick p).1 (ps.foldl pick p).2 ≤ nrm q.1 q.2 := by
  induction ps generalizing p with
  | nil => simp at hq
  | cons x xs ih =>
      simp only [List.foldl_cons]
      rcases List.mem_cons.mp hq with heq | htail
      · subst q
        calc
          nrm (xs.foldl pick (pick p x)).1 (xs.foldl pick (pick p x)).2 ≤ nrm (pick p x).1 (pick p x).2 := fold_le_init (pick p x) xs
          _ ≤ nrm x.1 x.2 := pick_le_right p x
      · exact ih (pick p x) htail

theorem selected_le_candidate (r : Nat) (q : Int × Int)
    (hq : q ∈ candidates r) :
    nrm (selectedDigit r).1 (selectedDigit r).2 ≤ nrm q.1 q.2 := by
  unfold selectedDigit
  cases hcs : candidates r with
  | nil => simp [hcs] at hq
  | cons p ps =>
      simp only [hcs]
      rcases List.mem_cons.mp (hcs ▸ hq) with heq | htail
      · subst q
        exact fold_le_init p ps
      · exact fold_le_member p q ps htail

theorem candidate_congruent (r : Nat) (q : Int × Int)
    (hq : q ∈ candidates r) :
    (q.1 + 190*q.2 - (r : Int)) % 35533 = 0 := by
  simp [candidates] at hq
  rcases hq with h | h | h | h | h | h <;> simp_all [candidate] <;> omega

theorem selected_congruent (r : Nat) :
    ((selectedDigit r).1 + 190*(selectedDigit r).2 - (r : Int)) % 35533 = 0 := by
  unfold selectedDigit
  cases hcs : candidates r with
  | nil => simp [candidates] at hcs
  | cons p ps =>
      have hall : ∀ q ∈ p :: ps,
          (q.1 + 190*q.2 - (r : Int)) % 35533 = 0 := by
        intro q hq
        exact candidate_congruent r q (hcs ▸ hq)
      have hfold : ∀ init : Int × Int,
          (init.1 + 190*init.2 - (r : Int)) % 35533 = 0 →
          ∀ rest : List (Int × Int),
            (∀ q ∈ rest, (q.1 + 190*q.2 - (r : Int)) % 35533 = 0) →
            (((rest.foldl pick init).1 + 190*(rest.foldl pick init).2 - (r : Int)) % 35533 = 0) := by
        intro init hinit rest hrest
        induction rest generalizing init with
        | nil => simpa using hinit
        | cons q qs ih =>
            simp only [List.foldl_cons]
            have hpick : (pick init q).1 + 190*(pick init q).2 =
                (if nrm init.1 init.2 ≤ nrm q.1 q.2 then
                  init.1 + 190*init.2 else q.1 + 190*q.2) := by
              by_cases h : nrm init.1 init.2 ≤ nrm q.1 q.2 <;> simp [pick, h]
            have hq := hrest q (by simp)
            have hi : ((pick init q).1 + 190*(pick init q).2 - (r : Int)) % 35533 = 0 := by
              rw [hpick]
              by_cases h : nrm init.1 init.2 ≤ nrm q.1 q.2
              · simp only [if_pos h]
                exact hinit
              · simp only [if_neg h]
                exact hq
            exact ih (pick init q) hi (by
              intro x hx
              exact hrest x (by simp [hx]))
      simpa [hcs] using hfold p (hall p (by simp)) ps
        (by intro q hq; exact hall q (by simp [hq]))


end NearestOrbit35533Selector
