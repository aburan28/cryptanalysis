# Q1436 v1 control-report failure

The first frozen Q1436 protocol was committed at `5d3a67bc` before any
ordinary query was run. Its N53 `free_partner` control returned a model whose
four-point relation passed the independent group-law check. The C++ report
omitted the closing `]` of its final JSON array, so the runner retained the
receipt with `solver_report: null` and a JSON decode error. That receipt and
the original protocol and compile receipt are preserved here. No N83 or
ordinary v1 cell was started.

The v2 source changes only the report terminator from `}` to `]}`. Its binary
and protocol have new hashes and are frozen in the parent directory before
the v2 run order starts. The v1 control is an output-format failure, not a
measured natural relation yield or a solver performance result.
