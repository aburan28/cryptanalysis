# Prime-proof provenance correction

The initial `n83.json` and `cryptanalysis-n83.json` receipts described prime
proof provenance generically as a reused historical receipt. The linked Sage
receipt concerns the wide a=0 prime. The a=1 order is known prime from the
earlier surface study's deterministic u64 check; the first new checker did
not itself repeat that check and its shared description was too broad.

The final source now explicitly re-runs the existing deterministic u64
seven-base Miller–Rabin routine for a=1, fails closed if it rejects, and
reports that result separately. The a=0 receipt is still honestly reused.
`n83-final.json` and the corresponding mirror receipt supersede the initial
prime-provenance descriptions. Original records are retained unchanged.

No curve, field, point, divisor, subgroup order or geometric proof changed.
Source hashes and the final implementation revision bind the additional
primality check. This is a validation/provenance correction, not a new
performance run or a proof of a larger class of subgroup orders.
