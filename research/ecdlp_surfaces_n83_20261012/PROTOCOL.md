# GF(2^83) surface and subgroup checks — 2026-10-12

Request: apply the surface-tool workflow at n=83 for Koblitz a=0 or a=1.
Check both curves `y^2+xy=x^3+a*x^2+1`, with the recorded polynomial basis
`z^83+z^45+z^2+z+1`. This is a correctness run, not an IC or rho benchmark.

Frozen source: `aburan28/crypto` commit
`8f7f796d694fd41b4db81b25c1aff3632d012c65`,
`src/cryptanalysis/koblitz_index_calculus.rs:975`–1054. The a=0 generator is
`(0x477f77103dfad59850800,0x2fa5e737d542c4e4fd5c3)` with
`r=2417851639230796216685689`, cofactor 4. The a=1 generator is
`(0x68a212cfe19a809fe0598,0x244a245ea0b17d8cc8297)` with
`r=8569786107849059`, cofactor 1128547018. Use public demonstration targets
`Q=37P`; disclose the known witness. Preserve the existing Sage proof receipt
for r under `research/f6_wide_n83_20261004/prime-check.txt`, with source link
and digest. No new Sage run is requested or represented as completed.

The archived a=1 benchmark in `docs/ic/boundary_targets.json` uses a different
polynomial basis and different point encodings. Do not substitute its points,
reuse its curve identity, or claim a basis conversion without a verified map.

Implement characteristic-two arithmetic and the quartic embedding natively in
the standalone Rust package. Verify the modulus by Rabin's irreducibility
criterion. Compute the Koblitz order by the Frobenius trace recurrence and
check it against `r*h`. Check P, Q, annihilation, the supplied scalar relation,
projective round trips, Frobenius orbits, and a surface-only rejection control.
Reuse the cited primality proof for a=0 and repeat a deterministic u64 prime
test for a=1; distinguish those evidence sources in the output.

Classify the finite quadric pencil analytically rather than enumerate its
2^83 parameters. Validate the characteristic-two classification against
independently counted points on small fields. Ship evaluated IDC1 records
for exact integer lifts of the characteristic-two polynomial identities;
state how reduction modulo 2 is used. Preserve old odd-prime fixtures.

Acceptance: native tests, formatting, warning-free Clippy, deterministic replay
of both n=83 JSON outputs, positive and negative controls, exact field/curve
records, source-linked report, editable diagram, and inspected PDF. Record the
host and source/binary digests. No timing comparison, solver advantage,
arbitrary abelian-surface map, or general large-q filter is established.

Run status: protocol frozen before implementation; validation and results will
be recorded separately. Preserve failed attempts and the root-library gate
failure if it remains present. Conductor is unavailable in this environment.

Addendum before the final recorded run: also check the opposite product
`E_(1-a) x E_(1-a)` as a candidate destination. Reject it when the same-q
Frobenius quadratics are coprime and the source prime does not divide the
target elliptic order. This is a necessary-condition obstruction for this
specific destination, not a general abelian-surface search. Add its polynomial
difference identity to the IDC1 replay.

Also record the direct inclusions into the mixed `E_0 x E_1`, with each source
in its matching component. Certify the integer Frobenius product identity.
These explicit products keep the source ECDLP on an elliptic factor; no
solver benefit is inferred.
