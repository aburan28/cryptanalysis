import Lean

namespace BatchInverse

theorem prefix_reverse_identity
    {α : Type} (mul : α → α → α) (one : α)
    (hassoc : ∀ a b c : α, mul (mul a b) c = mul a (mul b c))
    (hcomm : ∀ a b : α, mul a b = mul b a)
    (n : Nat) (factor pref reverse output : Nat → α)
    (hprefix : ∀ i < n, pref (i+1) = mul (pref i) (factor i))
    (hlast : mul (reverse n) (pref n) = one)
    (hback : ∀ i < n, reverse i = mul (reverse (i+1)) (factor i))
    (hout : ∀ i < n, output i = mul (reverse (i+1)) (pref i)) :
    ∀ i < n, mul (output i) (factor i) = one := by
  have hstate : ∀ j ≤ n, mul (reverse (n-j)) (pref (n-j)) = one := by
    intro j hj
    induction j with
    | zero => simpa using hlast
    | succ k ih =>
        have hk : k ≤ n := by omega
        have hi : n-(k+1) < n := by omega
        have hnext : n-k = (n-(k+1))+1 := by omega
        have hp := hprefix (n-(k+1)) hi
        have hb := hback (n-(k+1)) hi
        rw [hnext] at ih
        rw [hb]
        calc
          mul (mul (reverse ((n-(k+1))+1)) (factor (n-(k+1))))
              (pref (n-(k+1))) =
              mul (reverse ((n-(k+1))+1))
                (mul (factor (n-(k+1))) (pref (n-(k+1)))) :=
                  hassoc _ _ _
          _ = mul (reverse ((n-(k+1))+1))
                (mul (pref (n-(k+1))) (factor (n-(k+1)))) := by
                  rw [hcomm (factor (n-(k+1))) (pref (n-(k+1)))]
          _ = mul (reverse ((n-(k+1))+1))
                (pref ((n-(k+1))+1)) := by rw [← hp]
          _ = one := ih hk
  intro i hi
  have hnext := hstate (n-(i+1)) (by omega)
  have heq : n-(n-(i+1)) = i+1 := by omega
  rw [heq] at hnext
  rw [hout i hi]
  calc
    mul (mul (reverse (i+1)) (pref i)) (factor i) =
      mul (reverse (i+1)) (mul (pref i) (factor i)) := hassoc _ _ _
    _ = mul (reverse (i+1)) (pref (i+1)) := by rw [← hprefix i hi]
    _ = one := hnext

#print axioms prefix_reverse_identity
end BatchInverse
