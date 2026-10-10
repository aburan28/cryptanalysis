# Frozen 80,000-conflict normal4 Gaussian activity gate

This gate tests whether the exact equal-B normal4-counter six-summand query
uses the two selected 8,262-by-13,084 Gaussian matrices during a longer
search. In the preceding [two-repeat gate](../ecc2k130-equalb-gauss-count-20261010/RESULT.md),
both normal4/two transcripts were externally killed before a Gaussian
elimination-call summary. W24/two printed positive calls after about 56,000
conflicts in one repetition; normal4/two reached about 50,000 conflicts in
that run. This preregistered extension stops at **80,000 conflicts**, an
internal 210-second limit, or an external 240-second wall guard, whichever
terminates it first. Exactly one paired `R1` runs two matrices first, then
five matrices on the same raw normal4 formula. A ten-second SIGINT grace
period follows the wall guard to allow a terminal solver summary; a surviving
process is killed. The 4-GiB sampled-RSS guard kills immediately.

[`CONFIG.json`](CONFIG.json) pins source parent commit
`e2f625983ea160f7fa25839b30de66009df4b67a`, parent and source-runner
hashes, the public query-zero input prefix, source curve
`EC1N131Ckb1h136f03e58c98`, `B=11,743,888` subgroup-usable base points,
four exact target lifts, the archived and raw normal4 XCNF hashes, and the
CryptoMiniSat 5.14.7 binary digest. The only solver-policy difference within
the pair is `--maxnummatrices=2` versus `5`; both retain one thread,
9,000-by-14,000 matrix limits, `--autodisablegauss=0`, native XOR, and the
same conflict/time/memory envelope. Formula decompression and hashing occur
before the solver interval. Preserve raw stdout/stderr, commands, hashes,
exit/signal, every guard, wall, sampled RSS, conflicts and matrix activity.

Before running `R1`, commit this protocol, configuration, runner and
independent auditor. Run the source/binary `--check` preflight, save its
output, and do not change the policy after seeing one cell. If the source,
binary, or RSS probe fails, preserve `PRODUCER_FAILURE` evidence and freeze
any retry separately. A solver result lacking a model is `BOUNDED_UNKNOWN`
under its recorded cap, not UNSAT. A SAT output is `SAT_UNVERIFIED` until an
independent curve/subgroup/factor-base relation replay establishes it.

The primary gate is **positive printed elimination calls** for the
normal4/two selected large matrix, with an 8,000-by-12,000-or-larger
component and live search. Absence of a summary stays unknown, even after
the longer cap. Report paired sampled-RSS and conflict progress as stage
diagnostics, with the exact stopping cause and host isolation status.
If a verified relation appears, freeze the 16-query held-out pilot and
subsequent 256-query yield/rank screen before opening those inputs. If both
cells remain bounded, keep those prefixes closed; use the observed conflict
and matrix behavior to choose a separately frozen algebraic or solver-policy
change. A single capped Q0 search is not a relation-yield estimate or an
end-to-end index-calculus comparison.
