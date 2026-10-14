# Large-field curve-audit certificates and extension transfer

- **Status:** `open`
- **Kind:** implementation and validation gaps
- **Affected work:** [curve-audit CLI](../bindings/rust/curve-audit/README.md), [PR #865](https://github.com/aburan28/cryptanalysis/pull/865)
- **Next action owner:** curve-audit implementer
- **Last updated:** 2026-10-14

## Problem

The curve-audit CLI now certifies the checked-in P-192 order from recursive prime certificates, generator arithmetic and Hasse uniqueness. Its prime-field point enumerator still stops at the declared `--point-count-limit` (at most 1,000,000); a large-field input without the required certificates and uniqueness witnesses remains `supplied_unverified`. Independently sampled 192–252-bit controls and extension-field cover and isogeny-transfer arithmetic remain open. Extension-field representations are accepted as input but have no verified arithmetic backend.

The intended input is an exact field representation, curve model, selected subgroup order and generator, with optional protocol and graph evidence. An audit conclusion for a selected subgroup needs a certificate for each promoted criterion's field, curve and subgroup assumptions. A protocol vulnerability additionally needs the actual implementation or oracle behavior. A catalog entry alone cannot supply those witnesses.

## Evidence and uncertainty

- **Observed:** `bindings/rust/curve-audit/examples/nist-p192.json` passes generator-on-curve and `[r]G=O`; without a certificate the order remains `supplied_unverified`, and with its bound prime certificates the order becomes `hasse_unique_multiple_certificate`. The same executable exactly counts the order-101 regression curve in `examples/anomalous-101.json`; the checked Sage launcher independently returns curve and generator order 101. The extension-field test in `src/main.rs` keeps its cover criterion `unassessed`.
- **Derived or proved:** the P-192 certificate checks `p` and `r` primality, `[r]G=O`, the claimed order's Hasse interval and uniqueness bound, giving exact `#E`, trace and twist order. An independent checked-Sage point count and generator-order replay agree. Exact small-prime point enumeration establishes the reported trace and twist order for those counted models. Bounded modular embedding-degree searches establish only the stated degree interval. The Lean proof checks the interval-uniqueness step; its elliptic-curve and primality bridges remain unformalized.
- **Suspected explanation:** no mathematical obstruction is known; the missing pieces are certificate-producing arithmetic and map-replay implementations.
- **Missing capability:** independent 192–252-bit controls beyond P-192, a general certified point-count route when the selected subgroup does not exceed the Hasse interval width; irreducibility, field arithmetic, and point-count evidence for extension fields; explicit cover/isogeny maps with selected-subgroup kernel and image-order checks; protocol harnesses for input-validation criteria.
- **What this evidence does not establish:** an all-criteria safety result, an extension-field weakness finding, or an attack cost. A `not_found_within_bound` pairing row does not exclude larger embedding degrees.

## What would unblock it

- [ ] For the checked-in P-192 input and independently sampled 192–252-bit short-Weierstrass controls, verify `p`, `r`, `#E(F_p)`, the generator's exact order, trace and twist order with replayable certificates or independent point-count cross-checks. Bind every promoted result to the exact input and source revision.
- [ ] For one exact extension-field input with a pinned irreducible modulus, implement and cross-check field arithmetic, curve membership, selected generator order and an exact or certified curve order. For each proposed cover or isogeny transfer, retain its equations, field of definition, map/kernel checks, selected-subgroup image order and full cost boundary before promoting the row.
- [ ] For implementation or protocol criteria, bind the tested parser, scalar multiplication and oracle behavior to a source/binary digest and retain accepted/rejected input transcripts before promoting any such row.

These conditions would close the named evidence gaps for the tested inputs and criteria. They would still leave other catalog methods and newly discovered attacks to be assessed separately; no finite catalog proves universal security.

## Next discriminating step

- **Action or proof obligation:** sample an independent 192–252-bit short-Weierstrass control with a prime selected order satisfying `r²>16p`; generate and verify its bound certificates and compare its order, trace and twist with a checked-Sage point count. Then formalize the elliptic group/Hasse bridge in Lean.
- **Inputs and controls:** use the exact `nist-p192.json` bytes and NIST FIPS 186-4 Appendix D.1.2.1; retain the order-101 exact-count fixture and an intentionally incorrect subgroup-order fixture as positive and rejection controls.
- **Execution limits and stop condition:** limit the first integration to P-192 and the existing 192–252-bit parser range; stop on a certificate mismatch or unsupported certificate format, preserving both outputs rather than marking the curve safe.
- **Outcomes and next actions:** matching independently replayed evidence can promote only the large-prime order fields and downstream arithmetic criteria; a mismatch requires an arithmetic/input correction; an unavailable proof tool leaves `supplied_unverified` intact. The extension-field backend is a separate follow-on check.
- **Recheck trigger:** a large-prime order backend, an extension-field arithmetic backend, an explicit transfer map, or a protocol harness lands.

## Resolution and history

- 2026-10-14: P-192 recursive prime certificates and Hasse uniqueness verifier added. Checked-Sage replay returned the claimed `#E`, generator order, trace and twist. Lean proves interval uniqueness with standard foundations; the full elliptic result remains a documented formalization task.
- 2026-10-13: opened with PR #865 when the first audit binary and criteria catalog were versioned. Large-prime orders and extension transfer were unassessed by the first executable.

Unresolved.
