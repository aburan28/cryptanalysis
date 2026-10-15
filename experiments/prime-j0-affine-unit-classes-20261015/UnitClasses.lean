import Lean

namespace UnitClasses

variable {P : Type}

def foldPoints (zero : P) (add : P → P → P) : List P → P
  | [] => zero
  | point :: rest => add point (foldPoints zero add rest)

theorem hom_fold (zero : P) (add : P → P → P) (tau : P → P)
    (hzero : tau zero = zero)
    (hadd : ∀ a b, tau (add a b) = add (tau a) (tau b))
    (points : List P) :
    tau (foldPoints zero add points) =
      foldPoints zero add (points.map tau) := by
  induction points with
  | nil => simp [foldPoints, hzero]
  | cons point rest ih => simp [foldPoints, hadd, ih]

theorem three_class_delayed
    (zero : P) (add : P → P → P) (tau : P → P)
    (hzero : tau zero = zero)
    (hadd : ∀ a b, tau (add a b) = add (tau a) (tau b))
    (class0 class1 class2 : List P) :
    add (add (foldPoints zero add class0)
             (tau (foldPoints zero add class1)))
        (tau (tau (foldPoints zero add class2))) =
    add (add (foldPoints zero add class0)
             (foldPoints zero add (class1.map tau)))
        (foldPoints zero add (class2.map (fun point => tau (tau point)))) := by
  have hzero2 : (fun point => tau (tau point)) zero = zero := by
    simp [hzero]
  have hadd2 : ∀ a b, tau (tau (add a b)) =
      add (tau (tau a)) (tau (tau b)) := by
    intro a b
    simp [hadd]
  rw [hom_fold zero add tau hzero hadd class1]
  rw [hom_fold zero add (fun point => tau (tau point)) hzero2 hadd2 class2]

#print axioms hom_fold
#print axioms three_class_delayed
end UnitClasses
