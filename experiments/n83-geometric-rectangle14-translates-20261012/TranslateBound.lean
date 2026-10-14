/- The finite screen supplies at most 8347 rational lifts for each
   single high-coordinate translation. The orbit-cardinality bridge
   says a folded column requires at least one rational lift. -/

namespace N83Rectangle14Translate

theorem translated_base_below_original (columns validLifts : Nat)
    (hOrbit : columns ≤ validLifts)
    (hScreen : validLifts ≤ 8347) : columns < 8532 :=
  Nat.lt_of_le_of_lt (Nat.le_trans hOrbit hScreen) (by decide)

#print axioms translated_base_below_original

end N83Rectangle14Translate
