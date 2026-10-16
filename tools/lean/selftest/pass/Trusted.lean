-- expect: ^PASS +1 thm +1 trusted
-- `native_decide`, listed in selftest/trusted-native.txt: expected `TRUST`, gate passes.
theorem triangle50 : (List.range 50).foldl (· + ·) 0 = 1225 := by native_decide
