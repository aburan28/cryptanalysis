import NearestOrbit35533Secp

namespace NearestOrbit35533Generator
open SplitPrime12211Nearest NearestOrbit35533Complete
open NearestOrbit35533Lattice NearestOrbit35533Secp

theorem tau_scalar_from_generator {P : Type}
    (pointZero : P) (pointAdd : P → P → P) (pointNeg tauPoint : P → P)
    (eval : Int → P)
    (hzero : eval 0 = pointZero)
    (hadd : ∀ x y, eval (x+y) = pointAdd (eval x) (eval y))
    (hneg : ∀ x, eval (-x) = pointNeg (eval x))
    (htauZero : tauPoint pointZero = pointZero)
    (htauAdd : ∀ p q, tauPoint (pointAdd p q) =
      pointAdd (tauPoint p) (tauPoint q))
    (htauNeg : ∀ p, tauPoint (pointNeg p) = pointNeg (tauPoint p))
    (htauGenerator : tauPoint (eval 1) = eval tauEigen)
    (t : Int) : tauPoint (eval t) = eval (tauEigen*t) := by
  have hnat : ∀ n : Nat, tauPoint (eval (n : Int)) =
      eval (tauEigen*(n : Int)) := by
    intro n
    induction n with
    | zero =>
        simpa [hzero, htauZero]
    | succ n ih =>
        have hcast : ((n+1 : Nat) : Int) = (n : Int)+1 := by omega
        rw [hcast, Int.mul_add, Int.mul_one, hadd, hadd, htauAdd,
          ih, htauGenerator]
  cases t with
  | ofNat n => exact hnat n
  | negSucc n =>
      have hnegInt : Int.negSucc n = -((n+1 : Nat) : Int) := by omega
      rw [hnegInt, hneg, htauNeg, hnat (n+1)]
      have hmul : tauEigen * -((n+1 : Nat) : Int) =
          -(tauEigen * ((n+1 : Nat) : Int)) := by
        rw [Int.mul_neg]
      rw [hmul, hneg]

theorem selected_scalar_replay_from_generator {P : Type}
    (pointZero : P) (pointAdd : P → P → P)
    (pointNeg times190 tauPoint : P → P) (eval : Int → P)
    (hzero : eval 0 = pointZero)
    (hadd : ∀ x y, eval (x+y) = pointAdd (eval x) (eval y))
    (hneg : ∀ x, eval (-x) = pointNeg (eval x))
    (h190 : ∀ x, times190 (eval x) = eval (190*x))
    (htauZero : tauPoint pointZero = pointZero)
    (htauAdd : ∀ p q, tauPoint (pointAdd p q) =
      pointAdd (tauPoint p) (tauPoint q))
    (htauNeg : ∀ p, tauPoint (pointNeg p) = pointNeg (tauPoint p))
    (htauGenerator : tauPoint (eval 1) = eval tauEigen)
    (hmod : ∀ x y, (x-y) % order = 0 → eval x = eval y)
    (scalar : Int) :
    eval scalar = NearestOrbit35533Action.pointFold pointAdd
      (pointRadix pointAdd pointNeg times190 tauPoint)
      (fun z => eval (scalarValue z))
      (stateAt (selectedCandidate scalar))
      (digitAt (selectedCandidate scalar)) 0 16 := by
  exact NearestOrbit35533Secp.selected_scalar_point_replay
    pointAdd pointNeg times190 tauPoint eval hadd hneg h190
    (tau_scalar_from_generator pointZero pointAdd pointNeg tauPoint eval
      hzero hadd hneg htauZero htauAdd htauNeg htauGenerator)
    hmod scalar

#print axioms tau_scalar_from_generator
#print axioms selected_scalar_replay_from_generator
end NearestOrbit35533Generator
