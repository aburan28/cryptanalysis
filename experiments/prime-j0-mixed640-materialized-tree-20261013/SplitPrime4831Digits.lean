import Lean
import SplitPrime4831Bound

set_option maxRecDepth 100000
set_option maxHeartbeats 0

namespace SplitPrime4831Digits

def centered (x : Nat) : Nat := min (x % 4831) (4831 - x % 4831)

def canonicalSeed (r : Nat) : Nat :=
  min (centered r) (min (centered (4761*r)) (centered (69*r)))

def canonicalSeeds : List Nat :=
  (List.range 1565).filter (fun m => decide (0 < m ∧ canonicalSeed m = m))

theorem canonical_seed_count : canonicalSeeds.length = 805 := by decide
theorem canonical_seed_last : canonicalSeeds.getLast? = some 1564 := by decide

def digitPair (m u : Nat) : Int × Int :=
  match u with
  | 0 => ((m : Int), 0)
  | 1 => (-(m : Int), 0)
  | 2 => ((m : Int), -(m : Int))
  | 3 => (-(m : Int), (m : Int))
  | 4 => (-2*(m : Int), (m : Int))
  | 5 => (2*(m : Int), -(m : Int))
  | _ => (0, 0)

def residue (z : Int × Int) : Int := (z.1 + 71*z.2) % 4831

def valid (r : Nat) : Bool :=
  decide (canonicalSeed r ≤ 1564) &&
    (List.range 6).any (fun u =>
      decide (residue (digitPair (canonicalSeed r) u) = (r : Int)))

theorem coverage_bitmap : (List.range 4831).all valid = true := by decide

theorem canonical_cover (r : Nat) (hr : r < 4831) :
    canonicalSeed r ≤ 1564 ∧
    ∃ u : Nat, u < 6 ∧
      residue (digitPair (canonicalSeed r) u) = (r : Int) := by
  have h := (List.all_eq_true.mp coverage_bitmap) r (List.mem_range.mpr hr)
  simp only [valid, Bool.and_eq_true, decide_eq_true_eq] at h
  obtain ⟨hm, hu⟩ := h
  obtain ⟨u, huMem, huEq⟩ := List.any_eq_true.mp hu
  exact ⟨hm, u, List.mem_range.mp huMem, (decide_eq_true_eq.mp huEq)⟩

theorem digit_norm (m u : Nat) (hu : u < 6) :
    nrm (digitPair m u).1 (digitPair m u).2 = (m : Int)*(m : Int) := by
  have hcases : u = 0 ∨ u = 1 ∨ u = 2 ∨ u = 3 ∨ u = 4 ∨ u = 5 := by omega
  rcases hcases with h | h | h | h | h | h <;>
    subst u <;> simp [digitPair, nrm] <;> grind

theorem bounded_step (a b : Int) :
    ∃ m u : Nat, ∃ next : Int × Int,
      m = canonicalSeed (((a+71*b)%4831).toNat) ∧
      m ≤ 1564 ∧ u < 6 ∧
      nrm (digitPair m u).1 (digitPair m u).2 ≤ 1564*1564 ∧
      a = (digitPair m u).1 + 71*next.1 + 3*next.2 ∧
      b = (digitPair m u).2 - next.1 + 68*next.2 := by
  let residueWord : Int := (a+71*b)%4831
  let r : Nat := residueWord.toNat
  have hr0 : 0 ≤ residueWord := Int.emod_nonneg _ (by decide)
  have hrmax : residueWord < 4831 := Int.emod_lt _ (by decide)
  have hr : r < 4831 := by dsimp [r]; omega
  have hcast : (r : Int) = residueWord := by
    dsimp [r]
    rw [Int.ofNat_toNat]
    omega
  obtain ⟨hm, u, hu, hres⟩ := canonical_cover r hr
  let d := digitPair (canonicalSeed r) u
  have hres' : (d.1+71*d.2)%4831 = residueWord := by
    change (d.1+71*d.2)%4831 = (r : Int) at hres
    rw [hcast] at hres
    exact hres
  have hmod : ((a-d.1)+71*(b-d.2))%4831 = 0 := by
    dsimp [residueWord] at hres'
    omega
  obtain ⟨k, hk⟩ := Int.dvd_of_emod_eq_zero hmod
  have hq : 4831*k = (a-d.1)+71*(b-d.2) := by omega
  let next : Int × Int := (68*k-(b-d.2), k)
  refine ⟨canonicalSeed r, u, next, rfl, hm, hu, ?_, ?_, ?_⟩
  · rw [digit_norm _ _ hu]
    exact square_le_abs (canonicalSeed r : Int) 1564
      (by decide) (by omega) (by omega)
  · have hs := SplitPrime4831.recoding_step_identity a b d.1 d.2 k hq
    simpa [d, next] using hs.1
  · have hs := SplitPrime4831.recoding_step_identity a b d.1 d.2 k hq
    simpa [d, next] using hs.2

#print axioms coverage_bitmap
#print axioms canonical_seed_count
#print axioms canonical_seed_last
#print axioms canonical_cover
#print axioms digit_norm
#print axioms bounded_step

end SplitPrime4831Digits
