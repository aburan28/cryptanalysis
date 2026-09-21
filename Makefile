# Convenience wrapper around CMake and the language bindings.
BUILD ?= build
CMAKE_FLAGS ?= -DCMAKE_BUILD_TYPE=Release
JOBS ?= $(shell nproc 2>/dev/null || echo 4)

.PHONY: all lib test bench asan tsan valgrind coverage tidy cppcheck analyzer \
        shellcheck format checks rust go python bindings clean install cuda cuda-kernel \
        orchestrator orchestrator-test smoke fpga fpga-lint fpga-synth ecc2k130 ecc2k130-gpu

all: lib

lib:
	cmake -S . -B $(BUILD) $(CMAKE_FLAGS)
	cmake --build $(BUILD) -j$(JOBS)

test: lib
	ctest --test-dir $(BUILD) --output-on-failure -j$(JOBS)

# Every `ca` subcommand, with the answers checked where they are known in
# closed form. This is the guard on "every public header is reachable from the
# command line": a newly exported function that no command calls shows up here.
cli: lib
	./scripts/cli_smoke.sh $(BUILD)/ca

bench: lib
	$(BUILD)/ca_bench ops
	$(BUILD)/ca_bench generic --bits 24,28,32,36 --reps 3
	$(BUILD)/ca_bench interval --bits 24,28,32 --reps 3
	$(BUILD)/ca_bench precomp --bits 24,28,32,36 --reps 5
	$(BUILD)/ca_bench complexity --bits 20,24,28,32,36 --reps 5
	$(BUILD)/ca_bench glv
	$(BUILD)/ca_bench ic --bits 32,40,48
	$(BUILD)/ca_bench cheon --bits 32,40
	$(BUILD)/ca_bench gpu --bits 24,28,32

# Build with the CUDA backend.  Needs a real CUDA toolkit (nvcc, or clang
# with a complete toolkit); see docs/GPU.md.
cuda:
	cmake -S . -B build-cuda -DCMAKE_BUILD_TYPE=Release -DCA_CUDA=ON
	cmake --build build-cuda -j$(JOBS)
	ctest --test-dir build-cuda --output-on-failure -R gpu

# Compile just the kernel and report registers / local memory.  Needs no GPU
# and no CUDA install (--fetch pulls the pieces from NVIDIA's pip wheels).
cuda-kernel:
	./scripts/build_cuda_kernel.sh --fetch

# ---- the orchestration layer (Go; control plane + agents) -----------------
# The Go tests take the library's own `ca` as their reference implementation
# and skip without it, so the library is built first.
orchestrator: lib
	cd orchestrator && CGO_ENABLED=0 go build -trimpath -o ../$(BUILD)/ca-control ./cmd/ca-control
	cd orchestrator && CGO_ENABLED=0 go build -trimpath -o ../$(BUILD)/ca-agent ./cmd/ca-agent

orchestrator-test: lib
	cd orchestrator && go vet ./... && CA_BIN=$(CURDIR)/$(BUILD)/ca go test -race ./...

# One control plane, two agents, one instance, one real answer -- as separate
# processes over a socket, which is where deployment bugs live.
smoke: orchestrator
	orchestrator/scripts/smoke.sh $(BUILD)

# ---- the ECC2K-130 FPGA core (fpga/) ---------------------------------------
# A separate tree with its own toolchain: a golden C model, synthesisable
# Verilog, testbenches that compare the two, and a host tool.  It is not part
# of the library build -- the library works over 64-bit groups and ECC2K-130
# is a 131-bit field -- so it has its own Makefile and its own CI workflow.
fpga:
	$(MAKE) -C fpga sim

fpga-lint:
	$(MAKE) -C fpga lint

fpga-synth:
	$(MAKE) -C fpga synth CORES=1 DIGIT=4

# ---- the ECC2K-130 GPU client (ecc2k130/) ----------------------------------
# The packed GF(2^131) table walk for CUDA devices with a carry-less
# multiplier, held to fpga/model's golden model.  `ecc2k130` is the host test
# (no CUDA needed); `ecc2k130-gpu` builds the client with nvcc >= 13.3, which
# ecc2k130/scripts/fetch_cuda.sh can supply from NVIDIA's pip wheels.
ecc2k130:
	$(MAKE) -C ecc2k130 test

ecc2k130-gpu:
	$(MAKE) -C ecc2k130 gpu

asan:
	cmake -S . -B build-asan -DCMAKE_BUILD_TYPE=Debug -DCA_SANITIZE=address,undefined \
	      -DCA_BUILD_SHARED=OFF
	cmake --build build-asan -j$(JOBS)
	ctest --test-dir build-asan --output-on-failure

# The rho and index-calculus solvers are pthreads plus C11 atomics.
tsan:
	cmake -S . -B build-tsan -DCMAKE_BUILD_TYPE=RelWithDebInfo -DCA_SANITIZE=thread \
	      -DCA_BUILD_SHARED=OFF
	cmake --build build-tsan -j$(JOBS)
	ctest --test-dir build-tsan --output-on-failure
	TSAN_OPTIONS=halt_on_error=1 build-tsan/ca ic --p 1099511627791 --g 3 --h 123456789 --threads 4

# The fast suites only; linalg and indexcalc take about an hour each here.
valgrind:
	cmake -S . -B build-vg -DCMAKE_BUILD_TYPE=RelWithDebInfo -DCA_BUILD_SHARED=OFF
	cmake --build build-vg -j$(JOBS)
	for t in modarith group bsgs rho kangaroo grumpy pohlig cheon ffi gpu; do \
	  echo "== $$t"; \
	  valgrind -q --error-exitcode=9 --leak-check=full \
	           --errors-for-leak-kinds=definite build-vg/test_$$t >/dev/null || exit 1; \
	done

coverage:
	cmake -S . -B build-cov -DCMAKE_BUILD_TYPE=Debug -DCA_BUILD_SHARED=OFF \
	      -DCMAKE_C_FLAGS="--coverage -O0 -g" -DCMAKE_EXE_LINKER_FLAGS="--coverage"
	cmake --build build-cov -j$(JOBS)
	ctest --test-dir build-cov --output-on-failure
	gcovr --root . --filter 'src/' --exclude 'src/gpu_cuda_stub.c' \
	      --gcov-ignore-parse-errors negative_hits.warn_once_per_file --print-summary \
	      --fail-under-line 85 --fail-under-function 88

# ---- static analysis -------------------------------------------------------
# Each of these is a CI gate; the tree is clean under all of them.

tidy:
	cmake -S . -B build-tidy -DCMAKE_BUILD_TYPE=Debug \
	      -DCMAKE_EXPORT_COMPILE_COMMANDS=ON -DCA_BUILD_SHARED=OFF
	clang-tidy -p build-tidy --quiet src/*.c tools/*.c tests/*.c

cppcheck:
	cppcheck --enable=warning,performance,portability,style --inline-suppr --std=c11 \
	         --error-exitcode=1 --suppress=missingIncludeSystem \
	         -Iinclude -Isrc -Icuda --quiet src tools tests

analyzer:
	cmake -S . -B build-analyzer -DCMAKE_BUILD_TYPE=Debug -DCA_BUILD_TESTS=OFF \
	      -DCA_BUILD_SHARED=OFF -DCMAKE_C_COMPILER=gcc \
	      -DCMAKE_C_FLAGS="-fanalyzer -Wall -Wextra -Werror"
	cmake --build build-analyzer -j$(JOBS)

shellcheck:
	shellcheck scripts/*.sh

# Everything a pull request is gated on, in the order that fails fastest.
checks: format cppcheck shellcheck tidy analyzer test cli asan tsan

rust:
	cd bindings/rust && cargo test

go:
	cd bindings/go && go vet ./... && go test ./...

python: lib
	cd bindings/python && python3 -m unittest discover -s tests -v

bindings: rust go python

install: lib
	cmake --install $(BUILD)

# Only the lines this branch touches.  The sources predate .clang-format and
# a wholesale reformat would bury every future diff; new code still matches.
FORMAT_BASE ?= HEAD

format:
	git-clang-format --diff --extensions c,h,cu,cuh $(FORMAT_BASE)

clean:
	rm -rf $(BUILD) build-asan build-tsan build-vg build-cov build-tidy \
	       build-analyzer build-cuda build-cuda-kernel bindings/rust/target
