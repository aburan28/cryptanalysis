# experiments/bounds: this library's measured constants as ecbench.bound/v1
# records, in their own unit.  README.md says what a record claims and why it
# is never compared with an ecbench.gae record.
#
#   make sweep      ca_bench complexity --json: one row per solved instance
#   make records    one sealed record per (algorithm, group kind, tier)
#   make frontier   frontier.json and FRONTIER.md, built by ecbench (ECBENCH=/abs/path)
#   make check      the committed page matches the committed records
#   make test       the seal round trip on real ecbench records, the adapter
#   make list       every record's seal, id and headline
#
# The sweep is written under sweeps/ with today's date; `records` reads the
# newest sweep unless SWEEP= names another.  Build the library first
# (`make lib` at the top level); the ca_bench rule below only fills in a
# missing binary and does not track source changes.

ROOT      := ../..
BUILD     ?= $(ROOT)/build
BITS      ?= 20,24,28,32,36
REPS      ?= 16
DATE      ?= $(shell date -u +%Y%m%d)
SWEEP_NEW ?= sweeps/complexity-$(DATE).jsonl
SWEEP     ?= $(lastword $(sort $(wildcard sweeps/*.jsonl)))
ECBENCH   ?= ecbench

.PHONY: all sweep records frontier check test list

all: records frontier

$(BUILD)/ca_bench:
	cmake -S $(ROOT) -B $(BUILD) -DCMAKE_BUILD_TYPE=Release
	cmake --build $(BUILD) -j --target ca_bench

sweep: $(BUILD)/ca_bench
	mkdir -p sweeps
	$(BUILD)/ca_bench complexity --bits $(BITS) --reps $(REPS) --json $(SWEEP_NEW)

records:
	python3 emit_bounds.py emit --sweep $(SWEEP) --out records

# ecbench writes the --bounds path into the page header, so the page is built
# from the repository root with repository-relative paths, as ecbench's own
# docs/bounds page is; give ECBENCH as an absolute path or a name on PATH.
HERE      := experiments/bounds
FRONTIER   = frontier build --bounds $(HERE)/records --out $(HERE)/frontier.json --markdown $(HERE)/FRONTIER.md

frontier:
	cd $(ROOT) && $(ECBENCH) $(FRONTIER)

check:
	cd $(ROOT) && $(ECBENCH) $(FRONTIER) --check

test:
	python3 -m pytest -q .

list:
	python3 emit_bounds.py list records
