# The ECC2K-130 GPU client: a packed GF(2^131) Pollard rho table walk for
# CUDA devices with a carry-less multiplier, held to fpga/model's golden model.
#
#   make            host tests: every packed routine against the golden model,
#                   the walk itself, the re-walk of reports, and the CPU walker
#                   (no CUDA needed)
#   make gpu        the CUDA client, ec2k-gpu (needs nvcc >= 13.3 for clmad)
#   make bench      throughput on the device (make gpu first)
#   make verify     a short collection with every report re-walked on the host
#   make cpu        the CPU client, ec2k-cpu: the same walk and reports on host
#                   cores, over PMULL (AArch64) or PCLMULQDQ (x86-64) where the
#                   host has one
#   make cpu-bench, cpu-verify      the same two measurements on the host
#   make metal      the Metal client, ec2k-metal (macOS): the same walk and
#                   reports on an Apple GPU, its shader compiled at start-up
#   make metal-test, metal-bench, metal-verify
#   make clean
#
# Build-time knobs (all also -D flags of the kernel; the defaults are the
# configuration README.md measures at 20.08 B/s on an RTX PRO 6000):
#   ARCH       nvcc -gencode flags (default sm_120)
#   THREADS    block size (512) and MINBLOCKS resident blocks per SM (1):
#              one block keeps one copy of the 48.7 KB walk table in shared
#              memory and 64 KB of L1; two blocks of 256 leave 28 KB
#   BATCH      walks per batched inversion per thread (16)
#   NVCC       the compiler (nvcc on PATH)

BUILD ?= build
CC    ?= cc
CXX   ?= g++
NVCC  ?= nvcc
ARCH  ?= -gencode arch=compute_120,code=sm_120
THREADS   ?= 512
MINBLOCKS ?= 1
BATCH     ?= 16

MODEL := ../fpga/model/ecc2k130.c
HDRS  := $(wildcard include/*.h include/*.cuh) src/hostcheck.h

# The kernel's configuration.  Every flag is documented in include/packed131.h,
# include/packedkernels.cuh and include/packedtablewalk.cuh; the host test is
# built with the same set so that the arithmetic it checks is the arithmetic
# the device runs (the host paths of the clmad routines are software).
DEFS := -DECC_BATCH=$(BATCH) -DECC_THREADS=$(THREADS) -DECC_MINBLOCKS=$(MINBLOCKS) \
        -DECC_PACKED_SINGLE_PRODUCT=1 -DECC_PACKED_CACHE_DENOM=1 -DECC_PACKED_BY_VALUE=1 \
        -DECC_PACKED_PERM_SIGMA=3 -DECC_PACKED_POLY_CHAIN=1 -DECC_PACKED_UNROLL_INV=1 \
        -DECC_PACKED_PAIR_PRODUCTS=1 -DECC_PACKED_POLY_STATE=1 -DECC_PACKED_DIRECT_REDUCE=1 \
        -DECC_PACKED_GENERATED_PRODUCT=1 -DECC_PACKED_CLMAD=1 -DECC_PACKED_STATE_TILE=256 \
        -DECC_PACKED_WEIGHTED_PREFIX=2 -DECC_PACKED_COMPACT_STATE=1 \
        -DECC_WALK_TABLE=1 -DECC_TABLE_PIVOT_BYTES=1 -DECC_PACKED_PAIR_ILP=1 \
        -DECC_PACKED_ALU_SQUARE=1 -DECC_TABLE_TAG_DENOM=1 -DECC_TABLE_PIPE_SELECT=1 \
        -DECC_PACKED_CHAIN_FIRST=1 -DECC_PACKED_INLINE_POLY=3 -DECC_UNROLL_SLOTS=1 \
        -DECC_PACKED_FROM_REDUCED=1

.PHONY: all test gpu bench verify cpu cpu-bench cpu-verify metal metal-test metal-bench \
        metal-verify clean

all: test

$(BUILD):
	mkdir -p $(BUILD)

$(BUILD)/model.o: $(MODEL) ../fpga/model/ecc2k130.h | $(BUILD)
	$(CC) -O2 -std=c11 -Wall -Wextra -c $(MODEL) -o $@

HOSTFLAGS := -O2 -std=c++17 -Wall -Wextra -Wno-unknown-pragmas -Wno-unused-function \
             -Wno-unused-parameter $(DEFS)

# The cross-check compiles the device's selection primitives as host code,
# which nvcc does not allow; g++ builds it and both programs link it.
$(BUILD)/hostcheck.o: src/hostcheck.cpp $(HDRS) | $(BUILD)
	$(CXX) $(HOSTFLAGS) -c src/hostcheck.cpp -o $@

$(BUILD)/hosttest: src/hosttest.cpp $(HDRS) $(BUILD)/model.o $(BUILD)/hostcheck.o | $(BUILD)
	$(CXX) $(HOSTFLAGS) src/hosttest.cpp $(BUILD)/hostcheck.o $(BUILD)/model.o -o $@

# ---- the CPU client ---------------------------------------------------------
# Its knobs are src/cpuknobs.h, force-included so that every translation unit
# and the tests agree on them.  Building for the native core lets the compiler
# emit the host's carry-less multiply: -mcpu=native on AArch64 (where
# -march=native names the baseline architecture and drops PMULL again),
# -march=native elsewhere.  CPUARCH= builds for the default target, and the
# -soft test builds the software product on every host, so both paths stay
# held to the model.
CPUNATIVE := $(if $(filter arm64 aarch64,$(shell uname -m)),-mcpu=native,-march=native)
CPUARCH   ?= $(shell $(CXX) $(CPUNATIVE) -x c++ -E /dev/null >/dev/null 2>&1 && echo $(CPUNATIVE))
CPUFLAGS := -O3 -std=c++17 -Wall -Wextra -Wno-unknown-pragmas -Wno-unused-function \
            -Wno-unused-parameter -pthread -include src/cpuknobs.h
CPUHDRS  := $(HDRS) src/client.h src/cpuwalk.h src/cpuknobs.h src/f131.h

$(BUILD)/hostcheck-cpu.o: src/hostcheck.cpp $(CPUHDRS) | $(BUILD)
	$(CXX) $(CPUFLAGS) $(CPUARCH) -c src/hostcheck.cpp -o $@

$(BUILD)/hostcheck-soft.o: src/hostcheck.cpp $(CPUHDRS) | $(BUILD)
	$(CXX) $(CPUFLAGS) -DECC_HOST_CLMUL=0 -c src/hostcheck.cpp -o $@

$(BUILD)/ec2k-cpu: src/ec2k_cpu.cpp $(CPUHDRS) $(BUILD)/model.o $(BUILD)/hostcheck-cpu.o | $(BUILD)
	$(CXX) $(CPUFLAGS) $(CPUARCH) src/ec2k_cpu.cpp $(BUILD)/hostcheck-cpu.o $(BUILD)/model.o -o $@

$(BUILD)/cputest: src/cputest.cpp $(CPUHDRS) $(BUILD)/model.o $(BUILD)/hostcheck-cpu.o | $(BUILD)
	$(CXX) $(CPUFLAGS) $(CPUARCH) src/cputest.cpp $(BUILD)/hostcheck-cpu.o $(BUILD)/model.o -o $@

$(BUILD)/cputest-soft: src/cputest.cpp $(CPUHDRS) $(BUILD)/model.o $(BUILD)/hostcheck-soft.o | $(BUILD)
	$(CXX) $(CPUFLAGS) -DECC_HOST_CLMUL=0 src/cputest.cpp $(BUILD)/hostcheck-soft.o \
	    $(BUILD)/model.o -o $@

cpu: $(BUILD)/ec2k-cpu

cpu-bench: $(BUILD)/ec2k-cpu
	$(BUILD)/ec2k-cpu bench --steps 1024 --launches 64

# The CUDA client's verify, scaled to a host: dp-weight 46 reports about one
# point in 2^13 steps, and the first 300 are re-walked on the model (a re-walk
# is a third of a millisecond per step there, which is what bounds this).
cpu-verify: $(BUILD)/ec2k-cpu
	$(BUILD)/ec2k-cpu walk --run-id 4242 --dp-weight 46 --steps 128 --launches 4 --verify 300

# ---- the Metal client (macOS) -------------------------------------------------
# The kernels are metal/walk.metal behind the same packed headers, rewritten
# as Metal Shading Language by scripts/mslgen.py and compiled by the client
# when it starts, so the Command Line Tools are enough: no offline Metal
# toolchain.  metal-test passes with a note where there is no Metal device.
METALFLAGS := $(CPUFLAGS) -fobjc-arc -I$(BUILD)
METALLIBS  := -framework Metal -framework Foundation
METALHDRS  := $(CPUHDRS) src/metalwalk.h $(BUILD)/walk_metal.inc

$(BUILD)/walk_metal.inc: scripts/mslgen.py metal/walk.metal $(HDRS) | $(BUILD)
	python3 scripts/mslgen.py include metal/walk.metal $@

$(BUILD)/ec2k-metal: src/ec2k_metal.mm $(METALHDRS) $(BUILD)/model.o $(BUILD)/hostcheck-cpu.o
	$(CXX) $(METALFLAGS) $(CPUARCH) src/ec2k_metal.mm $(BUILD)/hostcheck-cpu.o $(BUILD)/model.o \
	    $(METALLIBS) -o $@

$(BUILD)/metaltest: src/metaltest.mm $(METALHDRS) $(BUILD)/model.o $(BUILD)/hostcheck-cpu.o
	$(CXX) $(METALFLAGS) $(CPUARCH) src/metaltest.mm $(BUILD)/hostcheck-cpu.o $(BUILD)/model.o \
	    $(METALLIBS) -o $@

$(BUILD)/metalprof: src/metalprof.mm $(METALHDRS) $(BUILD)/model.o $(BUILD)/hostcheck-cpu.o
	$(CXX) $(METALFLAGS) $(CPUARCH) src/metalprof.mm $(BUILD)/hostcheck-cpu.o $(BUILD)/model.o \
	    $(METALLIBS) -o $@

metal: $(BUILD)/ec2k-metal

metal-test: $(BUILD)/metaltest
	$(BUILD)/metaltest 96

metal-bench: $(BUILD)/ec2k-metal
	$(BUILD)/ec2k-metal bench --steps 256 --launches 16

metal-verify: $(BUILD)/ec2k-metal
	$(BUILD)/ec2k-metal walk --run-id 4242 --dp-weight 46 --steps 128 --launches 4 --verify 300

test: $(BUILD)/hosttest $(BUILD)/cputest $(BUILD)/cputest-soft
	$(BUILD)/hosttest 64
	$(BUILD)/cputest 64
	$(BUILD)/cputest-soft 64

gpu: $(BUILD)/ec2k-gpu

$(BUILD)/ec2k-gpu: src/ec2k_gpu.cu $(HDRS) $(BUILD)/model.o $(BUILD)/hostcheck.o | $(BUILD)
	$(NVCC) -O3 -std=c++17 $(ARCH) $(DEFS) -Xptxas -v -lineinfo -Xcompiler -O3 \
	    src/ec2k_gpu.cu $(BUILD)/hostcheck.o $(BUILD)/model.o -o $@ 2>&1 \
	    | grep -E "Compiling entry|Used|spill|error" | grep -v "0 bytes spill" || true
	@test -x $@

bench: $(BUILD)/ec2k-gpu
	$(BUILD)/ec2k-gpu bench --steps 1024 --launches 64

# dp-weight 46 makes a point appear about once in 2^13 steps, so six launches
# of 96 steps report ~470k points; the first 300 are re-walked on the model.
verify: $(BUILD)/ec2k-gpu
	$(BUILD)/ec2k-gpu walk --run-id 4242 --dp-weight 46 --dp-cap 1048576 --steps 96 \
	    --launches 6 --verify 300

clean:
	rm -rf $(BUILD)
