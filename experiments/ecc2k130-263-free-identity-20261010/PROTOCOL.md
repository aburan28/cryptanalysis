# Q1420 free-selector field-identity gate

The W24 leaf equations imply `alpha*x*z=(x+alpha)^2` without fixing any
selector bit. This gate tests whether adding that redundant equation to the
archived native-XOR XCNF changes search on one all-free leaf. It uses source
and oriented degree-263 descendant circuits, the same W24 bases
(`B=16,772,828` usable points each), one fixed-witness control and the
public Q0 ordinary query per curve. The ordinary query has no fixed selector,
x, or z units. Both base and strengthened formulas are solved afresh in
the frozen order.

For leaf 0, append one fresh AND variable `a[i,j]=x[i]&z[j]` for every
`0<=i,j<131`, encoded by three ordinary clauses. For each field-output
bit, append one native-XOR equation equating the reduced product
`alpha*x*z` to the GF(2)-linear bit of `x^2+alpha^2`. The coefficients
come from the pinned polynomial basis and modulus
`t^131+t^13+t^2+t+1`. This adds 17,161 variables, 51,483 ordinary
clauses, and 131 native-XOR records. It does not change the named input
variables, target lifts, sign choices, or subgroup projection.

Freeze the code, protocol, and source pins before creating the eight complete
XCNF input hashes. Commit those hashes before any solver run. Controls use
the archived selector-derived x0 units and 20,000 conflicts / 30-second
internal / 40-second external wall caps. Ordinary Q0 uses zero extra units,
2,000 conflicts / 120-second internal / 45-second external wall caps, the
same four Gaussian limits as the previous Q1420 panel. All runs use one
thread, pinned CryptoMiniSat 5.14.7, native XOR, and sampled 4-GiB RSS
guard through Darwin `libproc.proc_pidinfo`. Interleave base and identity
per curve and input kind. Record
construction, full-input hashes, solver wall/CPU, sampled memory, caps,
stdout/stderr, and model verification.

The independent audit reconstructs every formula from the pinned archives,
checks each transcript and SAT assignment against all ordinary clauses and
native XORs, then replays any six-leaf signed group sum on the exact curve.
A bounded or wall-censored solve is `BOUNDED_UNKNOWN`. Timings on the
unisolated host are exploratory. The panel is a PDP-stage diagnostic:
relation yield, rank, matrix solving, target descent, and single-target
IC/rho comparison remain separate gates. Q1420 retains
`candidate_id: null` until those gates are measured.

The first frozen input manifest used a `ps` RSS sampler. A sandbox denial
stopped its first launch before any solver process began. The corrected
`libproc` runner must be committed and the identical eight formula hashes
refrozen before any solve; retain the first manifest and traceback as a
prelaunch failure record.
