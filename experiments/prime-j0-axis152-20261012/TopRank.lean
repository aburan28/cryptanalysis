import DigitCover

namespace PrimeJ0Axis152TopRank

open PrimeJ0Radix919TerminalUnit
open PrimeJ0Axis152TopBound

def sector (a b : Int) : Prop :=
  a < 0 ∧ -a ≤ 3 * b ∧ 3 * b < -2 * a

theorem sector_cover (a b : Int) (h : a ≠ 0 ∨ b ≠ 0) :
    sector a b ∨ sector (-a) (-b) ∨
    sector (a+3*b) (-a-2*b) ∨ sector (-a-3*b) (a+2*b) ∨
    sector (-2*a-3*b) (a+b) ∨ sector (2*a+3*b) (-a-b) := by
  unfold sector
  omega

def image (code : Fin 6) (a b : Int) : Int × Int :=
  if code.val = 0 then (a,b) else
  if code.val = 1 then (-a,-b) else
  if code.val = 2 then (a+3*b,-a-2*b) else
  if code.val = 3 then (-a-3*b,a+2*b) else
  if code.val = 4 then (-2*a-3*b,a+b) else
  (2*a+3*b,-a-b)

theorem sector_unique (a b : Int) (i j : Fin 6)
    (hi : sector (image i a b).1 (image i a b).2)
    (hj : sector (image j a b).1 (image j a b).2) : i = j := by
  have hiCases : i.val = 0 ∨ i.val = 1 ∨ i.val = 2 ∨
      i.val = 3 ∨ i.val = 4 ∨ i.val = 5 := by
    have h := i.isLt
    omega
  have hjCases : j.val = 0 ∨ j.val = 1 ∨ j.val = 2 ∨
      j.val = 3 ∨ j.val = 4 ∨ j.val = 5 := by
    have h := j.isLt
    omega
  rcases hiCases with h | h | h | h | h | h <;>
    rcases hjCases with k | k | k | k | k | k <;>
    apply Fin.ext <;>
    simp_all [image, sector] <;> omega

theorem unique_sector_image (a b : Int) (h : a ≠ 0 ∨ b ≠ 0) :
    ∃ code : Fin 6,
      sector (image code a b).1 (image code a b).2 ∧
      ∀ other : Fin 6,
        sector (image other a b).1 (image other a b).2 → other = code := by
  have hExists : ∃ code : Fin 6,
      sector (image code a b).1 (image code a b).2 := by
    rcases sector_cover a b h with h0 | h1 | h2 | h3 | h4 | h5
    · exact ⟨⟨0, by decide⟩, by simpa [image] using h0⟩
    · exact ⟨⟨1, by decide⟩, by simpa [image] using h1⟩
    · exact ⟨⟨2, by decide⟩, by simpa [image] using h2⟩
    · exact ⟨⟨3, by decide⟩, by simpa [image] using h3⟩
    · exact ⟨⟨4, by decide⟩, by simpa [image] using h4⟩
    · exact ⟨⟨5, by decide⟩, by simpa [image] using h5⟩
  obtain ⟨code, hcode⟩ := hExists
  refine ⟨code, hcode, ?_⟩
  intro other hother
  exact sector_unique a b other code hother hcode

theorem top_row_identity (u b : Int) :
    12 * norm (-u, b) = 9 * (2*b-u)^2 + 3*u^2 := by
  simp only [norm]
  grind +ring

theorem top_row_bound (u b : Int)
    (h : 3 * norm (-u, b) ≤ topCap) :
    9 * (2*b-u)^2 + 3*u^2 ≤ 4 * topCap := by
  have hid := top_row_identity u b
  omega

theorem top_row_limit (u b : Int) (_hu : 0 ≤ u)
    (h : 3 * norm (-u, b) ≤ topCap) : u ≤ 4840 := by
  have hrow := top_row_bound u b h
  have hsq := Int.sq_nonneg (2*b-u)
  have hu2 : 3 * u^2 ≤ 4 * topCap := by omega
  by_cases hgood : u ≤ 4840
  · exact hgood
  · have hge : 4841 ≤ u := by omega
    have hs := Int.mul_self_le_mul_self (by decide : (0 : Int) ≤ 4841) hge
    have hu2' : 4841 * 4841 ≤ u^2 := by simpa [Int.pow_succ] using hs
    have hcert : 4 * topCap < 3 * (4841 : Int)^2 := by decide
    omega

theorem norm_image (code : Fin 6) (a b : Int) :
    norm (image code a b) = norm (a, b) := by
  have h : code.val = 0 ∨ code.val = 1 ∨ code.val = 2 ∨
      code.val = 3 ∨ code.val = 4 ∨ code.val = 5 := by
    have hlt := code.isLt
    omega
  rcases h with h | h | h | h | h | h <;>
    simp [image, h, norm] <;> grind +ring

theorem image_has_inverse (code : Fin 6) (a b : Int) :
    ∃ inverse : Fin 6,
      image inverse (image code a b).1 (image code a b).2 = (a, b) := by
  have h : code.val = 0 ∨ code.val = 1 ∨ code.val = 2 ∨
      code.val = 3 ∨ code.val = 4 ∨ code.val = 5 := by
    have hlt := code.isLt
    omega
  rcases h with h | h | h | h | h | h
  · exact ⟨⟨0, by decide⟩, by simp [image, h]⟩
  · exact ⟨⟨1, by decide⟩, by simp [image, h]⟩
  · exact ⟨⟨4, by decide⟩, by simp [image, h] <;> omega⟩
  · exact ⟨⟨5, by decide⟩, by simp [image, h] <;> omega⟩
  · exact ⟨⟨2, by decide⟩, by simp [image, h] <;> omega⟩
  · exact ⟨⟨3, by decide⟩, by simp [image, h] <;> omega⟩

theorem axis_factorization (terminal : Pair)
    (hnonzero : terminal ≠ (0, 0))
    (hbound : 3 * norm terminal ≤ topCap) :
    ∃ code : Fin 6, ∃ u b : Int,
      1 ≤ u ∧ u ≤ 4840 ∧ 1 ≤ b ∧ b ≤ 3226 ∧
      terminal = image code (-u) b ∧
      (-u, b) = add (-u, 0) (0, b) := by
  have hnonzero' : terminal.1 ≠ 0 ∨ terminal.2 ≠ 0 := by
    rcases terminal with ⟨a, b⟩
    simp only [ne_eq, Prod.mk.injEq] at hnonzero
    omega
  obtain ⟨sectorCode, hsector, _⟩ :=
    unique_sector_image terminal.1 terminal.2 hnonzero'
  let canonical := image sectorCode terminal.1 terminal.2
  let u := -canonical.1
  let b := canonical.2
  have hu : 1 ≤ u := by
    dsimp [u, canonical, sector] at *
    omega
  have hb : 1 ≤ b := by
    dsimp [u, b, canonical, sector] at *
    omega
  have hnorm : 3 * norm (-u, b) ≤ topCap := by
    have heq : (-u, b) = canonical := by simp [u, b]
    rw [heq]
    simpa [canonical, norm_image] using hbound
  have huMax : u ≤ 4840 := top_row_limit u b (by omega) hnorm
  have hbMax : b ≤ 3226 := by
    have hsec : sector (-u) b := by
      simpa [u, b, canonical] using hsector
    dsimp [sector] at hsec
    omega
  obtain ⟨inverse, hinverse⟩ :=
    image_has_inverse sectorCode terminal.1 terminal.2
  refine ⟨inverse, u, b, hu, huMax, hb, hbMax, ?_, ?_⟩
  · simpa [u, b, canonical] using hinverse.symm
  · simp [add]

#print axioms sector_cover
#print axioms sector_unique
#print axioms unique_sector_image
#print axioms top_row_identity
#print axioms top_row_bound
#print axioms top_row_limit
#print axioms norm_image
#print axioms image_has_inverse
#print axioms axis_factorization

end PrimeJ0Axis152TopRank
