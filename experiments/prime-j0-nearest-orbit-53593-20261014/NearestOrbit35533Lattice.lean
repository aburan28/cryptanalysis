import NearestOrbit35533Action

namespace NearestOrbit35533Lattice
open SplitPrime12211Nearest SplitPrimeRadix NearestOrbit35533Complete

def tauEigen : Int :=
  78074008874160198520644763525212887401909906723592317393988542598630163514320

theorem tau_polynomial :
    (tauEigen * tauEigen - 3 * tauEigen + 3) % order = 0 := by decide

theorem basis_scalar_W :
    W.1 + tauEigen * W.2 =
      order * (-248072105426244568656964927078881993893) := by decide

theorem basis_scalar_V :
    V.1 + tauEigen * V.2 =
      order * 204580311103670717363538375293302872898 := by decide

def scalarValue (z : Coeff) : Int := z.1 + tauEigen * z.2

theorem candidate_scalar (s fw fv i j : Int) :
    scalarValue (candidate s fw fv i j) =
      s - order * ((fw+i) * (-248072105426244568656964927078881993893)
        + (fv+j) * 204580311103670717363538375293302872898) := by
  dsimp [scalarValue, candidate, tauEigen, order, W, V]
  omega

theorem minByNorm_scalar {s : Int} {p q : Coeff}
    (hp : (scalarValue p - s) % order = 0)
    (hq : (scalarValue q - s) % order = 0) :
    (scalarValue (minByNorm p q) - s) % order = 0 := by
  by_cases h : eNorm p.1 p.2 ≤ eNorm q.1 q.2
  · simpa [minByNorm, h] using hp
  · simpa [minByNorm, h] using hq

theorem candidate_congruent (s fw fv i j : Int) :
    (scalarValue (candidate s fw fv i j) - s) % order = 0 := by
  rw [candidate_scalar]
  have heq :
      s - order * ((fw+i) * (-248072105426244568656964927078881993893)
        + (fv+j) * 204580311103670717363538375293302872898) - s =
      -(order * ((fw+i) * (-248072105426244568656964927078881993893)
        + (fv+j) * 204580311103670717363538375293302872898)) := by omega
  rw [heq]
  rw [← Int.mul_neg]
  exact Int.mul_emod_right _ _

theorem selected_candidate_congruent (s : Int) :
    (scalarValue (selectedCandidate s) - s) % order = 0 := by
  unfold selectedCandidate
  apply minByNorm_scalar
  · apply minByNorm_scalar <;> exact candidate_congruent _ _ _ _ _
  · apply minByNorm_scalar <;> exact candidate_congruent _ _ _ _ _

theorem radix_scalar_difference (x : Coeff) :
    scalarValue (NearestOrbit35533.radixMul x) -
      (190-tauEigen) * scalarValue x =
      (tauEigen*tauEigen - 3*tauEigen + 3) * x.2 := by
  rcases x with ⟨a, b⟩
  dsimp [scalarValue, NearestOrbit35533.radixMul, tauEigen]
  omega

theorem radix_scalar_congruent (x : Coeff) :
    (scalarValue (NearestOrbit35533.radixMul x) -
      (190-tauEigen) * scalarValue x) % order = 0 := by
  rw [radix_scalar_difference]
  obtain ⟨k, hk⟩ := Int.dvd_of_emod_eq_zero tau_polynomial
  rw [hk, Int.mul_assoc]
  exact Int.mul_emod_right _ _

theorem selected_scalar_action_replay {P : Type}
    (pointAdd : P → P → P) (radixPoint : P → P)
    (eval : Int → P)
    (hadd : ∀ x y, eval (x+y) = pointAdd (eval x) (eval y))
    (hmod : ∀ x y, (x-y) % order = 0 → eval x = eval y)
    (hradix : ∀ x,
      eval (scalarValue (NearestOrbit35533.radixMul x)) =
        radixPoint (eval (scalarValue x)))
    (scalar : Int) :
    eval scalar = NearestOrbit35533Action.pointFold pointAdd radixPoint
      (fun z => eval (scalarValue z))
      (stateAt (selectedCandidate scalar))
      (digitAt (selectedCandidate scalar)) 0 16 := by
  have hact : ∀ x y,
      eval (scalarValue (add x y)) =
        pointAdd (eval (scalarValue x)) (eval (scalarValue y)) := by
    intro x y
    have hs : scalarValue (add x y) = scalarValue x + scalarValue y := by
      dsimp [scalarValue, add, tauEigen]
      omega
    rw [hs, hadd]
  apply NearestOrbit35533Action.selected_scalar_action_replay pointAdd radixPoint
    (fun z => eval (scalarValue z)) eval hact hradix scalar
  exact hmod _ _ (selected_candidate_congruent scalar)

theorem selected_scalar_point_replay {P : Type}
    (pointAdd : P → P → P) (radixPoint : P → P)
    (eval : Int → P)
    (hadd : ∀ x y, eval (x+y) = pointAdd (eval x) (eval y))
    (hmod : ∀ x y, (x-y) % order = 0 → eval x = eval y)
    (hpointRadix : ∀ t, radixPoint (eval t) =
      eval ((190-tauEigen)*t))
    (scalar : Int) :
    eval scalar = NearestOrbit35533Action.pointFold pointAdd radixPoint
      (fun z => eval (scalarValue z))
      (stateAt (selectedCandidate scalar))
      (digitAt (selectedCandidate scalar)) 0 16 := by
  apply selected_scalar_action_replay pointAdd radixPoint eval hadd hmod _ scalar
  intro x
  rw [hpointRadix]
  exact hmod _ _ (radix_scalar_congruent x)

#print axioms tau_polynomial
#print axioms selected_candidate_congruent
#print axioms selected_scalar_action_replay
#print axioms selected_scalar_point_replay
end NearestOrbit35533Lattice
