# Public-target replay results

The native curve-witness producer and independent Python checker pass the frozen
correctness panel. No speedup is claimed: this host did not admit a timing trial.

The final local run used Apple M4 Pro ARM64, macOS 26.6, Python 3.13.1, with
native libraries rebuilt in optimized and UBSan modes. Results:

| Check | Result |
| --- | --- |
| Unit test groups | 14 passed |
| Full-query preflight records | 92 |
| Verified records | 40, including 20 complete PDP queries |
| Retained inconclusive records | 52 algebraic budget failures |
| Independently audited algebraic proofs | 7 distinct proofs |
| Source, generated-code, binary and resource bindings | 199 |
| Measured source files bound in the build receipt | 163 |
| Qualified timing trials / timed queries | 0 / 0 |
| Load admission | 2 rejections; 31 scheduled trials unrun |
| Observed one-minute load / frozen threshold | 40.3101 / 14 |
| Further 2× target | Unestablished |

Differential arithmetic controls cover degrees 3, 5, 9, 31 and 63, randomized
points, non-unit curve coefficients, sign limits 0/1/7/8/256, 64 Boolean
coordinates including bit 63, cancellation, doubling and zero x-coordinates.
Malformed inputs and altered points, slopes, intermediate results, equations,
assignments and public targets are rejected. Native calls agree with the
Python producer in both optimized and UBSan builds. Concurrent calls and close
are serialized. The checker passes with inversion, lifting and group addition
replaced by functions that raise, demonstrating their absence from its path.

The full-query panel preserves the round62 basis, proof DAG, logical algebraic
counters, first solution and extraction counts. The five primary controls all
find assignment 6. Their fresh curve searches lift three points each and check
respectively 4, 1, 2, 1 and 4 sign patterns. The five controls contain three
full public target points (two x-coordinates); they are not five independent
random targets. Both new arms perform identical full-point checks.

The earlier replay profile retained 50 successful calls across those five
controls. It counted 320 inversions, 50 field constructions, 50 irreducibility
checks and 29,430 polynomial multiplication calls. Those are **instrumented
call-count diagnostics**, not a qualified speed ratio. The old verifier also
reconstructed the target from planted points inside each replay. The new
comparison puts ring validation and fixture construction outside both arms;
its public-input contract must not be conflated with historical timing panels.

`results/` retains the final receipt, preflight, timing rejection, independent
audit, logs, source snapshot and profile. It also retains the sandbox host-info
failure, the incorrect algebra-only assignment-comparison attempt, and the
intermediate successful run before strict input guards were added. None of
those earlier attempts ran qualified timing queries. The final measurement
plan SHA-256 is
`6ac7ee7f47e9be41062f60319ee74d69230520196606ff511c049d7e2267e2cb`.

CI must rebuild and repeat this experiment on Linux x86-64 and hosted macOS
ARM64 before any compatibility or performance claim for those environments.
This remains a PDP-stage correctness experiment. It does not measure natural
relation yield, a complete one-target IC recovery, GPU performance, or a novel
asymptotic Gröbner algorithm. The full IC candidate and online speedup remain
null. CPU dispatch outside this explicit experiment is unchanged.
