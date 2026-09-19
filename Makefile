# Convenience wrapper around CMake and the language bindings.
BUILD ?= build
CMAKE_FLAGS ?= -DCMAKE_BUILD_TYPE=Release
JOBS ?= $(shell nproc 2>/dev/null || echo 4)

.PHONY: all lib test bench asan rust go python bindings clean install format cuda cuda-kernel

all: lib

lib:
	cmake -S . -B $(BUILD) $(CMAKE_FLAGS)
	cmake --build $(BUILD) -j$(JOBS)

test: lib
	ctest --test-dir $(BUILD) --output-on-failure -j$(JOBS)

bench: lib
	$(BUILD)/ca_bench ops
	$(BUILD)/ca_bench generic --bits 24,28,32,36 --reps 3
	$(BUILD)/ca_bench interval --bits 24,28,32 --reps 3
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

asan:
	cmake -S . -B build-asan -DCMAKE_BUILD_TYPE=Debug -DCA_SANITIZE=ON -DCA_BUILD_SHARED=OFF
	cmake --build build-asan -j$(JOBS)
	ctest --test-dir build-asan --output-on-failure

rust:
	cd bindings/rust && cargo test

go:
	cd bindings/go && go vet ./... && go test ./...

python: lib
	cd bindings/python && python3 -m unittest discover -s tests -v

bindings: rust go python

install: lib
	cmake --install $(BUILD)

format:
	clang-format -i include/cryptanalysis/*.h src/*.c src/*.h tests/*.c tests/*.h tools/*.c

clean:
	rm -rf $(BUILD) build-asan build-cuda build-cuda-kernel bindings/rust/target
