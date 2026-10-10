# Full-registry normalized-coefficient cost audit

## Question and boundary

This retrospective exploratory audit asks whether any of the 2,226 retained
P-256-isogenous curves has a normalized `3b` coefficient cheap enough to justify
a candidate-specific implementation of the Renes-Costello-Batina complete
addition formula. It covers the complete retained registry through low-degree
path depth 17 plus the one-hop prime-degree search through 199. It is not the
entire isogeny class.

The machine-readable result is [`audit.json`](audit.json). It is independently
reconstructed from fourteen frozen candidate registries and the depth-seventeen
retained-union list by
[`../../scripts/verify_retained_coefficient_audit.py`](../../scripts/verify_retained_coefficient_audit.py).

## Typed transformation

Each source model `y^2 = x^3 + a*x + b` is mapped by an `F_p`-isomorphism

```text
(x,y) -> (x/u^2,y/u^3)
a' = a/u^4
b' = b/u^6
```

to the already-certified `a' = 1` or `a' = 3` model. The audit verifies the
fourth-root certificate and transported generator on all 2,226 curves. The
coefficient used twice in each complete addition is then `3b'`.

## Results

P-256's normalized `3b'` has 251 bits, popcount 125, and a binary
double-and-add upper bound of 374 field additions/doublings. Across all retained
curves:

- the minimum coefficient bit length is 243, implying an addition-chain lower
  bound of 242 operations;
- the minimum popcount is 100;
- the best binary double-and-add upper bound is 352 operations;
- zero candidates pass the conservative 32-operation formula-screening gate.

The best binary-bound candidate is
`p256-j-a6abe6e03e490339f47ecb3a6465cfd55f4a06f4c3085a178390c12d45985fe0`
at path depth 12. Its normalized `3b'` is still a 253-bit constant requiring at
least 252 addition-chain steps and 352 steps under the stored binary bound.

## Requirement-to-evidence status

| Obligation | Status | Evidence and limitation |
| --- | --- | --- |
| Reconstruct the retained registry | supported | Exactly 2,226 unique IDs recovered from fourteen hashed inputs. |
| Normalize models and transport generators | supported | All 2,226 fourth-root and target-curve checks pass. |
| Find a low-operation normalized `3b` | refuted within this boundary | Minimum provable chain lower bound is 242, versus the 32-operation screening gate. |
| Coefficient-specialized native speedup | unknown / not benchmarked | No candidate passed the operation-count gate; no wall-time advantage is claimed. |
| Dramatic end-to-end ECDLP speedup | not established | No supplied numeric threshold, new collision, or newly measured path-evaluation cost. |

## Cost and decision

Registry reconstruction and normalization are reusable discovery work. The
audit reports deterministic operation-count bounds rather than wall time.
Per-key isogeny evaluation remains unmeasured for the later paths, and no new
online attack cost is reported.

No coefficient-specialized candidate advances to native timing. This is a
negative result for the retained models and the `a in {1,3}` complete-addition
coefficient family, not a proof against other coordinate systems, formula
families, unknown ECDLP algorithms, deeper paths, or the unenumerated class-group
orbit.
