# Local result: public finite-field point addition

## Decision and accounting

**PASS_LOCAL** for the frozen public `P+Q` workload. Both arms execute the
same point pairs through Sage's public operator. The incumbent is the
unmodified field-point method; the candidate uses the existing native NTL
addition for standard supported binary points and a Cython-initialized
standard output for the general finite-field formula. Input generation is
outside the timed operator calls. Every timed output is compared with the
incumbent. The eight cells use 24 balanced arm pairs each and fresh worker
processes; confirmation uses new seeds, an alternate binary modulus, and
nonrouted prime and unsupported-model controls.

| Frozen accepted run | Workload | Public `P+Q` speedup |
| --- | --- | ---: |
| `run-005` primary | Degrees 19/67/131/163, standard binary model | **1.177x** geometric mean; min 1.137x |
| `run-005` binary confirmation | Degree 31, `a=0`; degree 131, alternate modulus | **1.182x** geometric mean; min 1.149x |
| `run-005` prime control | GF(101) | **2.045x** |
| `run-005` unsupported binary control | Degree 19 with nonzero `a3` | **1.482x** |

The accepted run verified **94,080 timed Sage-point outputs**. The initial
native singleton profile was a different API boundary. A guarded public
class override then improved binary cases by about 1.45x but regressed
both nonrouted controls. Two in-method candidates also missed those
controls; the Python-only constructor variant additionally failed parent
identity. All are retained in the archive and excluded from the accepted
speedup.

The final edge suite passed four groups, including exceptional sums,
unnormalized representatives, field-context switches, alternate moduli,
prime and non-NTL finite fields, custom point classes, and the fallback
when the optional native extension is unavailable. Sage's `ell_point.py`
passed all **1,077 doctests**. The helper sets the C-level point parent in
Cython, matching the standard constructor state for verified affine data.

Fresh-process degree-131, 4,096-pair, six-call peak RSS was **262,799,360 B**
for the incumbent and **266,878,976 B** for the candidate: +4,079,616 B,
or about 1.55%, within the frozen 5% limit.

This measures Sage point arithmetic only. The local degree-131 IC reference
uses separate ONB and SAT/F5 paths. A complete IC or DLP speedup requires
a frozen candidate and workload, every exclusive phase cost, and a verified
recovered logarithm under the repository's naming and accounting rules.
