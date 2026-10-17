import TerminalOrbit8011

namespace AdaptiveBucketFusion

open TerminalOrbit8011

-- A point assigned to either nonzero rotation bucket can instead be
-- rotated before addition to bucket zero. The sign bit is retained.
theorem fold_bucket_one (a b : Int) (sign : Nat) (hsign : sign < 2) :
    unitImage a b (2 + sign) =
      unitImage (omega a b).1 (omega a b).2 sign := by
  have h : sign = 0 ∨ sign = 1 := by omega
  rcases h with h | h <;> subst sign <;> simp [unitImage]

theorem fold_bucket_two (a b : Int) (sign : Nat) (hsign : sign < 2) :
    unitImage a b (4 + sign) =
      unitImage (omega (omega a b).1 (omega a b).2).1
        (omega (omega a b).1 (omega a b).2).2 sign := by
  have h : sign = 0 ∨ sign = 1 := by omega
  rcases h with h | h <;> subst sign <;> simp [unitImage]

theorem chosen_bucket_fusion (a b : Int) (fused sign : Nat)
    (hfused : fused = 1 ∨ fused = 2) (hsign : sign < 2) :
    unitImage a b (2*fused + sign) =
      if fused = 1 then unitImage (omega a b).1 (omega a b).2 sign
      else unitImage (omega (omega a b).1 (omega a b).2).1
        (omega (omega a b).1 (omega a b).2).2 sign := by
  rcases hfused with h | h
  · subst fused
    simpa using fold_bucket_one a b sign hsign
  · subst fused
    simpa using fold_bucket_two a b sign hsign

#print axioms fold_bucket_one
#print axioms fold_bucket_two
#print axioms chosen_bucket_fusion

end AdaptiveBucketFusion
