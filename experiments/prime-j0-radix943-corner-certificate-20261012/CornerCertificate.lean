import DigitCover

namespace PrimeJ0Radix943CornerCertificate

open PrimeJ0Radix943Termination
open PrimeJ0Radix943DigitCover

-- Codes 0,1,2,3 are the native (dw,dv) corners
-- (0,0), (1,0), (0,1), (1,1).
private theorem code_cases (code : Fin 4) :
    code.val = 0 ∨ code.val = 1 ∨ code.val = 2 ∨ code.val = 3 := by
  have h := code.isLt
  omega

def scaledDifference (C X Y : Int) (code : Fin 4) : Int :=
  if code.val = 0 then 0 else
  if code.val = 1 then C - 2*X + Y else
  if code.val = 2 then C + X - 2*Y else C - X - Y

def lowerBound (C U V N : Int) (code : Fin 4) : Int :=
  if code.val = 0 then 0 else
  if code.val = 1 then C - 2*U + V - 4*N else
  if code.val = 2 then C + U - 2*V - 4*N else C - U - V - 4*N

def upperBound (C U V N : Int) (code : Fin 4) : Int :=
  if code.val = 0 then 0 else
  if code.val = 1 then C - 2*U + V + 2*N else
  if code.val = 2 then C + U - 2*V + 2*N else C - U - V

theorem score_in_bounds (C U V X Y N : Int)
    (hXlo : U ≤ X) (hXhi : X ≤ U + 2*N)
    (hYlo : V ≤ Y) (hYhi : Y ≤ V + 2*N)
    (code : Fin 4) :
    lowerBound C U V N code ≤ scaledDifference C X Y code ∧
    scaledDifference C X Y code ≤ upperBound C U V N code := by
  rcases code_cases code with h | h | h | h <;>
    simp [lowerBound, scaledDifference, upperBound, h] <;> omega

def certified (C U V N : Int) (winner : Fin 4) : Prop :=
  ∀ rival : Fin 4, rival ≠ winner →
    upperBound C U V N winner < lowerBound C U V N rival

theorem certificate_unique_minimum (C U V X Y N : Int)
    (hXlo : U ≤ X) (hXhi : X ≤ U + 2*N)
    (hYlo : V ≤ Y) (hYhi : Y ≤ V + 2*N)
    (winner : Fin 4) (hCertificate : certified C U V N winner) :
    ∀ rival : Fin 4, rival ≠ winner →
      scaledDifference C X Y winner < scaledDifference C X Y rival := by
  intro rival hDifferent
  have hWin := (score_in_bounds C U V X Y N hXlo hXhi hYlo hYhi winner).2
  have hRival := (score_in_bounds C U V X Y N hXlo hXhi hYlo hYhi rival).1
  have hSeparate := hCertificate rival hDifferent
  omega

def scalarCorner (scalar : Int) (code : Fin 4) : Pair :=
  let fw := (scalar * basisV.2) / subgroupOrder
  let fv := (-scalar * basisW.2) / subgroupOrder
  if code.val = 0 then representativeCorner scalar fw fv basisW basisV else
  if code.val = 1 then representativeCorner scalar (fw+1) fv basisW basisV else
  if code.val = 2 then representativeCorner scalar fw (fv+1) basisW basisV else
  representativeCorner scalar (fw+1) (fv+1) basisW basisV

theorem scalar_corner_difference (scalar : Int) (code : Fin 4) :
    norm (scalarCorner scalar code) -
      norm (scalarCorner scalar ⟨0, by decide⟩) =
    scaledDifference subgroupOrder
      (scalar*basisV.2 - (scalar*basisV.2)/subgroupOrder*subgroupOrder)
      (-scalar*basisW.2 - (-scalar*basisW.2)/subgroupOrder*subgroupOrder)
      code := by
  rcases code_cases code with h | h | h | h <;>
    simp [scalarCorner, scaledDifference, h, representativeCorner, norm,
      sub, scale, basisW, basisV, basisU, subgroupOrder] <;>
    grind +ring

theorem scaled_difference_scale (factor C X Y : Int) (code : Fin 4) :
    scaledDifference (factor*C) (factor*X) (factor*Y) code =
      factor * scaledDifference C X Y code := by
  rcases code_cases code with h | h | h | h <;>
    simp [scaledDifference, h] <;> grind +ring

def cellX (scalar : Int) : Int := scalar*basisV.2 % subgroupOrder
def cellY (scalar : Int) : Int := -scalar*basisW.2 % subgroupOrder

theorem exact_corner_score (scalar factor : Int) (code : Fin 4) :
    scaledDifference (factor*subgroupOrder)
      (factor*cellX scalar) (factor*cellY scalar) code =
    factor * (norm (scalarCorner scalar code) -
      norm (scalarCorner scalar ⟨0, by decide⟩)) := by
  have hx := Int.ediv_mul_add_emod (scalar*basisV.2) subgroupOrder
  have hy := Int.ediv_mul_add_emod (-scalar*basisW.2) subgroupOrder
  have hx' : cellX scalar = scalar*basisV.2 -
      (scalar*basisV.2)/subgroupOrder*subgroupOrder := by
    dsimp [cellX]
    omega
  have hy' : cellY scalar = -scalar*basisW.2 -
      (-scalar*basisW.2)/subgroupOrder*subgroupOrder := by
    dsimp [cellY]
    omega
  rw [scaled_difference_scale, hx', hy', scalar_corner_difference]

theorem certified_corner_nearest (scalar factor hw hv : Int) (winner : Fin 4)
    (hFactor : 0 < factor)
    (hXlo : hw*subgroupOrder ≤ factor*cellX scalar)
    (hXhi : factor*cellX scalar ≤ (hw+2)*subgroupOrder)
    (hYlo : hv*subgroupOrder ≤ factor*cellY scalar)
    (hYhi : factor*cellY scalar ≤ (hv+2)*subgroupOrder)
    (hCertificate : certified (factor*subgroupOrder)
      (hw*subgroupOrder) (hv*subgroupOrder) subgroupOrder winner) :
    ∀ rival : Fin 4, rival ≠ winner →
      norm (scalarCorner scalar winner) < norm (scalarCorner scalar rival) := by
  intro rival hDifferent
  have hxhi' : factor*cellX scalar ≤ hw*subgroupOrder + 2*subgroupOrder := by
    calc
      factor*cellX scalar ≤ (hw+2)*subgroupOrder := hXhi
      _ = hw*subgroupOrder + 2*subgroupOrder := by grind +ring
  have hyhi' : factor*cellY scalar ≤ hv*subgroupOrder + 2*subgroupOrder := by
    calc
      factor*cellY scalar ≤ (hv+2)*subgroupOrder := hYhi
      _ = hv*subgroupOrder + 2*subgroupOrder := by grind +ring
  have hScore := certificate_unique_minimum
    (factor*subgroupOrder) (hw*subgroupOrder) (hv*subgroupOrder)
    (factor*cellX scalar) (factor*cellY scalar) subgroupOrder
    hXlo hxhi' hYlo hyhi' winner hCertificate rival hDifferent
  rw [exact_corner_score, exact_corner_score] at hScore
  by_cases hLess : norm (scalarCorner scalar winner) < norm (scalarCorner scalar rival)
  · exact hLess
  · have hReverse : norm (scalarCorner scalar rival) ≤
        norm (scalarCorner scalar winner) := by omega
    have hDiff : norm (scalarCorner scalar rival) -
        norm (scalarCorner scalar ⟨0, by decide⟩) ≤
        norm (scalarCorner scalar winner) -
        norm (scalarCorner scalar ⟨0, by decide⟩) := by omega
    have hScaled := Int.mul_le_mul_of_nonneg_left hDiff (Int.le_of_lt hFactor)
    omega

private def maxAbs (z : Pair) : Nat := max z.1.natAbs z.2.natAbs

private def representativeScoreLt (a b : Pair) : Prop :=
  norm a < norm b ∨
  (norm a = norm b ∧
    (maxAbs a < maxAbs b ∨
     (maxAbs a = maxAbs b ∧
      (a.1 < b.1 ∨ (a.1 = b.1 ∧ a.2 < b.2)))))

private instance (a b : Pair) : Decidable (representativeScoreLt a b) := by
  unfold representativeScoreLt
  infer_instance

private def chooseRepresentative (old next : Pair) : Pair :=
  if representativeScoreLt next old then next else old

private def replicatedNearest (scalar : Int) : Pair :=
  let fw := (scalar*basisV.2)/subgroupOrder
  let fv := (-scalar*basisW.2)/subgroupOrder
  chooseRepresentative
    (chooseRepresentative
      (chooseRepresentative
        (representativeCorner scalar fw fv basisW basisV)
        (representativeCorner scalar fw (fv+1) basisW basisV))
      (representativeCorner scalar (fw+1) fv basisW basisV))
    (representativeCorner scalar (fw+1) (fv+1) basisW basisV)

private theorem replica_eq (scalar : Int) :
    replicatedNearest scalar = nearestRepresentative scalar := by rfl

private theorem choose_member (old next : Pair) :
    chooseRepresentative old next = old ∨ chooseRepresentative old next = next := by
  unfold chooseRepresentative
  split
  · exact Or.inr rfl
  · exact Or.inl rfl

private theorem choose_norm_le_left (old next : Pair) :
    norm (chooseRepresentative old next) ≤ norm old := by
  unfold chooseRepresentative
  split
  · rename_i h
    dsimp [representativeScoreLt] at h
    omega
  · omega

private theorem choose_norm_le_right (old next : Pair) :
    norm (chooseRepresentative old next) ≤ norm next := by
  unfold chooseRepresentative
  split
  · omega
  · rename_i h
    have hNoLess : ¬ norm next < norm old := by
      intro hlt
      exact h (Or.inl hlt)
    omega

theorem nearest_representative_is_corner (scalar : Int) :
    ∃ code : Fin 4, nearestRepresentative scalar = scalarCorner scalar code := by
  let c00 := scalarCorner scalar ⟨0, by decide⟩
  let c01 := scalarCorner scalar ⟨2, by decide⟩
  let c10 := scalarCorner scalar ⟨1, by decide⟩
  let c11 := scalarCorner scalar ⟨3, by decide⟩
  have hReplica : replicatedNearest scalar =
      chooseRepresentative (chooseRepresentative (chooseRepresentative c00 c01) c10) c11 := by
    rfl
  rw [← replica_eq, hReplica]
  rcases choose_member (chooseRepresentative (chooseRepresentative c00 c01) c10) c11 with h | h
  · rw [h]
    rcases choose_member (chooseRepresentative c00 c01) c10 with h | h
    · rw [h]
      rcases choose_member c00 c01 with h | h
      · exact ⟨⟨0, by decide⟩, h⟩
      · exact ⟨⟨2, by decide⟩, h⟩
    · exact ⟨⟨1, by decide⟩, h⟩
  · exact ⟨⟨3, by decide⟩, h⟩

theorem nearest_norm_le_corner (scalar : Int) (code : Fin 4) :
    norm (nearestRepresentative scalar) ≤ norm (scalarCorner scalar code) := by
  let c00 := scalarCorner scalar ⟨0, by decide⟩
  let c01 := scalarCorner scalar ⟨2, by decide⟩
  let c10 := scalarCorner scalar ⟨1, by decide⟩
  let c11 := scalarCorner scalar ⟨3, by decide⟩
  have hRep : nearestRepresentative scalar =
      chooseRepresentative (chooseRepresentative (chooseRepresentative c00 c01) c10) c11 := by
    rw [← replica_eq]
    rfl
  have h00 : norm (nearestRepresentative scalar) ≤ norm c00 := by
    rw [hRep]
    exact Int.le_trans (choose_norm_le_left _ _)
      (Int.le_trans (choose_norm_le_left _ _) (choose_norm_le_left _ _))
  have h01 : norm (nearestRepresentative scalar) ≤ norm c01 := by
    rw [hRep]
    exact Int.le_trans (choose_norm_le_left _ _)
      (Int.le_trans (choose_norm_le_left _ _) (choose_norm_le_right _ _))
  have h10 : norm (nearestRepresentative scalar) ≤ norm c10 := by
    rw [hRep]
    exact Int.le_trans (choose_norm_le_left _ _) (choose_norm_le_right _ _)
  have h11 : norm (nearestRepresentative scalar) ≤ norm c11 := by
    rw [hRep]
    exact choose_norm_le_right _ _
  rcases code_cases code with h | h | h | h
  · simpa [scalarCorner, h, c00] using h00
  · simpa [scalarCorner, h, c10] using h10
  · simpa [scalarCorner, h, c01] using h01
  · simpa [scalarCorner, h, c11] using h11

theorem certified_corner_eq_nearest (scalar factor hw hv : Int) (winner : Fin 4)
    (hFactor : 0 < factor)
    (hXlo : hw*subgroupOrder ≤ factor*cellX scalar)
    (hXhi : factor*cellX scalar ≤ (hw+2)*subgroupOrder)
    (hYlo : hv*subgroupOrder ≤ factor*cellY scalar)
    (hYhi : factor*cellY scalar ≤ (hv+2)*subgroupOrder)
    (hCertificate : certified (factor*subgroupOrder)
      (hw*subgroupOrder) (hv*subgroupOrder) subgroupOrder winner) :
    scalarCorner scalar winner = nearestRepresentative scalar := by
  obtain ⟨other, hNearest⟩ := nearest_representative_is_corner scalar
  by_cases hSame : other = winner
  · rw [hSame] at hNearest
    exact hNearest.symm
  · have hStrict := certified_corner_nearest scalar factor hw hv winner
      hFactor hXlo hXhi hYlo hYhi hCertificate other hSame
    have hWeak := nearest_norm_le_corner scalar winner
    rw [hNearest] at hWeak
    omega

theorem certified_representative_bound_and_congruence
    (scalar factor hw hv : Int) (winner : Fin 4)
    (hFactor : 0 < factor)
    (hXlo : hw*subgroupOrder ≤ factor*cellX scalar)
    (hXhi : factor*cellX scalar ≤ (hw+2)*subgroupOrder)
    (hYlo : hv*subgroupOrder ≤ factor*cellY scalar)
    (hYhi : factor*cellY scalar ≤ (hv+2)*subgroupOrder)
    (hCertificate : certified (factor*subgroupOrder)
      (hw*subgroupOrder) (hv*subgroupOrder) subgroupOrder winner) :
    3 * norm (scalarCorner scalar winner) ≤ subgroupOrder ∧
    (scalarMap (scalarCorner scalar winner)-scalar)%subgroupOrder = 0 := by
  have hEq := certified_corner_eq_nearest scalar factor hw hv winner
    hFactor hXlo hXhi hYlo hYhi hCertificate
  rw [hEq]
  exact ⟨nearest_representative_bound scalar,
    nearest_representative_congruence scalar⟩

def reciprocalScale : Int := 0x100000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000
def highLimbScale : Int := 0x10000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000
def limbScale : Int := 0x10000000000000000

theorem reciprocal_fraction_envelope (product exactProduct scalar : Int)
    (hScalar : 0 ≤ scalar ∧ scalar < highLimbScale)
    (hLower : product*subgroupOrder ≤ reciprocalScale*exactProduct)
    (hUpper : reciprocalScale*exactProduct <
      (product+scalar)*subgroupOrder)
    (hFloor : product/reciprocalScale = exactProduct/subgroupOrder) :
    let highLimb := (product%reciprocalScale)/highLimbScale
    let exactRemainder := exactProduct%subgroupOrder
    highLimb*subgroupOrder ≤ limbScale*exactRemainder ∧
      limbScale*exactRemainder ≤ (highLimb+2)*subgroupOrder := by
  have hScale : reciprocalScale = limbScale*highLimbScale := by decide
  have hP := Int.ediv_mul_add_emod product reciprocalScale
  have hT := Int.ediv_mul_add_emod exactProduct subgroupOrder
  have hHigh := Int.ediv_mul_add_emod (product%reciprocalScale) highLimbScale
  have hRem : 0 ≤ (product%reciprocalScale)%highLimbScale ∧
      (product%reciprocalScale)%highLimbScale < highLimbScale := by
    constructor
    · exact Int.emod_nonneg _ (by decide)
    · exact Int.emod_lt_of_pos _ (by decide)
  dsimp
  simp only [reciprocalScale, highLimbScale, limbScale, subgroupOrder] at *
  omega

theorem reciprocal_floor_from_product_bounds (product exactProduct scalar : Int)
    (hScalar : 0 < scalar ∧ scalar < subgroupOrder)
    (hLower : product*subgroupOrder ≤ reciprocalScale*exactProduct)
    (hUpper : reciprocalScale*exactProduct <
      (product+scalar)*subgroupOrder)
    (hRemainder : 1 ≤ exactProduct%subgroupOrder) :
    product/reciprocalScale = exactProduct/subgroupOrder := by
  have hP := Int.ediv_mul_add_emod product reciprocalScale
  have hT := Int.ediv_mul_add_emod exactProduct subgroupOrder
  have hPmod : 0 ≤ product%reciprocalScale ∧
      product%reciprocalScale < reciprocalScale := by
    constructor
    · exact Int.emod_nonneg _ (by decide)
    · exact Int.emod_lt_of_pos _ (by decide)
  have hTmod : exactProduct%subgroupOrder < subgroupOrder := by
    exact Int.emod_lt_of_pos _ (by decide)
  have hScaleLarge : subgroupOrder*subgroupOrder < reciprocalScale := by decide
  simp only [reciprocalScale, subgroupOrder] at *
  omega

theorem reciprocal_product_bounds (scalar coefficient reciprocal : Int)
    (hScalar : 0 < scalar)
    (hReciprocalLower : reciprocal*subgroupOrder ≤ reciprocalScale*coefficient)
    (hReciprocalUpper : reciprocalScale*coefficient <
      (reciprocal+1)*subgroupOrder) :
    (scalar*reciprocal)*subgroupOrder ≤
      reciprocalScale*(scalar*coefficient) ∧
    reciprocalScale*(scalar*coefficient) <
      (scalar*reciprocal+scalar)*subgroupOrder := by
  have hLow := Int.mul_le_mul_of_nonneg_left hReciprocalLower
    (Int.le_of_lt hScalar)
  have hUp := Int.mul_lt_mul_of_pos_left hReciprocalUpper hScalar
  constructor <;> grind +ring

theorem reciprocal_floor_exact (scalar coefficient reciprocal : Int)
    (hScalar : 0 < scalar ∧ scalar < subgroupOrder)
    (hReciprocalLower : reciprocal*subgroupOrder ≤ reciprocalScale*coefficient)
    (hReciprocalUpper : reciprocalScale*coefficient <
      (reciprocal+1)*subgroupOrder)
    (hRemainder : 1 ≤ (scalar*coefficient)%subgroupOrder) :
    (scalar*reciprocal)/reciprocalScale =
      (scalar*coefficient)/subgroupOrder := by
  obtain ⟨hLow, hUp⟩ := reciprocal_product_bounds scalar coefficient reciprocal
    hScalar.1 hReciprocalLower hReciprocalUpper
  exact reciprocal_floor_from_product_bounds
    (scalar*reciprocal) (scalar*coefficient) scalar hScalar hLow hUp hRemainder

theorem nonzero_remainder_from_inverse (scalar coefficient inverse multiple : Int)
    (hInverse : coefficient*inverse = subgroupOrder*multiple+1)
    (hScalar : 0 < scalar ∧ scalar < subgroupOrder) :
    1 ≤ (scalar*coefficient)%subgroupOrder := by
  have hNonneg : 0 ≤ (scalar*coefficient)%subgroupOrder :=
    Int.emod_nonneg _ (by decide)
  by_cases hZero : (scalar*coefficient)%subgroupOrder = 0
  · have hDiv := Int.ediv_mul_add_emod (scalar*coefficient) subgroupOrder
    have hEq : scalar = subgroupOrder *
        ((scalar*coefficient)/subgroupOrder*inverse-scalar*multiple) := by
      grind +ring
    have hScalarDiv : subgroupOrder ∣ scalar := ⟨_, hEq⟩
    have hScalarMod : scalar%subgroupOrder=0 := Int.emod_eq_zero_of_dvd hScalarDiv
    have hScalarDecomp := Int.ediv_mul_add_emod scalar subgroupOrder
    simp only [subgroupOrder] at *
    omega
  · omega

-- These constants are the seven little-endian limbs in eisenstein_fixed.rs.
def reciprocalV : Int :=
  0xe4437ed6010e88286f547fa90abfe4c4221208ac9df506c61571b4ae8ac47f7146683369b37d763044180e526536385c
def reciprocalW : Int :=
  0x114ca50f7a8e2f3f657c1108d9d44cfd95fbc92c10fddd145fe04d548d0a02fa230e98f407e1a0fa206dfcbca80313b00

private def inverseV : Int :=
  93315342734088478194468943808457753085541896514852243494941512349958024398345
private def multipleV : Int := 244517761065088206286623414864222006362
private def inverseW : Int :=
  113859244173077282785050241834804787623472567142703998078252165831100869442129
private def multipleW : Int := 361775997307656764103407721907293435543

theorem reciprocal_constant_certificates :
    reciprocalV*subgroupOrder ≤ reciprocalScale*basisV.2 ∧
    reciprocalScale*basisV.2 < (reciprocalV+1)*subgroupOrder ∧
    reciprocalW*subgroupOrder ≤ reciprocalScale*(-basisW.2) ∧
    reciprocalScale*(-basisW.2) < (reciprocalW+1)*subgroupOrder := by decide

theorem coefficient_inverse_certificates :
    basisV.2*inverseV = subgroupOrder*multipleV+1 ∧
    (-basisW.2)*inverseW = subgroupOrder*multipleW+1 := by decide

theorem exact_two_reciprocal_floors (scalar : Int)
    (hScalar : 0 ≤ scalar ∧ scalar < subgroupOrder) :
    (scalar*reciprocalV)/reciprocalScale =
      (scalar*basisV.2)/subgroupOrder ∧
    (scalar*reciprocalW)/reciprocalScale =
      (scalar*(-basisW.2))/subgroupOrder := by
  by_cases hZero : scalar = 0
  · subst scalar
    simp
  · have hPositive : 0 < scalar := by omega
    have hBounds := reciprocal_constant_certificates
    have hInverses := coefficient_inverse_certificates
    have hRemV := nonzero_remainder_from_inverse
      scalar basisV.2 inverseV multipleV hInverses.1 ⟨hPositive, hScalar.2⟩
    have hRemW := nonzero_remainder_from_inverse
      scalar (-basisW.2) inverseW multipleW hInverses.2 ⟨hPositive, hScalar.2⟩
    exact ⟨
      reciprocal_floor_exact scalar basisV.2 reciprocalV
        ⟨hPositive, hScalar.2⟩ hBounds.1 hBounds.2.1 hRemV,
      reciprocal_floor_exact scalar (-basisW.2) reciprocalW
        ⟨hPositive, hScalar.2⟩ hBounds.2.2.1 hBounds.2.2.2 hRemW⟩

def nativeHighV (scalar : Int) : Int :=
  ((scalar*reciprocalV)%reciprocalScale)/highLimbScale
def nativeHighW (scalar : Int) : Int :=
  ((scalar*reciprocalW)%reciprocalScale)/highLimbScale

theorem native_fraction_envelopes (scalar : Int)
    (hScalar : 0 ≤ scalar ∧ scalar < subgroupOrder) :
    nativeHighV scalar*subgroupOrder ≤ limbScale*cellX scalar ∧
    limbScale*cellX scalar ≤ (nativeHighV scalar+2)*subgroupOrder ∧
    nativeHighW scalar*subgroupOrder ≤ limbScale*cellY scalar ∧
    limbScale*cellY scalar ≤ (nativeHighW scalar+2)*subgroupOrder := by
  by_cases hZero : scalar = 0
  · subst scalar
    simp [nativeHighV, nativeHighW, cellX, cellY, limbScale, subgroupOrder]
  · have hPositive : 0 < scalar := by omega
    have hHigh : scalar < highLimbScale := by
      have hOrder : subgroupOrder < highLimbScale := by decide
      omega
    have hBounds := reciprocal_constant_certificates
    have hFloors := exact_two_reciprocal_floors scalar hScalar
    have hProductV := reciprocal_product_bounds scalar basisV.2 reciprocalV
      hPositive hBounds.1 hBounds.2.1
    have hProductW := reciprocal_product_bounds scalar (-basisW.2) reciprocalW
      hPositive hBounds.2.2.1 hBounds.2.2.2
    have hEnvelopeV := reciprocal_fraction_envelope
      (scalar*reciprocalV) (scalar*basisV.2) scalar
      ⟨hScalar.1,hHigh⟩ hProductV.1 hProductV.2 hFloors.1
    have hEnvelopeW := reciprocal_fraction_envelope
      (scalar*reciprocalW) (scalar*(-basisW.2)) scalar
      ⟨hScalar.1,hHigh⟩ hProductW.1 hProductW.2 hFloors.2
    have hCoeff : scalar*(-basisW.2) = -scalar*basisW.2 := by grind +ring
    rw [hCoeff] at hEnvelopeW
    constructor
    · exact hEnvelopeV.1
    constructor
    · exact hEnvelopeV.2
    constructor
    · exact hEnvelopeW.1
    · exact hEnvelopeW.2

def nativeLower (hw hv : Int) (code : Fin 4) : Int :=
  if code.val = 0 then 0 else
  if code.val = 1 then limbScale - 2*hw + hv - 4 else
  if code.val = 2 then limbScale + hw - 2*hv - 4 else
  limbScale - hw - hv - 4

def nativeUpper (hw hv : Int) (code : Fin 4) : Int :=
  if code.val = 0 then 0 else
  if code.val = 1 then limbScale - 2*hw + hv + 2 else
  if code.val = 2 then limbScale + hw - 2*hv + 2 else
  limbScale - hw - hv

theorem native_lower_scaled (hw hv : Int) (code : Fin 4) :
    lowerBound (limbScale*subgroupOrder) (hw*subgroupOrder)
      (hv*subgroupOrder) subgroupOrder code =
    nativeLower hw hv code * subgroupOrder := by
  rcases code_cases code with h | h | h | h <;>
    simp [lowerBound, nativeLower, h] <;> grind +ring

theorem native_upper_scaled (hw hv : Int) (code : Fin 4) :
    upperBound (limbScale*subgroupOrder) (hw*subgroupOrder)
      (hv*subgroupOrder) subgroupOrder code =
    nativeUpper hw hv code * subgroupOrder := by
  rcases code_cases code with h | h | h | h <;>
    simp [upperBound, nativeUpper, h] <;> grind +ring

def nativeCertified (hw hv : Int) (winner : Fin 4) : Prop :=
  ∀ rival : Fin 4, rival ≠ winner →
    nativeUpper hw hv winner < nativeLower hw hv rival

theorem native_certificate_sound (hw hv : Int) (winner : Fin 4)
    (hNative : nativeCertified hw hv winner) :
    certified (limbScale*subgroupOrder)
      (hw*subgroupOrder) (hv*subgroupOrder) subgroupOrder winner := by
  intro rival hDifferent
  have hStrict := hNative rival hDifferent
  have hScaled := Int.mul_lt_mul_of_pos_right hStrict
    (by decide : (0:Int) < subgroupOrder)
  rw [native_upper_scaled, native_lower_scaled]
  exact hScaled

theorem native_certificate_eq_nearest (scalar : Int) (winner : Fin 4)
    (hScalar : 0 ≤ scalar ∧ scalar < subgroupOrder)
    (hCertificate : certified (limbScale*subgroupOrder)
      (nativeHighV scalar*subgroupOrder)
      (nativeHighW scalar*subgroupOrder) subgroupOrder winner) :
    scalarCorner scalar winner = nearestRepresentative scalar := by
  have hEnvelope := native_fraction_envelopes scalar hScalar
  exact certified_corner_eq_nearest scalar limbScale
    (nativeHighV scalar) (nativeHighW scalar) winner
    (by decide) hEnvelope.1 hEnvelope.2.1
    hEnvelope.2.2.1 hEnvelope.2.2.2 hCertificate

theorem rust_interval_certificate_eq_nearest (scalar : Int) (winner : Fin 4)
    (hScalar : 0 ≤ scalar ∧ scalar < subgroupOrder)
    (hNative : nativeCertified (nativeHighV scalar) (nativeHighW scalar) winner) :
    scalarCorner scalar winner = nearestRepresentative scalar := by
  exact native_certificate_eq_nearest scalar winner hScalar
    (native_certificate_sound _ _ winner hNative)

def nativeChoice (scalar : Int) (winner : Option (Fin 4)) : Pair :=
  match winner with
  | none => nearestRepresentative scalar
  | some code => scalarCorner scalar code

theorem native_choice_eq_nearest (scalar : Int) (winner : Option (Fin 4))
    (hScalar : 0 ≤ scalar ∧ scalar < subgroupOrder)
    (hCertified : ∀ code : Fin 4, winner = some code →
      nativeCertified (nativeHighV scalar) (nativeHighW scalar) code) :
    nativeChoice scalar winner = nearestRepresentative scalar := by
  cases winner with
  | none => rfl
  | some code =>
      exact rust_interval_certificate_eq_nearest scalar code hScalar
        (hCertified code rfl)

theorem native_choice_bound_and_congruence (scalar : Int) (winner : Option (Fin 4))
    (hScalar : 0 ≤ scalar ∧ scalar < subgroupOrder)
    (hCertified : ∀ code : Fin 4, winner = some code →
      nativeCertified (nativeHighV scalar) (nativeHighW scalar) code) :
    3 * norm (nativeChoice scalar winner) ≤ subgroupOrder ∧
    (scalarMap (nativeChoice scalar winner)-scalar)%subgroupOrder = 0 := by
  rw [native_choice_eq_nearest scalar winner hScalar hCertified]
  exact ⟨nearest_representative_bound scalar,
    nearest_representative_congruence scalar⟩

#print axioms score_in_bounds
#print axioms certificate_unique_minimum
#print axioms scalar_corner_difference
#print axioms exact_corner_score
#print axioms certified_corner_nearest
#print axioms nearest_representative_is_corner
#print axioms nearest_norm_le_corner
#print axioms certified_corner_eq_nearest
#print axioms certified_representative_bound_and_congruence
#print axioms reciprocal_fraction_envelope
#print axioms reciprocal_floor_from_product_bounds
#print axioms reciprocal_product_bounds
#print axioms reciprocal_floor_exact
#print axioms nonzero_remainder_from_inverse
#print axioms reciprocal_constant_certificates
#print axioms coefficient_inverse_certificates
#print axioms exact_two_reciprocal_floors
#print axioms native_fraction_envelopes
#print axioms native_lower_scaled
#print axioms native_upper_scaled
#print axioms native_certificate_sound
#print axioms native_certificate_eq_nearest
#print axioms rust_interval_certificate_eq_nearest
#print axioms native_choice_eq_nearest
#print axioms native_choice_bound_and_congruence

end PrimeJ0Radix943CornerCertificate
