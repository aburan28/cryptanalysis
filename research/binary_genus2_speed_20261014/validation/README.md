# Local validation records

Native package tests include the pinned upstream arithmetic/reference tests,
the existing exhaustive small-field cover controls, n=83 subgroup arithmetic,
native-Jacobian versus elliptic trajectory equivalence, checkpoint replay,
a constructed collision unit test, and malformed-input rejection. Constructed
test collisions and fixed-log fixtures are not full-subgroup benchmark solves.

The first restart test, before saved rounds were added, found that a numeric
step budget could overshoot at a partially live batch: 64 versus 67 steps after
a split. The implementation now schedules an exact number of complete rounds;
the saved-state replay tests pass. This initial tool-output-only failure was
not saved as a raw log. `missing-num-integer.log` records the later snapshot
dependency error. `upstream-type-complexity-clippy.log` records an upstream
lint difference; the namespace bridge now uses the same type-complexity
allowance as the original crate. Upstream snapshots remain byte-identical.

`native-tests.log`, `clippy.log` and `build.log` are final scoped records.
The root logs are the canonical crypto checkout's validation. The separately
captured `suite/check.log` reruns the complete scoped gate in the cryptanalysis
checkout; copying performance evidence does not count as suite validation.
The backend source is unchanged by this campaign. The preceding whole-library
gate remains qualified by the existing two JV F4 minimum-completed-cases
failures, documented in the construction study and the named problem. Do not
describe that older full gate as green or these scoped checks as a full gate.
