# The ECC2K-130 GPU client: packed GF(2^131) Pollard rho for CUDA devices with
# a carry-less multiplier, held to fpga/model's golden model.
#
#   make            host test: every packed routine against the golden model,
#                   the walk itself, the campaign's known answers and the
#                   re-walk of reports (no CUDA needed)
#   make gpu        the client, ec2k-gpu (needs nvcc >= 13.3 for clmad)
#   make bench      throughput on the device (make gpu first)
#   make verify     a short collection with every report re-walked on the host
#   make clean
#
# WALK picks the iteration function, and with it the corpus a point can
# collide with:
#   sigma  (default) R' = R + sigma^j(R), j = 3 + ((HW(x) >> 1) & 7), the walk
#          of Bailey et al. and of fpga/model, which the live ecc2k-130
#          campaign runs.  Built with the campaign fleet's knobs.  Points from
#          this build are points of that campaign.
#   table  the r-adding table walk README.md measures at 20.08 B/s.  A
#          different iteration function: its points never collide with the
#          campaign's, so it is a throughput experiment, not collection.
#
# Build-time knobs (all also -D flags of the kernel):
#   ARCH       nvcc -gencode flags (default sm_120)
#   THREADS    block size and MINBLOCKS resident blocks per SM (per WALK below)
#   BATCH      walks per batched inversion per thread (16)
#   NVCC       the compiler (nvcc on PATH)

CC    ?= cc
CXX   ?= g++
NVCC  ?= nvcc
ARCH  ?= -gencode arch=compute_120,code=sm_120
WALK  ?= sigma
BATCH ?= 16

ifeq ($(WALK),sigma)
# The campaign fleet's preset (github.com/aburan28/crypto ecc2k130/aws/build.sh):
# two 256-thread blocks per SM, the Frobenius masks in shared memory.
THREADS   ?= 256
MINBLOCKS ?= 2
WALKDEFS  := -DECC_WALK_TABLE=0 -DECC_PACKED_SHARED_SIGMA=1
else ifeq ($(WALK),table)
# One block of 512 threads keeps one copy of the 48.7 KB walk table in shared
# memory and 64 KB of L1; two blocks of 256 leave 28 KB.
THREADS   ?= 512
MINBLOCKS ?= 1
WALKDEFS  := -DECC_WALK_TABLE=1 -DECC_TABLE_PIVOT_BYTES=1 -DECC_PACKED_PAIR_ILP=1 \
             -DECC_PACKED_ALU_SQUARE=1 -DECC_TABLE_TAG_DENOM=1 -DECC_TABLE_PIPE_SELECT=1 \
             -DECC_PACKED_CHAIN_FIRST=1 -DECC_PACKED_INLINE_POLY=3 -DECC_UNROLL_SLOTS=1 \
             -DECC_PACKED_FROM_REDUCED=1
else
$(error WALK must be sigma or table)
endif

# Objects depend on the configuration, so each walk builds in its own
# directory and a table object is never linked into a sigma client.
BUILD ?= build
OBJ   := $(BUILD)/$(WALK)

MODEL := ../fpga/model/ecc2k130.c
HDRS  := $(wildcard include/*.h include/*.cuh) src/hostcheck.h
KAT   := tests/campaign-kat.hex

# The kernel's configuration.  Every flag is documented in include/packed131.h,
# include/packedkernels.cuh and include/packedtablewalk.cuh; the host test is
# built with the same set so that the arithmetic it checks is the arithmetic
# the device runs (the host paths of the clmad routines are software).
DEFS := -DECC_BATCH=$(BATCH) -DECC_THREADS=$(THREADS) -DECC_MINBLOCKS=$(MINBLOCKS) \
        -DECC_PACKED_SINGLE_PRODUCT=1 -DECC_PACKED_CACHE_DENOM=1 -DECC_PACKED_BY_VALUE=1 \
        -DECC_PACKED_PERM_SIGMA=3 -DECC_PACKED_POLY_CHAIN=1 -DECC_PACKED_UNROLL_INV=1 \
        -DECC_PACKED_PAIR_PRODUCTS=1 -DECC_PACKED_POLY_STATE=1 -DECC_PACKED_DIRECT_REDUCE=1 \
        -DECC_PACKED_GENERATED_PRODUCT=1 -DECC_PACKED_CLMAD=1 -DECC_PACKED_STATE_TILE=256 \
        -DECC_PACKED_WEIGHTED_PREFIX=2 -DECC_PACKED_COMPACT_STATE=1 $(WALKDEFS)

.PHONY: all test gpu bench verify clean

all: test

$(OBJ):
	mkdir -p $(OBJ)

$(OBJ)/model.o: $(MODEL) ../fpga/model/ecc2k130.h | $(OBJ)
	$(CC) -O2 -std=c11 -Wall -Wextra -c $(MODEL) -o $@

HOSTFLAGS := -O2 -std=c++17 -Wall -Wextra -Wno-unknown-pragmas -Wno-unused-function \
             -Wno-unused-parameter $(DEFS)

# The cross-check compiles the device's selection primitives as host code,
# which nvcc does not allow; g++ builds it and both programs link it.
$(OBJ)/hostcheck.o: src/hostcheck.cpp $(HDRS) | $(OBJ)
	$(CXX) $(HOSTFLAGS) -c src/hostcheck.cpp -o $@

$(OBJ)/hosttest: src/hosttest.cpp $(HDRS) $(OBJ)/model.o $(OBJ)/hostcheck.o | $(OBJ)
	$(CXX) $(HOSTFLAGS) src/hosttest.cpp $(OBJ)/hostcheck.o $(OBJ)/model.o -o $@

test: $(OBJ)/hosttest
	$(OBJ)/hosttest 64 $(KAT)

# The client is named for what it runs: build/ec2k-gpu is the campaign's sigma
# walk, build/ec2k-gpu-table the experiment.
ifeq ($(WALK),sigma)
CLIENT := $(BUILD)/ec2k-gpu
else
CLIENT := $(BUILD)/ec2k-gpu-table
endif

gpu: $(CLIENT)

$(CLIENT): src/ec2k_gpu.cu $(HDRS) $(OBJ)/model.o $(OBJ)/hostcheck.o | $(OBJ)
	$(NVCC) -O3 -std=c++17 $(ARCH) $(DEFS) -Xptxas -v -lineinfo -Xcompiler -O3 \
	    src/ec2k_gpu.cu $(OBJ)/hostcheck.o $(OBJ)/model.o -o $@ 2>&1 \
	    | grep -E "Compiling entry|Used|spill|error" | grep -v "0 bytes spill" || true
	@test -x $@

bench: $(CLIENT)
	$(CLIENT) bench --steps 1024 --launches 64

# dp-weight 46 makes a point appear about once in 2^13 steps, so six launches
# of 96 steps report hundreds of thousands of points; the first 300 are
# re-walked on the model from the challenge points.
verify: $(CLIENT)
	$(CLIENT) walk --run-id 4242 --dp-weight 46 --dp-cap 1048576 --steps 96 \
	    --launches 6 --verify 300

clean:
	rm -rf $(BUILD)
