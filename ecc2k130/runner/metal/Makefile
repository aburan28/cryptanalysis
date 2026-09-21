CXX = clang++
TARGET = ../build/metal-pair-table

all: $(TARGET)

$(TARGET): pair_table.mm
	mkdir -p ../build
	$(CXX) -O2 -std=c++17 -fobjc-arc -Wall -Wextra -framework Foundation -framework Metal $< -o $@

.PHONY: all
