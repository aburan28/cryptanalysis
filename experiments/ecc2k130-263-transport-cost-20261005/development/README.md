# First same-input pass

`result-r1.json` and `verification-r1.json` retain the first successful,
exploratory pass. The source snapshots exactly match the SHA-256 values in
those receipts. They were executed from the experiment directory before the
producer and verifier acquired explicit `--runtime-info` and `--result`
arguments. A source snapshot copied back to its original parent directory
in a scratch checkout is required to execute it, because its `HERE` path is
relative to the original location. The main result uses the second pass with
the explicit receipt arguments; neither pass is a controlled CPU timing
comparison.
