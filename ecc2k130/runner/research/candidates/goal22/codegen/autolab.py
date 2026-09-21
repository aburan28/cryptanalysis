"""Offline search over the walk kernel's build space.

What this can and cannot see is the whole design.  ptxas is deterministic and
needs no GPU, so registers, spill traffic, stack frame and the occupancy that
follows from them are all measurable here.  Wall-clock is not.  So this does not
pick a winner -- it produces the few configurations worth measuring, and
`modal run modal_app.py::autotune` measures those instead of a full cross
product.  Six builds on a real card beats a hundred and forty-four.

The tension it exists to map is occupancy against spilling.  Asking ptxas for
more resident blocks makes it use fewer registers per thread, and past a point
it pays for them by spilling to local memory -- which for this kernel is already
the dominant cost.  Where that trade turns is a curve, and the curve is
something an offline tool can draw even though the optimum on it is not.

Nothing here is a substitute for a measurement.  The session that produced it
had a static analysis say a 66-word leaf was better while the only hardware
available said it was worse, for a reason -- register file size -- that does not
apply to the target.  Treat the ranking as a shortlist, never as a result.

The ranking is at least no longer a second, unchecked opinion.  The cost was a
static count of the call closure, which charges FieldBs::mul and FieldBs::inv
alike even though a step calls the first 157 times and the second once; on that
count the leaf-33 multiplier looked better, and the card ran it 15% slower.  It
now defers to perfmodel.py, which weights each routine by how often a step calls
it and weights local traffic against arithmetic with one constant fitted to
eight measured rates -- and which, asked about that same leaf, was right to 1.1%.
The occupancy term is still uncalibrated, and a shortlist that fell back to the
static count says so in `costBasis`.

Because the shortlist is a Pareto front, a knob that works can dominate every
other row and leave the front a single build -- a GPU run with no baseline in
it.  The knobs-off build at the base point is added back for that reason: a
sweep needs its own control, on the same card, from the same image.

    python3 autolab.py --threads 64,128,256 --min-blocks 1,2,3,4 --leaf 0,17,66

Two ways to get PTX out.  With a CUDA toolkit installed, `--compiler nvcc` is
the honest one: nvcc emits PTX for the target architecture directly.  Without
one, `--compiler clang` needs only a CUDA include tree and a standalone ptxas
(see the check-cuda target in the Makefile for the pip route that supplies
both), but clang 18 will not emit sm_120, so it compiles for sm_90 and retargets
the PTX header before handing it to ptxas.  That is sound for this kernel, which
uses no architecture-specific instructions, and unsound in general.  Prefer nvcc
where it exists; `modal run modal_app.py::autolab` runs it in a CPU container
that has one.

Three axes are not sizes.  streamKarat rewrites the Karatsuba schedule to keep
one subproduct live instead of three, smemSpill emits the pragma that moves part
of the spill frame into shared memory, and globalCg changes the cache level a
global load may hit.  They are searched as one more spoke of the star, at the
base size point, because the first is a property of the multiplier the way the
leaf is and the other two do not interact with size at all.

They are not equally visible from here, and the report says which is which.
streamKarat shows up in full: it cuts the multiplier's local-memory operations
from 1918 to 384 and its instructions from 8140 to 6063, which is exactly the
routine perfmodel.py blames for 84% of a step.  smemSpill shows up as smem bytes
and as a spill count ptxas then reports negative, having subtracted what it
relocated.  globalCg does not show up at all -- it changes one assembler flag,
not one instruction, so every static metric is identical to its knob-off row by
construction.  It is carried to the GPU shortlist anyway, marked, because an
axis this tool cannot rank is still an axis, and dropping it silently would be
worse than admitting it.

One axis deliberately absent: ptxas --maxrregcount.  It was measured against
__launch_bounds__ at 255, 168, 128, 80 and 64 registers and produced
byte-identical spill counts at every one, so it is the same lever reached by a
different spelling, not a second dimension.  The kernel always carries launch
bounds, which take precedence over the flag anyway.

No type hints, camelCase identifiers, no itertools (project convention).
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REGS_PER_SM = 65536
MAX_WARPS_PER_SM = 64
CACHE_SCHEMA = 4


def run(cmd, cwd=None, timeout=1800):
    p = subprocess.Popen(cmd, shell=True, cwd=cwd, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True)
    try:
        out = p.communicate(timeout=timeout)[0]
    except subprocess.TimeoutExpired:
        p.kill()
        return 1, 'timeout'
    return p.returncode, out


def regenerate(leaf, regs, cudaPath):
    arg = ('--leaf %d' % leaf) if leaf else ('--regs %d' % regs)
    rc, out = run('python3 gen.py --out ../generated %s' % arg, cwd=HERE)
    return rc == 0, out


GEN_DIR = os.path.join(ROOT, 'generated')


def saveGenerated():
    """The generated headers as they are now, to put back when the search ends.

    Searching the leaf axis rewrites tracked files in generated/, and a run
    leaves them at whatever it happened to build last -- so the next thing
    compiled in that tree gets a leaf nobody chose.  That is not hypothetical:
    it silently made a knob comparison in this session a leaf-33 build measured
    against a leaf-66 one, a 15% difference in the wrong direction, reported as
    if it were the knob.

    Keeping the bytes rather than re-deriving the leaf is deliberate.  Asking
    gen.py for leaf N and asking it to choose N from a register budget are
    different requests that happen to agree today, and restoring by the wrong
    one would leave a tree that looks right and is not.  Bytes cannot be wrong
    about which of the two produced them."""
    saved = {}
    if not os.path.isdir(GEN_DIR):
        return saved
    for name in sorted(os.listdir(GEN_DIR)):
        path = os.path.join(GEN_DIR, name)
        if os.path.isfile(path):
            saved[name] = open(path, 'rb').read()
    return saved


def restoreGenerated(saved):
    """Put back exactly what saveGenerated held.  Returns the files rewritten."""
    changed = []
    for name, blob in saved.items():
        path = os.path.join(GEN_DIR, name)
        if not os.path.exists(path) or open(path, 'rb').read() != blob:
            open(path, 'wb').write(blob)
            changed.append(name)
    return changed


# The build knobs that are not sizes.  Each is off by default and each reaches
# the toolchain by a different route, which is the whole reason they need
# describing rather than just listing:
#
#   streamKarat  a source define.  Karatsuba keeps one subproduct live at a
#                time instead of three, so it is aimed straight at the thing
#                perfmodel.py blames for 89% of the instructions and 84% of the
#                local traffic.  Fully visible offline.
#   smemSpill    a source define that emits .pragma "enable_smem_spilling",
#                which moves part of the spill frame from local memory into
#                shared.  Visible offline as smem bytes, and as a spill count
#                that ptxas then reports negative -- see parseMetrics.
#   globalCg     a ptxas flag, --def-load-cache=cg.  It changes the cache level
#                a global load is allowed to hit, not a single instruction, so
#                the static metrics cannot see it at all and this tool cannot
#                rank it.  It is here so that a search can still carry it
#                through to the GPU rather than pretending the axis does not
#                exist; `staticallyVisible` is False and the report says so.
KNOBS = (
    ('streamKarat', 'ECC_STREAM_KARAT', True),
    ('smemSpill', 'ECC_SMEM_SPILL', True),
    ('globalCg', None, False),
)
KNOB_NAMES = tuple(k[0] for k in KNOBS)


def knobKey(knobs):
    """A stable short label, and '-' when nothing is on."""
    on = [n for n in KNOB_NAMES if knobs.get(n)]
    return '+'.join(on) if on else '-'


def compile(batch, threads, minBlocks, arch, cudaPath, ptxas, clang, compiler,
            knobs=None):
    knobs = knobs or {}
    ptx = '/tmp/autolab.ptx'
    defs = '-DECC_BATCH=%d -DECC_THREADS=%d -DECC_MINBLOCKS=%d' % (batch, threads, minBlocks)
    for name, macro, _visible in KNOBS:
        if macro is not None:
            defs += ' -D%s=%d' % (macro, 1 if knobs.get(name) else 0)
    ptxasFlags = '--def-load-cache=cg' if knobs.get('globalCg') else ''
    if compiler == 'nvcc':
        rc, out = run('%s/bin/nvcc -ptx -arch=compute_%s -O3 -std=c++17 %s '
                      '-o %s src/ptxspike.cu' % (cudaPath, arch, defs, ptx), cwd=ROOT)
        if rc != 0:
            return None, 'nvcc: ' + out[-400:]
        src = open(ptx).read()
    else:
        rc, out = run('%s -x cuda --cuda-device-only --cuda-gpu-arch=sm_90 '
                      '--cuda-path=%s -nocudalib -Wno-unknown-cuda-version -O3 -std=c++17 '
                      '%s -S -o %s src/ptxspike.cu' % (clang, cudaPath, defs, ptx), cwd=ROOT)
        if rc != 0:
            return None, 'clang: ' + out[-400:]
        # clang 18 will not emit sm_120; the PTX is architecture neutral for this
        # code, so retarget it and let ptxas do the real architecture work
        src = open(ptx).read()
        src = re.sub(r'^\.version 8\.3', '.version 8.7', src, flags=re.M)
        src = re.sub(r'^\.target sm_90', '.target sm_%s' % arch, src, flags=re.M)
        open(ptx, 'w').write(src)
    rc, log = run('%s -arch=sm_%s -O3 -v %s %s -o /tmp/autolab.cubin'
                  % (ptxas, arch, ptxasFlags, ptx))
    if rc != 0:
        return None, 'ptxas: ' + log[-400:]
    return (src, log), None


# A PTX instruction is a statement and a statement ends in a semicolon, except a
# call, whose argument list both compilers spread over several lines -- so calls
# are counted separately.  Register and parameter declarations start with a dot
# and are not instructions; nor are the bare identifier lines inside a call's
# argument list, which a looser rule counted, inflating a configuration in
# proportion to how many calls it makes -- which is the thing being compared.
INSTR_RE = re.compile(r"\n\t(?!\.)[@a-z][^\n]*;")
CALL_RE = re.compile(r"\bcall\.uni\b")
LOCAL_RE = re.compile(r"(?:ld|st)\.local")


def countPtx(part):
    instrs = len(INSTR_RE.findall(part)) + len(CALL_RE.findall(part))
    return instrs, len(LOCAL_RE.findall(part))


def splitFunctions(src):
    """Map every PTX function name to its text.

    A name appears twice, once as a forward declaration and once as the
    definition; the definition comes second and wins.  Splitting on function
    boundaries and matching the name is what makes this reliable -- a plain
    search for the kernel's name finds it first in the file header comment, and
    then measures the comment."""
    parts = {}
    for part in re.split(r"\n(?=\.(?:visible|weak) \.(?:entry|func))", src):
        head = re.match(r"\.(?:visible|weak) \.(?:entry|func)\s*"
                        r"(?:\([^)]*\)\s*)?([A-Za-z0-9_$]+)", part)
        if head is not None:
            parts[head.group(1)] = part
    return parts


def reachableFrom(parts, entry):
    """Names the entry can reach, following call.uni edges transitively.

    The walk kernel calls out to __noinline__ helpers -- the multiplier above
    all -- so counting only the entry function is blind to exactly the knob this
    tool exists to turn.  Counting the whole module is wrong the other way: it
    charges the walk for the init and reseed kernels, which run once.  The call
    closure is the code a walk step actually issues."""
    seen, stack = set(), [entry]
    while stack:
        n = stack.pop()
        if n in seen or n not in parts:
            continue
        seen.add(n)
        stack.extend(re.findall(r"call\.uni\s*(?:\([^)]*\)\s*,\s*)?([A-Za-z0-9_$]+)\s*,",
                                parts[n]))
    return seen


# ptxas reports the walk kernel's frame like this, and every field can move:
#
#   12672 bytes stack frame, 16 bytes spill stores, 16 bytes spill loads
#   ptxas info : Used 255 registers, used 0 barriers, 12624 bytes cumulative
#                stack size, 7168 bytes smem
#
# The spill counts go NEGATIVE under enable_smem_spilling -- ptxas subtracts the
# part of the frame it relocated into shared memory rather than reporting the
# two pools separately.  A \d+ pattern therefore did not fail on a smem-spilling
# build, it simply did not match, parseMetrics returned None, and the knob
# looked like a compile failure.  Hence -?\d+, and hence smem being captured:
# a build that moved bytes out of local memory has not made them free, it has
# made them cheaper, and the two need telling apart.
ENTRY_RE = re.compile(
    r"Compiling entry function '_Z13eccWalkKernel.*?"
    r"(-?\d+) bytes stack frame, (-?\d+) bytes spill stores, "
    r"(-?\d+) bytes spill loads"
    r".*?Used (\d+) registers([^\n]*)", re.S)
SMEM_RE = re.compile(r"(\d+) bytes smem")


def parseMetrics(src, log, threads):
    m = ENTRY_RE.search(log)
    if not m:
        return None
    stack, spillSt, spillLd, regs = (int(x) for x in m.groups()[:4])
    smem = SMEM_RE.search(m.group(5))
    smemBytes = int(smem.group(1)) if smem else 0
    parts = splitFunctions(src)
    entry = None
    moduleInstrs = moduleLocal = 0
    for name, part in parts.items():
        n, l = countPtx(part)
        moduleInstrs += n
        moduleLocal += l
        if name.startswith('_Z13eccWalkKernel'):
            entry = name
    walkInstrs = walkLocal = kernelInstrs = kernelLocal = 0
    if entry is not None:
        kernelInstrs, kernelLocal = countPtx(parts[entry])
        for name in reachableFrom(parts, entry):
            n, l = countPtx(parts[name])
            walkInstrs += n
            walkLocal += l
    blocks = REGS_PER_SM // (regs * threads) if regs * threads else 0
    warps = blocks * threads // 32
    return {'registers': regs, 'stack': stack, 'spillStores': spillSt,
            'spillLoads': spillLd, 'spillBytes': spillSt + spillLd,
            'smemBytes': smemBytes,
            'walkInstrs': walkInstrs, 'walkLocalOps': walkLocal,
            'kernelInstrs': kernelInstrs, 'kernelLocalOps': kernelLocal,
            'moduleInstrs': moduleInstrs, 'moduleLocalOps': moduleLocal,
            'blocksPerSM': blocks, 'warpsPerSM': warps,
            'occupancy': round(100.0 * warps / MAX_WARPS_PER_SM, 1)}


def dominates(a, b):
    """a dominates b: at least as good everywhere, strictly better somewhere.

    Better means fewer instructions and less local-memory traffic resident on an
    SM -- traffic per thread times the threads that carry it.  Occupancy is not
    a good in itself here; see the ladder above heuristicCost."""
    aTraffic = a['spillBytes'] + a['walkLocalOps'] * 4
    bTraffic = b['spillBytes'] + b['walkLocalOps'] * 4
    ge = (a['warpsPerSM'] * aTraffic <= b['warpsPerSM'] * bTraffic and
          a['walkInstrs'] <= b['walkInstrs'])
    gt = (a['warpsPerSM'] * aTraffic < b['warpsPerSM'] * bTraffic or
          a['walkInstrs'] < b['walkInstrs'])
    return ge and gt


def bindingBound(r):
    """Whether __launch_bounds__ actually constrained the register allocator.

    Occupancy here is register limited: an SM has 65536 registers, so the
    resident warps are 2048/registers and the block size does not enter.  The
    bound only bites once minBlocks * threads exceeds 65536/255, about 257
    threads -- below that ptxas takes its 255 and every minBlocks gives an
    identical build.  Saying so keeps eight copies of one configuration off a
    shortlist that exists to be measured on a card."""
    return r['minBlocks'] * r['threads'] > REGS_PER_SM // 255


def knobCombos(names, cross):
    """The knob settings to try: all off, then one on at a time.

    Same reasoning as the size axes -- a star, not a product.  Three knobs cross
    to eight builds and the interactions are the least likely part to matter,
    because two of the three do not even act on the same stage of the toolchain:
    streamKarat and smemSpill rewrite what ptxas is given, globalCg only changes
    a flag it is given alongside.  `cross` restores the product for when an
    interaction is the actual question."""
    allOff = tuple(False for _ in KNOB_NAMES)
    if not names:
        return [allOff]
    if cross:
        out = [()]
        for name in KNOB_NAMES:
            grown = []
            for prefix in out:
                grown.append(prefix + (False,))
                if name in names:
                    grown.append(prefix + (True,))
            out = grown
        return out
    out = [allOff]
    for i, name in enumerate(KNOB_NAMES):
        if name not in names:
            continue
        one = list(allOff)
        one[i] = True
        out.append(tuple(one))
    return out


def planConfigs(leaves, batches, threadList, minBlocks, prune, cross, knobSets=None):
    """The builds to compile.

    The metrics are separable, and measurably so: across a full sweep the
    instruction and local-op counts depend only on the leaf, while registers and
    spill depend only on threads and minBlocks.  Neither ever moved with the
    other axis.  So the cross product measures the same two curves over and over
    -- vary one axis at a time around a base point instead and the search falls
    from |leaf|*|batch|*|threads|*|minBlocks| builds to roughly their sum.  That
    is what makes an expensive point like a fully straight-line leaf, which
    takes ptxas minutes on its own, affordable to include at all.

    The knobs join as one more spoke of the same star.  They belong on the leaf
    axis rather than the occupancy one -- streamKarat changes what the
    multiplier compiles to, which is exactly what the leaf changes -- so they
    are varied at the base size point and not re-tried at every other one.

    `cross` restores the full product for when that assumption is worth
    rechecking, which is any time the kernel's structure changes.

    Pruning drops a launch bound that cannot bind: below about 257 total threads
    the allocator keeps its 255 registers and every minBlocks compiles to the
    same binary, so only the smallest is kept."""
    if knobSets is None:
        knobSets = [tuple(False for _ in KNOB_NAMES)]
    baseKnobs = knobSets[0]
    out = []

    def add(leaf, batch, threads, mb, knobs):
        if (leaf, batch, threads, mb, knobs) not in out:
            out.append((leaf, batch, threads, mb, knobs))

    def occupancyPoints(leaf, batch, knobs):
        for threads in threadList:
            seenLoose = False
            for mb in minBlocks:
                if prune and not bindingBound({'minBlocks': mb, 'threads': threads}):
                    if seenLoose:
                        continue
                    seenLoose = True
                add(leaf, batch, threads, mb, knobs)

    if cross:
        for leaf in leaves:
            for batch in batches:
                for knobs in knobSets:
                    occupancyPoints(leaf, batch, knobs)
        return out

    # Sorting by leaf below keeps the generator from being re-run: it is the one
    # per-configuration step that is not a compile.

    baseLeaf, baseBatch = leaves[0], batches[0]
    baseThreads, baseMb = threadList[0], minBlocks[0]
    occupancyPoints(baseLeaf, baseBatch, baseKnobs)
    for leaf in leaves:
        add(leaf, baseBatch, baseThreads, baseMb, baseKnobs)
    for batch in batches:
        add(baseLeaf, batch, baseThreads, baseMb, baseKnobs)
    for knobs in knobSets:
        add(baseLeaf, baseBatch, baseThreads, baseMb, knobs)
    out.sort(key=lambda c: leaves.index(c[0]))
    return out


def dedupe(rows):
    """Collapse configurations that are the same thing to RUN, not just to build.

    The collapse is over minBlocks alone, and the distinction matters.  Below
    about 257 total threads the launch bound cannot bind, so every minBlocks at
    one block size hands ptxas the same problem and gets back the same cubin --
    that is the redundancy this exists to remove, and it is the one the report
    describes.

    Block size is not part of it.  ECC_THREADS is not only the second half of
    __launch_bounds__; it is the block size the kernel is launched with
    (`<<<blocks, ECC_THREADS>>>`) and the size occupancy is computed for.  An
    earlier key collapsed across it, on the reasoning that ptxas reported the
    two identical -- and it does, because 128 threads at minBlocks 2 and 256 at
    minBlocks 1 are the same register budget.  They are not the same launch.
    That is not academic: it took the base point 0/32/128/2 out of the results
    of a real search and left 0/32/256/1 standing in for it, and the measured
    ladder says those two run at 607 and 315 M it/s.  A shortlist naming the
    second where the search explored the first is recommending a configuration
    nobody measured.

    globalCg is in the key even though every static metric is blind to it:
    collapsing it would drop the one axis this tool cannot rank but can still
    carry to a GPU, and it would drop it silently."""
    seen = {}
    for r in rows:
        key = (r['leaf'], r['threads'], r['registers'], r['walkInstrs'],
               r['spillBytes'], r['walkLocalOps'], r['warpsPerSM'],
               r.get('smemBytes', 0), r.get('knobs', '-'))
        if key not in seen or r['minBlocks'] < seen[key]['minBlocks']:
            seen[key] = r
    return list(seen.values())


def paretoFront(rows):
    out = []
    for r in rows:
        beaten = False
        for s in rows:
            if s is not r and dominates(s, r):
                beaten = True
                break
        if not beaten:
            out.append(r)
    return out


# Measured on an RTX PRO 6000 Blackwell (sm_120), batch 32, leaf 0, by
# ::autotune over the occupancy ladder this tool had put on its Pareto front:
#
#   threads/minBlocks  regs  warps/SM  spillB   M it/s
#   128/2               255         8   12664    607.2
#   256/2               128        16   17168    314.5
#   256/3                80        24   21636    233.8
#   256/4                64        32   23444    209.5
#
# Four times the resident warps cost 2.9x the throughput, monotonically.  The
# first version of this cost divided work by warpsPerSM, on the assumption that
# occupancy hides latency, and therefore ranked the ladder exactly upside down.
# It does not hide latency here because every resident thread carries its own
# multi-kilobyte spill frame: going from 8 to 32 warps takes the local-memory
# footprint resident on an SM from 3.2 MB to 24 MB, far past any cache, so the
# added warps compete for DRAM rather than covering for each other.
MEASURED_LADDER = ((8, 607.2), (16, 314.5), (24, 233.8), (32, 209.5))


def dynamicCost(parts, batch):
    """Per-thread work per walk-iteration, weighted by the fit in perfmodel.py.

    This tool and perfmodel.py had two different cost models over the same PTX,
    and only one of them had ever been checked against a measurement.  The
    static proxy below counts every instruction in the call closure once, so it
    cannot tell that FieldBs::mul runs 157 times a step while inv runs once --
    which is why it preferred the leaf-33 multiplier on instruction count, and
    why the card then ran it 15% slower.  perfmodel weights each routine by how
    often a step calls it and weights a local-memory operation against
    arithmetic with one constant fitted to eight measured rates; asked about a
    leaf it had not been fitted to, it was right to 1.1%.

    So use it when it is available and say so when it is not.  Returns None if
    perfmodel or its history is missing, or if the PTX has no walk kernel."""
    try:
        import perfmodel
    except ImportError:
        return None
    weight = perfmodel.fittedWeight()
    if weight is None:
        return None
    got = perfmodel.dynamicFromParts(parts, batch)
    if got is None:
        return None
    return got['instrs'] + weight * got['local'], weight


# Measured on an RTX PRO 6000 Blackwell (sm_120), batch 32, leaf 0, by
# ::autotune over the occupancy ladder this tool had put on its Pareto front:
#
#   threads/minBlocks  regs  warps/SM  spillB   M it/s
#   128/2               255         8   12664    607.2
#   256/2               128        16   17168    314.5
#   256/3                80        24   21636    233.8
#   256/4                64        32   23444    209.5
#
# Four times the resident warps cost 2.9x the throughput, monotonically.  The
# first version of this cost divided work by warpsPerSM, on the assumption that
# occupancy hides latency, and therefore ranked the ladder exactly upside down.
# It does not hide latency here because every resident thread carries its own
# multi-kilobyte spill frame: going from 8 to 32 warps takes the local-memory
# footprint resident on an SM from 3.2 MB to 24 MB, far past any cache, so the
# added warps compete for DRAM rather than covering for each other.
MEASURED_LADDER = ((8, 607.2), (16, 314.5), (24, 233.8), (32, 209.5))


def heuristicCost(r):
    """Per-SM work: per-thread work times the threads resident on an SM.

    A proxy, and named one.  Two things feed it and they are not equally good:

      * the per-thread term, which is dynamicCost above when perfmodel and its
        history are available -- calibrated, and checked against a rate it was
        not fitted to -- and the static closure count when they are not.  The
        row records which, in `costBasis`, because a shortlist built on the
        uncalibrated proxy deserves less trust than one built on the fit and
        the printed number looks identical either way.
      * the occupancy term, which is uncalibrated in both cases.  It assumes
        throughput falls with resident warps, which is what the ladder above
        measured, but nothing has checked that on a build that spills less --
        and the whole point of the streamKarat knob is to be such a build.

    Spill bytes stay in the static path because they are the one part of the
    frame the PTX does not show: ptxas decides them, and a leaf that fits the
    register file differs from one that does not almost entirely there.

    It is for ranking a shortlist, never for predicting a rate."""
    if r.get('dynWork'):
        perThread = r['dynWork'] + r['spillBytes'] / 4.0
    else:
        perThread = r['walkInstrs'] + r['spillBytes'] / 4.0 + r['walkLocalOps']
    return perThread * r['warpsPerSM'] / 1000.0


SELFTEST_PTX = """//
// Generated by NVIDIA NVVM Compiler
// _Z13eccWalkKernelI7CfgF131jEv10WalkParamsIT0_E is named here, in a comment
//
.version 8.7
.target sm_120
.address_size 64

.weak .func _ZN3mulE;
.visible .entry _Z13eccWalkKernelI7CfgF131jEv10WalkParamsIT0_E(
\t.param .align 8 .b8 p[8]
)
{
\t.reg .b32 %r<4>;
\tld.param.u64 %rd1, [p];
\tst.local.u32 [%rd1], %r1;
\tcall.uni
\t_ZN3mulE,
\t(
\tparam0
\t);
\tret;
}

.weak .func _ZN3mulE(
\t.param .b64 q
)
{
\txor.b32 %r1, %r2, %r3;
\tld.local.u32 %r2, [%rd1];
\tret;
}

.visible .entry _Z13eccInitKernelI7CfgF131jEv10WalkParamsIT0_E()
{
\tmov.u32 %r1, 0;
\tmov.u32 %r2, 0;
\tmov.u32 %r3, 0;
\tret;
}
"""


def selfTest():
    """Guard the extraction bugs that produced plausible wrong numbers.

    All three were silent -- a name matched inside the file header comment
    reported zero instructions, counting only the entry function reported the
    same total for every multiplier leaf, and counting indented lines charged a
    call once per argument.  None of them failed, so none of them was noticed."""
    parts = splitFunctions(SELFTEST_PTX)
    walk = '_Z13eccWalkKernelI7CfgF131jEv10WalkParamsIT0_E'
    init = '_Z13eccInitKernelI7CfgF131jEv10WalkParamsIT0_E'
    assert set(parts) == {walk, init, '_ZN3mulE'}, sorted(parts)
    # the definition must win over the forward declaration
    assert 'xor.b32' in parts['_ZN3mulE']
    assert reachableFrom(parts, walk) == {walk, '_ZN3mulE'}
    # three statements plus one call; the call's argument lines are not counted
    assert countPtx(parts[walk]) == (4, 1), countPtx(parts[walk])
    assert countPtx(parts['_ZN3mulE']) == (3, 1), countPtx(parts['_ZN3mulE'])
    assert countPtx(parts[init]) == (4, 0), countPtx(parts[init])

    log = ("ptxas info    : Compiling entry function "
           "'_Z13eccWalkKernelI7CfgF131jEv10WalkParamsIT0_E' for 'sm_120'\n"
           "ptxas info    : Function properties for "
           "_Z13eccWalkKernelI7CfgF131jEv10WalkParamsIT0_E\n"
           "    16 bytes stack frame, 8 bytes spill stores, 4 bytes spill loads\n"
           "ptxas info    : Used 64 registers\n")
    m = parseMetrics(SELFTEST_PTX, log, 256)
    assert m['registers'] == 64 and m['spillBytes'] == 12, m
    # the entry alone sees 4; the closure sees the multiplier too; the module
    # also charges the init kernel, which runs once and is not the walk's cost
    assert (m['kernelInstrs'], m['walkInstrs'], m['moduleInstrs']) == (4, 7, 11), m
    assert (m['kernelLocalOps'], m['walkLocalOps'], m['moduleLocalOps']) == (1, 2, 2), m
    # 65536/64 registers is 1024 resident threads, which is 32 warps
    assert m['warpsPerSM'] == 32, m
    assert bindingBound({'minBlocks': 4, 'threads': 256})
    assert not bindingBound({'minBlocks': 2, 'threads': 128})

    # enable_smem_spilling makes ptxas report the spill counts negative, having
    # subtracted what it relocated into shared memory.  The \d+ pattern this
    # replaced did not fail on that line, it just failed to match, so
    # parseMetrics returned None and the knob was indistinguishable from a
    # compile error.  Both halves are pinned: the negative counts parse, and the
    # smem bytes are carried rather than dropped.
    smemLog = ("ptxas info    : Compiling entry function "
               "'_Z13eccWalkKernelI7CfgF131jEv10WalkParamsIT0_E' for 'sm_120'\n"
               "ptxas info    : Function properties for "
               "_Z13eccWalkKernelI7CfgF131jEv10WalkParamsIT0_E\n"
               "    12624 bytes stack frame, -56 bytes spill stores, "
               "-60 bytes spill loads\n"
               "ptxas info    : Used 64 registers, used 0 barriers, "
               "12624 bytes cumulative stack size, 7168 bytes smem\n")
    sm = parseMetrics(SELFTEST_PTX, smemLog, 256)
    assert sm is not None, 'negative spill counts must parse, not vanish'
    assert (sm['spillStores'], sm['spillLoads']) == (-56, -60), sm
    assert sm['smemBytes'] == 7168, sm
    # and a build without the pragma must not pick up a stray smem number
    assert m['smemBytes'] == 0, m

    # The knob star: all off, then one on at a time, and nothing duplicated.
    combos = knobCombos(list(KNOB_NAMES), False)
    assert combos[0] == (False, False, False), combos
    assert len(combos) == 1 + len(KNOB_NAMES), combos
    assert len(set(combos)) == len(combos), combos
    assert knobCombos([], False) == [(False, False, False)]
    assert len(knobCombos(list(KNOB_NAMES), True)) == 2 ** len(KNOB_NAMES)
    # one knob asked for, one knob varied -- not all of them
    assert knobCombos(['smemSpill'], False) == [(False, False, False),
                                                (False, True, False)]
    assert knobKey({'streamKarat': True}) == 'streamKarat'
    assert knobKey({}) == '-'

    # A knob the static metrics cannot see must survive dedupe, or the search
    # would quietly drop the only axis it is unable to rank.
    base = dict(leaf=0, registers=255, walkInstrs=1, spillBytes=0,
                walkLocalOps=0, warpsPerSM=8, smemBytes=0, minBlocks=2,
                threads=128, knobs='-')
    cg = dict(base, knobs='globalCg')
    assert len(dedupe([base, cg])) == 2, 'globalCg collapsed away'
    assert len(dedupe([base, dict(base)])) == 1, 'true duplicates must collapse'

    # Two block sizes that ptxas cannot tell apart are still two launches, and
    # this is the case that actually went wrong: 128 threads at minBlocks 2 and
    # 256 at minBlocks 1 are one register budget and report identically, so an
    # earlier key collapsed them and kept the 256 -- which the card runs at half
    # the rate.  Same block size, different minBlocks, is the collapse that is
    # meant to happen.
    wide = dict(base, threads=256, minBlocks=1)
    assert len(dedupe([base, wide])) == 2, 'collapsed two different launches'
    assert len(dedupe([base, dict(base, minBlocks=3)])) == 1, \
        'same launch at a bound that cannot bind must collapse'
    assert dedupe([dict(base, minBlocks=3), base])[0]['minBlocks'] == 2, \
        'the surviving row should be the loosest bound, whatever the input order'

    # planConfigs must vary the knobs at the base size point only, and must not
    # re-run them at every leaf -- that is the whole reason it is a star.
    plan = planConfigs([0, 33], [32], [128], [2], True, False,
                       knobCombos(list(KNOB_NAMES), False))
    assert len(plan) == 2 + len(KNOB_NAMES), plan
    assert all(len(c) == 5 for c in plan), plan
    # generated/ is tracked, and the leaf axis rewrites it.  A restore that
    # quietly did nothing would leave the next build on a leaf nobody chose,
    # and would look exactly like a restore that worked.
    global GEN_DIR
    realGen = GEN_DIR
    try:
        GEN_DIR = tempfile.mkdtemp()
        open(os.path.join(GEN_DIR, 'a.h'), 'w').write('original')
        saved = saveGenerated()
        assert restoreGenerated(saved) == [], 'a no-op restore must rewrite nothing'
        open(os.path.join(GEN_DIR, 'a.h'), 'w').write('clobbered by a leaf sweep')
        assert restoreGenerated(saved) == ['a.h']
        assert open(os.path.join(GEN_DIR, 'a.h')).read() == 'original'
        # a file the sweep deleted comes back too
        os.remove(os.path.join(GEN_DIR, 'a.h'))
        assert restoreGenerated(saved) == ['a.h']
        assert open(os.path.join(GEN_DIR, 'a.h')).read() == 'original'
    finally:
        shutil.rmtree(GEN_DIR, ignore_errors=True)
        GEN_DIR = realGen

    print('autolab self-test: PTX extraction, occupancy model, knob plan and '
          'generated/ restore agree')


def perfmodelPoints():
    """The measured rates the shared weight was fitted to, for reporting."""
    try:
        import perfmodel
    except ImportError:
        return ()
    return perfmodel.MEASURED


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--batch', default='4,8,16,32')
    ap.add_argument('--threads', default='64,128,256')
    ap.add_argument('--min-blocks', default='1,2,3,4')
    ap.add_argument('--leaf', default='0,17,33,66,131',
                    help='generated leaf sizes; 0 means the register-budget choice')
    ap.add_argument('--regs', type=int, default=255)
    ap.add_argument('--arch', default='120')
    ap.add_argument('--cuda-path', default='/tmp/cudaroot')
    ap.add_argument('--ptxas', default='/tmp/cudaroot/bin/ptxas')
    ap.add_argument('--clang', default='clang')
    ap.add_argument('--compiler', default='auto', choices=('auto', 'nvcc', 'clang'),
                    help='auto picks nvcc when --cuda-path has one')
    ap.add_argument('--out', default='autolab.json')
    ap.add_argument('--top', type=int, default=6)
    ap.add_argument('--cross', action='store_true',
                    help='compile the full cross product rather than varying one '
                         'axis at a time; worth doing when the kernel changes shape')
    ap.add_argument('--no-prune', action='store_true',
                    help='compile every combination, including the ones whose '
                         'launch bound cannot bind and so cannot differ')
    ap.add_argument('--knobs', default=','.join(KNOB_NAMES),
                    help='non-size build knobs to try, one at a time on top of '
                         'the base point: %s.  "none" searches none of them'
                         % ','.join(KNOB_NAMES))
    ap.add_argument('--self-test', action='store_true',
                    help='check the PTX extraction against a fixture and exit')
    args = ap.parse_args()

    if args.self_test:
        selfTest()
        return 0

    compiler = args.compiler
    if compiler == 'auto':
        compiler = 'nvcc' if os.path.exists(
            os.path.join(args.cuda_path, 'bin', 'nvcc')) else 'clang'
    print('compiling with %s, ptxas targeting sm_%s' % (compiler, args.arch))

    ints = lambda s: [int(x) for x in s.split(',') if x != '']
    batches, threadList = ints(args.batch), ints(args.threads)
    minBlocks, leaves = ints(args.min_blocks), ints(args.leaf)

    wanted = [] if args.knobs.strip() in ('', 'none') else [
        k.strip() for k in args.knobs.split(',') if k.strip()]
    unknown = [k for k in wanted if k not in KNOB_NAMES]
    if unknown:
        print('unknown knob(s) %s; known: %s' % (unknown, ', '.join(KNOB_NAMES)))
        return 1
    knobSets = knobCombos(wanted, args.cross)

    # A cached row is only comparable to a fresh build if the same metrics were
    # extracted from it, so key the file by schema and start over when that
    # changes rather than silently mixing two definitions of the cost.
    cache = {}
    if os.path.exists(args.out):
        loaded = json.load(open(args.out))
        if loaded.get('schema') == CACHE_SCHEMA and loaded.get('compiler') == compiler:
            cache = loaded.get('rows', {})
        else:
            print('%s came from a different build of this tool; recompiling' % args.out)

    plan = planConfigs(leaves, batches, threadList, minBlocks,
                       not args.no_prune, args.cross, knobSets)
    total = len(plan)
    full = (len(leaves) * len(batches) * len(threadList) * len(minBlocks)
            * len(knobSets))
    if total < full:
        print('%d builds instead of the %d in the cross product: the launch bound '
              'does not bind below %d total threads, and leaf and occupancy move '
              'different metrics (--cross to check that)'
              % (total, full, REGS_PER_SM // 255 + 1))
    print('%d configurations, about %.0f min at 23 s each' % (total, total * 23 / 60.0))
    rows = []
    n = 0
    curLeaf = None
    savedGen = saveGenerated()
    for leaf, batch, threads, mb, knobTuple in plan:
        knobs = dict(zip(KNOB_NAMES, knobTuple))
        if leaf != curLeaf:
            ok, out = regenerate(leaf, args.regs, args.cuda_path)
            if not ok:
                print('generator failed for leaf %d: %s' % (leaf, out[-300:]))
                continue
            curLeaf = leaf
        n += 1
        label = knobKey(knobs)
        key = '%d/%d/%d/%d/%s' % (leaf, batch, threads, mb, label)
        if key in cache:
            rows.append(cache[key])
            print('[%d/%d] %-28s cached' % (n, total, key), flush=True)
            continue
        t0 = time.time()
        got, err = compile(batch, threads, mb, args.arch, args.cuda_path,
                           args.ptxas, args.clang, compiler, knobs)
        if err:
            print('[%d/%d] %-28s FAILED %s' % (n, total, key, err[:80]), flush=True)
            continue
        met = parseMetrics(got[0], got[1], threads)
        if met is None:
            print('[%d/%d] %-28s no walk kernel in the log' % (n, total, key), flush=True)
            continue
        met.update({'leaf': leaf, 'batch': batch, 'threads': threads,
                    'minBlocks': mb, 'knobs': label,
                    'seconds': round(time.time() - t0, 1)})
        met.update(knobs)
        dyn = dynamicCost(splitFunctions(got[0]), batch)
        met['costBasis'] = 'static'
        if dyn is not None:
            met['dynWork'], met['localWeight'] = round(dyn[0], 2), dyn[1]
            met['costBasis'] = 'perfmodel'
        met['cost'] = round(heuristicCost(met), 1)
        rows.append(met)
        cache[key] = met
        json.dump({'schema': CACHE_SCHEMA, 'compiler': compiler,
                   'arch': args.arch, 'rows': cache},
                  open(args.out, 'w'), indent=1)
        print('[%d/%d] %-28s regs %3d  warps/SM %2d  instrs %6d  '
              'spill %5dB  local %5d  smem %5dB  cost %7.1f'
              % (n, total, key, met['registers'], met['warpsPerSM'],
                 met['walkInstrs'], met['spillBytes'], met['walkLocalOps'],
                 met.get('smemBytes', 0), met['cost']), flush=True)

    restored = restoreGenerated(savedGen)
    if restored:
        print('\nrestored %d file(s) in generated/ that the leaf search '
              'rewrote: %s' % (len(restored), ', '.join(restored)))

    if not rows:
        print('nothing measured')
        return 1
    # Over every row, cached ones included: a run that reused the whole cache
    # was otherwise reported with no statement of which cost model ranked it.
    basisSeen = set(r.get('costBasis', 'static') for r in rows)
    weights = [r['localWeight'] for r in rows if r.get('localWeight')]
    unique = dedupe(rows)
    if len(unique) < len(rows):
        loose = len([r for r in rows if not bindingBound(r)])
        print('\n%d of %d configurations compiled to something already seen; %d of '
              'them asked for a launch bound that cannot bind (minBlocks * threads '
              'below %d)' % (len(rows) - len(unique), len(rows), loose,
                             REGS_PER_SM // 255 + 1))
    front = paretoFront(unique)
    front.sort(key=lambda r: r['cost'])
    print('\n%d distinct builds, %d on the Pareto front '
          '(occupancy vs instructions vs traffic)' % (len(unique), len(front)))
    print('  %-6s %-6s %-8s %-10s %5s %6s %8s %8s %8s  %s' %
          ('leaf', 'batch', 'threads', 'minBlocks', 'regs', 'warps', 'instrs',
           'spillB', 'cost', 'knobs'))
    for r in front[:args.top]:
        print('  %-6d %-6d %-8d %-10d %5d %6d %8d %8d %8.1f  %s'
              % (r['leaf'], r['batch'], r['threads'], r['minBlocks'],
                 r['registers'], r['warpsPerSM'], r['walkInstrs'],
                 r['spillBytes'], r['cost'], r.get('knobs', '-')))
    if weights:
        print('  cost weights a local-memory operation at %.1f instructions, '
              'fitted to %d measured rates in perfhistory.json'
              % (weights[0], len(perfmodelPoints())))
    if 'static' in basisSeen:
        print('  some rows fell back to the uncalibrated static count; those '
              'ranks carry less weight than the rest')
    if any(r.get('globalCg') for r in unique):
        print('  globalCg only changes a ptxas cache-policy flag, so every '
              'metric above is identical to its knob-off row by construction; '
              'it is on the list to be measured, not because it was ranked')

    # Name the front's rows, not the distinct values in them.  Crossing the
    # values back out measures two or three times as many builds as the front
    # has points, which gives away the whole reason for searching offline first.
    short = front[:args.top]
    # A shortlist has to carry its own control.  The front is a set of winners,
    # and when one build dominates the rest -- which is exactly what a knob that
    # works looks like -- the front is that build alone and the GPU run has
    # nothing to compare it against.  The measurement would then report a rate
    # with no baseline in the same sweep, on the same card, from the same image,
    # which is the only kind of baseline worth having.  So put the all-knobs-off
    # build at the base size point back on the list if the front dropped it.
    # Over `rows`, not `unique`.  The control is defined by the plan's base
    # point, so it has to be looked up among the configurations actually
    # compiled -- a dedupe pass is free to drop that exact row in favour of a
    # metric-identical one, and when it did, this lookup found nothing and the
    # shortlist went out with no control at all.  Silently, because "no base row
    # found" and "base row already on the front" took the same branch.
    baseRow = None
    for r in rows:
        if (r['leaf'], r['batch'], r['threads'], r['minBlocks']) == \
                (leaves[0], batches[0], threadList[0], minBlocks[0]) and \
                r.get('knobs', '-') == '-':
            baseRow = r
            break
    if baseRow is None:
        print('  no knobs-off build at the base point %d/%d/%d/%d to use as a '
              'control; the rates below share no baseline'
              % (leaves[0], batches[0], threadList[0], minBlocks[0]))
    onFront = any((r['leaf'], r['batch'], r['threads'], r['minBlocks'],
                   r.get('knobs', '-')) ==
                  (leaves[0], batches[0], threadList[0], minBlocks[0], '-')
                  for r in short)
    if baseRow is not None and not onFront:
        short.append(baseRow)
        print('  ...and the knobs-off build at the base point, which the front '
              'dropped as dominated -- a sweep needs its own control')

    # leaf:batch:threads:minBlocks, then the three knobs as 0/1 in KNOBS order.
    # modal_app.autotuneConfigs accepts the four-field form too, so a shortlist
    # from before the knobs existed still parses.
    plan = ','.join('%d:%d:%d:%d:%d:%d:%d'
                    % (r['leaf'], r['batch'], r['threads'], r['minBlocks'],
                       int(bool(r.get('streamKarat'))), int(bool(r.get('smemSpill'))),
                       int(bool(r.get('globalCg'))))
                    for r in short)
    # The front is the product, so write it where a caller can pick it up
    # rather than making them scrape it back out of this output.
    json.dump({'schema': CACHE_SCHEMA, 'compiler': compiler, 'arch': args.arch,
               'rows': cache, 'front': short, 'configs': plan},
              open(args.out, 'w'), indent=1)
    print('\nMeasure these %d builds on a GPU -- the ranking above is a proxy, '
          'not a result:' % len(short))
    print('  modal run modal_app.py::autotune --configs %s' % plan)
    return 0


if __name__ == '__main__':
    sys.exit(main())
