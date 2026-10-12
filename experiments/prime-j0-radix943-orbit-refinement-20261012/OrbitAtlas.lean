import DigitCover

namespace PrimeJ0Radix943OrbitAtlas

open PrimeJ0Radix943Termination
open PrimeJ0Radix943DigitCover

def negPair (z : Pair) : Pair := (-z.1, -z.2)

-- This is the integer action used by unit_orbit_windows.rs.
def omegaUnit (z : Pair) : Pair := (z.1 + 3*z.2, -z.1 - 2*z.2)

def unitImage (code : Fin 6) (z : Pair) : Pair :=
  if code.val = 0 then z else
  if code.val = 1 then negPair z else
  if code.val = 2 then omegaUnit z else
  if code.val = 3 then negPair (omegaUnit z) else
  if code.val = 4 then omegaUnit (omegaUnit z) else
  negPair (omegaUnit (omegaUnit z))

private theorem code_cases (code : Fin 6) :
    code.val = 0 ∨ code.val = 1 ∨ code.val = 2 ∨
    code.val = 3 ∨ code.val = 4 ∨ code.val = 5 := by
  have h := code.isLt
  omega

theorem omega_cubed (z : Pair) :
    omegaUnit (omegaUnit (omegaUnit z)) = z := by
  rcases z with ⟨a,b⟩
  simp only [omegaUnit]
  apply Prod.ext <;> omega

theorem omega_norm (z : Pair) : norm (omegaUnit z) = norm z := by
  rcases z with ⟨a,b⟩
  simp only [omegaUnit, norm]
  grind +ring

theorem neg_norm (z : Pair) : norm (negPair z) = norm z := by
  rcases z with ⟨a,b⟩
  simp only [negPair, norm]
  grind +ring

theorem unit_image_norm (code : Fin 6) (z : Pair) :
    norm (unitImage code z) = norm z := by
  rcases code_cases code with h | h | h | h | h | h <;>
    simp [unitImage, h, neg_norm, omega_norm]

theorem unit_image_add (code : Fin 6) (x y : Pair) :
    unitImage code (add x y) = add (unitImage code x) (unitImage code y) := by
  rcases code_cases code with h | h | h | h | h | h <;>
    rcases x with ⟨a,b⟩ <;> rcases y with ⟨c,d⟩ <;>
    simp [unitImage, h, omegaUnit, negPair, add] <;>
    constructor <;> omega

theorem unit_image_scale (code : Fin 6) (k : Int) (z : Pair) :
    unitImage code (scale k z) = scale k (unitImage code z) := by
  rcases code_cases code with h | h | h | h | h | h <;>
    rcases z with ⟨a,b⟩ <;>
    simp [unitImage, h, omegaUnit, negPair, scale] <;>
    constructor <;> grind +ring

theorem unit_image_digit_bound (code : Fin 6) (c : Pair) :
    3 * norm (unitImage code (nearestStep c).1) ≤ (943 : Int)^2 := by
  rw [unit_image_norm]
  exact nearest_digit_bound c

-- The atlas code lookup supplies hResidue: the queried pair differs from
-- the coded image of its canonical residue by a multiple of 943.
theorem orbit_digit_step (code : Fin 6) (canonical query offset : Pair)
    (hResidue : query = add (unitImage code canonical) (scale 943 offset)) :
    ∃ quotient : Pair,
      query = add (unitImage code (nearestStep canonical).1) (scale 943 quotient) ∧
      3 * norm (unitImage code (nearestStep canonical).1) ≤ (943 : Int)^2 := by
  let digit := (nearestStep canonical).1
  let stepQuotient := (nearestStep canonical).2
  have hStep : canonical = add digit (scale 943 stepQuotient) := by
    exact nearest_step_equation canonical
  have hTransport := congrArg (unitImage code) hStep
  rw [unit_image_add, unit_image_scale] at hTransport
  refine ⟨add (unitImage code stepQuotient) offset, ?_, unit_image_digit_bound code canonical⟩
  rw [hTransport] at hResidue
  cases hD : unitImage code digit with
  | mk a b =>
  cases hQ : unitImage code stepQuotient with
  | mk c d =>
  rcases offset with ⟨e,f⟩
  rcases query with ⟨g,h⟩
  simp only [hD, hQ, add, scale, Prod.mk.injEq] at hResidue ⊢
  rcases hResidue with ⟨h₁,h₂⟩
  constructor <;> omega

-- This is the exact observable contract of the atlas's residue-code array.
-- It does not require the transported digit to be the global tie-breaking
-- minimum for the query residue.
theorem orbit_digit_from_residue (code : Fin 6) (canonical query : Pair)
    (hFirst : query.1 % 943 = (unitImage code canonical).1 % 943)
    (hSecond : query.2 % 943 = (unitImage code canonical).2 % 943) :
    ∃ quotient : Pair,
      query = add (unitImage code (nearestStep canonical).1) (scale 943 quotient) ∧
      3 * norm (unitImage code (nearestStep canonical).1) ≤ (943 : Int)^2 := by
  let image := unitImage code canonical
  let offset : Pair :=
    (query.1 / 943 - image.1 / 943, query.2 / 943 - image.2 / 943)
  have hQueryFirst := Int.ediv_mul_add_emod query.1 943
  have hImageFirst := Int.ediv_mul_add_emod image.1 943
  have hQuerySecond := Int.ediv_mul_add_emod query.2 943
  have hImageSecond := Int.ediv_mul_add_emod image.2 943
  have hResidue : query = add image (scale 943 offset) := by
    apply Prod.ext
    · dsimp [image, offset, add, scale] at *
      omega
    · dsimp [image, offset, add, scale] at *
      omega
  exact orbit_digit_step code canonical query offset hResidue

theorem orbit_thirteen_terminate (initial terminal : Pair) (digits : List Pair)
    (hLength : digits.length = 13)
    (hInitial : 3 * norm initial ≤ subgroupOrder)
    (hAtlas : ∀ digit ∈ digits,
      ∃ code : Fin 6, ∃ canonical : Pair,
        digit = unitImage code (nearestStep canonical).1)
    (hSteps : Recodes initial digits terminal) : terminal = (0, 0) := by
  apply thirteen_steps_terminate initial terminal digits hLength hInitial ?_ hSteps
  intro digit hDigit
  obtain ⟨code, canonical, hImage⟩ := hAtlas digit hDigit
  rw [hImage]
  exact unit_image_digit_bound code canonical

#print axioms omega_cubed
#print axioms omega_norm
#print axioms unit_image_norm
#print axioms unit_image_add
#print axioms unit_image_scale
#print axioms unit_image_digit_bound
#print axioms orbit_digit_step
#print axioms orbit_digit_from_residue
#print axioms orbit_thirteen_terminate

end PrimeJ0Radix943OrbitAtlas
