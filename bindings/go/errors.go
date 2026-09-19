package cryptanalysis

import (
	"errors"
	"fmt"
)

// Status is a ca_status code returned by the C library.
type Status int

// Status codes (mirroring ca_status in ca_types.h).
const (
	StatusOK          Status = 0
	StatusInvalid     Status = 1 // invalid argument (bad modulus, point not on curve, ...)
	StatusNotFound    Status = 2 // the search space was exhausted without a solution
	StatusNoMem       Status = 3 // allocation failure
	StatusLimit       Status = 4 // an explicit work/memory/time limit was reached
	StatusUnsupported Status = 5 // the operation is not supported for this group/params
	StatusInternal    Status = 6 // internal consistency failure
	StatusSingular    Status = 7 // linear system had no usable solution
)

// String returns the library's description of the status code.
func (s Status) String() string { return statusString(s) }

// Sentinel errors.  An [*Error] returned by this package matches the
// sentinel for its status under errors.Is, so callers can write
// errors.Is(err, cryptanalysis.ErrNotFound) without inspecting the code.
var (
	ErrInvalid     = errors.New("cryptanalysis: invalid argument")
	ErrNotFound    = errors.New("cryptanalysis: not found")
	ErrNoMem       = errors.New("cryptanalysis: out of memory")
	ErrLimit       = errors.New("cryptanalysis: limit reached")
	ErrUnsupported = errors.New("cryptanalysis: unsupported")
	ErrInternal    = errors.New("cryptanalysis: internal error")
	ErrSingular    = errors.New("cryptanalysis: singular system")
	ErrClosed      = errors.New("cryptanalysis: use of closed context")
)

// Error is the error type returned for every failing library call.  Status
// is the ca_status code and Msg the thread-local ca_last_error() message
// captured right after the failing call (it may be empty when the library
// did not record a message for that status, e.g. a plain "not found").
type Error struct {
	Status Status
	Msg    string
}

// Error implements the error interface.
func (e *Error) Error() string {
	if e.Msg != "" {
		return fmt.Sprintf("cryptanalysis: %s: %s", e.Status, e.Msg)
	}
	return fmt.Sprintf("cryptanalysis: %s", e.Status)
}

// Is reports whether target is the sentinel corresponding to e.Status.
func (e *Error) Is(target error) bool {
	switch target {
	case ErrInvalid:
		return e.Status == StatusInvalid
	case ErrNotFound:
		return e.Status == StatusNotFound
	case ErrNoMem:
		return e.Status == StatusNoMem
	case ErrLimit:
		return e.Status == StatusLimit
	case ErrUnsupported:
		return e.Status == StatusUnsupported
	case ErrInternal:
		return e.Status == StatusInternal
	case ErrSingular:
		return e.Status == StatusSingular
	}
	return false
}

// Version returns the version string of the compiled C library.
func Version() string { return version() }
