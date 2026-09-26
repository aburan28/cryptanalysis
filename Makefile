# Convenience wrapper around CMake and the language bindings.
BUILD ?= build
CMAKE_FLAGS ?= -DCMAKE_BUILD_TYPE=Release
JOBS ?= $(shell nproc 2>/dev/null || echo 4)

.PHONY: all lib test bench asan tsan valgrind coverage tidy cppcheck analyzer \
        shellcheck format checks rust go python bindings clean install cuda cuda-kernel \
        coordinator coordinator-test fpga fpga-lint fpga-synth ecc2k130 ecc2k130-gpu \
        ecc2k130-cpu ecc2k130-metal gpu-health gpu-health-image \
        suite suite-build suite-test suite-lint suite-python \
        cloud-doctor cloud-all modal-setup modal-bench modal-long modal-sync \
        modal-sync-loop runpod-start runpod-status runpod-stop \
        fanout-start fanout-status fanout-stop \
        modal-sync-ensure modal-sync-status \
        ingest-start ingest-status ingest-stop

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

# ---- the coordinator (Go; the service agents dial out to) ------------------
# The Go package compiles the C sources itself through cgo, so there is no
# prior cmake step; `lib` is built anyway because the tests exercise both.
coordinator: lib
	cd bindings/go && go build -trimpath -o ../../$(BUILD)/ca-coordinator ./cmd/ca-coordinator

coordinator-test:
	cd bindings/go && go vet ./... && go test -race ./...

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

# The same walk and reports without a CUDA device: on host cores over PMULL or
# PCLMULQDQ, and on an Apple GPU through Metal (macOS; shader built at start-up).
ecc2k130-cpu:
	$(MAKE) -C ecc2k130 cpu

ecc2k130-metal:
	$(MAKE) -C ecc2k130 metal

# ---- the GPU health check (deploy/gpu-health/) -----------------------------
# ec2k-gpu's `health` command and the orchestrator that turns one run per GPU
# into a verdict.  `gpu-health` runs the orchestrator's tests against scripted
# stand-ins for ec2k-gpu and nvidia-smi (no GPU); `gpu-health-image` builds
# the image, which compiles and self-checks ec2k-gpu on the way.
gpu-health:
	python3 -m unittest discover -s deploy/gpu-health/tests

gpu-health-image:
	docker build -f deploy/gpu-health/Dockerfile -t gpu-health:dev .

# ---- the attack suite (suite/) ---------------------------------------------
# The Rust cryptanalysis library and its tools (ca-suite, ca-ic,
# ca-koblitz-pdp-prepare), independent of the C library.  `make suite` is
# what the suite workflow gates a pull request on, in the order that fails
# fastest; the tests run in release because they are arithmetic over
# num-bigint and take ten times longer unoptimised.
suite: suite-lint suite-test suite-python

suite-build:
	cd suite && cargo build --release

suite-lint:
	cd suite && cargo fmt --all --check
	cd suite && cargo clippy --all-targets -- -D warnings
	cd suite && RUSTDOCFLAGS="-D warnings" cargo doc --no-deps
	cd suite && cargo deny check

suite-test:
	cd suite && cargo test --release

# The stdlib-only engine behind `ca-ic fixed`; the SAT back ends it can use
# are in suite/python/indexcalc/requirements-sat.txt.
suite-python:
	cd suite/python/indexcalc && ruff check . && \
	  python3 -m unittest test_indexcalc_e2e test_indexcalc_fixed test_indexcalc_selector testirschedule

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
	shellcheck scripts/*.sh deploy/*/*.sh

# ---- cloud ECC2K-130 (Modal + RunPod + ingest MiG) -----------------------
# See docs/CLOUD_LAUNCH.md. GPU time is billed; these are not CI gates.
cloud-doctor:
	./scripts/cloud_launch.sh doctor

cloud-all:
	./scripts/cloud_launch.sh all

modal-setup:
	./scripts/cloud_launch.sh modal setup

modal-bench:
	./scripts/cloud_launch.sh modal bench

modal-long:
	./scripts/cloud_launch.sh modal long

modal-sync:
	./scripts/cloud_launch.sh modal sync

modal-sync-loop:
	./scripts/cloud_launch.sh modal sync-loop

modal-sync-ensure:
	./scripts/cloud_launch.sh sync ensure

modal-sync-status:
	./scripts/cloud_launch.sh sync status

runpod-start:
	./scripts/cloud_launch.sh runpod start

runpod-status:
	./scripts/cloud_launch.sh runpod status

runpod-stop:
	./scripts/cloud_launch.sh runpod stop

fanout-start:
	./scripts/cloud_launch.sh fanout start

fanout-status:
	./scripts/cloud_launch.sh fanout status

fanout-stop:
	./scripts/cloud_launch.sh fanout stop

ingest-start:
	./scripts/cloud_launch.sh ingest start

ingest-status:
	./scripts/cloud_launch.sh ingest status

ingest-stop:
	./scripts/cloud_launch.sh ingest stop

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
	       build-analyzer build-cuda build-cuda-kernel bindings/rust/target suite/target
