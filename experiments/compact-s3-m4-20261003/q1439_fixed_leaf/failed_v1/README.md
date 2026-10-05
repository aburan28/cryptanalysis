# Q1439 preliminary v1 archive

These four stage rows are preserved because the original frozen workload
record omitted the ordinary anchor seed and included solver caps in the
workload hash. Both planted controls verified; both ordinary attempts timed
out at 60 seconds. The experiment source, protocol, runtime receipt, XCNFs,
stdout/stderr, run receipts, and archive replay retain their original hashes.
The [custody record](custody.json) checks those hashes and marks this
identity superseded. Use the corrected parent `protocol.json` and `runs/`
for the named Q1439 comparison. Do not pool the two sets of runs as eight
independent ordinary targets: each pair repeats the same public point and
anchor under a corrected workload ID.
