import Lean

namespace N83Normalized

variable {G : Type} [Add G]

-- F is the chosen Frobenius power and I its inverse on the point group.
theorem normalize_five
    (F I : G → G)
    (hI : ∀ x y, I (x + y) = I x + I y)
    (hleft : ∀ x, I (F x) = x)
    (s b c d e t : G)
    (h : F s + b + c + d + e = t) :
    s + I b + I c + I d + I e = I t := by
  have hmap : I (F s + b + c + d + e) =
      s + I b + I c + I d + I e := by
    simp only [hI, hleft]
  calc
    s + I b + I c + I d + I e = I (F s + b + c + d + e) := hmap.symm
    _ = I t := congrArg I h

theorem denormalize_five
    (F I : G → G)
    (hF : ∀ x y, F (x + y) = F x + F y)
    (hright : ∀ x, F (I x) = x)
    (s b c d e t : G)
    (h : s + I b + I c + I d + I e = I t) :
    F s + b + c + d + e = t := by
  have hmap : F (s + I b + I c + I d + I e) =
      F s + b + c + d + e := by
    simp only [hF, hright]
  calc
    F s + b + c + d + e = F (s + I b + I c + I d + I e) := hmap.symm
    _ = F (I t) := congrArg F h
    _ = t := hright t

-- The closure hypothesis states exactly what the complete Frobenius
-- factor base supplies to the four remaining leaves.
omit [Add G] in theorem normalize_preserves_four_memberships
    (I : G → G) (base : G → Prop)
    (closed : ∀ x, base x → base (I x))
    (b c d e : G)
    (hb : base b) (hc : base c) (hd : base d) (he : base e) :
    base (I b) ∧ base (I c) ∧ base (I d) ∧ base (I e) := by
  exact ⟨closed b hb, closed c hc, closed d hd, closed e he⟩

#print axioms normalize_five
#print axioms denormalize_five
#print axioms normalize_preserves_four_memberships

end N83Normalized
