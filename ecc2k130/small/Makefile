CXX = clang++

../build/ksmall: ksmall.mm
	mkdir -p ../build
	$(CXX) -O2 -std=c++17 -fobjc-arc -Wall -Wextra -framework Foundation -framework Metal $< -o $@

.PHONY: test
test: ../build/ksmall
	python3 run.py selftest ../../challenges/ecc/curves/f2-koblitz-a0-m41.json
	python3 run.py solve ../../challenges/ecc/curves/f2-koblitz-a0-m41.json --collisions 3
