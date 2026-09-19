# The ECC2K-130 FPGA core: model, simulation, lint and synthesis.
#
#   make            model self-test, vectors, every testbench, host tooling
#   make model      the golden model's own checks
#   make sim        the testbenches (DIGIT=4 DPW=60 CASES=64)
#   make lint       verilator -Wall over the RTL
#   make synth      yosys area report (CORES=1 DIGIT=4)
#   make sweep      the DIGIT table in README.md, regenerated
#   make host       just the host tool
#
# Needs iverilog for sim, verilator for lint, yosys for synth.  No vendor
# tools: everything this Makefile can do is open-source, and everything it
# cannot do (timing, device utilisation, throughput) is named as such in
# README.md rather than estimated.

BUILD  ?= build
CC     ?= cc
CFLAGS ?= -O2 -std=c11 -Wall -Wextra
DIGIT  ?= 4
DPW    ?= 60
CASES  ?= 64
CORES  ?= 1

RTL    := $(wildcard rtl/*.v)
MODEL  := model/ecc2k130.c

.PHONY: all model sim lint synth sweep host clean

all: sim

$(BUILD):
	mkdir -p $(BUILD)

model: $(BUILD)
	$(CC) $(CFLAGS) -o $(BUILD)/ec2k_test $(MODEL) model/ecc2k130_test.c
	$(BUILD)/ec2k_test

host: $(BUILD)
	$(CC) $(CFLAGS) -o $(BUILD)/ec2k $(MODEL) host/ec2k_tool.c

sim:
	DIGIT=$(DIGIT) scripts/run_sim.sh $(DIGIT) $(DPW) $(CASES)

lint:
	verilator --lint-only -Wall -Irtl --top-module ecc2k130_top $(RTL)

synth:
	scripts/synth.sh $(CORES) $(DIGIT)

# The measured table in README.md: cycles from simulation, area from yosys.
# Kept as a target rather than as prose that somebody has to remember to
# update, because a table nobody can regenerate is a table nobody can trust.
sweep: $(BUILD)
	@for d in 1 2 4 8 16; do \
	  printf 'DIGIT=%-3s ' $$d; \
	  scripts/run_sim.sh $$d $(DPW) 16 2>/dev/null | grep 'cycles/step' || echo "(sim failed)"; \
	done
	@for d in 1 2 4 8 16; do \
	  printf 'DIGIT=%-3s ' $$d; \
	  scripts/synth.sh 1 $$d 2>/dev/null | awk '/lut|DFF/ {s[$$1]=$$2} END {l=0;f=0; for (k in s) { if (k ~ /lut/) l+=s[k]; if (k ~ /DFF/) f+=s[k]} print "LUT4="l" FF="f}'; \
	done

clean:
	rm -rf $(BUILD)
