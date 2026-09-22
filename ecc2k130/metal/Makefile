CXX = clang++
TARGET = ../build/metal-pair-table

all: $(TARGET) ../build/metal-artifact-walk ../build/metal-fused-benchmark

$(TARGET): pair_table.mm
	mkdir -p ../build
	$(CXX) -O2 -std=c++17 -fobjc-arc -Wall -Wextra -framework Foundation -framework Metal $< -o $@

../build/artifact_walk_metal.inc: artifact_walk.metal ../scripts/mslgen.py $(wildcard ../include/*.h) $(wildcard ../include/*.cuh)
	mkdir -p ../build
	python3 ../scripts/mslgen.py ../include artifact_walk.metal $@

../build/metal-artifact-walk: artifact_walk.mm ../build/artifact_walk_metal.inc
	$(CXX) -O2 -std=c++17 -fobjc-arc -Wall -Wextra -I../build -framework Foundation -framework Metal $< -o $@

../build/fused_benchmark_source.metal: artifact_walk.metal fused_benchmark_extra.metal
	mkdir -p ../build
	cat $^ > $@

../build/fused_benchmark_metal.inc: ../build/fused_benchmark_source.metal ../scripts/mslgen.py $(wildcard ../include/*.h) $(wildcard ../include/*.cuh)
	python3 ../scripts/mslgen.py ../include ../build/fused_benchmark_source.metal $@

../build/metal-fused-benchmark: fused_benchmark.mm ../build/fused_benchmark_metal.inc
	$(CXX) -O2 -std=c++17 -fobjc-arc -Wall -Wextra -I../build -framework Foundation -framework Metal $< -o $@

.PHONY: all
