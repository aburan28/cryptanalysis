CXX = clang++
TARGET = ../build/metal-pair-table

all: $(TARGET) ../build/metal-artifact-walk

$(TARGET): pair_table.mm
	mkdir -p ../build
	$(CXX) -O2 -std=c++17 -fobjc-arc -Wall -Wextra -framework Foundation -framework Metal $< -o $@

../build/artifact_walk_metal.inc: artifact_walk.metal ../scripts/mslgen.py $(wildcard ../include/*.h) $(wildcard ../include/*.cuh)
	mkdir -p ../build
	python3 ../scripts/mslgen.py ../include artifact_walk.metal $@

../build/metal-artifact-walk: artifact_walk.mm ../build/artifact_walk_metal.inc
	$(CXX) -O2 -std=c++17 -fobjc-arc -Wall -Wextra -I../build -framework Foundation -framework Metal $< -o $@

.PHONY: all
