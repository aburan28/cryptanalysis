import NearestOrbit35533Complete
import NearestOrbit35533

namespace NearestOrbit35533Action
open SplitPrimeRadix NearestOrbit35533Complete SplitPrime12211Nearest

def pointFold {P : Type} (pointAdd : P → P → P) (radixPoint : P → P)
    (act : Coeff → P) (state digit : Nat → Coeff) : Nat → Nat → P
  | i, 0 => act (state i)
  | i, n + 1 => pointAdd (act (digit i))
      (radixPoint (pointFold pointAdd radixPoint act state digit (i+1) n))

theorem action_replay {P : Type} (pointAdd : P → P → P)
    (radixPoint : P → P) (act : Coeff → P)
    (hadd : ∀ x y, act (add x y) = pointAdd (act x) (act y))
    (hradix : ∀ x, act (NearestOrbit35533.radixMul x) = radixPoint (act x))
    (state digit : Nat → Coeff)
    (hstep : ∀ i, state i = add (digit i)
      (NearestOrbit35533.radixMul (state (i+1))))
    (i n : Nat) :
    act (state i) = pointFold pointAdd radixPoint act state digit i n := by
  induction n generalizing i with
  | zero => rfl
  | succ n ih =>
      calc
        act (state i) = act (add (digit i)
          (NearestOrbit35533.radixMul (state (i+1)))) :=
            congrArg act (hstep i)
        _ = pointAdd (act (digit i)) (radixPoint (act (state (i+1)))) := by
          rw [hadd, hradix]
        _ = pointFold pointAdd radixPoint act state digit i (n+1) := by
          rw [ih (i+1)]
          rfl

theorem selected_step (start : Coeff) (i : Nat) :
    stateAt start i = add (digitAt start i)
      (NearestOrbit35533.radixMul (stateAt start (i+1))) := by
  apply Prod.ext
  · have h := (trajectory_step start i).2.1
    dsimp [add, NearestOrbit35533.radixMul]
    omega
  · have h := (trajectory_step start i).2.2
    dsimp [add, NearestOrbit35533.radixMul]
    omega

theorem selected_scalar_action_replay {P : Type}
    (pointAdd : P → P → P) (radixPoint : P → P)
    (act : Coeff → P) (scalarMul : Int → P)
    (hadd : ∀ x y, act (add x y) = pointAdd (act x) (act y))
    (hradix : ∀ x, act (NearestOrbit35533.radixMul x) = radixPoint (act x))
    (scalar : Int)
    (hscalar : act (selectedCandidate scalar) = scalarMul scalar) :
    scalarMul scalar = pointFold pointAdd radixPoint act
      (stateAt (selectedCandidate scalar))
      (digitAt (selectedCandidate scalar)) 0 16 := by
  rw [← hscalar]
  exact action_replay pointAdd radixPoint act hadd hradix
    (stateAt (selectedCandidate scalar))
    (digitAt (selectedCandidate scalar))
    (selected_step (selectedCandidate scalar)) 0 16

#print axioms action_replay
#print axioms selected_step
#print axioms selected_scalar_action_replay
end NearestOrbit35533Action
