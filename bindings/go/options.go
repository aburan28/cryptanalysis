package cryptanalysis

import "fmt"

// Solver selects the algorithm used by [Group.Dlog] (after Pohlig-Hellman).
type Solver int

// Solver choices (mirroring ca_solver).
const (
	SolverAuto     Solver = 0 // BSGS for small prime factors, rho for large ones
	SolverBSGS     Solver = 1
	SolverRho      Solver = 2
	SolverKangaroo Solver = 3
	SolverGrumpy   Solver = 4
	SolverBrute    Solver = 5
)

// String returns the solver's name.
func (s Solver) String() string {
	switch s {
	case SolverAuto:
		return "auto"
	case SolverBSGS:
		return "bsgs"
	case SolverRho:
		return "rho"
	case SolverKangaroo:
		return "kangaroo"
	case SolverGrumpy:
		return "grumpy"
	case SolverBrute:
		return "brute"
	}
	return fmt.Sprintf("Solver(%d)", int(s))
}

// Options mirrors ca_ffi_options.  Zero values generally mean "automatic";
// start from [DefaultOptions] and change what you need.  A nil *Options
// passed to a solver means library defaults.
type Options struct {
	Threads uint32 // rho: worker threads (0 => 1)
	Seed    uint64 // 0 => random
	MaxOps  uint64 // 0 => unlimited; exceeding it yields ErrLimit

	BSGSTableSize uint64 // 0 => sqrt(width)

	RhoR               uint32 // number of r-adding walk partitions (0 => auto)
	RhoDPBits          int32  // distinguished-point bits (-1 => auto)
	RhoWalksPerThread  uint32 // 0 => auto
	RhoNegationMap     bool   // use the negation map when available
	RhoMaxTableEntries uint64 // 0 => unlimited

	KangarooHerdSize uint32 // 0 => auto
	KangarooDPBits   int32  // -1 => auto
	KangarooJumps    uint32 // 0 => auto

	GrumpyM     uint64  // 0 => alpha*sqrt(width)
	GrumpyAlpha float64 // 0 => 0.7

	Solver       Solver // used by Dlog
	BSGSMaxPrime uint64 // auto solver: BSGS for prime factors <= this (0 => 2^36)
}

// DefaultOptions returns the library's default solver options.
func DefaultOptions() Options { return defaultOptions() }

// Stats holds the work counters common to all solvers (ca_stats).
type Stats struct {
	GroupOps     uint64  // group operations performed
	Iterations   uint64  // algorithm-specific step counter
	TableEntries uint64  // entries stored in lookup tables
	Collisions   uint64  // useful collisions / relations found
	BytesPeak    uint64  // approximate peak heap usage of tables
	Seconds      float64 // wall-clock time spent
	Threads      uint32  // threads used
}
