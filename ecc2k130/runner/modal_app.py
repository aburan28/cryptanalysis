"""Run the ECC2K-130 client on Modal GPUs.

    ECC_GPU=RTX-PRO-6000 modal run modal_app.py::validate
    ECC_GPU=RTX-PRO-6000 modal run modal_app.py::bench
    ECC_GPU=RTX-PRO-6000 modal run modal_app.py::autolab    # no GPU, picks candidates
    ECC_GPU=RTX-PRO-6000 modal run modal_app.py::autotune   # measures them
    ECC_GPU=RTX-PRO-6000 modal run modal_app.py::campaign   # both, in one call
    ECC_GPU=RTX-PRO-6000 modal run modal_app.py::profile    # Nsight Compute
    ECC_GPU=RTX-PRO-6000 modal run modal_app.py::search --curve 97 --hours 4
    ECC_GPU=RTX-PRO-6000 modal run modal_app.py::fanout --curve 97 --count 8 --hours 4

Curve 97 is ECC2K-95, a 2^44 iteration problem: feasible in GPU-hours, and its
answer has been public since Harley's group solved it in 1998, so a recovered
logarithm can be checked rather than merely believed.

The GPU comes from the ECC_GPU environment variable, which is read when this
file is imported and baked into the function definitions.  That works on every
Modal version.  Newer clients also accept --gpu on the entry points, which
overrides it per call via Function.with_options.

The image builds a fat binary covering Ampere through Blackwell so any GPU type
works without a rebuild.  The autotuner rebuilds for the local architecture
only, which takes seconds rather than minutes.

Distinguished points and results land in a Modal Volume, so a search can be
stopped and resumed and several containers can contribute to one corpus.
"""

import hashlib
import json
import os
import pathlib
import re
import select
import signal
import struct
import subprocess
import sys
import time

import modal
# Modal imports this module as /root/modal_app.py, separately from the source
# tree copied into the image. Resolve helpers from that tree on the container.
REMOTE = "/root/ecc2k130"
helperRoot = pathlib.Path(__file__).parent if modal.is_local() else pathlib.Path(REMOTE)
sys.path.insert(0, str(helperRoot))
from codegen.benchreport import benchResult, bestResult, parseRate, reportsVerified, summarizeSamples
from codegen.profilereport import NCU_BINARY, NCU_PACKAGE, profilerVersionError, profileResult

CUDA_VERSION = os.environ.get("ECC_CUDA_VERSION", "12.8.1")
if not re.fullmatch(r'\d+\.\d+\.\d+', CUDA_VERSION):
    raise ValueError("ECC_CUDA_VERSION must be a toolkit version such as 13.0.2")

# This setting is fixed for the image and all rebuilds within it. Keep the
# previous packed multiplier available for controlled comparisons.
PACKED_SINGLE_PRODUCT = os.environ.get("ECC_PACKED_SINGLE_PRODUCT", "0")
if PACKED_SINGLE_PRODUCT not in ("0", "1"):
    raise ValueError("ECC_PACKED_SINGLE_PRODUCT must be 0 or 1")
PACKED_CACHE_DENOM = os.environ.get("ECC_PACKED_CACHE_DENOM", "0")
if PACKED_CACHE_DENOM not in ("0", "1"):
    raise ValueError("ECC_PACKED_CACHE_DENOM must be 0 or 1")
PACKED_BY_VALUE = os.environ.get("ECC_PACKED_BY_VALUE", "0")
if PACKED_BY_VALUE not in ("0", "1"):
    raise ValueError("ECC_PACKED_BY_VALUE must be 0 or 1")
PACKED_PERM_SIGMA = os.environ.get("ECC_PACKED_PERM_SIGMA", "0")
if PACKED_PERM_SIGMA not in ("0", "1", "2", "3"):
    raise ValueError("ECC_PACKED_PERM_SIGMA must be a bit mask from 0 to 3")
PACKED_POLY_CHAIN = os.environ.get("ECC_PACKED_POLY_CHAIN", "0")
if PACKED_POLY_CHAIN not in ("0", "1"):
    raise ValueError("ECC_PACKED_POLY_CHAIN must be 0 or 1")
if PACKED_POLY_CHAIN == "1" and PACKED_CACHE_DENOM != "1":
    raise ValueError("ECC_PACKED_POLY_CHAIN=1 requires ECC_PACKED_CACHE_DENOM=1")
PACKED_UNROLL_INV = os.environ.get("ECC_PACKED_UNROLL_INV", "0")
PACKED_PAIR_PRODUCTS = os.environ.get("ECC_PACKED_PAIR_PRODUCTS", "0")
if PACKED_UNROLL_INV not in ("0", "1") or PACKED_PAIR_PRODUCTS not in ("0", "1"):
    raise ValueError("ECC_PACKED_UNROLL_INV and ECC_PACKED_PAIR_PRODUCTS must be 0 or 1")
if PACKED_PAIR_PRODUCTS == "1" and PACKED_POLY_CHAIN != "1":
    raise ValueError("ECC_PACKED_PAIR_PRODUCTS=1 requires ECC_PACKED_POLY_CHAIN=1")
PACKED_POLY_STATE = os.environ.get("ECC_PACKED_POLY_STATE", "0")
if PACKED_POLY_STATE not in ("0", "1"):
    raise ValueError("ECC_PACKED_POLY_STATE must be 0 or 1")
if PACKED_POLY_STATE == "1" and (PACKED_CACHE_DENOM != "1" or PACKED_POLY_CHAIN != "1"):
    raise ValueError("ECC_PACKED_POLY_STATE=1 requires ECC_PACKED_CACHE_DENOM=1 "
                     "and ECC_PACKED_POLY_CHAIN=1")
PACKED_DIRECT_REDUCE = os.environ.get("ECC_PACKED_DIRECT_REDUCE", "0")
if PACKED_DIRECT_REDUCE not in ("0", "1"):
    raise ValueError("ECC_PACKED_DIRECT_REDUCE must be 0 or 1")
PACKED_GENERATED_PRODUCT = os.environ.get("ECC_PACKED_GENERATED_PRODUCT", "0")
if PACKED_GENERATED_PRODUCT not in ("0", "1"):
    raise ValueError("ECC_PACKED_GENERATED_PRODUCT must be 0 or 1")
if PACKED_GENERATED_PRODUCT == "1" and PACKED_DIRECT_REDUCE != "1":
    raise ValueError("ECC_PACKED_GENERATED_PRODUCT=1 requires ECC_PACKED_DIRECT_REDUCE=1")
PACKED_CLMAD = os.environ.get("ECC_PACKED_CLMAD", "0")
if PACKED_CLMAD not in ("0", "1"):
    raise ValueError("ECC_PACKED_CLMAD must be 0 or 1")
PACKED_CLMAD_SQUARE = os.environ.get("ECC_PACKED_CLMAD_SQUARE", "0")
if PACKED_CLMAD_SQUARE not in ("0", "1"):
    raise ValueError("ECC_PACKED_CLMAD_SQUARE must be 0 or 1")
if PACKED_CLMAD_SQUARE == "1" and PACKED_CLMAD != "1":
    raise ValueError("ECC_PACKED_CLMAD_SQUARE requires ECC_PACKED_CLMAD")
PACKED_KARAT3 = os.environ.get("ECC_PACKED_KARAT3", "0")
if PACKED_KARAT3 not in ("0", "1"):
    raise ValueError("ECC_PACKED_KARAT3 must be 0 or 1")
if PACKED_KARAT3 == "1" and PACKED_CLMAD != "1":
    raise ValueError("ECC_PACKED_KARAT3 requires ECC_PACKED_CLMAD")
PACKED_WEIGHTED_PREFIX = os.environ.get("ECC_PACKED_WEIGHTED_PREFIX", "0")
if PACKED_WEIGHTED_PREFIX not in ("0", "1", "2"):
    raise ValueError("ECC_PACKED_WEIGHTED_PREFIX must be 0, 1 or 2")
if PACKED_WEIGHTED_PREFIX != "0" and any(value != "1" for value in
        (PACKED_POLY_STATE, PACKED_POLY_CHAIN, PACKED_CACHE_DENOM, PACKED_PAIR_PRODUCTS)):
    raise ValueError("ECC_PACKED_WEIGHTED_PREFIX requires polynomial state, polynomial chains, denominator cache and paired products")
if PACKED_WEIGHTED_PREFIX == "2" and not (int(PACKED_PERM_SIGMA) & 1):
    raise ValueError("ECC_PACKED_WEIGHTED_PREFIX=2 requires the walk permutation network")
PACKED_SHARED_SIGMA = os.environ.get("ECC_PACKED_SHARED_SIGMA", "0")
if PACKED_SHARED_SIGMA not in ("0", "1"):
    raise ValueError("ECC_PACKED_SHARED_SIGMA must be 0 or 1")
if PACKED_SHARED_SIGMA == "1" and (PACKED_WEIGHTED_PREFIX != "2" or not (int(PACKED_PERM_SIGMA) & 1)):
    raise ValueError("ECC_PACKED_SHARED_SIGMA=1 requires weighted-prefix mode 2 and the walk permutation network")
# The 3-bit top-word cross terms of every product on the carryless unit
# instead of as masked shifts: four more clmads per product, 25 fewer ALU
# instructions in SASS (77 -> 52).  Measured slower on an RTX PRO 6000
# (12.859 vs 15.116 B/s); leave off.  See TOP-CLMAD.md.
PACKED_TOP_CLMAD = os.environ.get("ECC_PACKED_TOP_CLMAD", "0")
if PACKED_TOP_CLMAD not in ("0", "1"):
    raise ValueError("ECC_PACKED_TOP_CLMAD must be 0 or 1")
if PACKED_TOP_CLMAD == "1" and PACKED_CLMAD != "1":
    raise ValueError("ECC_PACKED_TOP_CLMAD=1 requires ECC_PACKED_CLMAD=1")
WALK_TABLE = os.environ.get("ECC_WALK_TABLE", "0")
if WALK_TABLE not in ("0", "1"):
    raise ValueError("ECC_WALK_TABLE must be 0 or 1")
if WALK_TABLE == "1" and PACKED_WEIGHTED_PREFIX == "0":
    raise ValueError("ECC_WALK_TABLE=1 requires ECC_PACKED_WEIGHTED_PREFIX")
TABLE_PIVOT_BYTES = os.environ.get("ECC_TABLE_PIVOT_BYTES", "0")
if TABLE_PIVOT_BYTES not in ("0", "1"):
    raise ValueError("ECC_TABLE_PIVOT_BYTES must be 0 or 1")
if TABLE_PIVOT_BYTES == "1" and WALK_TABLE != "1":
    raise ValueError("ECC_TABLE_PIVOT_BYTES=1 requires ECC_WALK_TABLE=1")
PACKED_STATE_TILE = os.environ.get("ECC_PACKED_STATE_TILE", "0")
if PACKED_STATE_TILE not in ("0", "256"):
    raise ValueError("ECC_PACKED_STATE_TILE must be 0 or 256")
if PACKED_STATE_TILE == "256" and (PACKED_POLY_STATE != "1" or PACKED_CACHE_DENOM != "1" or PACKED_POLY_CHAIN != "1"):
    raise ValueError("ECC_PACKED_STATE_TILE=256 requires polynomial state, denominator cache and polynomial chains")
PACKED_COMPACT_STATE = os.environ.get("ECC_PACKED_COMPACT_STATE", "0")
if PACKED_COMPACT_STATE not in ("0", "1"):
    raise ValueError("ECC_PACKED_COMPACT_STATE must be 0 or 1")
if PACKED_COMPACT_STATE == "1" and (PACKED_STATE_TILE != "256" or any(value != "1" for value in
        (PACKED_POLY_STATE, PACKED_POLY_CHAIN, PACKED_CACHE_DENOM))):
    raise ValueError("ECC_PACKED_COMPACT_STATE=1 requires TILE256, polynomial state, polynomial chains and denominator cache")

# Valid values include T4, L4, A10, L40S, A100, A100-40GB, A100-80GB,
# RTX-PRO-6000, H100, H100!, H200, B200, B200+ and B300; append ":n" for
# several of them. H100! / A100-40GB / B200 pin the SKU against Modal's
# automatic upgrades (H100→H200, A100→A100-80GB, B200→B300).
DEFAULT_GPU = os.environ.get("ECC_GPU", "H100")

# Compute capability per Modal GPU type.  sm_120 is the Blackwell workstation
# part (RTX PRO 6000), sm_100 is B200/B300, sm_90 is H100/H200, sm_89 is
# L40S/L4, sm_86 is A10, sm_80 is A100, sm_75 is T4. Modal B300 reports
# compute capability 10.3; the survey image still bakes sm_100, which ran.
GPU_ARCH = {
    "T4": "75", "L4": "89", "L40S": "89", "A10": "86", "A10G": "86",
    "A100": "80", "A100-40GB": "80", "A100-80GB": "80",
    "H100": "90", "H100!": "90", "H200": "90",
    "B200": "100", "B200+": "100", "B300": "100", "RTX-PRO-6000": "120",
}
ALL_ARCHES = ("80", "89", "90", "100", "120")


def archesFor(gpu):
    """Architectures to bake into the image.

    Every architecture is a separate full ptxas pass over a kernel that takes
    minutes to compile, so a fat binary covering five of them costs about four
    minutes on every image rebuild -- and add_local_dir invalidates the layer on
    any source change, so that is every iteration.  Build only what the chosen
    GPU can run.  An unrecognised name falls back to the full set rather than
    guessing, since a missing architecture is a runtime failure, not a slow
    build."""
    key = gpu.split(":")[0].strip()
    arch = GPU_ARCH.get(key)
    if arch is None and key.endswith(("!", "+")):
        arch = GPU_ARCH.get(key.rstrip("!+"))
    return (arch,) if arch else ALL_ARCHES


BAKED_ARCHES = archesFor(DEFAULT_GPU)
GENCODE = " ".join(
    "-gencode arch=compute_%s,code=sm_%s" % (a, a) for a in BAKED_ARCHES
)
LOCAL = pathlib.Path(__file__).parent

# What the image already contains.  A request for exactly this on a matching
# architecture needs no rebuild, and the default ::bench is exactly this -- it
# was spending minutes recompiling a binary it already had, in silence.
BAKED = {"batch": 32, "threads": 256 if PACKED_STATE_TILE == "256" else 128, "leaf": 0, "minBlocks": 2,
         "packedPolynomialState": PACKED_POLY_STATE == "1",
         "packedDirectReduction": PACKED_DIRECT_REDUCE == "1",
         "packedGeneratedProduct": PACKED_GENERATED_PRODUCT == "1",
         "packedClmad": PACKED_CLMAD == "1",
         "packedClmadSquare": PACKED_CLMAD_SQUARE == "1",
         "packedKarat3": PACKED_KARAT3 == "1",
         "packedCompactState": PACKED_COMPACT_STATE == "1",
         "packedSharedSigma": PACKED_SHARED_SIGMA == "1",
         "packedTopClmad": PACKED_TOP_CLMAD == "1",
         "walkTable": WALK_TABLE == "1",
         "tablePivotBytes": TABLE_PIVOT_BYTES == "1",
         "packedWeightedPrefix": int(PACKED_WEIGHTED_PREFIX),
         "packedStateTile": int(PACKED_STATE_TILE)}

# Cleared the first time buildFor actually builds.  `make -B gpu` replaces
# ./ecc2k130 in place, so once anything has rebuilt, the image's baked binary is
# gone and a later request for BAKED has to build it again.  Without this a
# sweep that rebuilt for one point and then reached BAKED would time the
# previous point's binary and report it under BAKED's knobs -- the same trap the
# generator comment in buildFor warns about, one level up.
bakedIntact = [True]

image = (
    modal.Image.from_registry(
        f"nvidia/cuda:{CUDA_VERSION}-devel-ubuntu24.04", add_python="3.12"
    )
    .entrypoint([])
    # Containers re-import this module; preserve the settings that selected
    # their image and baked architecture rather than reverting to defaults.
    .env({"ECC_CUDA_VERSION": CUDA_VERSION, "ECC_GPU": DEFAULT_GPU,
          "ECC_PACKED_SINGLE_PRODUCT": PACKED_SINGLE_PRODUCT,
          "ECC_PACKED_CACHE_DENOM": PACKED_CACHE_DENOM,
          "ECC_PACKED_BY_VALUE": PACKED_BY_VALUE,
          "ECC_PACKED_PERM_SIGMA": PACKED_PERM_SIGMA,
          "ECC_PACKED_POLY_CHAIN": PACKED_POLY_CHAIN,
          "ECC_PACKED_UNROLL_INV": PACKED_UNROLL_INV,
          "ECC_PACKED_PAIR_PRODUCTS": PACKED_PAIR_PRODUCTS,
          "ECC_PACKED_POLY_STATE": PACKED_POLY_STATE,
          "ECC_PACKED_DIRECT_REDUCE": PACKED_DIRECT_REDUCE,
          "ECC_PACKED_GENERATED_PRODUCT": PACKED_GENERATED_PRODUCT,
          "ECC_PACKED_CLMAD": PACKED_CLMAD,
          "ECC_PACKED_CLMAD_SQUARE": PACKED_CLMAD_SQUARE,
          "ECC_PACKED_KARAT3": PACKED_KARAT3,
          "ECC_PACKED_COMPACT_STATE": PACKED_COMPACT_STATE,
          "ECC_PACKED_SHARED_SIGMA": PACKED_SHARED_SIGMA,
          "ECC_PACKED_TOP_CLMAD": PACKED_TOP_CLMAD,
          "ECC_WALK_TABLE": WALK_TABLE,
          "ECC_TABLE_PIVOT_BYTES": TABLE_PIVOT_BYTES,
          "ECC_PACKED_WEIGHTED_PREFIX": PACKED_WEIGHTED_PREFIX,
          "ECC_PACKED_STATE_TILE": PACKED_STATE_TILE})
    .apt_install("build-essential")
    .add_local_dir(
        LOCAL,
        remote_path=REMOTE,
        copy=True,
        ignore=["ecc2k130-cpu", "ecc2k130", "build/*", "__pycache__", "*.pyc"],
    )
    .run_commands(
        # Regenerate before building so the baked binary's leaf is known to be
        # BAKED["leaf"] rather than whatever headers the local checkout held.
        f"cd {REMOTE}/codegen && python3 gen.py --out ../generated "
        f"--leaf {BAKED['leaf']}",
        # x86-64-v3 keeps the host binary runnable on any Modal machine; the
        # GPU client picks its own word width on the device.
        f"cd {REMOTE} && make cpu MARCH=x86-64-v3",
        f'cd {REMOTE} && make gpu ARCH="{GENCODE}" BATCH={BAKED["batch"]} '
        f'THREADS={BAKED["threads"]} MINBLOCKS={BAKED["minBlocks"]} '
        f'PACKED_SINGLE_PRODUCT={PACKED_SINGLE_PRODUCT} PACKED_CACHE_DENOM={PACKED_CACHE_DENOM} '
        f'PACKED_BY_VALUE={PACKED_BY_VALUE} PACKED_PERM_SIGMA={PACKED_PERM_SIGMA} '
        f'PACKED_POLY_CHAIN={PACKED_POLY_CHAIN} PACKED_UNROLL_INV={PACKED_UNROLL_INV} '
        f'PACKED_PAIR_PRODUCTS={PACKED_PAIR_PRODUCTS} PACKED_POLY_STATE={PACKED_POLY_STATE} '
        f'PACKED_DIRECT_REDUCE={PACKED_DIRECT_REDUCE} '
        f'PACKED_GENERATED_PRODUCT={PACKED_GENERATED_PRODUCT} PACKED_CLMAD={PACKED_CLMAD} PACKED_CLMAD_SQUARE={PACKED_CLMAD_SQUARE} PACKED_KARAT3={PACKED_KARAT3} PACKED_COMPACT_STATE={PACKED_COMPACT_STATE} PACKED_SHARED_SIGMA={PACKED_SHARED_SIGMA} PACKED_TOP_CLMAD={PACKED_TOP_CLMAD} PACKED_WEIGHTED_PREFIX={PACKED_WEIGHTED_PREFIX} PACKED_STATE_TILE={PACKED_STATE_TILE} WALK_TABLE={WALK_TABLE} TABLE_PIVOT_BYTES={TABLE_PIVOT_BYTES}',
    )
)

# Nsight Compute lives in its own image.  It is about two gigabytes and only the
# profiler wants it, so putting it in the main image would slow every bench and
# search rebuild for a tool most runs never invoke.  It layers on top, so the
# baked binary and the source are already present.
profileImage = image.apt_install(NCU_PACKAGE).run_commands(f"{NCU_BINARY} --version")

volume = modal.Volume.from_name("ecc2k130", create_if_missing=True)
app = modal.App("ecc2k130")

HOUR = 60 * 60

def onGpu(fn, gpu):
    """Point a function at a GPU type.

    Modal clients from 0.72 on can retarget a call with Function.with_options;
    older ones cannot, so fall back to the ECC_GPU environment variable, which
    is baked in at import time and therefore always works."""
    if not gpu or gpu == DEFAULT_GPU:
        return fn
    if hasattr(fn, "with_options"):
        return fn.with_options(gpu=gpu)
    raise SystemExit(
        "This Modal client cannot change the GPU per call "
        "(Function.with_options was added in 0.72).\n"
        "Either upgrade with `pip install -U modal`, or select the GPU through "
        "the environment:\n\n"
        f"    ECC_GPU={gpu} modal run modal_app.py::<entrypoint>\n"
    )


# ---------------------------------------------------------------------------
def sh(cmd, cwd=REMOTE, timeout=None):
    r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    return r.returncode, r.stdout + r.stderr


def shStream(cmd, cwd=REMOTE, timeout=None, prefix=""):
    """Run a command, echoing each line as it arrives and returning them too.

    Modal forwards a container's stdout to the caller's terminal live, but only
    if something writes to it.  Capturing the whole of a multi-minute compile and
    printing it at the end looks identical to a hang, which is what running
    ::bench used to look like."""
    p = subprocess.Popen(cmd, shell=True, cwd=cwd, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True, bufsize=1)
    lines = []
    try:
        for line in p.stdout:
            lines.append(line)
            print(prefix + line.rstrip(), flush=True)
        p.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        p.kill()
        return 1, "".join(lines) + "\ntimeout"
    return p.returncode, "".join(lines)


def computeCapability():
    rc, out = sh("nvidia-smi --query-gpu=compute_cap --format=csv,noheader")
    if rc != 0 or not out.strip():
        return "90"
    return out.strip().splitlines()[0].strip().replace(".", "")


def gpuName():
    rc, out = sh("nvidia-smi --query-gpu=name --format=csv,noheader")
    return out.strip().splitlines()[0].strip() if rc == 0 and out.strip() else "unknown"


def buildFor(batch, threads, leaf, arch=None, minBlocks=2,
             streamKarat=False, smemSpill=False, globalCg=False):
    """Rebuild the client for one architecture and one set of knobs."""
    if PACKED_STATE_TILE == "256" and threads != 256:
        return False, "ECC_PACKED_STATE_TILE=256 requires 256 threads per block"
    arch = arch or computeCapability()
    # leaf 0 means "let the generator choose by register budget", which is what
    # gen.py does with no --leaf: the largest halving-chain size whose
    # straight-line multiply still fits 255 live values.  On a 255-register GPU
    # that is 66 words at m=131; it is emphatically not the right answer for the
    # 16-register host, so the CPU reference build and the device build do not
    # want the same leaf, and only a GPU settles which one this is.
    # Regenerate unconditionally, passing leaf 0 straight through: gen.py reads
    # 0 as "choose by register budget".  Skipping the generator instead would
    # compile whatever headers the container already holds, which during an
    # autotune sweep is the previous point's leaf -- so the sweep would score
    # that build twice and label one of them the register-budget choice.
    want = {"batch": batch, "threads": threads, "leaf": leaf, "minBlocks": minBlocks,
            "packedPolynomialState": PACKED_POLY_STATE == "1",
            "packedDirectReduction": PACKED_DIRECT_REDUCE == "1",
            "packedGeneratedProduct": PACKED_GENERATED_PRODUCT == "1",
            "packedClmad": PACKED_CLMAD == "1",
            "packedClmadSquare": PACKED_CLMAD_SQUARE == "1",
            "packedKarat3": PACKED_KARAT3 == "1",
            "packedCompactState": PACKED_COMPACT_STATE == "1",
            "packedSharedSigma": PACKED_SHARED_SIGMA == "1",
            "packedTopClmad": PACKED_TOP_CLMAD == "1",
            "walkTable": WALK_TABLE == "1",
            "tablePivotBytes": TABLE_PIVOT_BYTES == "1",
            "packedWeightedPrefix": int(PACKED_WEIGHTED_PREFIX),
            "packedStateTile": int(PACKED_STATE_TILE)}
    if smemSpill and int(CUDA_VERSION.split('.')[0]) < 13:
        return False, "--smem-spill requires ECC_CUDA_VERSION=13.x.y (CUDA 13 or newer)"
    experimental = streamKarat or smemSpill or globalCg
    if want == BAKED and not experimental and arch in BAKED_ARCHES and bakedIntact[0]:
        print(f"sm_{arch}: batch {batch}, threads {threads}, leaf {leaf}, "
              f"minBlocks {minBlocks} is what the image already holds; not rebuilding",
              flush=True)
        return True, "baked into the image"
    print(f"building for sm_{arch}: batch {batch}, threads {threads}, leaf {leaf}, "
          f"minBlocks {minBlocks} -- ptxas takes a few minutes on this kernel",
          flush=True)
    bakedIntact[0] = False
    rc, out = sh(f"cd codegen && python3 gen.py --out ../generated --leaf {leaf}")
    if rc != 0:
        return False, out
    gencode = f"-gencode arch=compute_{arch},code=sm_{arch}"
    rc, out = shStream(
        f'make -B gpu ARCH="{gencode}" BATCH={batch} THREADS={threads} '
        f"MINBLOCKS={minBlocks} STREAM_KARAT={int(streamKarat)} "
        f"SMEM_SPILL={int(smemSpill)} GLOBAL_CG={int(globalCg)} "
        f"PACKED_SINGLE_PRODUCT={PACKED_SINGLE_PRODUCT} PACKED_CACHE_DENOM={PACKED_CACHE_DENOM} "
        f"PACKED_BY_VALUE={PACKED_BY_VALUE} PACKED_PERM_SIGMA={PACKED_PERM_SIGMA} "
        f"PACKED_POLY_CHAIN={PACKED_POLY_CHAIN} PACKED_UNROLL_INV={PACKED_UNROLL_INV} "
        f"PACKED_PAIR_PRODUCTS={PACKED_PAIR_PRODUCTS} PACKED_POLY_STATE={PACKED_POLY_STATE} "
        f"PACKED_DIRECT_REDUCE={PACKED_DIRECT_REDUCE} "
        f"PACKED_GENERATED_PRODUCT={PACKED_GENERATED_PRODUCT} PACKED_CLMAD={PACKED_CLMAD} PACKED_CLMAD_SQUARE={PACKED_CLMAD_SQUARE} PACKED_KARAT3={PACKED_KARAT3} PACKED_COMPACT_STATE={PACKED_COMPACT_STATE} PACKED_SHARED_SIGMA={PACKED_SHARED_SIGMA} PACKED_TOP_CLMAD={PACKED_TOP_CLMAD} PACKED_WEIGHTED_PREFIX={PACKED_WEIGHTED_PREFIX} PACKED_STATE_TILE={PACKED_STATE_TILE} WALK_TABLE={WALK_TABLE} TABLE_PIVOT_BYTES={TABLE_PIVOT_BYTES}",
        timeout=1800,
        prefix="  build| ",
    )
    return rc == 0, out


def benchmarkIdentity(packed=False):
    """Identity travels with the result even though the image has no .git."""
    root = pathlib.Path(REMOTE)
    source = hashlib.sha256()
    paths = [root / 'Makefile', root / 'modal_app.py']
    for folder in ('include', 'src', 'generated', 'codegen'):
        paths += sorted(p for p in (root / folder).rglob('*')
                        if p.suffix in ('.h', '.cuh', '.cu', '.cpp', '.py'))
    for path in paths:
        source.update(str(path.relative_to(root)).encode() + b'\0' + path.read_bytes() + b'\0')
    rc, compiler = sh('nvcc --version')
    gpuRc, gpu = sh('nvidia-smi --query-gpu=name,uuid,driver_version,pstate,clocks.current.sm,'
                   'clocks.current.memory,power.limit,temperature.gpu --format=csv')
    leaf = re.search(r'LEAF = (\d+)', (root / 'generated/eccF131.h').read_text())
    return dict(sourceSha256=source.hexdigest(),
                binarySha256=hashlib.sha256((root / 'ecc2k130').read_bytes()).hexdigest(),
                actualLeaf=None if packed else int(leaf.group(1)), generatedLeaf=int(leaf.group(1)),
                activeBackend=('packed-poly131' if PACKED_POLY_STATE == '1' else 'packed-onb131') if packed else 'bitsliced',
                compiler=compiler, compilerReturncode=rc,
                packedMultiplier=('single-product' if PACKED_SINGLE_PRODUCT == '1' else 'two-product') if packed else None,
                packedDenominatorCache=(PACKED_CACHE_DENOM == '1') if packed else None,
                packedByValue=(PACKED_BY_VALUE == '1') if packed else None,
                packedFrobeniusMode=int(PACKED_PERM_SIGMA) if packed else None,
                packedPolynomialChain=(PACKED_POLY_CHAIN == '1') if packed else None,
                packedUnrolledInverse=(PACKED_UNROLL_INV == '1') if packed else None,
                packedPairedProducts=(PACKED_PAIR_PRODUCTS == '1') if packed else None,
                packedPolynomialState=(PACKED_POLY_STATE == '1') if packed else None,
                packedDirectReduction=(PACKED_DIRECT_REDUCE == '1') if packed else None,
                packedGeneratedProduct=(PACKED_GENERATED_PRODUCT == '1') if packed else None,
                packedClmad=(PACKED_CLMAD == '1') if packed else None,
                packedClmadSquare=(PACKED_CLMAD_SQUARE == '1') if packed else None,
                packedKarat3=(PACKED_KARAT3 == '1') if packed else None,
                packedCompactState=(PACKED_COMPACT_STATE == '1') if packed else None,
                packedSharedSigma=(PACKED_SHARED_SIGMA == '1') if packed else None,
                packedTopClmad=(PACKED_TOP_CLMAD == '1') if packed else None,
                walkTable=(WALK_TABLE == '1') if packed else None,
                tablePivotBytes=(TABLE_PIVOT_BYTES == '1') if packed else None,
                packedWeightedPrefix=int(PACKED_WEIGHTED_PREFIX) if packed else None,
                packedStateTile=int(PACKED_STATE_TILE) if packed else None,
                gpuState=gpu, gpuStateReturncode=gpuRc, cudaImageVersion=CUDA_VERSION)


def checkPackedReduction(sample):
    """Reject rates whose reducer, generated-product or physical-layout mode disagrees."""
    for marker, field, expectedField, expected in (
        ('direct reduction', 'packedDirectReduction', 'expectedPackedDirectReduction', PACKED_DIRECT_REDUCE),
        ('generated product', 'packedGeneratedProduct', 'expectedPackedGeneratedProduct', PACKED_GENERATED_PRODUCT),
        ('native carryless multiply', 'packedClmad', 'expectedPackedClmad', PACKED_CLMAD),
        ('native carryless square', 'packedClmadSquare', 'expectedPackedClmadSquare', PACKED_CLMAD_SQUARE),
        ('three-limb Karatsuba', 'packedKarat3', 'expectedPackedKarat3', PACKED_KARAT3),
        ('compact state', 'packedCompactState', 'expectedPackedCompactState', PACKED_COMPACT_STATE),
        ('shared sigma', 'packedSharedSigma', 'expectedPackedSharedSigma', PACKED_SHARED_SIGMA),
        ('top clmad', 'packedTopClmad', 'expectedPackedTopClmad', PACKED_TOP_CLMAD),
    ):
        modes = re.findall(r'^packed ' + marker + r': (.*)$', sample.get('raw', ''), re.MULTILINE)
        actual = modes[0] if len(modes) == 1 else None
        sample[expectedField] = expected == '1'
        sample[field] = (actual == '1') if actual in ('0', '1') else None
        sample['valid'] = bool(sample.get('valid') and actual == expected)
        if actual != expected:
            sample.setdefault('error', 'packed ' + marker + ' identity is missing, duplicated or different from the requested build')
    weighted = re.findall(r'^packed weighted prefix: (.*)$', sample.get('raw', ''), re.MULTILINE)
    actualWeighted = weighted[0] if len(weighted) == 1 else None
    sample['expectedPackedWeightedPrefix'] = int(PACKED_WEIGHTED_PREFIX)
    sample['packedWeightedPrefix'] = int(actualWeighted) if actualWeighted in ('0', '1', '2') else None
    if actualWeighted != PACKED_WEIGHTED_PREFIX:
        sample['valid'] = False
        sample.setdefault('error', 'packed weighted prefix identity is missing, duplicated or different from the requested build')
    tiles = re.findall(r'^packed state tile: (.*)$', sample.get('raw', ''), re.MULTILINE)
    actualTile = tiles[0] if len(tiles) == 1 else None
    sample['expectedPackedStateTile'] = int(PACKED_STATE_TILE)
    sample['packedStateTile'] = int(actualTile) if actualTile in ('0', '256') else None
    if actualTile != PACKED_STATE_TILE:
        sample['valid'] = False
        sample.setdefault('error', 'packed state tile identity is missing, duplicated or different from the requested build')
    if not sample['valid']:
        sample['rate'] = 0.0
    return sample['valid']


def measureBench(steps, launches, workers, preferL1, repeats, packed=False):
    if steps <= 0 or launches <= 0 or repeats <= 0 or workers < 0:
        raise ValueError('steps, launches and repeats must be positive; workers must be nonnegative')
    cmd = f'./ecc2k130 --curve 131 --bench --steps {steps} --launches {launches} --verify 0'
    if packed:
        cmd += ' --packed'
    if workers:
        cmd += f' --threads {workers}'
    if preferL1:
        cmd += ' --prefer-l1'
    samples = []
    for repeat in range(repeats):
        try:
            rc, out = sh(cmd, timeout=1800)
        except subprocess.TimeoutExpired as exc:
            rc = 124
            out = exc.stdout or ''
            if isinstance(out, bytes):
                out = out.decode(errors='replace')
            out += '\nbenchmark timed out'
        sample = benchResult(cmd, rc, out)
        if packed:
            checkPackedReduction(sample)
        samples.append(sample)
        print(f'  repeat {repeat + 1}/{repeats}: {sample["rate"]:.3f} M it/s '
              f'({"complete" if sample["valid"] else "FAILED"})', flush=True)
        if not sample['valid']:
            break
    return summarizeSamples(samples)


# ---------------------------------------------------------------------------
@app.function(image=image, gpu=DEFAULT_GPU, timeout=2 * HOUR, volumes={"/data": volume})
def runValidate(batch=32, threads=128, leaf=0, minBlocks=2,
                streamKarat=False, smemSpill=False, globalCg=False, preferL1=False, packed=False):
    """Field arithmetic, orbit invariants, solver, and end-to-end discrete
    logarithms recovered on the GPU itself."""
    if packed and (leaf or streamKarat or smemSpill):
        raise ValueError('packed arithmetic requires leaf=0 and no stream/smem flags')
    cc = computeCapability()
    out = ["device: " + gpuName(), "compute capability: " + cc, ""]
    # Validate the requested candidate on the actual architecture. buildFor
    # reuses the image only when its untouched binary matches the request.
    ok, log = buildFor(batch, threads, leaf, arch=cc, minBlocks=minBlocks,
                       streamKarat=streamKarat, smemSpill=smemSpill, globalCg=globalCg)
    if not ok:
        raise RuntimeError("\n".join(out + ["rebuild failed", log]))
    out.append(json.dumps(benchmarkIdentity(packed), indent=2))
    cacheFlag = ' --prefer-l1' if preferL1 else ''
    rc, t = sh("./ecc2k130-cpu --test")
    out.append(t.strip())
    if rc != 0:
        raise RuntimeError("\n".join(out) + "\nHOST VALIDATION FAILED")

    out.append("\n--- end-to-end on the GPU ---")
    ok = True
    # A small curve reaches a collision almost immediately, so keep the walk
    # count modest: a million walks would overrun the report buffer on the
    # first launch and throw most of the points away.  Curves 19 and 13 have no
    # normal basis, so they exercise the polynomial-basis backend that ECC2K-95
    # depends on; curve 41 is solved through both backends.
    for curve, instances, workers, steps in (("23", 4, 256, 8), ("19", 4, 256, 8),
                                             ("13", 2, 128, 4), ("41", 4, 2048, 32),
                                             ("41 --poly-basis", 4, 2048, 32)):
        for i in range(instances):
            rc, t = sh(
                f"./ecc2k130 --curve {curve} --instance {i} --threads {workers} "
                f"--steps {steps} --dp-cap 262144 --verify 4{cacheFlag}"
            )
            line = [l for l in t.splitlines() if "planted" in l or "MISMATCH" in l]
            good = rc == 0 and 'MISMATCH' not in t and any("yes" in l for l in line)
            ok = ok and good
            out.append(f"curve {curve} instance {i}: " + ("; ".join(line) if line else t.strip()[-200:]))
    out.append("GPU END TO END: " + ("all instances solved" if ok else "FAILED"))

    # ECC2K-95 itself: no collision in a short run, but the reports have to be
    # reproducible from their seeds, which is what the server depends on.
    #
    # dp weight 36 is theta = 1/139 at m=97, far looser than any real search
    # would use: the point is to make a short run report at all, so there is
    # something to recompute.  Size the run to that.  4096 threads for 4
    # launches walked 268M iterations to verify 16 reports and took ten minutes
    # -- most of a validate run -- while overrunning the report buffer, so the
    # gate people are told to run first was the slowest thing here.  512 threads
    # for 2 launches still produces about 120k reports from half a million
    # parallel walks, stays inside --dp-cap, and takes well under a minute.
    # Staying inside the cap matters beyond speed: it means a "dropped" count in
    # validate output is a real signal rather than the expected state.
    for curve, weight, workers in ((97, 36, 512), (131, 50, 128)):
        backendFlag = ' --packed' if packed and curve == 131 else ''
        rc, t = sh(f"./ecc2k130 --curve {curve} --dp-weight {weight} --threads {workers} "
                   f"--steps 16 --launches 2 --dp-cap 262144 --verify 16{cacheFlag}{backendFlag}", timeout=1800)
        out.append(f"\n--- GF(2^{curve}) reporting path ---")
        out.append(t.strip())
        passed = reportsVerified(rc, t)
        out.append('REPORT REPLAY: ' + ('PASS' if passed else 'FAILED'))
        ok = ok and passed
    if not ok:
        raise RuntimeError("\n".join(out))
    return "\n".join(out)


@app.function(image=image, gpu=DEFAULT_GPU, timeout=2 * HOUR)
def runBench(batch=32, threads=128, leaf=0, minBlocks=2, steps=64, launches=20,
             workers=0, rebuild=True, repeats=3, streamKarat=False,
             smemSpill=False, globalCg=False, preferL1=False, packed=False):
    """Completed-run median on the challenge curve, with reproducible identity."""
    if packed and (leaf or streamKarat or smemSpill):
        raise ValueError('packed arithmetic requires leaf=0 and no stream/smem flags')
    info = dict(gpu=gpuName(), cc=computeCapability(), batch=batch,
                threads=threads, leaf=leaf, minBlocks=minBlocks, workers=workers,
                steps=steps, launches=launches, repeats=repeats, streamKarat=streamKarat,
                smemSpill=smemSpill, globalCg=globalCg, preferL1=preferL1, packed=packed,
                packedPolynomialState=(PACKED_POLY_STATE == '1') if packed else None,
                packedDirectReduction=(PACKED_DIRECT_REDUCE == '1') if packed else None,
                packedGeneratedProduct=(PACKED_GENERATED_PRODUCT == '1') if packed else None,
                packedClmad=(PACKED_CLMAD == '1') if packed else None,
                packedClmadSquare=(PACKED_CLMAD_SQUARE == '1') if packed else None,
                packedKarat3=(PACKED_KARAT3 == '1') if packed else None,
                packedCompactState=(PACKED_COMPACT_STATE == '1') if packed else None,
                packedSharedSigma=(PACKED_SHARED_SIGMA == '1') if packed else None,
                packedTopClmad=(PACKED_TOP_CLMAD == '1') if packed else None,
                walkTable=(WALK_TABLE == '1') if packed else None,
                tablePivotBytes=(TABLE_PIVOT_BYTES == '1') if packed else None,
                packedWeightedPrefix=int(PACKED_WEIGHTED_PREFIX) if packed else None,
                packedStateTile=int(PACKED_STATE_TILE) if packed else None)
    want = dict(batch=batch, threads=threads, leaf=leaf, minBlocks=minBlocks,
                packedPolynomialState=PACKED_POLY_STATE == '1',
                packedDirectReduction=PACKED_DIRECT_REDUCE == '1',
                packedGeneratedProduct=PACKED_GENERATED_PRODUCT == '1',
                packedClmad=PACKED_CLMAD == '1',
                packedClmadSquare=PACKED_CLMAD_SQUARE == '1',
                packedKarat3=PACKED_KARAT3 == '1',
                packedCompactState=PACKED_COMPACT_STATE == '1',
                packedSharedSigma=PACKED_SHARED_SIGMA == '1',
                packedTopClmad=PACKED_TOP_CLMAD == '1',
                walkTable=WALK_TABLE == '1',
                tablePivotBytes=TABLE_PIVOT_BYTES == '1',
                packedWeightedPrefix=int(PACKED_WEIGHTED_PREFIX),
                packedStateTile=int(PACKED_STATE_TILE))
    if not rebuild and (streamKarat or smemSpill or globalCg or not bakedIntact[0]
                        or want != BAKED or info['cc'] not in BAKED_ARCHES):
        raise ValueError('rebuild=False requires the untouched matching baked binary')
    if rebuild:
        ok, log = buildFor(batch, threads, leaf, minBlocks=minBlocks,
                           streamKarat=streamKarat, smemSpill=smemSpill, globalCg=globalCg)
        info['buildLog'] = log
        if not ok:
            return dict(info, valid=False, rate=0.0, error=log)
    info['identity'] = benchmarkIdentity(packed)
    info.update(measureBench(steps, launches, workers, preferL1, repeats, packed))
    return info


def parseWaveList(text):
    """Positive integer wave counts, comma-separated, order preserved."""
    waves = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        n = int(part)
        if n < 1:
            raise ValueError("waves must be positive integers, got %r" % part)
        waves.append(n)
    if not waves:
        raise ValueError("waves is empty")
    return waves


def parsePackedLaunch(text):
    """SM count and automatic worker count from one packed client dump."""
    sms = re.search(r"(\d+) SMs", text)
    resident = re.search(
        r"(\d+) block\(s\) of (\d+) packed threads resident per SM", text)
    threads = re.search(r"backend cuda-packed131: (\d+) threads", text)
    if not (sms and resident and threads):
        raise ValueError("packed launch identity missing from:\n" + text[-2000:])
    return {
        "sms": int(sms.group(1)),
        "residentBlocks": int(resident.group(1)),
        "blockThreads": int(resident.group(2)),
        "automaticThreads": int(threads.group(1)),
    }


@app.function(image=image, gpu=DEFAULT_GPU, timeout=4 * HOUR)
def runWaves(batch=32, threads=256, leaf=0, minBlocks=2, steps=1024, launches=32,
             repeats=3, packed=True, waves="1,4,6,8", preferL1=False):
    """One allocation, several oversubscribed grids.

    Automatic occupancy is one wave: SMs × resident blocks × block threads.
    The shipping 6000 preset is four waves. This measures that multiplier on
    the same GPU, same binary, without a rebuild between rows.
    """
    if not packed:
        raise ValueError("runWaves is the packed-walk occupancy sweep")
    if leaf:
        raise ValueError("packed arithmetic requires leaf=0")
    waveList = parseWaveList(waves)
    info = dict(gpu=gpuName(), cc=computeCapability(), batch=batch,
                threads=threads, leaf=leaf, minBlocks=minBlocks,
                steps=steps, launches=launches, repeats=repeats,
                packed=True, waves=waveList, preferL1=preferL1)
    ok, log = buildFor(batch, threads, leaf, minBlocks=minBlocks)
    info["buildLog"] = log
    if not ok:
        return dict(info, valid=False, error=log)
    info["identity"] = benchmarkIdentity(True)
    probe = ("./ecc2k130 --curve 131 --bench --packed --steps 1 --launches 1 "
             "--verify 0")
    rc, out = sh(probe, timeout=600)
    if rc != 0:
        return dict(info, valid=False, error=out, probe=out)
    launch = parsePackedLaunch(out)
    info.update(launch)
    info["probe"] = out
    print("automatic occupancy: %d threads on %d SMs (%d x %d resident)"
          % (launch["automaticThreads"], launch["sms"],
             launch["residentBlocks"], launch["blockThreads"]), flush=True)
    rows = []
    for wave in waveList:
        workers = launch["automaticThreads"] * wave
        print("=== wave %d: %d workers ===" % (wave, workers), flush=True)
        measured = measureBench(steps, launches, workers, preferL1, repeats, True)
        row = dict(wave=wave, workers=workers, **measured)
        if launch["sms"] and measured.get("valid"):
            row["perSmM"] = measured["rate"] / launch["sms"]
            row["medianB"] = measured["rate"] / 1000.0
        rows.append(row)
        if not measured.get("valid"):
            break
    info["rows"] = rows
    info["valid"] = bool(rows) and all(r.get("valid") for r in rows)
    validRows = [r for r in rows if r.get("valid")]
    info["best"] = max(validRows, key=lambda r: r["rate"]) if validRows else None
    return info


def autotuneConfigs(batches, threadCounts, leaves, minBlocksList, configs,
                    knobs=(False, False, False)):
    """The (leaf, batch, threads, minBlocks, streamKarat, smemSpill, globalCg)
    builds to measure.

    `configs` names them one per entry, which is what autolab.py emits.  Its
    Pareto front is a handful of points, and expanding the distinct values of
    those points back into a cross product measures two or three times as many
    builds as the front has rows.  Without it the four lists are crossed, as
    before.

    An entry is leaf:batch:threads:minBlocks, optionally followed by the three
    knobs as 0/1.  They are per-entry rather than per-run because that is how
    autolab searches them: its shortlist can hold a streamKarat build and a
    plain one side by side, and a run-level flag would force them into separate
    sweeps whose rates are then not directly comparable.  The four-field form
    still parses and takes `knobs`, which is what the run-level flags supply, so
    a shortlist emitted before the knobs existed means exactly what it did."""
    if configs.strip():
        out = []
        for entry in configs.split(","):
            if not entry.strip():
                continue
            parts = [int(x) for x in entry.split(":")]
            if len(parts) == 4:
                parts += [int(bool(k)) for k in knobs]
            if len(parts) != 7:
                raise ValueError(
                    "config %r has %d fields; expected leaf:batch:threads:"
                    "minBlocks with the three knobs optional" % (entry, len(parts)))
            leaf, batch, threads, mb, sk, ss, cg = parts
            out.append((leaf, batch, threads, mb, bool(sk), bool(ss), bool(cg)))
        return out
    ints = lambda t: [int(x) for x in t.split(",") if x]
    sk, ss, cg = (bool(k) for k in knobs)
    return [(leaf, batch, threads, mb, sk, ss, cg)
            for leaf in ints(leaves)
            for threads in ints(threadCounts)
            for batch in ints(batches)
            for mb in ints(minBlocksList)]


@app.function(image=image, gpu=DEFAULT_GPU, timeout=4 * HOUR, volumes={"/data": volume})
def runAutotune(batches="8,16,32,64", threadCounts="64,128,256", leaves="0,17,33,66",
                minBlocksList="2,4,8", steps=64, launches=12, configs="",
                workers=0, repeats=3, streamKarat=False, smemSpill=False,
                globalCg=False, preferL1=False, packed=False):
    """Rank completed repetitions by median; retain failed candidates as errors."""
    results = []
    arch = computeCapability()
    name = gpuName()
    if packed and not configs.strip():
        if leaves not in ('0', '0,17,33,66'):
            raise ValueError('packed arithmetic has no generated-leaf tuning; use --leaves 0')
        leaves = '0'
    plan = autotuneConfigs(batches, threadCounts, leaves, minBlocksList, configs,
                           (streamKarat, smemSpill, globalCg))
    if packed and any(leaf or sk or ss for leaf, batch, threads, mb, sk, ss, cg in plan):
        raise ValueError('packed configs require leaf=0 and no stream/smem flags')
    print(f"{len(plan)} builds to measure on {name} (sm_{arch})")
    for leaf, batch, threads, mb, sk, ss, cg in plan:
        t0 = time.time()
        ok, log = buildFor(batch, threads, leaf, arch, mb,
                           streamKarat=sk, smemSpill=ss, globalCg=cg)
        cfg = dict(batch=batch, threads=threads, leaf=leaf, minBlocks=mb,
                   workers=workers, repeats=repeats, steps=steps, launches=launches,
                   streamKarat=sk, smemSpill=ss,
                   globalCg=cg, preferL1=preferL1, packed=packed,
                   packedPolynomialState=(PACKED_POLY_STATE == '1') if packed else None,
                   packedDirectReduction=(PACKED_DIRECT_REDUCE == '1') if packed else None,
                   packedGeneratedProduct=(PACKED_GENERATED_PRODUCT == '1') if packed else None,
                   packedClmad=(PACKED_CLMAD == '1') if packed else None,
                   packedClmadSquare=(PACKED_CLMAD_SQUARE == '1') if packed else None,
                   packedKarat3=(PACKED_KARAT3 == '1') if packed else None,
                   packedCompactState=(PACKED_COMPACT_STATE == '1') if packed else None,
                   packedSharedSigma=(PACKED_SHARED_SIGMA == '1') if packed else None,
                   packedTopClmad=(PACKED_TOP_CLMAD == '1') if packed else None,
                   walkTable=(WALK_TABLE == '1') if packed else None,
                   tablePivotBytes=(TABLE_PIVOT_BYTES == '1') if packed else None,
                   packedWeightedPrefix=int(PACKED_WEIGHTED_PREFIX) if packed else None,
                   packedStateTile=int(PACKED_STATE_TILE) if packed else None,
                   buildSeconds=round(time.time() - t0, 1), buildLog=log)
        if not ok:
            results.append(dict(cfg, valid=False, rate=0.0, error=log))
            continue
        cfg['identity'] = benchmarkIdentity(packed)
        cfg.update(measureBench(steps, launches, workers, preferL1, repeats, packed))
        results.append(cfg)
        knobLabel = ' '.join(n for n, on in (('streamKarat', sk), ('smemSpill', ss),
                                             ('globalCg', cg)) if on) or 'no knobs'
        print(f"leaf {leaf} threads {threads} batch {batch} "
              f"minBlocks {mb} [{knobLabel}]: {cfg['rate']:.3f} M it/s median")
    results.sort(key=lambda r: -r.get("rate", 0.0))
    report = {"gpu": name, "cc": arch, "results": results,
              "best": bestResult(results)}
    os.makedirs("/data/autotune", exist_ok=True)
    # Each sweep is evidence, including experiments that lose. Keep the legacy
    # latest-result path too for existing consumers.
    stem = name.replace(' ', '_')
    path = f"/data/autotune/{stem}-{time.time_ns()}.json"
    report['reportPath'] = path
    for dest in (path, f"/data/autotune/{stem}.json"):
        with open(dest, "w") as fh:
            json.dump(report, fh, indent=2)
    volume.commit()
    return report


@app.function(image=image, timeout=4 * HOUR, volumes={"/data": volume})
def runAutolab(batches="4,8,16,32", threadCounts="64,128,256",
               minBlocksList="1,2,3,4", leaves="0,17,33,66,131", arch="", top=6,
               knobs="streamKarat,smemSpill,globalCg"):
    """Search the build space offline, on a CPU container, and return a shortlist.

    ptxas is deterministic and needs no device, so registers, spill traffic and
    the occupancy that follows from them are all measurable without renting a
    GPU -- and this image already carries nvcc and ptxas for the real build.
    What it cannot measure is time, so it produces the few configurations worth
    running through ::autotune rather than a verdict.

    The metric cache lives in the volume keyed by architecture, so a second run
    only compiles what the first one did not."""
    arch = arch or (BAKED_ARCHES[0] if len(BAKED_ARCHES) == 1 else "90")
    os.makedirs("/data/autolab", exist_ok=True)
    out = f"/data/autolab/sm{arch}.json"
    rc, log = sh(
        f"python3 autolab.py --compiler nvcc --cuda-path=/usr/local/cuda "
        f"--ptxas=/usr/local/cuda/bin/ptxas --arch={arch} --batch {batches} "
        f"--threads {threadCounts} --min-blocks {minBlocksList} --leaf {leaves} "
        f"--knobs {knobs or 'none'} --top {top} --out {out}",
        cwd=f"{REMOTE}/codegen",
        timeout=4 * HOUR - 600,
    )
    volume.commit()
    # The front is the product, so read it back rather than scraping the log.
    front, configs = [], ""
    if os.path.exists(out):
        with open(out) as fh:
            saved = json.load(fh)
        front, configs = saved.get("front", []), saved.get("configs", "")
    return {"arch": arch, "returncode": rc, "cache": out, "front": front,
            "configs": configs, "log": log}


@app.function(image=profileImage, gpu=DEFAULT_GPU, timeout=2 * HOUR)
def runProfile(batch=32, threads=128, leaf=0, minBlocks=2, steps=4, launches=1,
               section="", metrics="", workers=0, streamKarat=False,
               smemSpill=False, globalCg=False, preferL1=False, packed=False):
    """Profile the walk kernel with Nsight Compute, or say precisely why not.

    Both a compatible profiler and host counter access are required. Check the
    selected binary before launching; distinguish explicit counter denials
    from generic profiling failures and preserve the complete diagnostic.

    `steps` and `launches` default low: ncu serialises and replays each kernel
    to collect counters, so a profiled launch is orders of magnitude slower than
    a real one.  Four steps is plenty to characterise a kernel whose every step
    is identical."""
    arch = computeCapability()
    name = gpuName()
    rc, ver = sh(f"{NCU_BINARY} --version")
    print(f"profiler: {NCU_BINARY}\n{ver.strip()}", flush=True)
    if rc != 0:
        return {"gpu": name, "available": False,
                "why": "the pinned Nsight Compute binary could not run",
                "returncode": rc, "log": ver, "profilerBinary": NCU_BINARY}
    versionError = profilerVersionError(ver)
    if versionError:
        return {"gpu": name, "available": False, "kind": "unsupported_profiler",
                "why": versionError, "log": ver, "profilerBinary": NCU_BINARY}

    if packed and (leaf or streamKarat or smemSpill):
        raise ValueError('packed arithmetic requires leaf=0 and no stream/smem flags')
    ok, log = buildFor(batch, threads, leaf, arch, minBlocks,
                       streamKarat=streamKarat, smemSpill=smemSpill, globalCg=globalCg)
    if not ok:
        return {"gpu": name, "available": False, "why": "build failed",
                "log": log[-2000:]}

    what = ""
    if metrics:
        what = "--metrics %s" % metrics
    elif section:
        what = "--section %s" % section
    else:
        # Enough to answer where the walk kernel's time goes without asking for
        # the full set, which replays the kernel many more times.
        what = ("--section SpeedOfLight --section MemoryWorkloadAnalysis "
                "--section LaunchStats --section Occupancy "
                "--section WarpStateStats")
    runFlags = f" --threads {workers}" if workers else ""
    if preferL1:
        runFlags += " --prefer-l1"
    if packed:
        runFlags += ' --packed'
    kernelFilter = "--kernel-name-base demangled --kernel-name 'regex:eccPacked131::walk'" if packed else '--kernel-name eccWalkKernel'
    identity = benchmarkIdentity(packed)
    command = (
        f"{NCU_BINARY} --target-processes all {kernelFilter} "
        f"--launch-count 1 {what} "
        f"./ecc2k130 --curve 131 --bench --steps {steps} --launches {launches} "
        f"--verify 0{runFlags}"
    )
    rc, out = shStream(command, timeout=1 * HOUR, prefix="  ncu| ")

    result = profileResult(rc, out)
    result.update(gpu=name, cc=arch, batch=batch, threads=threads, leaf=leaf,
                  minBlocks=minBlocks, workers=workers, identity=identity,
                  streamKarat=streamKarat, smemSpill=smemSpill, globalCg=globalCg,
                  expectedPackedSharedSigma=(PACKED_SHARED_SIGMA == "1") if packed else None,
                  preferL1=preferL1, packed=packed, profilerBinary=NCU_BINARY, profilerVersion=ver,
                  command=command)
    if packed:
        sharedModes = re.findall(r'^packed shared sigma: (.*)$', out, re.MULTILINE)
        actualShared = sharedModes[0] if len(sharedModes) == 1 else None
        result['packedSharedSigma'] = (actualShared == '1') if actualShared in ('0', '1') else None
        if result.get('available') and sharedModes != [PACKED_SHARED_SIGMA]:
            result.update(available=False, kind='packed_identity_mismatch',
                          why='packed shared sigma identity is missing, duplicated or different from the requested build')
    else:
        result['packedSharedSigma'] = None
    return result


# Expected rho iterations, and the weight cutoff that makes walks short enough
# that most of them actually report within the run.
CURVE_FACTS = {
    # curve: (field size m, log2 of expected iterations)
    131: (131, 60.9),
    97: (97, 44.0),
    83: (83, 37.1),
    41: (41, 16.6),
    23: (23, 8.1),
}


def recommendedWeight(curve, walks, plannedIters=0):
    """Pick the distinguished-point cutoff for a given amount of parallelism.

    A walk reports after about 1/theta steps, and each of `walks` parallel walks
    only gets budget/walks steps, so the cutoff has to satisfy 1/theta well below
    that or most walks never report at all.  Aim for a quarter of the budget.

    The budget is the whole expected run only when the run can actually finish.
    ECC2K-130 needs 2^60.9 iterations -- decades of GPU time -- so sizing its
    cutoff against that yields a weight no walk reaches in any session anyone
    will ever run: at the full-run choice a four-hour pass on a fast GPU reports
    about two hundred points in total.  Pass plannedIters and the cutoff is
    sized for the run being done instead, which stores more points per useful
    iteration but is the difference between collecting a corpus and collecting
    nothing.  Storing more is never wrong -- collision probability depends on
    iterations walked, not on how often walks report -- it only costs disk."""
    if curve not in CURVE_FACTS:
        return -1
    m, logIters = CURVE_FACTS[curve]
    budget = 2.0 ** logIters
    if plannedIters > 0:
        budget = min(budget, float(plannedIters))
    budget /= max(1.0, float(walks))
    target = max(64.0, budget / 4.0)
    total = 0
    for k in range(0, m + 1):
        c = 1
        for i in range(k):
            c = c * (m - i) // (i + 1)
        total += c
        p = float(total) / (2.0 ** m)
        if p > 0 and 1.0 / p <= target:
            return k
    return m


DP_RECORD = struct.Struct("<Q3Q")  # seed, then the canonical orbit hash


def corpusFiles(curve, root="/data/dp"):
    """Every distinguished-point file in the volume for one curve."""
    if not os.path.isdir(root):
        return []
    return [os.path.join(root, fn) for fn in sorted(os.listdir(root))
            if fn.startswith(f"curve{curve}-") and fn.endswith(".bin")]


def corpusCount(path):
    """Records in a corpus file.  Fixed-width, so this is a stat, not a scan."""
    if not os.path.exists(path):
        return 0
    return os.path.getsize(path) // DP_RECORD.size


# The client prints a progress line every couple of seconds:
#   "     12.0 s     842.135 M it/s   1234567 iterations    890 dp    889 stored"
PROGRESS_RE = re.compile(
    r"([\d.]+)\s+s\s+([\d.]+)\s+M it/s\s+(\d+)\s+iterations\s+(\d+)\s+dp\s+(\d+)\s+stored"
    r"(?:\s+(\d+)\s+dropped)?")
RESUME_RE = re.compile(r"resumed from .* at iteration (\d+)")
# Status ingest only needs the 40-byte checkpoint header. The walk-state file
# on this geometry is ~370MB, so a 60s full-file cadence still left the page
# idle: volume commits raced, and sync hashed the blob every pass. The sidecar
# is what the feed polls; the full file still lands for resume.
STATUS_HEADER_S = 15
VOLUME_COMMIT_S = 15
PROGRESS_PRINT_S = 15


CKPT_MAGIC = b"ECC2K130"
CKPT_HEADER_BYTES = 40


def packCheckpointHeader(version, m, threads, batch, lanes, runId, iterBase):
    return struct.pack("<8s6IQ", CKPT_MAGIC, int(version), int(m), int(threads),
                       int(batch), int(lanes), int(runId), int(iterBase))


def unpackCheckpointHeader(blob):
    if len(blob) < CKPT_HEADER_BYTES or blob[:8] != CKPT_MAGIC:
        return None
    version, m, threads, batch, lanes, runId = struct.unpack_from("<6I", blob, 8)
    iterBase, = struct.unpack_from("<Q", blob, 32)
    return dict(version=version, m=m, threads=threads, batch=batch,
                lanes=lanes, runId=runId, iterBase=iterBase)


def readCheckpointHeader(path):
    try:
        with open(path, "rb") as fh:
            return unpackCheckpointHeader(fh.read(CKPT_HEADER_BYTES))
    except OSError:
        return None


def writeCheckpointHeaderFile(path, header):
    blob = (packCheckpointHeader(header["version"], header["m"], header["threads"],
                                 header["batch"], header["lanes"], header["runId"],
                                 header["iterBase"])
            if isinstance(header, dict) else header)
    tmp = path + ".tmp"
    with open(tmp, "wb") as fh:
        fh.write(blob)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)
    return blob


def iterBaseFromProgress(resumeIterBase, passIters, walks):
    if int(walks) <= 0:
        return int(resumeIterBase)
    return int(resumeIterBase) + int(passIters) // int(walks)


def parseProgress(line):
    """Pull the numbers out of one client progress line, or None."""
    m = PROGRESS_RE.search(line)
    if not m:
        return None
    return {"seconds": float(m.group(1)), "rate": float(m.group(2)),
            "iters": int(m.group(3)), "dp": int(m.group(4)), "stored": int(m.group(5)),
            "dropped": int(m.group(6)) if m.group(6) else 0}


def parseResumeIterBase(line):
    m = RESUME_RE.search(line)
    return int(m.group(1)) if m else None


def waitForLine(proc, timeout):
    """Read one client line, or None on timeout. Commits must not wait on stdout."""
    if proc.stdout is None:
        return None
    ready, _, _ = select.select([proc.stdout], [], [], max(0.0, timeout))
    if not ready:
        return None
    return proc.stdout.readline()


def defaultStatusHeader(curve, threads, batch, runId, packed):
    return dict(version=2 if packed else 1, m=int(curve), threads=int(threads),
                batch=int(batch), lanes=1 if packed else 32, runId=int(runId),
                iterBase=0)


def tryCommitVolume(volume, ckFile):
    """Skip while the client is still writing the 370MB tmp; retry conflicts."""
    if ckFile and os.path.exists(ckFile + ".tmp"):
        return False
    try:
        volume.commit()
        return True
    except Exception as exc:
        print("  volume commit failed: %s: %s" % (type(exc).__name__, exc), flush=True)
        return False


def humanRate(r):
    """M it/s spans four orders of magnitude between a debug run on a CPU and a
    real one on a GPU, so let the small end keep its digits."""
    return ("%.3f" % r) if r < 10 else ("%.1f" % r)


def humanCount(n):
    """Counts here run to the trillions, where digits stop being readable."""
    for scale, suffix in ((1e12, "T"), (1e9, "G"), (1e6, "M"), (1e3, "k")):
        if n >= scale:
            return "%.2f%s" % (n / scale, suffix)
    return str(int(n))


def humanTime(sec):
    if sec < 0:
        return "0s"
    if sec < 3600:
        return "%dm%02ds" % (sec // 60, sec % 60)
    return "%dh%02dm" % (sec // 3600, (sec % 3600) // 60)


def humanBytes(n):
    for scale, suffix in ((1 << 30, "GB"), (1 << 20, "MB"), (1 << 10, "kB")):
        if n >= scale:
            return "%.1f %s" % (float(n) / scale, suffix)
    return "%d B" % n


@app.function(image=image, gpu=DEFAULT_GPU, timeout=24 * HOUR, volumes={"/data": volume})
def runSearch(hours=1.0, curve=97, batch=8, threads=128, leaf=0, dpWeight=-1,
              runId=1, steps=256, workers=0, rebuild=True, walksTarget=4000000,
              checkpointEvery=60, resume=True, loadMax=50000000, packed=False, verify=0):
    """Collect distinguished points into the volume until the time budget runs
    out.  Records are 32 bytes of (seed, canonical orbit hash); a collision is
    resolved by recomputing both walks from their seeds.

    Nothing here is throwaway.  The container dies at the deadline, but the run
    does not: the client checkpoints its live walks to the volume, reloads the
    corpus at startup so old points still collide with new ones, and is stopped
    with SIGTERM rather than killed so it writes a final checkpoint first.  At
    any instant about a quarter of a run's iterations sit in walks that have not
    yet reported, so a hard kill would throw away 25% of the work done.

    Resuming needs the same shape it saved: curve, runId, worker thread count
    and the build-time batch size all appear in the checkpoint header, and a
    mismatch is rejected without overwriting the checkpoint.  So pass
    the same batch/workers/walksTarget you passed the first time.

    curve=97 is ECC2K-95, which Harley's group solved in 1998 after about
    2.16e13 iterations; the published answer is baked into the generated header
    so a recovered logarithm can be checked against it."""
    if packed and (curve != 131 or leaf):
        raise ValueError('packed search requires curve=131 and leaf=0')
    if int(verify) > 0:
        # --verify N replays the first N reports through the CPU reference
        # before they are written. At dp-weight 32 that is ~2^32 scalar steps
        # per point, and the GPU sits idle while it runs. That is why the
        # recycled 6000s printed "resumed from" and then produced no DPs:
        # the first report never finished verifying. validate/ still uses a
        # budget; campaign collection does not.
        print("WARNING: --verify %d replays reports on the CPU; campaign "
              "collection uses --verify 0 so the walk is not stalled"
              % int(verify), flush=True)
    backendFlag = ' --packed' if packed else ''
    if rebuild:
        ok, log = buildFor(batch, threads, leaf)
        if not ok:
            return {"error": log[-2000:]}
    name = gpuName()
    os.makedirs("/data/dp", exist_ok=True)
    os.makedirs("/data/ckpt", exist_ok=True)
    dpFile = f"/data/dp/curve{curve}-run{runId}.bin"
    ckFile = f"/data/ckpt/curve{curve}-run{runId}.ck"
    rc, out = sh(f"./ecc2k130 --curve {curve} --bench --steps 8 --launches 4 --verify 0{backendFlag}")
    rate = parseRate(out) or 1.0
    # The number of reports comes out at roughly four times the number of
    # parallel walks, because each walk has only total/walks steps to spend and
    # the cutoff is set so it reports a few times within that.  So the walk
    # count, not the GPU, decides how much storage the run needs: cap it.
    workerThreads = workers
    if not workerThreads and walksTarget:
        perThread = batch * (1 if packed else 32)
        workerThreads = max(1024, int(walksTarget) // perThread)
    if not workerThreads:
        match = re.search(r'backend .*?: (\d+) threads', out)
        if not match:
            raise RuntimeError('could not determine the automatic worker count')
        workerThreads = int(match.group(1))
    walks = workerThreads * batch * (1 if packed else 32)
    # The bench above measured this GPU, so the length of the pass about to run
    # is known rather than guessed; size the cutoff against that.
    plannedIters = rate * 1e6 * hours * HOUR
    if dpWeight < 0:
        dpWeight = recommendedWeight(curve, walks, plannedIters)
    print(f"{walks} parallel walks, distinguished-point weight {dpWeight}, "
          f"{plannedIters:.3g} iterations planned this pass")
    cmd = (f"./ecc2k130 --curve {curve} --steps {steps} --run-id {runId} "
           f"--dp-file {dpFile} --verify {verify} --launches 0 --threads {workerThreads} "
           f"--checkpoint-every {int(checkpointEvery)} --load-max {int(loadMax)}")
    cmd += backendFlag
    if resume:
        cmd += f" --checkpoint {ckFile}"
    if dpWeight >= 0:
        cmd += f" --dp-weight {dpWeight}"
    # Every other worker's corpus counts too: a collision between this run and a
    # sibling's is just as good as one within a single run, and finding it here
    # beats waiting for an offline merge.  The client's own dp file reloads
    # itself, so it is not named twice.  It reads newest-first and stops at
    # loadMax, because a collection run that never finishes -- ECC2K-130 is
    # decades of GPU time -- grows a corpus no container can hold in memory.
    for other in sorted(corpusFiles(curve)):
        if other != dpFile:
            cmd += f" --load {other}"
    deadline = time.time() + hours * HOUR
    print(f"{name}: collecting into {dpFile} for {hours} h at ~{rate:.2f} M it/s")
    proc = subprocess.Popen(cmd, shell=True, cwd=REMOTE, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True)
    lines = []
    solved = None
    started = time.time()
    # Stagger the two GPUs on one volume so their commits do not collide.
    lastCommit = started - (int(runId) % 2) * (VOLUME_COMMIT_S / 2.0)
    lastReport = started
    last = None
    stopped = ""
    hdrFile = f"/data/ckpt/curve{curve}-run{runId}.hdr"
    header = readCheckpointHeader(ckFile) or defaultStatusHeader(
        curve, workerThreads, batch, runId, packed)
    resumeIterBase = int(header.get("iterBase", 0) or 0)
    lastWrittenIter = None
    lastHdrAt = 0.0
    # A container's output is the only window into a run that will outlive the
    # terminal that started it, so summarise on a fixed clock rather than
    # relaying the client's own line every two seconds.
    expected = 2.0 ** CURVE_FACTS[curve][1] if curve in CURVE_FACTS else 0.0
    print(f"progress every {PROGRESS_PRINT_S} s; status header every {STATUS_HEADER_S} s; "
          f"checkpoint every {int(checkpointEvery)} s; corpus {dpFile}"
          + (f", checkpoint {ckFile}" if resume else ""), flush=True)

    def pulse(now):
        nonlocal lastCommit, lastReport, lastWrittenIter, lastHdrAt
        # Rewrite the 40-byte sidecar when iterBase moves, at most every
        # STATUS_HEADER_S; commit is a separate clock because two GPUs share
        # the volume.
        moved = header is not None and int(header["iterBase"]) != lastWrittenIter
        if moved and (lastWrittenIter is None or now - lastHdrAt >= STATUS_HEADER_S):
            writeCheckpointHeaderFile(hdrFile, header)
            lastWrittenIter = int(header["iterBase"])
            lastHdrAt = now
        if now - lastCommit >= VOLUME_COMMIT_S:
            lastCommit = now if tryCommitVolume(volume, ckFile) else now - VOLUME_COMMIT_S + 5
        if now - lastReport >= PROGRESS_PRINT_S:
            lastReport = now
            if last:
                frac = (" (%.3f%% of 2^%.1f)" % (100.0 * last["iters"] / expected,
                                                 CURVE_FACTS[curve][1])) if expected else ""
                drop = ("  %s DROPPED" % humanCount(last["dropped"])) if last["dropped"] else ""
                print("[%s] %s M it/s  %s iters%s  %s dp  %s distinct  "
                      "corpus %s  %s left%s"
                      % (humanTime(now - started), humanRate(last["rate"]),
                         humanCount(last["iters"]), frac,
                         humanCount(last["dp"]), humanCount(last["stored"]),
                         humanBytes(os.path.getsize(dpFile) if os.path.exists(dpFile) else 0),
                         humanTime(deadline - now), drop), flush=True)
            else:
                print("[%s] no progress line yet (still starting up?)"
                      % humanTime(now - started), flush=True)

    try:
        while proc.poll() is None:
            now = time.time()
            wait = min(5.0, max(0.0, deadline - now))
            for stamp, every in ((lastCommit, VOLUME_COMMIT_S),
                                 (lastReport, PROGRESS_PRINT_S)):
                wait = min(wait, max(0.0, stamp + every - now))
            line = waitForLine(proc, wait)
            now = time.time()
            if line:
                lines.append(line.rstrip())
                if "k = " in line:
                    solved = line.strip()
                resumed = parseResumeIterBase(line)
                if resumed is not None:
                    resumeIterBase = resumed
                    header["iterBase"] = resumed
                prog = parseProgress(line)
                if prog:
                    last = prog
                    header["iterBase"] = iterBaseFromProgress(
                        resumeIterBase, prog["iters"], walks)
                # Anything that is not a progress line is an event -- a collision, a
                # verification failure, a checkpoint warning -- and is worth showing
                # as it happens rather than only in the tail at the end.
                elif line.strip():
                    print("  " + line.rstrip(), flush=True)
            elif line == "":
                break
            pulse(now)
            if now > deadline:
                stopped = "deadline"
                break
    finally:
        if proc.poll() is None:
            # SIGTERM, not kill: the client finishes the launch in flight, then
            # writes its checkpoint and flushes the corpus.  Draining stdout
            # while it does keeps the pipe from filling and wedging the exit.
            proc.send_signal(signal.SIGTERM)
            graceful = time.time() + 600
            while proc.poll() is None and time.time() < graceful:
                line = proc.stdout.readline()
                if not line:
                    break
                lines.append(line.rstrip())
            try:
                proc.wait(timeout=max(1, graceful - time.time()))
            except Exception:
                stopped = "killed before it could checkpoint"
                proc.kill()
                proc.wait(timeout=60)
    if header is not None:
        writeCheckpointHeaderFile(hdrFile, header)
    # Commit last, so the checkpoint the client just wrote is part of the
    # snapshot rather than the one before it.
    tryCommitVolume(volume, ckFile)
    return {"gpu": name, "distinguishedPoints": corpusCount(dpFile), "file": dpFile,
            "checkpoint": ckFile if os.path.exists(ckFile) else None,
            "checkpointBytes": os.path.getsize(ckFile) if os.path.exists(ckFile) else 0,
            "iterations": last["iters"] if last else 0,
            "rate": last["rate"] if last else 0.0,
            "elapsed": round(time.time() - started, 1),
            "stopped": stopped, "solved": solved, "tail": lines[-25:]}


@app.function(image=image, timeout=2 * HOUR, volumes={"/data": volume})
def mergeCorpus(curve=131):
    """Merge every distinguished-point file in the volume and report duplicate
    hashes, which are the candidate collisions.

    Records are the client's 32-byte binary format, so a partial trailing record
    (a container that died mid-write) is ignored rather than misparsed."""
    seen = {}
    dup = []
    total = 0
    short = 0
    files = corpusFiles(curve)
    if not files:
        return {"error": "no distinguished points yet"}
    for path in files:
        with open(path, "rb") as fh:
            while True:
                rec = fh.read(DP_RECORD.size)
                if len(rec) < DP_RECORD.size:
                    short += len(rec)
                    break
                seed, h0, h1, h2 = DP_RECORD.unpack(rec)
                total += 1
                h = (h0, h1, h2)
                if h in seen and seen[h] != seed:
                    dup.append(("%016x" % seen[h], "%016x" % seed,
                                "%016x%016x%016x" % (h2, h1, h0)))
                else:
                    seen[h] = seed
    return {"files": len(files), "records": total, "distinct": len(seen),
            "truncatedBytes": short, "collisions": dup[:50],
            "collisionCount": len(dup)}


@app.function(image=image, timeout=4 * HOUR, volumes={"/data": volume})
def solveCorpus(curve=131, loadMax=0):
    """Recover the logarithm from a collision spanning several corpora.

    mergeCorpus reports that two seeds reached the same orbit; it does not say
    what k is, and a campaign that ends with collisionCount 1 and no answer has
    not finished.  The client already knows how: --load rebuilds the store from
    the corpora, and a collision found during that reload is rewalked from both
    seeds and solved on the spot.  Nothing here needs a GPU -- rewalking two
    walks is cheap -- so this runs the host build and the whole thing costs a
    container without a card.

    --load-max defaults to off here, which is the opposite of the search, and
    the reason is that the two runs want opposite things.  The cap keeps a long
    collection run inside memory; this wants the whole corpus resident at once,
    because the colliding pair is exactly what a cap might drop.  Which risk
    matters depends on whether the run can finish: a complete ECC2K-95 corpus
    is about 17M points, near 1 GB resident, so uncapped is free.  An ECC2K-130
    collection run does not finish and grows by roughly that much every pass,
    so there uncapped eventually means out of memory -- hence the parameter,
    and hence reporting the size before asking for it rather than after."""
    files = corpusFiles(curve)
    if not files:
        return {"error": "no distinguished points yet"}
    records = 0
    for f in files:
        records += corpusCount(f)
    resident = records * 64          # key, entry and table overhead, roughly
    cmd = ("./ecc2k130-cpu --curve %d --threads 1 --steps 1 --launches 1 "
           "--verify 0 --run-id 65535" % curve)
    if loadMax:
        cmd += " --load-max %d" % int(loadMax)
    for f in files:
        cmd += " --load %s" % f
    print("solving from %d file(s), %s points, roughly %s resident%s"
          % (len(files), humanCount(records), humanBytes(resident),
             "" if not loadMax else " (capped at %s)" % humanCount(loadMax)),
          flush=True)
    rc, out = sh(cmd, timeout=4 * HOUR - 60)
    k = None
    verified = False
    matches = None
    for line in out.splitlines():
        t = line.strip()
        if t.startswith("k = "):
            k = t[4:].strip()
        if "verified [k]P == Q" in t:
            verified = True
        if "matches the published solution:" in t:
            matches = t.split(":")[-1].strip()
    return {"files": len(files), "records": records,
            "residentBytes": resident, "k": k, "verified": verified,
            "matchesPublished": matches, "tail": out.strip()[-1500:]}


# ---------------------------------------------------------------------------
@app.function(image=image, timeout=1 * HOUR)
def runCompileCheck(arch="120", streamKarat=False, smemSpill=False, globalCg=False):
    """Compile experimental device code on a CPU container, without renting a GPU."""
    if not re.fullmatch(r'\d+', arch):
        raise ValueError('arch must be a numeric compute capability')
    ok, log = buildFor(32, 128, 0, arch=arch, streamKarat=streamKarat,
                       smemSpill=smemSpill, globalCg=globalCg)
    if not ok:
        raise RuntimeError(log)
    return dict(arch=arch, cudaImageVersion=CUDA_VERSION, streamKarat=streamKarat,
                smemSpill=smemSpill, globalCg=globalCg, buildLog=log,
                packedPolynomialState=PACKED_POLY_STATE == '1',
                packedDirectReduction=PACKED_DIRECT_REDUCE == '1',
                packedGeneratedProduct=PACKED_GENERATED_PRODUCT == '1',
                packedClmad=PACKED_CLMAD == '1',
                packedClmadSquare=PACKED_CLMAD_SQUARE == '1',
                packedKarat3=PACKED_KARAT3 == '1',
                packedCompactState=PACKED_COMPACT_STATE == '1',
                packedSharedSigma=PACKED_SHARED_SIGMA == '1',
                packedTopClmad=PACKED_TOP_CLMAD == '1',
                walkTable=WALK_TABLE == '1',
                tablePivotBytes=TABLE_PIVOT_BYTES == '1',
                packedWeightedPrefix=int(PACKED_WEIGHTED_PREFIX),
                packedStateTile=int(PACKED_STATE_TILE),
                binarySha256=hashlib.sha256(pathlib.Path(REMOTE, 'ecc2k130').read_bytes()).hexdigest())


@app.local_entrypoint()
def compile_check(arch: str = "120", stream_karat: bool = False,
                  smem_spill: bool = False, global_cg: bool = False):
    print(json.dumps(runCompileCheck.remote(arch=arch, streamKarat=stream_karat,
                                           smemSpill=smem_spill, globalCg=global_cg), indent=2))


@app.local_entrypoint()
def validate(gpu: str = "", batch: int = 32, threads: int = 128, leaf: int = 0,
             min_blocks: int = 2, stream_karat: bool = False, smem_spill: bool = False,
             global_cg: bool = False, prefer_l1: bool = False, packed: bool = False):
    print(onGpu(runValidate, gpu).remote(batch=batch, threads=threads, leaf=leaf,
          minBlocks=min_blocks, streamKarat=stream_karat, smemSpill=smem_spill,
          globalCg=global_cg, preferL1=prefer_l1, packed=packed))


@app.local_entrypoint()
def bench(gpu: str = "", batch: int = 32, threads: int = 128, leaf: int = 0,
          min_blocks: int = 2, steps: int = 64, launches: int = 20,
          workers: int = 0, repeats: int = 3, stream_karat: bool = False,
          smem_spill: bool = False, global_cg: bool = False, prefer_l1: bool = False, packed: bool = False):
    r = onGpu(runBench, gpu).remote(batch=batch, threads=threads, leaf=leaf,
                                    minBlocks=min_blocks, steps=steps, launches=launches,
                                    workers=workers, repeats=repeats, streamKarat=stream_karat,
                                    smemSpill=smem_spill, globalCg=global_cg, preferL1=prefer_l1, packed=packed)
    print(json.dumps(r, indent=2))
    if not r.get('valid'):
        raise RuntimeError('benchmark did not complete successfully')


@app.local_entrypoint()
def waves(gpu: str = "", batch: int = 16, threads: int = 256, leaf: int = 0,
          min_blocks: int = 2, steps: int = 1024, launches: int = 32,
          repeats: int = 3, packed: bool = True, wave_list: str = "1,4,6,8",
          prefer_l1: bool = False):
    """Oversubscribed-grid sweep on one packed binary. --wave-list is 1,4,6,8."""
    r = onGpu(runWaves, gpu).remote(batch=batch, threads=threads, leaf=leaf,
                                    minBlocks=min_blocks, steps=steps,
                                    launches=launches, repeats=repeats,
                                    packed=packed, waves=wave_list,
                                    preferL1=prefer_l1)
    print(json.dumps(r, indent=2))
    if not r.get("valid"):
        raise RuntimeError("wave sweep did not complete successfully")


@app.local_entrypoint()
def autotune(gpu: str = "", batches: str = "8,16,32,64",
             thread_counts: str = "64,128,256", leaves: str = "0,17,33,66",
             min_blocks_list: str = "2,4,8", configs: str = "",
             steps: int = 64, launches: int = 12, workers: int = 0, repeats: int = 3,
             stream_karat: bool = False, smem_spill: bool = False,
             global_cg: bool = False, prefer_l1: bool = False, packed: bool = False):
    """--configs takes leaf:batch:threads:minBlocks entries, as ::autolab
    prints them, and measures exactly those instead of a cross product."""
    r = onGpu(runAutotune, gpu).remote(batches=batches, threadCounts=thread_counts,
                                       leaves=leaves, minBlocksList=min_blocks_list,
                                       configs=configs, steps=steps, launches=launches,
                                       workers=workers, repeats=repeats, streamKarat=stream_karat,
                                       smemSpill=smem_spill, globalCg=global_cg, preferL1=prefer_l1, packed=packed)
    print(json.dumps(r, indent=2))
    if r['best'] is None:
        raise RuntimeError('no benchmark candidate completed successfully')


@app.local_entrypoint()
def autolab(batches: str = "4,8,16,32", thread_counts: str = "64,128,256",
            min_blocks_list: str = "1,2,3,4", leaves: str = "0,17,33,66,131",
            arch: str = "", top: int = 6):
    """Offline build-space search.  No GPU is rented; ptxas does not need one."""
    r = runAutolab.remote(batches=batches, threadCounts=thread_counts,
                          minBlocksList=min_blocks_list, leaves=leaves,
                          arch=arch, top=top)
    print(r["log"])
    print("cache: %s (in the ecc2k130 volume)" % r["cache"])


@app.local_entrypoint()
def campaign(gpu: str = "", batches: str = "4,8,16,32",
             thread_counts: str = "64,128,256", min_blocks_list: str = "1,2,3,4",
             leaves: str = "0,17,33,66,131", top: int = 6, arch: str = ""):
    """Offline search, then measure its Pareto front on the card.

    The two halves are the point: the CPU container maps the whole space for
    the price of compile time, and the GPU only ever runs the handful of builds
    that survived.  Nothing here decides a winner offline -- the ranking that
    comes out of the search is a proxy, and the rates that come out of the
    measurement are the result."""
    r = runAutolab.remote(batches=batches, threadCounts=thread_counts,
                          minBlocksList=min_blocks_list, leaves=leaves,
                          arch=arch, top=top)
    print(r["log"])
    if not r["configs"]:
        print("the offline search produced no front; not renting a GPU")
        return
    print("measuring %d builds on a GPU: %s\n" % (len(r["front"]), r["configs"]))
    m = onGpu(runAutotune, gpu).remote(configs=r["configs"])
    print(json.dumps(m, indent=2))


@app.local_entrypoint()
def profile(gpu: str = "", batch: int = 32, threads: int = 128, leaf: int = 0,
            min_blocks: int = 2, steps: int = 4, section: str = "",
            metrics: str = "", workers: int = 0, stream_karat: bool = False,
            smem_spill: bool = False, global_cg: bool = False, prefer_l1: bool = False, packed: bool = False):
    """Nsight Compute on the walk kernel.

    Print actionable diagnostics and exit nonzero when profiling is unavailable."""
    r = onGpu(runProfile, gpu).remote(batch=batch, threads=threads, leaf=leaf,
                                      minBlocks=min_blocks, steps=steps,
                                      section=section, metrics=metrics, workers=workers,
                                      streamKarat=stream_karat, smemSpill=smem_spill,
                                      globalCg=global_cg, preferL1=prefer_l1, packed=packed)
    if not r.get("available"):
        print("Nsight Compute did not run: %s" % r.get("why"))
        if r.get("remedy"):
            print("  %s" % r["remedy"])
        print(r.get("log", ""))
        raise SystemExit(1)
    print(json.dumps({k: v for k, v in r.items() if k != 'report'}, indent=2))
    print(r["report"])


@app.local_entrypoint()
def search(gpu: str = "", hours: float = 1.0, curve: int = 97, batch: int = 8,
           threads: int = 128, leaf: int = 0, dp_weight: int = -1, run_id: int = 1,
           walks: int = 4000000, load_max: int = 50000000, packed: bool = False,
           verify: int = 0, checkpoint_every: int = 60):
    r = onGpu(runSearch, gpu).remote(hours=hours, curve=curve, batch=batch,
                                     threads=threads, leaf=leaf, dpWeight=dp_weight,
                                     runId=run_id, walksTarget=walks, loadMax=load_max,
                                     packed=packed, verify=verify,
                                     checkpointEvery=checkpoint_every)
    print(json.dumps(r, indent=2))


@app.local_entrypoint()
def fanout(gpu: str = "", count: int = 4, hours: float = 1.0, curve: int = 97,
           batch: int = 8, threads: int = 128, leaf: int = 0, dp_weight: int = -1,
           walks: int = 4000000, load_max: int = 50000000, packed: bool = False,
           verify: int = 0, checkpoint_every: int = 60):
    """Run `count` independent searchers, each with its own run id so their
    seeds never collide, then merge what they produced."""
    fn = onGpu(runSearch, gpu)
    calls = [fn.spawn(hours=hours, curve=curve, batch=batch, threads=threads, leaf=leaf,
                      dpWeight=dp_weight, runId=i + 1, walksTarget=walks, loadMax=load_max,
                      packed=packed, verify=verify, checkpointEvery=checkpoint_every)
             for i in range(count)]
    for c in calls:
        print(json.dumps(c.get(), indent=2))
    print(json.dumps(mergeCorpus.remote(curve=curve), indent=2))


@app.local_entrypoint()
def merge(curve: int = 131, solve: bool = True, load_max: int = 0):
    """Scan the corpora for collisions, and recover k when one is there."""
    r = mergeCorpus.remote(curve=curve)
    print(json.dumps(r, indent=2))
    if solve and r.get("collisionCount"):
        print("\n%d collision(s); recovering the logarithm" % r["collisionCount"])
        print(json.dumps(solveCorpus.remote(curve=curve, loadMax=load_max), indent=2))

