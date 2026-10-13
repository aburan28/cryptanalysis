/- A width-11 affine translation by a vector already in the width-11
   subspace enumerates the same 2^11 seed vectors. -/

namespace N83Width11Coset

theorem xor_translate_surjective (offset target : BitVec 11) :
    ∃ seed : BitVec 11, seed ^^^ offset = target := by
  refine ⟨target ^^^ offset, ?_⟩
  simp [BitVec.xor_assoc]

#print axioms xor_translate_surjective

end N83Width11Coset
