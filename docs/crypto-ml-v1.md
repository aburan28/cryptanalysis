# crypto-ml-v1: shared ML cryptanalysis interchange contract

Canonical JSON Schema: [crypto-autoresearcher/schemas/crypto-ml-v1.schema.json](https://github.com/aburan28/crypto-autoresearcher/blob/feat/crypto-ml-v1-foundation/schemas/crypto-ml-v1.schema.json).

This repository consumes the schema; do not fork field definitions. Generate a JSON experiment manifest conforming to that schema before dataset generation. Primitive-specific extractors must not place post-outcome measurements among predictive features.

## Dataset row contract
Each row contains `experiment_id`, `sample_id`, `independent_unit_id`, `split`, `label`, `features`, `observation_ref`, and `generator_commit`. Store raw binary samples separately with byte order and encoding documented. JSONL is the portable baseline; Arrow/Parquet may be added with equivalent typed columns.

## Non-negotiable controls
Split by independent key, permutation instance, curve isogeny class, or equivalent correlated unit, not by individual observation. Match positive and negative distributions for sample count and acquisition pipeline. Report confidence intervals, held-out performance, classical baselines, and multiple-testing correction. Classification accuracy alone is not key recovery or a full-round break.

## Integration roadmap
1. Validate manifests against canonical schema in CI.
2. Implement seeded sample generator adapters and typed feature extractors for AES and one non-AES primitive.
3. Add reproducible JSONL/Parquet exports, checksums and split manifests.
4. Add training baselines (logistic regression, tree ensemble, MLP), label-shuffle negative controls and grouped evaluation.
5. Produce immutable receipts and compare distinguisher advantage to classical baselines.

**Current status:** shared contract documentation only; generators and training pipeline remain to be implemented.
