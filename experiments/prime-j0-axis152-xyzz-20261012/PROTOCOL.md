# Radix-152 XYZZ accumulator replay protocol

The candidate keeps the merged radix-152 representative, digit atlas,
69,698 affine table entries, selected point stream, unit grouping, and
binary affine output. It replaces the ordinary Jacobian accumulator with
the existing Sutherland XYZZ accumulator and its Solinas unit rotation.
The reference and candidate are separate disposable builds of the same
locked Rust crate; the candidate builder changes exactly three evaluator
expressions in an included source copy and records every source hash.

For a nonidentity, nonexceptional mixed addition, the implemented
Jacobian formula uses eight general field products and three squares;
the existing XYZZ formula uses eight general products and two squares.
This source-level difference predicts one fewer square per ordinary
addition. Identity initialization and exceptional branches have separate
paths. Complete scalar timing remains a separate measurement.

The merged second radix-152 holdout is the development control. Freeze
this protocol, candidate builder, independent fixture generator, and
differential checker in a commit before drawing the new 512-case panel.
The new generator uses seed `20261012231`, reduces each 256-bit draw
modulo the secp256k1 subgroup order, checks disjointness from the two
radix-152 holdouts and the radix-416 holdout, and computes every expected
point by the independent binary projective multiplier.

The acceptance gate is exact equality of every public point and every
JSON result row between the reference and candidate, with independent
point validation on all 512 new cases. Retain input/source/binary hashes,
the development result, the new-panel result, and the first failed
builder invocation caused by assuming the included evaluator lived in the
copied parent module. A Linux CI job rebuilds both locked binaries and
rechecks the saved semantic receipt. CPU timing ratios require the
repository's isolated benchmark service and a host that passes its
preflight; this replay checks correctness and the formula-level change.

## Portability amendment before the second new panel

The first replay receipt included a hash of the generated Rust module,
whose `include!` path embeds the local checkout and cannot match Linux.
The candidate evaluator and first new input panel remain frozen. The
checker now binds the portable base and included-source hashes in its
semantic receipt and keeps generated-module hashes in the local build
receipt. Freeze this revised checker and `holdout2.py` before drawing
seed `20261012232`. The second new panel must be disjoint from all three
listed prior controls, including this experiment's first holdout, and
pass the same exact reference/candidate/independent-point gate.
