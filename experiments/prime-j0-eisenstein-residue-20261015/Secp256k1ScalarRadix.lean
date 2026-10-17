import CheckpointedRadixFamily

namespace Secp256k1ScalarRadix

open SparseTauRadix
open SparseRadixFamily

def order : Int :=
  115792089237316195423570985008687907852837564279074904382605163141518161494337

def lambdaTau : Int :=
  78074008874160198520644763525212887401909906723592317393988542598630163514320

/-- The subgroup eigenvalue used by the frozen scalar lattice satisfies
the polynomial of τ on the secp256k1 generator subgroup. -/
theorem lambda_root :
    (lambdaTau*lambdaTau-3*lambdaTau+3)%order=0 := by decide

def scalarValue (x : Pair) : Int := x.1+lambdaTau*x.2

theorem scalar_add (x y : Pair) :
    scalarValue (pairAdd x y) = scalarValue x+scalarValue y := by
  rcases x with ⟨u,v⟩
  rcases y with ⟨s,t⟩
  simp only [scalarValue,pairAdd,Int.mul_add]
  omega

/-- Applying τ to an integer pair multiplies its subgroup scalar by the
concrete eigenvalue modulo the secp256k1 subgroup order. -/
theorem tau_scalar_mod (x : Pair) :
    scalarValue (tauPair x)%order =
      (lambdaTau*scalarValue x)%order := by
  apply (Int.emod_eq_emod_iff_emod_sub_eq_zero).2
  have hdiff : scalarValue (tauPair x)-lambdaTau*scalarValue x =
      -x.2*(lambdaTau*lambdaTau-3*lambdaTau+3) := by
    rcases x with ⟨u,v⟩
    simp only [scalarValue,tauPair]
    simp only [Int.mul_add,Int.mul_sub,Int.mul_neg,Int.neg_mul,
               Int.add_mul,Int.sub_mul,Int.mul_assoc,Int.mul_comm,
               Int.mul_left_comm,Int.mul_one]
    grind
  rw [hdiff,Int.mul_emod,lambda_root]
  simp

def multiplier (t : Int) : Int := (t-1)+t*lambdaTau

/-- Every member of the sparse-radix family acts on the concrete subgroup
scalar by multiplication with its eigenvalue, modulo the subgroup order. -/
theorem family_scalar_mod (t : Int) (x : Pair) :
    scalarValue (familyPair t x)%order =
      (multiplier t*scalarValue x)%order := by
  apply (Int.emod_eq_emod_iff_emod_sub_eq_zero).2
  have hdiff : scalarValue (familyPair t x)-multiplier t*scalarValue x =
      -(t*x.2)*(lambdaTau*lambdaTau-3*lambdaTau+3) := by
    rcases x with ⟨u,v⟩
    simp only [scalarValue,multiplier,familyPair]
    simp only [Int.mul_add,Int.mul_sub,Int.mul_neg,Int.neg_mul,
               Int.add_mul,Int.sub_mul,Int.mul_assoc,Int.mul_comm,
               Int.mul_left_comm,Int.mul_one]
    grind
  rw [hdiff,Int.mul_emod,lambda_root]
  simp

theorem checkpoint_scalar_reconstruction (t : Int)
    (original terminal : Pair) (blocks : List (List Pair))
    (htrace : original = CheckpointedRadixFamily.evaluateBlocks t blocks terminal) :
    scalarValue original%order =
      scalarValue (CheckpointedRadixFamily.evaluate t blocks.flatten terminal)%order := by
  rw [htrace,CheckpointedRadixFamily.evaluate_blocks_flatten]

#print axioms lambda_root
#print axioms scalar_add
#print axioms tau_scalar_mod
#print axioms family_scalar_mod
#print axioms checkpoint_scalar_reconstruction

end Secp256k1ScalarRadix
