# ECC2K-130 client.
#
#   make generate     regenerate the arithmetic headers from codegen/
#   make cpu          CPU build (64-bit lanes, OpenMP)
#   make test         run the validation suite
#   make gpu          CUDA build (needs nvcc)
#   make ptx          device-only compile + ptxas report (needs clang or nvcc,
#                     but no GPU) -- register, spill and code-size numbers
#   make verilog      emit the FPGA datapath from the same IR (python3 only)
#   make check-verilog  simulate the emitted RTL against the field model
#
# Build-time knobs:
#   BATCH      walks batched into one field inversion per thread (default 32)
#   THREADS    CUDA block size (default 128)
#   MINBLOCKS  resident blocks per SM to ask ptxas for (default 2)
#   PACKED_SINGLE_PRODUCT  use one polynomial product for packed mul (default 0)
#   PACKED_ADD_COMBINE  join clmul32 class products with adds, not ors (default 0)
#   PACKED_PAIR_ILP  independent buffers for the two paired products (default 0)
#   PACKED_L2_PERSIST  one field blob + stream L2 persist window (default 0)
#   PACKED_TOP_HOIST  hoisted 3-bit product correction, bit-identical (default 0)
#   PACKED_ONB_INV  ONB two-product multiply inside inv131 (default 0)
#   PACKED_FROM_REDUCED  5-word inverse of toPolynomial131 (default 0)
#   PACKED_CLMUL_FLAT  issue 128-bit Karatsuba as 3x lo then 3x hi clmad
#   PACKED_PAIR_CLMUL  twelve-clmad interleaved pair product (default 0)
#   PACKED_ALU_SQR  ONB sqr131 on the logic pipe instead of clmad (default 0)
#   PACKED_SLOT_PIPELINE  overlap next-slot compact loads with the current product
#   TABLE_ADDEND_GLOBAL  table-walk addends from global, selection in shared
#   TABLE_TAG_DENOM  reverse pass rebuilds d from the tag in hist; no
#                    denominator field (default 0; ONE-BLOCK-GEOMETRY.md)
#   TABLE_FUSED  one fused pass per step, alternating slot order (default 0)
#   TABLE_PIPE_SELECT  forward pass issues slot k's products before slot k+1's
#                      selection (default 0)
#   PACKED_CHAIN_FIRST  reverse pass issues inv*d before inv*W (default 0)
#   PHASE_PROFILE  clock64() timing of the walk's three phases, at exit
#   ARCH     CUDA architectures
#
# `make gpu-rtx-pro6000-20b` is the 20 B/s build of ONE-BLOCK-GEOMETRY.md.

MODAL   ?= modal
NVCC    ?= nvcc
CXX     ?= g++
# Apple's clang needs the runtime named separately; everywhere else the driver
# flag is enough.  Only the host walk is threaded, so this is all it reaches.
#   make cpu CXX=clang++ OMPFLAGS="-Xpreprocessor -fopenmp -lomp"
OMPFLAGS ?= -fopenmp
CLANG   ?= clang
PTXAS   ?= ptxas
PTX     ?= /tmp/autolab.ptx
CUDAPATH ?= /usr/local/cuda
BATCH   ?= 32
THREADS ?= 128
MINBLOCKS ?= 2
STREAM_KARAT ?= 0
SMEM_SPILL ?= 0
GLOBAL_CG ?= 0
PACKED_SINGLE_PRODUCT ?= 0
PACKED_CACHE_DENOM ?= 0
PACKED_BY_VALUE ?= 0
PACKED_PERM_SIGMA ?= 0
PACKED_POLY_CHAIN ?= 0
PACKED_UNROLL_INV ?= 0
PACKED_PAIR_PRODUCTS ?= 0
PACKED_POLY_STATE ?= 0
PACKED_DIRECT_REDUCE ?= 0
PACKED_GENERATED_PRODUCT ?= 0
# Bits: 1 inline single polynomial products, 2 inline paired products.
PACKED_INLINE_POLY ?= 0
PACKED_CLMAD ?= 0
PACKED_CLMAD_SQUARE ?= 0
PACKED_KARAT3 ?= 0
PACKED_WEIGHTED_PREFIX ?= 0
PACKED_COMPACT_STATE ?= 0
PACKED_SHARED_SIGMA ?= 0
# Inline the shared walk transform; validated with the fused 120k profile.
PACKED_INLINE_SIGMA ?= 0
PACKED_TOP_CLMAD ?= 0
PACKED_STATE_TILE ?= 0
PACKED_ADD_COMBINE ?= 0
PACKED_PAIR_ILP ?= 0
UNROLL_SLOTS ?= 1
PACKED_SLOT_PREFETCH ?= 0
PACKED_SLOT_PIPELINE ?= 0
PACKED_L2_PERSIST ?= 0
PACKED_TOP_HOIST ?= 0
PACKED_ONB_INV ?= 0
PACKED_FROM_REDUCED ?= 0
PACKED_CLMUL_FLAT ?= 0
PACKED_PAIR_CLMUL ?= 0
PACKED_ALU_SQR ?= 0
# The table walk of ITERATION-FUNCTION.md §4 (tablewalk.h) in place of sigma^j + 1.
WALK_TABLE ?= 0
TABLE_BRANCHES ?= 8
TABLE_PIVOT_BYTES ?= 0
# Read the table from global memory instead of a per-block shared copy.
# Drops the 48 KB smem tax so 80-register builds can resident 3 blocks on
# this SKU's 100 KB/SM; random table lookups then miss the LDS pipe.
TABLE_GLOBAL ?= 0
# Hybrid: selection tables in shared, addend table in global.
TABLE_ADDEND_GLOBAL ?= 0
# Reverse pass rebuilds the denominator from the step tag in hist instead of
# loading the 17-byte field the forward pass stored (no denominator field).
TABLE_TAG_DENOM ?= 0
# One fused pass per step: the reverse pass of step s runs step s+1's
# selection and chain product on the point it just produced (needs TAG_DENOM).
TABLE_FUSED ?= 0
TABLE_FUSED_PIPE ?= 0
# clock64() phase timing of the two-pass walk, printed at exit (diagnostic).
PHASE_PROFILE ?= 0
# Forward pass software-pipelined: slot k's products issue before slot k+1's
# selection (needs TAG_DENOM; two-pass kernel only).
TABLE_PIPE_SELECT ?= 0
# Reverse pass issues the chain product before lambda's.
PACKED_CHAIN_FIRST ?= 0
FROBENIUS_FUSED ?= 0
# Polynomial squaring on the logic pipe instead of the carryless one.
PACKED_ALU_SQUARE ?= 0
# Keep experimental tuning independent: one change per comparison initially.
GPUFLAGS = -Xptxas -v
ifeq ($(GLOBAL_CG),1)
GPUFLAGS += -Xptxas --def-load-cache=cg
endif
# The CPU build picks the widest word the target supports (AVX-512 -> 512 lanes,
# AVX2 -> 256, NEON -> 128, otherwise 64).  Use a portable baseline when the
# build machine and the run machine may differ.  That lever does not work on
# Apple clang, whose driver keeps the host CPU's features regardless of -march:
# MARCH=armv8-a leaves __ARM_FEATURE_SHA3 undefined yet the backend still folds
# XOR trees into EOR3.  Build portable binaries on the target OS.
MARCH   ?= native

# On aarch64 the wide word is NEON, and EOR3 (FEAT_SHA3) is most of what makes
# it faster than the 64-bit fallback rather than merely wider.  -march=native
# does not always imply +sha3 -- GCC on Darwin reports no SHA3 for native on
# cores that have it -- so ask the compiler which spelling actually defines the
# feature macro and take the first that does.  A compiler-accepted +sha3
# spelling is not proof the host can execute EOR3 (armv8.2-a+sha3 is accepted
# on any recent toolchain), so those candidates are used only when the CPU
# reports FEAT_SHA3.  They also rewrite the requested -march, so only search
# when MARCH is native: an explicit MARCH names a target this host is not
# evidence about.  Falling through to plain MARCH still gets NEON and BSL,
# just not the three-input XOR.
HOSTARCH := $(shell uname -m)
HOSTOS   := $(shell uname -s)
ifneq (,$(filter arm64 aarch64,$(HOSTARCH)))
# Linux lists sha3 in cpuinfo Features when FEAT_SHA3 is present.  Darwin has
# no /proc, and every Apple Silicon core has SHA3, so a missing
# hw.optional.arm.FEAT_SHA3 key means present there and absent anywhere else.
ifeq ($(HOSTOS),Darwin)
HOSTSHA3 := $(shell sysctl -n hw.optional.arm.FEAT_SHA3 2>/dev/null || echo 1)
else
HOSTSHA3 := $(shell grep -m1 '^Features' /proc/cpuinfo 2>/dev/null | grep -c -w sha3)
endif
sha3flag = $(shell $(CXX) $(1) -dM -E -x c++ /dev/null 2>/dev/null | grep -c __ARM_FEATURE_SHA3)
SHA3TRY := $(if $(filter native,$(MARCH)), \
    $(if $(filter-out 0,$(HOSTSHA3)), \
        -march=native+sha3 -mcpu=native+sha3 -march=armv8.2-a+sha3))
ARCHFLAGS := $(firstword \
    $(foreach f,-march=$(MARCH) $(SHA3TRY), \
        $(if $(filter-out 0,$(call sha3flag,$(f))),$(f))) \
    -march=$(MARCH))
else
ARCHFLAGS := -march=$(MARCH)
endif
ARCH    ?= -gencode arch=compute_80,code=sm_80 \
           -gencode arch=compute_86,code=sm_86 \
           -gencode arch=compute_89,code=sm_89 \
           -gencode arch=compute_90,code=sm_90 \
           -gencode arch=compute_120,code=sm_120
# clang emits PTX for CLANGARCH; ptxas then compiles that PTX for SMARCH, which
# may be newer than any architecture clang itself knows about (e.g. sm_120).
CLANGARCH ?= sm_90
SMARCH  ?= sm_90

HDRS = include/durable.h include/bitslice.h include/fieldbs.h include/fieldpb.h include/walk.h \
       include/packedfrobeniusfused.cuh \
       include/kernel.h include/ref.h include/solver.h include/bigmod.h include/tablewalk.h \
       include/curveparams.h include/packed131.h include/packedtransform131.h include/packedsigma131.h include/packedpolyreduce131.h include/packeddirectreduce131.h include/packedgeneratedproduct131.h include/packedcompactstate.cuh include/packedkernels.cuh include/packedengine.cuh
GEN  = generated/eccF131.h generated/eccF83.h generated/eccF41.h generated/eccF23.h \
       generated/eccP97.h generated/eccP41.h generated/eccP19.h generated/eccP13.h

COLLECTIVE_WARPS ?= 4
DEFS = -DECC_COLLECTIVE_WARPS=$(COLLECTIVE_WARPS) -DECC_BATCH=$(BATCH) -DECC_THREADS=$(THREADS) -DECC_MINBLOCKS=$(MINBLOCKS) \
       -DECC_STREAM_KARAT=$(STREAM_KARAT) -DECC_SMEM_SPILL=$(SMEM_SPILL) \
       -DECC_PACKED_SINGLE_PRODUCT=$(PACKED_SINGLE_PRODUCT) -DECC_PACKED_CACHE_DENOM=$(PACKED_CACHE_DENOM) \
       -DECC_PACKED_BY_VALUE=$(PACKED_BY_VALUE) -DECC_PACKED_PERM_SIGMA=$(PACKED_PERM_SIGMA) \
       -DECC_PACKED_POLY_CHAIN=$(PACKED_POLY_CHAIN) -DECC_PACKED_UNROLL_INV=$(PACKED_UNROLL_INV) \
       -DECC_PACKED_PAIR_PRODUCTS=$(PACKED_PAIR_PRODUCTS) -DECC_PACKED_POLY_STATE=$(PACKED_POLY_STATE) \
       -DECC_PACKED_DIRECT_REDUCE=$(PACKED_DIRECT_REDUCE) \
       -DECC_PACKED_GENERATED_PRODUCT=$(PACKED_GENERATED_PRODUCT) \
       -DECC_PACKED_INLINE_POLY=$(PACKED_INLINE_POLY) \
       -DECC_PACKED_CLMAD=$(PACKED_CLMAD) -DECC_PACKED_CLMAD_SQUARE=$(PACKED_CLMAD_SQUARE) -DECC_PACKED_KARAT3=$(PACKED_KARAT3) \
       -DECC_PACKED_WEIGHTED_PREFIX=$(PACKED_WEIGHTED_PREFIX) \
       -DECC_PACKED_COMPACT_STATE=$(PACKED_COMPACT_STATE) \
       -DECC_PACKED_SHARED_SIGMA=$(PACKED_SHARED_SIGMA) \
       -DECC_PACKED_INLINE_SIGMA=$(PACKED_INLINE_SIGMA) \
       -DECC_PACKED_TOP_CLMAD=$(PACKED_TOP_CLMAD) \
       -DECC_PACKED_STATE_TILE=$(PACKED_STATE_TILE) \
       -DECC_PACKED_ADD_COMBINE=$(PACKED_ADD_COMBINE) \
       -DECC_PACKED_PAIR_ILP=$(PACKED_PAIR_ILP) \
       -DECC_UNROLL_SLOTS=$(UNROLL_SLOTS) \
       -DECC_PACKED_SLOT_PREFETCH=$(PACKED_SLOT_PREFETCH) \
       -DECC_PACKED_SLOT_PIPELINE=$(PACKED_SLOT_PIPELINE) \
       -DECC_PACKED_L2_PERSIST=$(PACKED_L2_PERSIST) \
       -DECC_PACKED_TOP_HOIST=$(PACKED_TOP_HOIST) \
       -DECC_PACKED_ONB_INV=$(PACKED_ONB_INV) \
       -DECC_PACKED_FROM_REDUCED=$(PACKED_FROM_REDUCED) \
       -DECC_PACKED_CLMUL_FLAT=$(PACKED_CLMUL_FLAT) \
       -DECC_PACKED_PAIR_CLMUL=$(PACKED_PAIR_CLMUL) \
       -DECC_PACKED_ALU_SQR=$(PACKED_ALU_SQR) \
       -DECC_WALK_TABLE=$(WALK_TABLE) -DECC_TABLE_BRANCHES=$(TABLE_BRANCHES) \
       -DECC_TABLE_PIVOT_BYTES=$(TABLE_PIVOT_BYTES) \
       -DECC_TABLE_TAG_DENOM=$(TABLE_TAG_DENOM) -DECC_TABLE_FUSED=$(TABLE_FUSED) -DECC_TABLE_FUSED_PIPE=$(TABLE_FUSED_PIPE) -DECC_PHASE_PROFILE=$(PHASE_PROFILE) -DECC_TABLE_PIPE_SELECT=$(TABLE_PIPE_SELECT) -DECC_PACKED_CHAIN_FIRST=$(PACKED_CHAIN_FIRST) \
       -DECC_FROBENIUS_FUSED=$(FROBENIUS_FUSED) \
       -DECC_TABLE_GLOBAL=$(TABLE_GLOBAL) \
       -DECC_TABLE_ADDEND_GLOBAL=$(TABLE_ADDEND_GLOBAL) \
       -DECC_PACKED_ALU_SQUARE=$(PACKED_ALU_SQUARE)

all: cpu

# The generated leaf is sized to a register file: the largest halving-chain
# multiply whose peak liveness still fits REGS live values.  255 is a GPU's
# register budget and gives a 66-word leaf at m=131.
#
# A smaller leaf for the host is the obvious thing to want and it is measurably
# wrong.  Single core, M4 Pro, NEON words, curve 131, median of five:
#
#   REGS=32   leaf 9     9.820 M it/s
#   REGS=64   leaf 17   10.052
#   REGS=128  leaf 33   10.799
#   REGS=255  leaf 66   11.353
#
# The leaf spills either way -- 59% of the emitted multiply is loads and stores
# even at leaf 66 -- and spilling to a hot stack is cheaper than the extra
# Karatsuba level a small leaf buys.  Both targets want the same leaf.
REGS ?= 255

generate:
	cd codegen && python3 gen.py --out ../generated --regs $(REGS)
	cd codegen && python3 genpacked.py
	cd codegen && python3 gensigma.py
	cd codegen && python3 genshiftedsigma.py
	cd codegen && python3 genpolyreduce.py
	cd codegen && python3 gendirectreduce.py
	python3 codegen/genpackedproduct.py

# FPGA datapath: the same IR emitted as pipelined Verilog instead of C.
# See ../FPGA-CEILING.md; needs python3 only, no FPGA toolchain.
verilog:
	cd codegen && python3 genverilog.py --out ../generated/rtl

# Read the emitted RTL back and simulate it against field.Onb.  Checks the
# emission (stage crossings, register chains, output wiring), not the IR.
check-verilog:
	cd codegen && python3 testverilog.py --rtl ../generated/rtl

cpu: ecc2k130-cpu

ecc2k130-cpu: src/main.cu $(HDRS) $(GEN)
	$(CXX) -O3 -std=c++17 $(ARCHFLAGS) $(OMPFLAGS) $(DEFS) -DECC_NO_CUDA \
	    -Wall -Wno-unused-function -Wno-unknown-pragmas -x c++ src/main.cu -o $@

gpu: ecc2k130

ecc2k130: src/main.cu $(HDRS) $(GEN)
	$(NVCC) -O3 -std=c++17 $(ARCH) $(DEFS) $(GPUFLAGS) -lineinfo -Xcompiler -O3 \
	    -Xcompiler -fopenmp src/main.cu -o $@ -lgomp

# Modal entry-point parameters must survive the trip through click; see
# codegen/checkcli.py.  Cheap, needs nothing installed, and the failure it
# catches is otherwise invisible until someone runs that entry point.
check-cli:
	python3 codegen/genpacked.py --check --out include/packedtransform131.h
	python3 codegen/gensigma.py --check --out include/packedsigma131.h
	python3 codegen/genshiftedsigma.py --check --out include/packedshiftedsigma131.h
	python3 codegen/genpolyreduce.py --check --out include/packedpolyreduce131.h
	python3 codegen/gendirectreduce.py --check --out include/packeddirectreduce131.h
	python3 codegen/checkcli.py modal_app.py
	python3 codegen/checkcli.py profile_diagnostic.py
	python3 codegen/checkcli.py packed_audit.py
	python3 codegen/checkcli.py polystate_audit.py
	python3 codegen/checkcli.py tune_frobenius_v3.py
	python3 codegen/autolab.py --self-test
	python3 -m unittest discover -s codegen -p 'test*report.py'
	python3 -m unittest discover -s codegen -p 'testautotune*.py'
	python3 -m unittest discover -s codegen -p 'testpolystateaudit.py'
	python3 -m unittest discover -s codegen -p 'testdirectbuild.py'
	python3 -m unittest discover -s codegen -p 'testnativebench.py'
	python3 -m unittest discover -s codegen -p 'testirschedule.py'
	python3 -m unittest discover -s codegen -p 'testwdsat.py'

# The iteration exploits an automorphism group of order 2m, and the usual price
# for that is fruitless cycles.  This iteration cannot have them -- it is
# equivariant, so it needs no canonical representative and has nothing for a
# sign to feed back through -- but the arithmetic coincidence that would still
# produce one is checkable, so check it, for every curve, on every change to the
# step schedule.
check-cycles:
	cd codegen && python3 cycles.py --max-length 8

# SAT-based point decomposition (codegen/decomp.py, indexcalc.py).  Kept out of
# `test` because it needs solvers the rest of the repo does not:
#   pip install python-sat pycryptosat
test-decomp:
	cd codegen && python3 testdecomp.py

# Drive the whole campaign shape on a curve that finishes in seconds: several
# workers with disjoint seed spaces, one resumed from its checkpoint, and a
# collision that only the merge can see because no single worker holds both
# halves.  Those are the parts a long run only reaches at the very end.
rehearse: ecc2k130-cpu
	./rehearse.sh

build/test-production: src/testproduction.cpp src/main.cu $(HDRS) $(GEN)
	mkdir -p build
	$(CXX) -O2 -std=c++17 -DECC_NO_CUDA -DECC_BATCH=2 \
	    -DECC_WALK_TABLE=$(WALK_TABLE) -DECC_TABLE_BRANCHES=$(TABLE_BRANCHES) -DECC_TABLE_PIVOT_BYTES=$(TABLE_PIVOT_BYTES) \
	    -Wno-unknown-pragmas -Wno-unused-function src/testproduction.cpp -o $@

# The walks behind a corpus, orbit by orbit, for the status page's forest
# figure (docs/ecc2k130-status/walk-forest/README.md).  Host only.
build/trailforest: src/trailforest.cpp $(HDRS) $(GEN)
	mkdir -p build
	$(CXX) -O2 -std=c++17 $(DEFS) -DECC_NO_CUDA -Wall -Wno-unused-function -Wno-unused-variable \
	    -Wno-unknown-pragmas src/trailforest.cpp -o $@

trailforest: build/trailforest

test-production: ecc2k130-cpu build/test-production
	./build/test-production
	python3 -m unittest discover -s aws -p test_certification.py -v
	python3 -m unittest discover -s aws -p test_bootstrap_contract.py -v
	python3 -m unittest discover -s aws -p test_worker_family.py -v
	python3 -m unittest discover -s aws -p test_status_walks.py -v
	python3 -m unittest discover -s aws -p test_fleet_roll.py -v
	python3 -m unittest discover -s aws -p test_rollout.py -v
	python3 -m unittest discover -s aws -p test_dp_ingest.py -v
	python3 -m unittest discover -s aws -p test_worker_spool.py -v
	python3 -m unittest discover -s aws -p test_controlplane.py -v

# The control plane against real Postgres, Redis and S3 rather than SQLite, a
# fake and a directory.  `services.sh` brings the three up (docker compose
# where there is a daemon, the host's own binaries where there is not), and
# takes them down again whether the suite passed or failed.
#
# Not part of `test` or `test-production`: those must pass on a laptop with no
# services and no network, which is what test_controlplane.py is for.
test-integration:
	aws/integration/services.sh up
	@set -a; . build/integration/env; set +a; \
	  python3 -m unittest discover -s aws -p test_integration.py -v; rc=$$?; \
	  aws/integration/services.sh down; \
	  exit $$rc

# The clients production imports lazily.  Separate from the target above so
# that a run cannot quietly install into somebody's system python.
test-integration-deps:
	python3 -m pip install -r aws/integration/requirements.txt

certify-local: ecc2k130-cpu build/test-production
	python3 aws/certify.py --output build/certification-local.json

# Offline search over the build space against ptxas output, which needs no GPU.
# It ranks nothing it can measure the speed of -- it produces the few
# configurations worth spending GPU time on, for `modal run
# modal_app.py::autotune` to actually measure.  Uses nvcc when CUDAPATH has one
# and the check-cuda clang route when it does not; `modal run
# modal_app.py::autolab` runs the same search in a CPU container that has nvcc.
# Where a walk iteration actually goes, weighted by how many times a step calls
# each routine, plus the model's error against every rate ever measured.  Needs
# PTX for the build in question; make ptx or autolab leaves one behind.
perfmodel:
	cd codegen && python3 perfmodel.py --ptx $(PTX)

autolab:
	cd codegen && python3 autolab.py --cuda-path=$(CUDAPATH) --ptxas=$(PTXAS) \
	    --clang=$(CLANG) --arch=$(patsubst sm_%,%,$(SMARCH))

test-schedule:
	mkdir -p build
	$(CXX) -O2 -std=c++17 -DECC_STREAM_KARAT=0 -Wno-unknown-pragmas src/testschedule.cpp -o build/test-schedule-base
	$(CXX) -O2 -std=c++17 -DECC_STREAM_KARAT=1 -Wno-unknown-pragmas src/testschedule.cpp -o build/test-schedule-stream
	./build/test-schedule-base
	./build/test-schedule-stream

test-packed:
	mkdir -p build
	$(CXX) -O2 -std=c++17 -DECC_PACKED_SINGLE_PRODUCT=0 -DECC_PACKED_DIRECT_REDUCE=0 -DECC_PACKED_GENERATED_PRODUCT=0 -Wno-unknown-pragmas src/testpacked.cpp -o build/test-packed-base
	$(CXX) -O2 -std=c++17 -DECC_PACKED_SINGLE_PRODUCT=1 -DECC_PACKED_DIRECT_REDUCE=0 -DECC_PACKED_GENERATED_PRODUCT=0 -Wno-unknown-pragmas src/testpacked.cpp -o build/test-packed-single
	./build/test-packed-base
	./build/test-packed-single

test-packed-network:
	mkdir -p build
	$(CXX) -O2 -std=c++17 -DECC_PACKED_SINGLE_PRODUCT=1 -DECC_PACKED_BY_VALUE=1 -DECC_PACKED_PERM_SIGMA=3 -DECC_PACKED_DIRECT_REDUCE=0 -DECC_PACKED_GENERATED_PRODUCT=0 -Wno-unknown-pragmas src/testpacked.cpp -o build/test-packed-network
	$(CXX) -O2 -std=c++17 -DECC_PACKED_SINGLE_PRODUCT=1 -DECC_PACKED_BY_VALUE=1 -DECC_PACKED_PERM_SIGMA=3 -DECC_PACKED_DIRECT_REDUCE=1 -DECC_PACKED_GENERATED_PRODUCT=0 -Wno-unknown-pragmas src/testpacked.cpp -o build/test-packed-network-direct
	$(CXX) -O2 -std=c++17 -DECC_PACKED_SINGLE_PRODUCT=1 -DECC_PACKED_BY_VALUE=1 -DECC_PACKED_PERM_SIGMA=3 -DECC_PACKED_DIRECT_REDUCE=1 -DECC_PACKED_GENERATED_PRODUCT=1 -Wno-unknown-pragmas src/testpacked.cpp -o build/test-packed-network-generated
	$(CXX) -O2 -std=c++17 -DECC_PACKED_SINGLE_PRODUCT=1 -DECC_PACKED_BY_VALUE=1 -DECC_PACKED_PERM_SIGMA=3 -DECC_PACKED_DIRECT_REDUCE=1 -DECC_PACKED_ADD_COMBINE=1 -Wno-unknown-pragmas src/testpacked.cpp -o build/test-packed-network-add
	./build/test-packed-network
	./build/test-packed-network-direct
	./build/test-packed-network-generated
	./build/test-packed-network-add

test-generated-product:
	python3 codegen/genpackedproduct.py --check
	python3 -m unittest discover -s codegen -p testgeneratedproduct.py

test-clmad:
	python3 -m unittest discover -s codegen -p testclmad.py
	mkdir -p build
	$(CXX) -O2 -std=c++17 -DECC_PACKED_SINGLE_PRODUCT=1 -DECC_PACKED_BY_VALUE=1 -DECC_PACKED_PERM_SIGMA=3 -DECC_PACKED_DIRECT_REDUCE=1 -DECC_PACKED_GENERATED_PRODUCT=1 -DECC_PACKED_CLMAD=1 -Wno-unknown-pragmas src/testpacked.cpp -o build/test-packed-clmad-host
	$(CXX) -O2 -std=c++17 -DECC_PACKED_SINGLE_PRODUCT=1 -DECC_PACKED_BY_VALUE=1 -DECC_PACKED_PERM_SIGMA=3 -DECC_PACKED_DIRECT_REDUCE=1 -DECC_PACKED_GENERATED_PRODUCT=1 -DECC_PACKED_CLMAD=1 -DECC_PACKED_TOP_CLMAD=1 -Wno-unknown-pragmas src/testpacked.cpp -o build/test-packed-topclmad-host
	$(CXX) -O2 -std=c++17 -DECC_PACKED_SINGLE_PRODUCT=1 -DECC_PACKED_BY_VALUE=1 -DECC_PACKED_PERM_SIGMA=3 -DECC_PACKED_DIRECT_REDUCE=1 -DECC_PACKED_GENERATED_PRODUCT=1 -DECC_PACKED_CLMAD=1 -DECC_PACKED_PAIR_ILP=1 -Wno-unknown-pragmas src/testpacked.cpp -o build/test-packed-pair-ilp-host
	$(CXX) -O2 -std=c++17 -DECC_PACKED_SINGLE_PRODUCT=1 -DECC_PACKED_BY_VALUE=1 -DECC_PACKED_PERM_SIGMA=3 -DECC_PACKED_DIRECT_REDUCE=1 -DECC_PACKED_GENERATED_PRODUCT=1 -DECC_PACKED_CLMAD=1 -DECC_PACKED_TOP_HOIST=1 -Wno-unknown-pragmas src/testpacked.cpp -o build/test-packed-top-hoist-host
	$(CXX) -O2 -std=c++17 -DECC_PACKED_SINGLE_PRODUCT=1 -DECC_PACKED_BY_VALUE=1 -DECC_PACKED_PERM_SIGMA=3 -DECC_PACKED_DIRECT_REDUCE=1 -DECC_PACKED_GENERATED_PRODUCT=1 -DECC_PACKED_CLMAD=1 -DECC_PACKED_UNROLL_INV=1 -DECC_PACKED_ONB_INV=1 -Wno-unknown-pragmas src/testpacked.cpp -o build/test-packed-onb-inv-host
	$(CXX) -O2 -std=c++17 -DECC_PACKED_SINGLE_PRODUCT=1 -DECC_PACKED_BY_VALUE=1 -DECC_PACKED_PERM_SIGMA=3 -DECC_PACKED_DIRECT_REDUCE=1 -DECC_PACKED_GENERATED_PRODUCT=1 -DECC_PACKED_CLMAD=1 -DECC_PACKED_FROM_REDUCED=1 -Wno-unknown-pragmas src/testpacked.cpp -o build/test-packed-from-reduced-host
	$(CXX) -O2 -std=c++17 -DECC_PACKED_SINGLE_PRODUCT=1 -DECC_PACKED_BY_VALUE=1 -DECC_PACKED_PERM_SIGMA=3 -DECC_PACKED_DIRECT_REDUCE=1 -DECC_PACKED_GENERATED_PRODUCT=1 -DECC_PACKED_CLMAD=1 -DECC_PACKED_PAIR_ILP=1 -DECC_PACKED_PAIR_CLMUL=1 -Wno-unknown-pragmas src/testpacked.cpp -o build/test-packed-pair-clmul-host
	$(CXX) -O2 -std=c++17 -DECC_PACKED_SINGLE_PRODUCT=1 -DECC_PACKED_BY_VALUE=1 -DECC_PACKED_PERM_SIGMA=3 -DECC_PACKED_DIRECT_REDUCE=1 -DECC_PACKED_GENERATED_PRODUCT=1 -DECC_PACKED_CLMAD=1 -DECC_PACKED_ALU_SQUARE=1 -DECC_PACKED_ALU_SQR=1 -Wno-unknown-pragmas src/testpacked.cpp -o build/test-packed-alu-sqr-host
	./build/test-packed-clmad-host
	./build/test-packed-topclmad-host
	./build/test-packed-pair-ilp-host
	./build/test-packed-top-hoist-host
	./build/test-packed-onb-inv-host
	./build/test-packed-from-reduced-host
	./build/test-packed-pair-clmul-host
	./build/test-packed-alu-sqr-host

test-clmad-square:
	python3 -m unittest discover -s codegen -p testclmad.py
	mkdir -p build
	$(CXX) -O2 -std=c++17 -DECC_PACKED_SINGLE_PRODUCT=1 -DECC_PACKED_BY_VALUE=1 -DECC_PACKED_PERM_SIGMA=3 -DECC_PACKED_DIRECT_REDUCE=1 -DECC_PACKED_GENERATED_PRODUCT=1 -DECC_PACKED_CLMAD=1 -DECC_PACKED_CLMAD_SQUARE=1 -Wno-unknown-pragmas src/testpacked.cpp -o build/test-packed-clmad-square-host
	./build/test-packed-clmad-square-host

test-karat3:
	mkdir -p build
	$(CXX) -O2 -std=c++17 -DECC_PACKED_SINGLE_PRODUCT=1 -DECC_PACKED_BY_VALUE=1 -DECC_PACKED_PERM_SIGMA=3 -DECC_PACKED_DIRECT_REDUCE=1 -DECC_PACKED_GENERATED_PRODUCT=1 -DECC_PACKED_CLMAD=1 -DECC_PACKED_KARAT3=1 -Wno-unknown-pragmas src/testpacked.cpp -o build/test-packed-karat3-host
	./build/test-packed-karat3-host
	$(CXX) -O2 -std=c++17 -DECC_PACKED_CLMAD=1 -DECC_PACKED_KARAT3=1 -Wno-unknown-pragmas src/testkarat3.cpp -o build/test-karat3-product
	./build/test-karat3-product

test-packed-cuda:
	mkdir -p build
	$(NVCC) -O3 -std=c++17 $(ARCH) $(DEFS) src/testpackedcuda.cu -o build/test-packed-cuda
	./build/test-packed-cuda

test-packed-storage-cuda:
	mkdir -p build
	$(NVCC) -O3 -std=c++17 $(ARCH) $(DEFS) src/testpackedstatecuda.cu -o build/test-packed-storage-cuda
	./build/test-packed-storage-cuda

test-shared-sigma-cuda:
	mkdir -p build
	$(NVCC) -O3 -std=c++17 $(ARCH) $(DEFS) src/testsharedsigmacuda.cu -o build/test-shared-sigma-cuda
	./build/test-shared-sigma-cuda

# Device primitives of the table walk against the host reference; needs a GPU.
# The same probe on the host, for both selection layouts, so a layout change
# is held to the reference before any GPU sees it.
test-table-walk-host:
	mkdir -p build
	$(CXX) -O2 -std=c++17 -DECC_WALK_TABLE=1 -DECC_TABLE_PIVOT_BYTES=0 -Wno-unknown-pragmas -Wno-unused-function src/testtablewalkhost.cpp -o build/test-table-walk-host-nibble
	$(CXX) -O2 -std=c++17 -DECC_WALK_TABLE=1 -DECC_TABLE_PIVOT_BYTES=1 -Wno-unknown-pragmas -Wno-unused-function src/testtablewalkhost.cpp -o build/test-table-walk-host-bytes
	./build/test-table-walk-host-nibble
	./build/test-table-walk-host-bytes

test-table-walk-cuda:
	mkdir -p build
	$(NVCC) -O3 -std=c++17 $(ARCH) $(filter-out -DECC_WALK_TABLE=%,$(DEFS)) -DECC_WALK_TABLE=1 \
	    -Xcompiler -fopenmp src/testtablewalkcuda.cu -o build/test-table-walk-cuda -lgomp
	./build/test-table-walk-cuda
	$(NVCC) -O3 -std=c++17 $(ARCH) $(filter-out -DECC_WALK_TABLE=% -DECC_TABLE_ADDEND_GLOBAL=% -DECC_TABLE_PIVOT_BYTES=%,$(DEFS)) \
	    -DECC_WALK_TABLE=1 -DECC_TABLE_PIVOT_BYTES=1 -DECC_TABLE_ADDEND_GLOBAL=1 \
	    -Xcompiler -fopenmp src/testtablewalkcuda.cu -o build/test-table-walk-cuda-addend-global -lgomp
	./build/test-table-walk-cuda-addend-global

test-timing:
	mkdir -p build
	$(CXX) -O1 -std=c++17 -Wno-unknown-pragmas src/testtiming.cpp -o build/test-timing
	./build/test-timing

# Every host word type this machine can build, against the scalar definitions.
# Built at the tuned architecture so the wide word under test is the one the
# walk will actually use.
test-logic:
	mkdir -p build
	$(CXX) -O2 -std=c++17 $(ARCHFLAGS) -Wno-unknown-pragmas src/testlogic.cpp -o build/test-logic
	./build/test-logic

test: check-cli check-cycles test-schedule test-packed test-packed-network test-generated-product test-clmad test-clmad-square test-karat3 test-timing test-logic test-table-walk-host check-verilog ecc2k130-cpu
	./ecc2k130-cpu --test

# End-to-end: recover planted discrete logarithms on the small curves, through
# both field backends.
break-small: ecc2k130-cpu
	@echo "-- normal basis --"
	@for i in 0 1 2 3; do \
	    ./ecc2k130-cpu --curve 23 --instance $$i --threads 1 --steps 32 --verify 2 | grep -E "planted|MISMATCH"; \
	done
	@for i in 0 1 2 3; do \
	    ./ecc2k130-cpu --curve 41 --instance $$i --threads 4 --steps 64 --verify 2 | grep -E "planted|MISMATCH"; \
	done
	@echo "-- polynomial basis --"
	@for i in 0 1 2 3; do \
	    ./ecc2k130-cpu --curve 19 --instance $$i --threads 1 --steps 16 --verify 2 | grep -E "planted|MISMATCH"; \
	done
	@for i in 0 1 2 3; do \
	    ./ecc2k130-cpu --curve 41 --poly-basis --instance $$i --threads 4 --steps 32 --verify 2 | grep -E "planted|MISMATCH"; \
	done

# Throughput on ECC2K-95's curve.
bench95: ecc2k130-cpu
	./ecc2k130-cpu --curve 97 --bench --steps 32 --launches 8 --verify 0

bench: ecc2k130-cpu
	./ecc2k130-cpu --curve 131 --bench --steps 32 --launches 8 --verify 0

# Type-check the whole CUDA translation unit, host and device, with clang.
# Needs no GPU and no nvcc, only a CUDA include tree at CUDAPATH.  On a machine
# with no toolkit installed, pip supplies one:
#   pip install nvidia-cuda-runtime-cu12 nvidia-cuda-nvcc-cu12 \
#               nvidia-curand-cu12 nvidia-cuda-cccl-cu12
# then point CUDAPATH at a directory holding those include trees merged into
# include/, and PTXAS at nvidia/cuda_nvcc/bin/ptxas.  CLANGARCH must be an
# architecture the local clang knows: clang 18 stops at sm_90.
check-cuda: src/main.cu $(HDRS) $(GEN)
	printf '#include <cuda_runtime.h>\nextern "C" cudaError_t cudaConfigureCall(dim3, dim3, size_t, cudaStream_t);\n' > build/cudashim.h
	$(CLANG) -x cuda --cuda-host-only --cuda-path=$(CUDAPATH) -nocudalib \
	    -Wno-unknown-cuda-version -O2 -std=c++17 $(DEFS) -include build/cudashim.h \
	    -c src/main.cu -o build/main_host.o
	$(CLANG) -x cuda --cuda-device-only --cuda-gpu-arch=$(CLANGARCH) --cuda-path=$(CUDAPATH) \
	    -nocudalib -Wno-unknown-cuda-version -O3 -std=c++17 $(DEFS) \
	    -include build/cudashim.h -S -o build/main_dev.ptx src/main.cu
	$(PTXAS) -arch=$(SMARCH) -O3 -v build/main_dev.ptx -o build/main_dev.cubin

# Where the packed walk's instructions go: no GPU needed.  Prints the ALU
# composition of a scalar update and what a throughput objective implies.
# See THROUGHPUT-30B.md.
path-cost:
	CUDAPATH=$(CUDAPATH) CLANG=$(CLANG)++ python3 path_cost.py $(PATH_COST_ARGS)

# Offline device compile: no GPU needed, reports registers, spills and size.
ptx: src/ptxspike.cu $(HDRS) $(GEN)
	$(CLANG) -x cuda --cuda-device-only --cuda-gpu-arch=$(CLANGARCH) --cuda-path=$(CUDAPATH) \
	    -nocudalib -Wno-unknown-cuda-version -O3 -std=c++17 $(DEFS) -S -o build/spike.ptx src/ptxspike.cu
	$(PTXAS) -arch=$(SMARCH) -O3 -v build/spike.ptx -o build/spike.cubin

# Run on Modal GPUs (see modal_app.py).
modal:
	modal run modal_app.py::bench --gpu H100

# Audited packed configuration for the RTX PRO 6000 Blackwell Server Edition.
RTX_PRO6000_WORKERS ?= 385024
RTX_PRO6000_COMPACT_STATE ?= 1
RTX_PRO6000_SHARED_SIGMA ?= 1
RTX_PRO6000_TOP_CLMAD ?= 0
RTX_PRO6000_CLMAD_SQUARE ?= 0
RTX_PRO6000_KARAT3 ?= 0
RTX_PRO6000_WALK_TABLE ?= 0
RTX_PRO6000_TABLE_PIVOT_BYTES ?= 0
RTX_PRO6000_ENV = ECC_GPU=RTX-PRO-6000 ECC_CUDA_VERSION=13.3.1 \
                 ECC_PACKED_SINGLE_PRODUCT=1 ECC_PACKED_CACHE_DENOM=1 \
                 ECC_PACKED_BY_VALUE=1 ECC_PACKED_PERM_SIGMA=3 \
                 ECC_PACKED_POLY_CHAIN=1 ECC_PACKED_UNROLL_INV=1 \
                 ECC_PACKED_PAIR_PRODUCTS=1 ECC_PACKED_POLY_STATE=1 ECC_PACKED_DIRECT_REDUCE=1 \
                 ECC_PACKED_GENERATED_PRODUCT=1 ECC_PACKED_CLMAD=1 ECC_PACKED_STATE_TILE=256 \
                 ECC_PACKED_WEIGHTED_PREFIX=2 ECC_PACKED_COMPACT_STATE=$(RTX_PRO6000_COMPACT_STATE) \
                 ECC_PACKED_SHARED_SIGMA=$(RTX_PRO6000_SHARED_SIGMA) \
                 ECC_PACKED_TOP_CLMAD=$(RTX_PRO6000_TOP_CLMAD) \
                 ECC_PACKED_CLMAD_SQUARE=$(RTX_PRO6000_CLMAD_SQUARE) \
                 ECC_PACKED_KARAT3=$(RTX_PRO6000_KARAT3) \
                 ECC_WALK_TABLE=$(RTX_PRO6000_WALK_TABLE) \
                 ECC_TABLE_PIVOT_BYTES=$(RTX_PRO6000_TABLE_PIVOT_BYTES)

bench-rtx-pro6000:
	$(RTX_PRO6000_ENV) $(MODAL) run modal_app.py::bench --packed \
	    --batch 16 --threads 256 --leaf 0 --min-blocks 2 \
	    --steps 1024 --launches 32 --repeats 3 --workers $(RTX_PRO6000_WORKERS)

# The 20 B/s configuration of ONE-BLOCK-GEOMETRY.md: the table walk in one
# 512-thread block per SM (64 KB of L1 instead of 28), denominators rebuilt
# from the step tag, the products inlined, the forward pass software-pipelined.
# Local nvcc build (CUDA 13.3+); measured 20.08 B/s median on an RTX PRO 6000.
gpu-rtx-pro6000-20b:
	$(MAKE) -B ecc2k130 ARCH="-gencode arch=compute_120,code=sm_120" \
	    BATCH=16 THREADS=512 MINBLOCKS=1 \
	    PACKED_SINGLE_PRODUCT=1 PACKED_CACHE_DENOM=1 PACKED_BY_VALUE=1 PACKED_PERM_SIGMA=3 \
	    PACKED_POLY_CHAIN=1 PACKED_UNROLL_INV=1 PACKED_PAIR_PRODUCTS=1 PACKED_POLY_STATE=1 \
	    PACKED_DIRECT_REDUCE=1 PACKED_GENERATED_PRODUCT=1 PACKED_CLMAD=1 PACKED_STATE_TILE=256 \
	    PACKED_WEIGHTED_PREFIX=2 PACKED_COMPACT_STATE=1 PACKED_SHARED_SIGMA=1 \
	    WALK_TABLE=1 TABLE_PIVOT_BYTES=1 PACKED_PAIR_ILP=1 PACKED_L2_PERSIST=1 PACKED_ALU_SQUARE=1 \
	    TABLE_TAG_DENOM=1 TABLE_PIPE_SELECT=1 PACKED_CHAIN_FIRST=1 \
	    PACKED_INLINE_POLY=3 UNROLL_SLOTS=1 PACKED_FROM_REDUCED=1

# Ada preset for the EC2 g6 (L4) and g6e (L40S) instance types, both sm_89.
# It is the RTX PRO 6000 arithmetic/storage preset. CLMAD is on: the
# preblackwell receipt measured 1.811× on L40S and 1.881× on L4 against the
# software product. ADA_CLMAD=0 is the superseded before-arm.
ADA_GPU ?= L40S
ADA_CUDA ?= 13.3.1
ADA_CLMAD ?= 1
ADA_COMPACT_STATE ?= 1
ADA_SHARED_SIGMA ?= 1
ADA_ENV = ECC_GPU=$(ADA_GPU) ECC_CUDA_VERSION=$(ADA_CUDA) \
                 ECC_PACKED_SINGLE_PRODUCT=1 ECC_PACKED_CACHE_DENOM=1 \
                 ECC_PACKED_BY_VALUE=1 ECC_PACKED_PERM_SIGMA=3 \
                 ECC_PACKED_POLY_CHAIN=1 ECC_PACKED_UNROLL_INV=1 \
                 ECC_PACKED_PAIR_PRODUCTS=1 ECC_PACKED_POLY_STATE=1 ECC_PACKED_DIRECT_REDUCE=1 \
                 ECC_PACKED_GENERATED_PRODUCT=1 ECC_PACKED_CLMAD=$(ADA_CLMAD) ECC_PACKED_STATE_TILE=256 \
                 ECC_PACKED_WEIGHTED_PREFIX=2 ECC_PACKED_COMPACT_STATE=$(ADA_COMPACT_STATE) \
                 ECC_PACKED_SHARED_SIGMA=$(ADA_SHARED_SIGMA) \
                 ECC_PACKED_TOP_CLMAD=0

# Workers stay automatic.  The RTX PRO 6000 preset's 385,024 is four waves on a
# 188-SM part and has no claim on a 142-SM (L40S) or 58-SM (L4) one; automatic
# scales with multiProcessorCount and the occupancy the build actually admits
# (autoThreads in include/packedengine.cuh).
bench-ada-modal:
	$(ADA_ENV) $(MODAL) run modal_app.py::bench --packed \
	    --batch 16 --threads 256 --leaf 0 --min-blocks 2 \
	    --steps 1024 --launches 32 --repeats 3

# Instance-type aliases. g6 is L4, g6e is L40S, both sm_89. Workers stay
# automatic. CLMAD defaults on after the preblackwell receipt.
bench-g6-modal:
	$(MAKE) bench-ada-modal ADA_GPU=L4

bench-g6e-modal:
	$(MAKE) bench-ada-modal ADA_GPU=L40S

# Datacenter Blackwell B200 (Modal), sm_100. Same arithmetic/storage preset as
# the RTX PRO 6000; workers stay automatic — 385,024 is a 188-SM occupancy
# and has no claim on a 148-SM part. See B200.md. B200_CLMAD=0 is the
# software-product before-arm.
B200_CLMAD ?= 1
B200_ENV = ECC_GPU=B200 ECC_CUDA_VERSION=13.3.1 \
                 ECC_PACKED_SINGLE_PRODUCT=1 ECC_PACKED_CACHE_DENOM=1 \
                 ECC_PACKED_BY_VALUE=1 ECC_PACKED_PERM_SIGMA=3 \
                 ECC_PACKED_POLY_CHAIN=1 ECC_PACKED_UNROLL_INV=1 \
                 ECC_PACKED_PAIR_PRODUCTS=1 ECC_PACKED_POLY_STATE=1 ECC_PACKED_DIRECT_REDUCE=1 \
                 ECC_PACKED_GENERATED_PRODUCT=1 ECC_PACKED_CLMAD=$(B200_CLMAD) ECC_PACKED_STATE_TILE=256 \
                 ECC_PACKED_WEIGHTED_PREFIX=2 ECC_PACKED_COMPACT_STATE=1 \
                 ECC_PACKED_SHARED_SIGMA=1 \
                 ECC_PACKED_TOP_CLMAD=0

bench-b200-modal:
	$(B200_ENV) $(MODAL) run modal_app.py::bench --packed \
	    --batch 16 --threads 256 --leaf 0 --min-blocks 2 \
	    --steps 1024 --launches 32 --repeats 3

validate-b200-modal:
	$(B200_ENV) $(MODAL) run modal_app.py::validate --packed \
	    --batch 16 --threads 256 --leaf 0 --min-blocks 2

# Per-SM occupancy: several wave multipliers of automatic workers on one
# allocation. See benchmarks/per-sm/WAVES.md. WAVES_GPU selects the part;
# default is the campaign 6000. Does not change the shipping 385,024 preset.
WAVES_GPU ?= RTX-PRO-6000
WAVES_LIST ?= 1,4,6,8
WAVES_ENV = ECC_GPU=$(WAVES_GPU) ECC_CUDA_VERSION=13.3.1 \
                 ECC_PACKED_SINGLE_PRODUCT=1 ECC_PACKED_CACHE_DENOM=1 \
                 ECC_PACKED_BY_VALUE=1 ECC_PACKED_PERM_SIGMA=3 \
                 ECC_PACKED_POLY_CHAIN=1 ECC_PACKED_UNROLL_INV=1 \
                 ECC_PACKED_PAIR_PRODUCTS=1 ECC_PACKED_POLY_STATE=1 ECC_PACKED_DIRECT_REDUCE=1 \
                 ECC_PACKED_GENERATED_PRODUCT=1 ECC_PACKED_CLMAD=1 ECC_PACKED_STATE_TILE=256 \
                 ECC_PACKED_WEIGHTED_PREFIX=2 ECC_PACKED_COMPACT_STATE=1 \
                 ECC_PACKED_SHARED_SIGMA=1 \
                 ECC_PACKED_TOP_CLMAD=0

bench-waves-modal:
	$(WAVES_ENV) $(MODAL) run modal_app.py::waves --packed \
	    --batch 16 --threads 256 --leaf 0 --min-blocks 2 \
	    --steps 1024 --launches 32 --repeats 3 --wave-list $(WAVES_LIST)

# Turing T4 (EC2 g4dn), sm_75. Software product only; see T4-G4DN.md.
T4_ENV = ECC_GPU=T4 ECC_CUDA_VERSION=13.3.1 \
                 ECC_PACKED_SINGLE_PRODUCT=1 ECC_PACKED_CACHE_DENOM=1 \
                 ECC_PACKED_BY_VALUE=1 ECC_PACKED_PERM_SIGMA=3 \
                 ECC_PACKED_POLY_CHAIN=1 ECC_PACKED_UNROLL_INV=1 \
                 ECC_PACKED_PAIR_PRODUCTS=1 ECC_PACKED_POLY_STATE=1 ECC_PACKED_DIRECT_REDUCE=1 \
                 ECC_PACKED_GENERATED_PRODUCT=1 ECC_PACKED_CLMAD=0 ECC_PACKED_STATE_TILE=256 \
                 ECC_PACKED_WEIGHTED_PREFIX=2 ECC_PACKED_COMPACT_STATE=1 \
                 ECC_PACKED_SHARED_SIGMA=1 \
                 ECC_PACKED_TOP_CLMAD=0

bench-g4dn-modal:
	$(T4_ENV) $(MODAL) run modal_app.py::bench --packed \
	    --batch 16 --threads 256 --leaf 0 --min-blocks 2 \
	    --steps 1024 --launches 32 --repeats 3

# One matched packed-walk recipe on any Modal GPU type. Workers stay
# automatic. SURVEY_CLMAD defaults on; T4 must pass 0 (no clmad on sm_75).
# See benchmarks/modal-gpus/SURVEY.md. Do not pass --workers: 385,024 is a
# 188-SM occupancy.
SURVEY_GPU ?= L40S
SURVEY_CLMAD ?= 1
SURVEY_ENV = ECC_GPU=$(SURVEY_GPU) ECC_CUDA_VERSION=13.3.1 \
                 ECC_PACKED_SINGLE_PRODUCT=1 ECC_PACKED_CACHE_DENOM=1 \
                 ECC_PACKED_BY_VALUE=1 ECC_PACKED_PERM_SIGMA=3 \
                 ECC_PACKED_POLY_CHAIN=1 ECC_PACKED_UNROLL_INV=1 \
                 ECC_PACKED_PAIR_PRODUCTS=1 ECC_PACKED_POLY_STATE=1 ECC_PACKED_DIRECT_REDUCE=1 \
                 ECC_PACKED_GENERATED_PRODUCT=1 ECC_PACKED_CLMAD=$(SURVEY_CLMAD) ECC_PACKED_STATE_TILE=256 \
                 ECC_PACKED_WEIGHTED_PREFIX=2 ECC_PACKED_COMPACT_STATE=1 \
                 ECC_PACKED_SHARED_SIGMA=1 \
                 ECC_PACKED_TOP_CLMAD=0

bench-modal-gpu:
	$(SURVEY_ENV) $(MODAL) run modal_app.py::bench --packed \
	    --batch 16 --threads 256 --leaf 0 --min-blocks 2 \
	    --steps 1024 --launches 32 --repeats 3

# Thin native clients for one architecture. Need nvcc. These are the
# binaries a g6 / g6e / g4dn worker should run; the campaign fat default
# is still sm_120. Ada (g6/g6e) ships CLMAD=1; Turing (g4dn) cannot.
ADA_PACKED = BATCH=16 THREADS=256 MINBLOCKS=2 \
	PACKED_SINGLE_PRODUCT=1 PACKED_CACHE_DENOM=1 PACKED_BY_VALUE=1 \
	PACKED_PERM_SIGMA=3 PACKED_POLY_CHAIN=1 PACKED_UNROLL_INV=1 \
	PACKED_PAIR_PRODUCTS=1 PACKED_POLY_STATE=1 PACKED_DIRECT_REDUCE=1 \
	PACKED_GENERATED_PRODUCT=1 PACKED_CLMAD=1 PACKED_STATE_TILE=256 \
	PACKED_WEIGHTED_PREFIX=2 PACKED_COMPACT_STATE=1 PACKED_SHARED_SIGMA=1 \
	PACKED_TOP_CLMAD=0
T4_PACKED = BATCH=16 THREADS=256 MINBLOCKS=2 \
	PACKED_SINGLE_PRODUCT=1 PACKED_CACHE_DENOM=1 PACKED_BY_VALUE=1 \
	PACKED_PERM_SIGMA=3 PACKED_POLY_CHAIN=1 PACKED_UNROLL_INV=1 \
	PACKED_PAIR_PRODUCTS=1 PACKED_POLY_STATE=1 PACKED_DIRECT_REDUCE=1 \
	PACKED_GENERATED_PRODUCT=1 PACKED_CLMAD=0 PACKED_STATE_TILE=256 \
	PACKED_WEIGHTED_PREFIX=2 PACKED_COMPACT_STATE=1 PACKED_SHARED_SIGMA=1 \
	PACKED_TOP_CLMAD=0

gpu-g6 gpu-g6e:
	$(MAKE) gpu ARCH="-gencode arch=compute_89,code=sm_89" $(ADA_PACKED)

gpu-g4dn:
	$(MAKE) gpu ARCH="-gencode arch=compute_75,code=sm_75" $(T4_PACKED)

# On the g6/g6e instance itself, where the part actually is.  Measures both
# arms of the CLMAD question rather than assuming either.
bench-ada:
	bash benchmarks/ada/run.sh

bench-g4dn:
	bash benchmarks/t4/run.sh

# The g7 fleet runs the RTX PRO 4500, for which this tree records no rate at
# all; see RTX-PRO4500.md for the purchasing decision that waits on one. Unlike
# the RTX PRO 6000 targets this does not go through Modal -- it runs on the EC2
# instance itself, where the part actually is.
bench-rtx-pro4500:
	bash benchmarks/rtx-pro4500/run.sh

audit-rtx-pro6000:
	mkdir -p build
	$(RTX_PRO6000_ENV) $(MODAL) run packed_audit.py --batch 16 --min-blocks 2 --block-threads 256 --repeats 3 --workers $(RTX_PRO6000_WORKERS) \
	    --output build/rtx-pro6000-audit.json

clean:
	rm -f ecc2k130 ecc2k130-cpu build/*.ptx build/*.cubin build/*.o build/cudashim.h
	rm -f build/test-schedule-base build/test-schedule-stream
	rm -f build/test-packed build/test-packed-base build/test-packed-single
	rm -f build/test-packed-network build/test-packed-network-direct build/test-packed-network-generated build/test-packed-network-add
	rm -f build/test-packed-clmad-host build/test-packed-topclmad-host build/test-packed-pair-ilp-host build/test-packed-clmad-square-host
	rm -f build/test-packed-top-hoist-host build/test-packed-onb-inv-host
	rm -f build/test-packed-from-reduced-host
	rm -f build/test-packed-pair-clmul-host build/test-packed-alu-sqr-host
	rm -f build/test-packed-cuda build/test-packed-storage-cuda
	rm -f build/test-shared-sigma-cuda
	rm -f build/test-timing build/test-logic build/test-table-walk-host-nibble build/test-table-walk-host-bytes

.PHONY: path-cost all generate check-cli check-cycles perfmodel test-decomp test-schedule test-packed test-packed-network test-generated-product test-clmad test-clmad-square test-karat3 test-packed-cuda test-packed-storage-cuda test-shared-sigma-cuda test-timing test-logic test-table-walk-host test-table-walk-cuda test-production certify-local rehearse autolab cpu gpu test break-small bench bench95 ptx check-cuda modal bench-rtx-pro6000 bench-rtx-pro4500 bench-ada bench-ada-modal bench-g6-modal bench-g6e-modal bench-g4dn-modal bench-g4dn bench-b200-modal validate-b200-modal bench-waves-modal bench-modal-gpu gpu-g6 gpu-g6e gpu-g4dn audit-rtx-pro6000 clean

.PHONY: gpu-goal22
gpu-goal22:
	$(MAKE) -B ecc2k130 'ARCH=-gencode arch=compute_120,code=sm_120' BATCH=16 THREADS=640 MINBLOCKS=1 PACKED_SINGLE_PRODUCT=1 PACKED_CACHE_DENOM=1 PACKED_BY_VALUE=1 PACKED_PERM_SIGMA=3 PACKED_POLY_CHAIN=1 PACKED_UNROLL_INV=1 PACKED_PAIR_PRODUCTS=1 PACKED_POLY_STATE=1 PACKED_DIRECT_REDUCE=1 PACKED_GENERATED_PRODUCT=1 PACKED_CLMAD=1 PACKED_STATE_TILE=256 PACKED_WEIGHTED_PREFIX=2 PACKED_COMPACT_STATE=1 PACKED_SHARED_SIGMA=1 WALK_TABLE=1 TABLE_PIVOT_BYTES=1 PACKED_PAIR_ILP=0 PACKED_L2_PERSIST=1 PACKED_ALU_SQUARE=1 TABLE_TAG_DENOM=1 TABLE_PIPE_SELECT=0 PACKED_CHAIN_FIRST=1 PACKED_INLINE_POLY=3 UNROLL_SLOTS=1 PACKED_FROM_REDUCED=1

# Cloud persistence checks never start a GPU, database, or ingester.
.PHONY: check-cloud
check-cloud:
	python3 -m unittest discover -s tests -v
	python3 -m unittest discover -s aws -p 'test*.py' -v
	python3 codegen/checkcli.py modal_worker.py

.PHONY: gpu-rtx-pro6000-22b
gpu-rtx-pro6000-22b: gpu-goal22

# Production collection must preserve the existing ecc2k-130 walk and DP32.
# The faster table-walk research profile above remains a separate algorithm.
LEGACY_PRODUCTION_FLAGS = BATCH=16 THREADS=256 MINBLOCKS=2 \
    PACKED_SINGLE_PRODUCT=1 PACKED_CACHE_DENOM=1 PACKED_BY_VALUE=1 PACKED_PERM_SIGMA=3 \
    PACKED_POLY_CHAIN=1 PACKED_UNROLL_INV=1 PACKED_PAIR_PRODUCTS=1 PACKED_POLY_STATE=1 \
    PACKED_DIRECT_REDUCE=1 PACKED_GENERATED_PRODUCT=1 PACKED_CLMAD=1 PACKED_STATE_TILE=256 \
    PACKED_WEIGHTED_PREFIX=2 PACKED_COMPACT_STATE=1 PACKED_SHARED_SIGMA=1 WALK_TABLE=0 \
    COLLECTIVE_WARPS=0

.PHONY: gpu-production check-production-gpu
gpu-production:
	$(MAKE) -B ecc2k130 'ARCH=-gencode arch=compute_120,code=sm_120' $(FROBENIUS_120K_FLAGS)

check-production-gpu:
	$(MAKE) test-packed-cuda test-packed-storage-cuda test-shared-sigma-cuda \
	    'ARCH=-gencode arch=compute_120,code=sm_120' $(FROBENIUS_120K_FLAGS)
	python3 codegen/testpackedclient.py ./ecc2k130

# Same Frobenius walk, DP32 records and checkpoint v2 as the legacy campaign.
# Preserve the older 385,024-worker geometry and select scalar inversion:
# the table profile's default four-warp inverse is slower for this workload.
FROBENIUS_FAST_FLAGS = $(LEGACY_PRODUCTION_FLAGS) PACKED_FROM_REDUCED=1 \
    PACKED_INLINE_POLY=3 PACKED_L2_PERSIST=0 PACKED_ALU_SQUARE=1

# Selected production profile for a fresh 120,320-worker population.
# It preserves the walk, but must not load 385,024-worker checkpoints.
# Reuse updated coordinates to prepare the following step, and issue the
# reverse chain product first. The DP32 walk and checkpoint bytes are unchanged.
# Inline the shared Frobenius transform in this measured profile only.
FROBENIUS_120K_FLAGS = $(filter-out THREADS=% MINBLOCKS=% COLLECTIVE_WARPS=%,$(LEGACY_PRODUCTION_FLAGS)) \
    THREADS=640 MINBLOCKS=1 COLLECTIVE_WARPS=4 PACKED_FROM_REDUCED=1 \
    PACKED_INLINE_POLY=3 PACKED_L2_PERSIST=1 PACKED_ALU_SQUARE=1 PACKED_CHAIN_FIRST=1 \
    FROBENIUS_FUSED=1 PACKED_INLINE_SIGMA=1 PACKED_ONB_INV=1

.PHONY: gpu-frobenius32-fast gpu-frobenius32-120k check-frobenius32-fast-gpu
gpu-frobenius32-fast:
	$(MAKE) -B ecc2k130 'ARCH=-gencode arch=compute_120,code=sm_120' $(FROBENIUS_FAST_FLAGS)

gpu-frobenius32-120k:
	$(MAKE) -B ecc2k130 'ARCH=-gencode arch=compute_120,code=sm_120' $(FROBENIUS_120K_FLAGS)

check-frobenius32-fast-gpu: gpu-frobenius32-fast
	$(MAKE) test-packed-cuda test-packed-storage-cuda test-shared-sigma-cuda \
	    'ARCH=-gencode arch=compute_120,code=sm_120' $(FROBENIUS_FAST_FLAGS)
	python3 codegen/testpackedclient.py ./ecc2k130
