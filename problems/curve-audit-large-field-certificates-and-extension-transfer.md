# Large-field curve-audit certificates and extension transfer

- **Status:** `open`
- **Kind:** implementation and validation gaps
- **Affected work:** [curve-audit CLI](../bindings/rust/curve-audit/README.md), [PR #865](https://github.com/aburan28/cryptanalysis/pull/865)
- **Next action owner:** curve-audit implementer
- **Last updated:** 2026-10-13

## Problem

The curve-audit CLI cannot yet independently certify large-prime curve orders or evaluate extension-field cover and isogeny-transfer criteria. Its prime-field point enumerator stops at the declared `--point-count-limit` (at most 1,000,000); above that limit, supplied `#E` remains `supplied_unverified`. Extension-field representations are accepted as input but have no verified arithmetic backend. These gaps leave consequential rows `unassessed` for 192–252-bit prime-field inputs and for curves over fields such as `F_(p^6)`.

The intended input is an exact field representation, curve model, selected subgroup order and generator, with optional protocol and graph evidence. An audit conclusion for a selected subgroup needs a certificate for each promoted criterion's field, curve and subgroup assumptions. A protocol vulnerability additionally needs the actual implementation or oracle behavior. A catalog entry alone cannot supply those witnesses.

## Evidence and uncertainty

- **Observed:** `bindings/rust/curve-audit/examples/nist-p192.json` passes the generator-on-curve and `[r]G=O` checks, while the report labels the supplied large curve order `supplied_unverified`. The same executable exactly counts the order-101 regression curve in `examples/anomalous-101.json`; the checked Sage launcher independently returns curve and generator order 101. The extension-field test in `src/main.rs` keeps its cover criterion `unassessed`.
- **Derived or proved:** exact small-prime point enumeration establishes the reported trace and twist order for those counted models. Bounded modular embedding-degree searches establish only the stated degree interval. No large-prime point-count or extension transfer theorem is established by this CLI.
- **Suspected explanation:** no mathematical obstruction is known; the missing pieces are certificate-producing arithmetic and map-replay implementations.
- **Missing capability:** deterministic primality and point-count evidence for large prime fields; irreducibility, field arithmetic, and point-count evidence for extension fields; explicit cover/isogeny maps with selected-subgroup kernel and image-order checks; protocol harnesses for input-validation criteria.
- **What this evidence does not establish:** an all-criteria safety result, an extension-field weakness finding, or an attack cost. A `not_found_within_bound` pairing row does not exclude larger embedding degrees.

## What would unblock it

- [ ] For the checked-in P-192 input and independently sampled 192–252-bit short-Weierstrass controls, verify `p`, `r`, `#E(F_p)`, the generator's exact order, trace and twist order with replayable certificates or independent point-count cross-checks. Bind every promoted result to the exact input and source revision.
- [ ] For one exact extension-field input with a pinned irreducible modulus, implement and cross-check field arithmetic, curve membership, selected generator order and an exact or certified curve order. For each proposed cover or isogeny transfer, retain its equations, field of definition, map/kernel checks, selected-subgroup image order and full cost boundary before promoting the row.
- [ ] For implementation or protocol criteria, bind the tested parser, scalar multiplication and oracle behavior to a source/binary digest and retain accepted/rejected input transcripts before promoting any such row.

These conditions would close the named evidence gaps for the tested inputs and criteria. They would still leave other catalog methods and newly discovered attacks to be assessed separately; no finite catalog proves universal security.

## Next discriminating step

- **Action or proof obligation:** add a certificate-backed prime-field order verifier for the P-192 fixture, then compare its `#E`, `r`, trace and twist output with an independent checked-Sage replay of the same coefficients.
- **Inputs and controls:** use the exact `nist-p192.json` bytes and NIST FIPS 186-4 Appendix D.1.2.1; retain the order-101 exact-count fixture and an intentionally incorrect subgroup-order fixture as positive and rejection controls.
- **Execution limits and stop condition:** limit the first integration to P-192 and the existing 192–252-bit parser range; stop on a certificate mismatch or unsupported certificate format, preserving both outputs rather than marking the curve safe.
- **Outcomes and next actions:** matching independently replayed evidence can promote only the large-prime order fields and downstream arithmetic criteria; a mismatch requires an arithmetic/input correction; an unavailable proof tool leaves `supplied_unverified` intact. The extension-field backend is a separate follow-on check.
- **Recheck trigger:** a large-prime order backend, an extension-field arithmetic backend, an explicit transfer map, or a protocol harness lands.

## Resolution and history

- 2026-10-13: opened with PR #865 when the first audit binary and criteria catalog were versioned. Large-prime orders and extension transfer remain explicitly unassessed by the executable.

Unresolved.
