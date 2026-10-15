import Lean

namespace AffineLayer

variable {β α : Type}

def layer (pair : β → β → β) : List β → List β
  | a :: b :: rest => pair a b :: layer pair rest
  | rest => rest

def interpretedSum (decode : β → α) (add : α → α → α) (zero : α) :
    List β → α :=
  List.foldr (fun point total => add (decode point) total) zero

theorem layer_preserves_sum
    (pair : β → β → β) (decode : β → α) (add : α → α → α)
    (zero : α)
    (hassoc : ∀ a b c : α, add (add a b) c = add a (add b c))
    (hpair : ∀ a b : β, decode (pair a b) = add (decode a) (decode b)) :
    ∀ points : List β,
      interpretedSum decode add zero (layer pair points) =
      interpretedSum decode add zero points
  | [] => by simp [layer, interpretedSum]
  | [a] => by simp [layer, interpretedSum]
  | a :: b :: rest => by
      simp only [layer, interpretedSum, List.foldr_cons]
      have ih := layer_preserves_sum pair decode add zero hassoc hpair rest
      unfold interpretedSum at ih
      rw [hpair, ih]
      exact hassoc (decode a) (decode b)
        (List.foldr (fun point total => add (decode point) total) zero rest)

def layers (pair : β → β → β) : Nat → List β → List β
  | 0, points => points
  | n+1, points => layers pair n (layer pair points)

theorem layers_preserve_sum
    (pair : β → β → β) (decode : β → α) (add : α → α → α)
    (zero : α)
    (hassoc : ∀ a b c : α, add (add a b) c = add a (add b c))
    (hpair : ∀ a b : β, decode (pair a b) = add (decode a) (decode b))
    (n : Nat) (points : List β) :
    interpretedSum decode add zero (layers pair n points) =
    interpretedSum decode add zero points := by
  induction n generalizing points with
  | zero => rfl
  | succ n ih =>
      simp [layers, ih, layer_preserves_sum pair decode add zero hassoc hpair]

#print axioms layer_preserves_sum
#print axioms layers_preserve_sum
end AffineLayer
