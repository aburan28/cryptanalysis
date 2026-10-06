# Reordering independent algebraic certification

This experiment changes only the schedule of an exact checker's obligations.
It does not change polynomial arithmetic, reduction rules, field-pair handling,
proof interpretation or the condition for accepting a result. The opt-in schedule
checks reverse input inclusion, reducedness and ordinary/Boolean-field critical
pairs before replaying the original-equation derivation DAG. Every successful
answer must still pass all of these checks. A completed basis without a valid
original-input derivation remains rejected.

The candidate is generated from a hash-pinned copy of round11's independent
checker. It retains the checker's hash-set parity arithmetic, separate from the
producer. The source generator extracts the four obligation blocks and wraps
them in lambdas; only call order, phase bookkeeping and the schedule argument
change. Proof values keep call-local ownership. Schedule zero reproduces the
legacy order; schedule one postpones derivation. The original library is rebuilt
unchanged as an independent execution baseline. The default query schedule is
legacy, and this experiment does not promote automatic dispatch.

For a fully accepted result, both schedules execute the same arithmetic and have
the same logical counters and retention requirement. Earlier rejection can avoid
proof replay and free more of the shared checker budget for a fresh F4 fallback.
A budget failure can therefore change into a mathematical rejection. Errors need
not report the same first reason across schedules. A valid basis with a malformed
proof may become slower to reject: the algebraic checks precede its bad proof.
All cases remain bounded by the declared checker work limit. There is no claim
that reordering improves every input or changes asymptotic complexity.

The frozen panel preserves round92's 14 families and 28 inputs. Six arms compare
legacy/completion-first checking for fresh F4 and reused degree-one Macaulay
layouts (degree zero for linear families), plus the same bounded interpreted F5B
and native evaluation/interpolation comparators. The F4 and matrix producers,
packed input representation, resource limits, proofs and layouts are unchanged.
All accepted answers are independently replayed by a separate Python algebraic
checker; inputs through 20 variables also use the exhaustive zero-set/staircase
oracle within its declared cache limits.

The complete algebra interval begins with the same immutable full-support packed
ANF and includes producer work, every failed attempt, all independent checking,
fresh F4 fallback and basis/proof export. Packing and reusable layout preparation
are separate. Controls run once per optimized/UBSan build. The exploratory panel
has two warmup orders followed by six balanced observation orders; observations
are never replaced. This is not a complete curve query or single-target IC run.
No isolated host receipt is available, so timing eligibility is false and all
qualified/aggregate/online speedups remain null.

Correctness controls require exact legacy/schedule-zero behavior, accepted
counter parity, every small work limit, retention thresholds, malformed proof
and native ABI rejection, error recovery, concurrent checker calls, and ring
boundaries through 64 variables. Existing Macaulay integration controls run under
the new schedule. Four frozen 12/16-variable dense candidates must reject before
any proof replay and independently fail the exhaustive basis criterion. Native
libraries are rebuilt on each CI platform; archived libraries are never executed
by artifact audits. GPU behavior and the original complete-query/IC gates remain
outside this component experiment.
