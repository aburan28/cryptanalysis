/- The finite census supplies at most 8421 eligible nonzero rational
   x-lifts for every distinct two-bit translate of the rectangle plane.
   Two translations equal basis directions and reproduce the same plane.
   The finite-field census and orbit-cardinality bridge are independently
   replayed computational evidence outside this core Lean module. -/

namespace N83Rectangle14TwoBitTranslate

theorem distinct_translate_below_original (columns validLifts : Nat)
    (hOrbit : columns ≤ validLifts)
    (hScreen : validLifts ≤ 8421) : columns < 8532 :=
  Nat.lt_of_le_of_lt (Nat.le_trans hOrbit hScreen) (by decide)

#print axioms distinct_translate_below_original

end N83Rectangle14TwoBitTranslate
