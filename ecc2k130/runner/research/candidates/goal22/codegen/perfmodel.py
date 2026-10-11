"""Predict the walk kernel's rate offline, and say how far to trust the answer.

Three attempts at this went wrong in the same way, so the design is a reaction
to that.  The first counted static PTX instructions in the entry function and
could not see the multiplier at all.  The second counted the call closure and
ranked the occupancy ladder upside down.  The third fit rate = A/(B + spill) to
two measured points and predicted 1030 M it/s where the card delivered 857.

What they share is that nothing checked them.  A static count is not a rate, a
two-point fit is not a model, and neither was ever asked to reproduce a
measurement it had not already been fitted to.  So this tool does three things
differently:

  * It counts what executes, not what is written.  Per-function instruction
    counts are weighted by how many times a walk step actually calls each one,
    which comes from the loop structure rather than from a guess: at batch B a
    step performs 5B - 3 multiplications, one inversion, B squarings, 2B
    Frobenius applications and B Hamming weights.

  * It separates local memory from arithmetic.  ld.local and st.local are the
    thing this kernel is short of; counting them with the ALU work is what hid
    the multiplier's 1918 local operations behind the entry function's 1793.

  * It reports its error against every rate ever measured on this kernel, not
    just the ones it was fitted to.  A model that cannot reproduce the history
    has no business predicting the future, and the table below says plainly
    when it cannot.

It has since been tested on an axis it was not fitted to.  Fitted on three
builds that differ only in unrolling, it was asked about the leaf: leaf 33 runs
1242 instructions and 445 local operations per iteration against the shipped
leaf's 1390 and 348, so instruction count alone prefers it -- which is what the
older cost function in autolab.py did.  Weighting a local operation at twelve
instructions instead says leaf 33 is 15% slower, and the card measured 719.2
against 844.3.  Predicted within 1.1%.

The batch axis went the other way, and a second leaf confirmed it is systematic
rather than noise:

    batch       leaf 0    leaf 33   leaf 0 ahead by
    16           844.3      719.2       17.4%
    32           857.0      748.1       14.6%
    64           864.5      772.8       11.9%

Batch 16 to 64 is worth +2.4% at leaf 0 and +7.5% at leaf 33, and the model
predicts both of those negative.  The counting says a step performs 5B - 3
multiplications over B slots, which is (5 - 3/B)/32 per walk-iteration and
therefore rises with B; the one inversion it amortises away is too small to
cancel that.  So the model has a mechanism that says larger batches cost
slightly more, and the card says they are worth several percent.

Something real is missing and it is not yet known what.  Candidates that have
not been eliminated: independent slots giving the scheduler more to overlap,
which no static count can see; or the entry body being charged once per slot
when part of it runs once per step.  Recording the disagreement is the point --
guessing a mechanism to make the residual smaller would be fitting noise, and
the tool exists because three earlier predictions did exactly that.

What the model can do is rank leaves, which is what it was asked and where it
was right to 1.1% on a 15% gap.  What it cannot do is rank batches.

It then failed on a third axis, and badly.  The stream-Karatsuba schedule cuts
the multiplier from 1918 local operations to 384 and the fitted work per
iteration from 4046 to 1951; the model's mechanism says that halves the cost.
The card ran it at 747.9 against a same-day control of 857.2 -- 12.7% slower.
The static count sees fewer local instructions and cannot see that the
streaming schedule serialises what the original could overlap; a build with
less traffic is not a build with less latency.

That entry is in the table below, and adding it did not merely add a residual:
it broke the fit.  With nine points the least-squares weight on a local
operation goes to 0.0, the worst residual is 29.6%, and the model now ranks
leaf 33 FASTER than leaf 0 -- the one call it had previously got right.  A
one-parameter model cannot hold "fewer local ops was worth +40%" (the unroll
caps) and "fewer local ops was worth -13%" (stream Karatsuba) at the same
time, because the quantity it counts is not the quantity that costs.

So this file is no longer a predictor and does not claim to be.  It is kept
as the record of what was measured and what was predicted, because the gap
between those two columns is the most useful thing it ever produced.  Do not
use its "this build" line to choose a build.

The cost model itself is deliberately small: a walk iteration costs some
arithmetic and some local traffic, and the two are weighted against each other
by one constant.  That constant is fitted, so the tool cannot claim to predict a
rate it has never seen -- it can only say whether a change moves the quantity
the fit says matters, and by how much relative to a build that was measured.

    python3 perfmodel.py --ptx /tmp/sp.ptx

No type hints, camelCase identifiers, no itertools (project convention).
"""

import argparse
import json
import os
import sys

import autolab

# Rates measured on an RTX PRO 6000 Blackwell (sm_120) at batch 32, threads 128,
# minBlocks 2, leaf 0.  Every one of them is a full ::bench run on this kernel.
# A new entry belongs here the moment a build is measured, whether or not it
# agrees with the model -- the disagreements are the point.
# Each entry is (label, batch, leaf, rate).  batch and leaf are here because
# the cost of a build depends on both, and a history that recorded only the rate
# could not be recomputed when the counting changed.
MEASURED = (
    ("full unrolls everywhere", 32, 0, 609.3),
    ("walk loop unrolls capped", 32, 0, 818.0),
    ("field element unrolls capped", 32, 0, 857.2),
    ("batch 16", 16, 0, 844.3),
    ("batch 64", 64, 0, 864.5),
    ("leaf 33 at batch 16", 16, 33, 719.2),
    ("leaf 33 at batch 32", 32, 33, 748.1),
    ("leaf 33 at batch 64", 64, 33, 772.8),
    # TUNING.md: three runs at 747.721/748.012/747.949 against a same-day
    # control at 857.2.  The model predicted the fitted work would halve
    # (4046 -> 1951) and the card ran 12.7% SLOWER.  Different GPU allocation
    # and source digest from the control, so not a single-variable experiment,
    # but the direction is not in doubt.
    ("stream Karatsuba at batch 32", 32, 0, 747.9),
)


def closureCost(parts, entry):
    """Instructions and local-memory operations for a function and its callees."""
    instrs = local = 0
    for name in autolab.reachableFrom(parts, entry):
        i, l = autolab.countPtx(parts[name])
        instrs += i
        local += l
    return instrs, local


def findFunction(parts, needle):
    for name in parts:
        if needle in name:
            return name
    return None


def stepCounts(batch):
    """How many times one walk step calls each routine.

    Read off the two passes in Kernel::run.  The forward pass does one
    multiplication per slot after the first, building the Montgomery product
    chain.  The backward pass does two per slot after the first to walk the
    inverse back down the chain, then one for lambda and one for the y
    coordinate on every slot.  One inversion covers the whole batch."""
    return {
        "mul": (batch - 1) + 2 * (batch - 1) + 2 * batch,
        "inv": 1,
        "sqr": batch,
        "sigmaJ": 2 * batch,
        "hamming": batch,
    }


def dynamicPerIteration(ptxPath, batch, lanes=32):
    """Instructions and local operations one walk step issues, per walk-iteration.

    A step advances batch * lanes walks by one iteration, so dividing by that is
    what makes the number comparable across batch sizes."""
    return dynamicFromParts(autolab.splitFunctions(open(ptxPath).read()), batch, lanes)


def dynamicFromParts(parts, batch, lanes=32):
    """As dynamicPerIteration, from PTX a caller has already split.

    autolab.py builds the PTX and splits it anyway; making it re-read and
    re-split a file it is holding in memory just to get a cost was the only
    thing keeping the two tools on different cost models."""
    walk = findFunction(parts, "_Z13eccWalkKernel")
    if walk is None:
        return None
    names = {
        "mul": findFunction(parts, "3mulEPKjS3_Pj"),
        "inv": findFunction(parts, "3invEPKjPj"),
        "sqr": findFunction(parts, "3sqrEPKjPj"),
        "sigmaJ": findFunction(parts, "6sigmaJ"),
        "hamming": findFunction(parts, "7hammingIjEEvPKT_PS1_"),
    }
    counts = stepCounts(batch)
    instrs = local = 0
    detail = []
    for role, name in sorted(names.items()):
        if name is None:
            # sqr is a permutation the generator may inline away entirely
            detail.append((role, 0, 0, counts.get(role, 0), 0, 0))
            continue
        i, l = closureCost(parts, name)
        n = counts.get(role, 0)
        instrs += i * n
        local += l * n
        detail.append((role, i, l, n, i * n, l * n))
    # The entry's own body runs once per slot for each of the two passes; its
    # callees are already counted above, so take the entry alone.
    ei, el = autolab.countPtx(parts[walk])
    instrs += ei * batch
    local += el * batch
    detail.append(("walk body", ei, el, batch, ei * batch, el * batch))
    walks = batch * lanes
    return {"instrs": instrs / float(walks), "local": local / float(walks),
            "detail": detail, "walks": walks}


def fitWeight(points):
    """One constant: what a local-memory operation costs in units of arithmetic.

    Least squares on 1/rate = c * (instrs + w * local), which is the smallest
    model that can express "local traffic is the expensive part" without
    inventing structure the three data points cannot support."""
    best = None
    w = 0.0
    while w <= 200.0:
        num = den = 0.0
        for instrs, local, rate in points:
            work = instrs + w * local
            num += work / rate
            den += work * work
        c = num / den if den else 0.0
        err = 0.0
        for instrs, local, rate in points:
            pred = 1.0 / (c * (instrs + w * local)) if c else 0.0
            err += (pred - rate) ** 2
        if best is None or err < best[0]:
            best = (err, w, c)
        w += 0.05
    return best[1], best[2]


def fittedWeight(historyPath=None):
    """The local-operation weight the measured history supports, or None.

    None means the history is too thin to fit -- and a caller that cannot get a
    weight should say so and fall back, not invent one.  Three points is the
    floor because a two-point fit through a two-parameter model is not a fit,
    which is exactly how an earlier version of this came to predict 1030 M it/s
    against a measured 857."""
    if historyPath is None:
        historyPath = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "perfhistory.json")
    if not os.path.exists(historyPath):
        return None
    hist = json.load(open(historyPath))
    points = []
    for label, _batch, _leaf, rate in MEASURED:
        h = hist.get(label)
        if h is not None:
            points.append((h["instrs"], h["local"], rate))
    if len(points) < 3:
        return None
    return fitWeight(points)[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ptx", default="/tmp/sp.ptx",
                    help="PTX for the build to predict")
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--history", default="perfhistory.json",
                    help="per-build (instrs, local) for the measured rates")
    args = ap.parse_args()

    got = dynamicPerIteration(args.ptx, args.batch)
    if got is None:
        print("no walk kernel in %s" % args.ptx)
        return 1

    print("dynamic cost of one walk step at batch %d, per walk-iteration" % args.batch)
    sumI = sum(d[4] for d in got["detail"]) or 1
    sumL = sum(d[5] for d in got["detail"]) or 1
    print("  %-12s %8s %8s %6s %12s %7s %12s %7s" %
          ("routine", "instrs", "local", "calls", "instrs tot", "share", "local tot", "share"))
    for role, i, l, n, ti, tl in sorted(got["detail"], key=lambda d: -d[4]):
        print("  %-12s %8d %8d %6d %12d %6.1f%% %12d %6.1f%%"
              % (role, i, l, n, ti, 100.0 * ti / sumI, tl, 100.0 * tl / sumL))
    print("  %-12s %8s %8s %6s %12.0f %7s %12.0f" %
          ("per walk-it", "", "", "", got["instrs"], "", got["local"]))

    if not os.path.exists(args.history):
        print("\nNo history at %s, so nothing to validate against.  Record the "
              "current build with --history once its rate is measured." % args.history)
        return 0

    hist = json.load(open(args.history))
    points = []
    for label, batch, leaf, rate in MEASURED:
        h = hist.get(label)
        if h is None:
            continue
        points.append((h["instrs"], h["local"], rate))
    if len(points) < 3:
        print("\nOnly %d of %d measured builds have costs recorded; a fit on "
              "fewer than three cannot be checked against a point it did not "
              "see." % (len(points), len(MEASURED)))
        return 0

    w, c = fitWeight(points)
    print("\nfit: one local operation costs %.1f instructions" % w)
    print("  %-32s %9s %9s %8s" % ("build", "measured", "predicted", "error"))
    worst = 0.0
    for (label, _b, _l, rate), (instrs, local, _) in zip(MEASURED, points):
        pred = 1.0 / (c * (instrs + w * local))
        e = 100.0 * (pred - rate) / rate
        worst = max(worst, abs(e))
        print("  %-32s %9.1f %9.1f %+7.1f%%" % (label, rate, pred, e))
    pred = 1.0 / (c * (got["instrs"] + w * got["local"]))
    print("\nthis build: %.0f M it/s predicted" % pred)
    print("Every point above was used to fit, so the errors are a floor on the "
          "model's honesty, not a test of it.  Worst residual %.1f%%; treat a "
          "prediction closer than that to a decision boundary as a coin flip."
          % worst)
    return 0


if __name__ == "__main__":
    sys.exit(main())
