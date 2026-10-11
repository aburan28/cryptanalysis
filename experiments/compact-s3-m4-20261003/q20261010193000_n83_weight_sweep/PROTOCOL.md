# Q20261010193000: ordinary N83 S3 leaf-weight sweep

Use `EC1N83Ckb1h876c2921cb64`, Q1408's ordinary public point and complete
raw-preimage coset (`Wbab50a1e5f66`), and the same balanced three-link S3
builder and CryptoMiniSat binary in every cell. Rebuild weight five and
require its XCNF digest to equal Q1408's archived ordinary formula. Screen
leaf normal-x Hamming bounds five, six, seven, and eight in that order.
Each solver call uses one thread, seed zero, 100,000 conflicts, and a
180-second external wall cap. Archive full native-XOR XCNF and solver
streams; record child CPU, wall, peak RSS, status, and any four-point
relation. Do not infer a natural-yield rate from capped attempts.

The weight-five factor base is Q1325's exact B=30,977,592, K=186,612
signed/Frobenius columns and enumerated-set digest. For weights six through
eight, this screen changes only the formula leaf bound: actual projected
base B/K/digests remain null and no `IC1` or `fb<B>` name is assigned.
Every SAT model must satisfy the serialized XCNF and independently replay
the selected raw target lift, all signed curve points, cofactor projection,
subgroup membership, and the ordinary public point. This Q proposal uses
`isogeny: "none"` (`ISO0`).

Freeze source, exact input records, binary, and caps before preparation.
Run `python3 sweep.py freeze`, `python3 sweep.py prepare`, then
`python3 sweep.py run --weight W` for each W, and `python3 audit.py`.
Outputs refuse overwrite. Timings on the shared host are exploratory.
