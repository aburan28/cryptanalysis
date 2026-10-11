# Q20261010174500: ordinary N53 t-weight-four PDP gate

Use the exact `EC1N53Ckb1hf77aab617904` curve, archived ordinary public
target `W74f2979b3e68`, and Q20261010174100's complete t-weight≤4 base
(`B=151792`, `K=1432`, exact packed-key digest). The factor-base policy is
the controlled change from the existing x-weight≤3 Q1410 stage. Preserve
the original target's 428 raw cofactor preimages, map each x to
`t=x/(x²+x+1)`, and deduplicate the resulting t choices. Use four t leaves
of weight≤4, two free t intermediates, and three compact binary-Edwards
`f3` links. This avoids materializing `S5`.

Freeze source, exact base/curve/target receipts, solver binary, formula
bytes, one-thread seed-zero flags, a one-million-conflict cap, and a
120-second external wall cap. Save stdout, stderr, child CPU/RSS, model
status, formula dimensions, and group-law verification. For any SAT model,
lift each t leaf, project by cofactor, require exact-base membership, and
test all 16 sign choices against the same public target. A failed,
censored, or unusable model remains an explicit stage row. Host wall times
are exploratory. The stage is proposal `Q20261010174500`, with null
`candidate_id`/`run_id` and `ISO0`.
