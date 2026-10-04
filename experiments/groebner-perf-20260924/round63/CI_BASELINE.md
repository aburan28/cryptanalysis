# Required evidence

Optimized and UBSan replay must match the Python witness producer exactly.
All 14 test groups must pass. The full preflight has 92 records: 40 verified
(including 20 complete PDP queries) and 52 retained algebraic budget failures.
Basis, proof DAG, logical producer/checker counters, first extracted assignment
and extraction counts must agree with the frozen round62 complete-query record.

Every successful PDP record must carry an independently accepted full-point
curve witness. Every timing record must match its preflight identity. All four
exclusive phases must sum to wall time. Every measured source must be tracked
and match its archived receipt. The full panel, not isolated favorable samples,
controls any performance claim. Unavailable or rejected timing remains explicit.
