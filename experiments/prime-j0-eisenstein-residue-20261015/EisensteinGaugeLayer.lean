import Lean

namespace EisensteinGaugeLayer

-- This is the algebraic step used when one affine layer accumulates all
-- points in a cube-root class before applying the curve automorphism.
theorem rotate_list_sum {G : Type} [Add G] [Zero G]
    (rotate : G → G)
    (rotate_zero : rotate 0 = 0)
    (rotate_add : ∀ x y : G, rotate (x + y) = rotate x + rotate y)
    (points : List G) :
    rotate points.sum = (points.map rotate).sum := by
  induction points with
  | nil => simpa using rotate_zero
  | cons point rest ih =>
      simp only [List.sum_cons, List.map_cons]
      rw [rotate_add, ih]

theorem rotate_twice_list_sum {G : Type} [Add G] [Zero G]
    (rotate : G → G)
    (rotate_zero : rotate 0 = 0)
    (rotate_add : ∀ x y : G, rotate (x + y) = rotate x + rotate y)
    (points : List G) :
    rotate (rotate points.sum) =
      (points.map (fun point => rotate (rotate point))).sum := by
  rw [rotate_list_sum rotate rotate_zero rotate_add]
  rw [rotate_list_sum rotate rotate_zero rotate_add]
  simp only [List.map_map, Function.comp_def]

#print axioms rotate_list_sum
#print axioms rotate_twice_list_sum

end EisensteinGaugeLayer
