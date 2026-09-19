# Convenience wrapper around CMake and the language bindings.
BUILD ?= build
CMAKE_FLAGS ?= -DCMAKE_BUILD_TYPE=Release
JOBS ?= $(shell nproc 2>/dev/null || echo 4)

.PHONY: all lib test bench asan rust go python bindings clean install format

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
	rm -rf $(BUILD) build-asan bindings/rust/target
