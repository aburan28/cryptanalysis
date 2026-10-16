-- expect: FAIL +unlisted +non-standard axioms: \[unlisted\._native\.native_decide
-- `native_decide` not listed in the trust manifest.
theorem unlisted : (List.range 40).foldl (· + ·) 0 = 780 := by native_decide
