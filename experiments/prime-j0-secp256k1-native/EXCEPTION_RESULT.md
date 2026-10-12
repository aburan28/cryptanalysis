# Cached-add exceptional inputs

The updated native source and control runner were frozen in `f358cbb8`
before release execution. Cached Jacobian addition now handles equal-X
operands: equal points use doubling, opposite points return the identity.
The evaluator tracks these fallback cases separately from ordinary
cached additions because the generic operation count does not apply.

The offline release binary passed **24 direct branch controls** using
the generator, its double and triple, and four pairs of nonzero
projective scales per point. Each same-point result matched independent
Jacobian doubling; each opposite-point result was the identity. The
same binary replayed the original 64, zero/order edge 30, and held-out
256 scalar-input fixtures: all **350 representatives, digit streams,
final outputs, 3,150 prepared seed checks, and saved operation counts**
passed. These fixture cases reported **zero exceptional cached adds**,
so their previous generic operation accounting is unchanged. The
release binary SHA-256 is
`a87a2fdc5cde1f4460825ddfdc1d365bd8bdaa8df04701a03f5fff2046f3a80f`.
`native-exception-result.json` retains source/fixture/binary hashes,
compiler and host details, raw build/control/replay output, and exits.

This is a direct arithmetic branch control on valid secp256k1 points.
The executable remains variable time and has not been reviewed for
secret-scalar safety or arbitrary invalid-point inputs. No CPU timing
or academic novelty is claimed; the host lacks an isolation receipt.
