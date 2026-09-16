# HealthGraphBench

HealthGraphBench studies when relational information adds predictive value
beyond strong entity-local and relational baselines in public
health/regulatory ML. It does not assume that graph methods should
outperform non-graph methods.

Version **0.1** remains the reproducible frozen benchmark core. The immutable
`v0.1.0` commit/tag records the pre-message-passing baseline definition, and
the post-baseline v0.1.1/v0.1.2 release assets remain unchanged.

The current v0.2 development line admits CMS Medicare Part D as one bounded
cross-domain replication task. It preserves the MAUDE and CMS nursing tasks,
adds no new graph architecture, and keeps ClinicalTrials deferred. The v0.2
admission contract and publication artifacts are versioned separately from the
frozen v0.1 payloads.

The v0.2 research report is
[`docs/benchmark_report_v0_2.md`](docs/benchmark_report_v0_2.md). The historical
v0.1 report remains available at
[`docs/benchmark_report_v0_1.md`](docs/benchmark_report_v0_1.md).
Graph complexity must be justified empirically, not presumed beneficial.

## Release downloads and citation

`v0.1.1` is the immutable pre-DOI exploratory package. Its GitHub-generated
source archive is the exact source snapshot for tag `v0.1.1`.

The [v0.1.2 GitHub Release](https://github.com/carabistouflette/HealthGraphBench/releases/tag/v0.1.2)
is the post-DOI citation package. It provides the report PDF and Markdown
source, summary CSV/JSON/SVG, compressed combined results, a source archive
generated directly from tag `v0.1.2`, source manifest, task contract,
DOI-bearing `CITATION.cff`, and `SHA256SUMS`.
[`results/release_assets_v0_1_2.json`](results/release_assets_v0_1_2.json)
records download URLs, byte sizes, SHA-256 hashes, DOI, and packaging
provenance.

Download into a new external directory and verify before decompressing:

```bash
mkdir healthgraphbench-v0.1.2-download
gh release download v0.1.2 --repo carabistouflette/HealthGraphBench \
  --dir healthgraphbench-v0.1.2-download
(cd healthgraphbench-v0.1.2-download && sha256sum -c SHA256SUMS)
gzip -dk healthgraphbench-v0.1.2-download/large-results.json.gz
sha256sum healthgraphbench-v0.1.2-download/large-results.json
```

The uncompressed SHA-256 must equal `compression.uncompressed_sha256` in the
asset manifest. `large-results.json.gz` contains the combined execution
artifact, including task results, analyses, and synthetic controls; it is not
a new run. The compression preserves original provenance fields.

For citation, use [`CITATION.cff`](CITATION.cff) and the Zenodo DOI:
**[10.5281/zenodo.22765003](https://doi.org/10.5281/zenodo.22765003)**.
The DOI-bearing metadata belongs to v0.1.2. The v0.1.1 tag, its source
snapshot, and its pre-DOI release package remain unchanged.

### v0.2.0 release payload

The versioned v0.2.0 payload is prepared in this checkout. Its manifest records
the source-tree state, hashes for the report, contract, unified table, compact
execution records, and immutable Part D ranking artifact, plus hashes for the
built wheel and source distribution:
[`results/release_assets_v0_2.json`](results/release_assets_v0_2.json).
The canonical v0.2 citation metadata is [`CITATION.cff`](CITATION.cff).
The frozen v0.1 DOI metadata remains in the immutable v0.1.2 tag and release.
Repository payload checksums are in
[`results/SHA256SUMS_v0_2`](results/SHA256SUMS_v0_2). The manifest deliberately
records `doi: null` until a DOI is assigned.

### Artifact policy from the next release onward

- Keep small summaries, manifests, configurations, hashes, CSVs, and plots in Git.
- Publish large generated JSON as versioned GitHub Release assets or Zenodo
  deposits, optionally compressed as `.json.gz`; record both compressed and
  uncompressed SHA-256 hashes and stable download locations.
- Preserve source commits, input hashes, execution timestamps, and model
  configurations in each result. Keep raw FDA/CMS snapshots external.
- Never overwrite an existing result or published asset. Corrections require
  a new version and explicit provenance.
- Do not rewrite history to remove the current large files. `v0.1.0`,
  `v0.1.1`, and their result bytes remain immutable; asset distribution does
  not shrink existing clone history.

The v0.1 research design and model suite remain frozen. The v0.2 Part D
extension adds no model architecture: it admits the already-run specialty
popularity, history-overlap, tabular-logistic, and graph-BPR methods as a
replication task. The model-gate result remains `no_go_for_escalation`.

The machine-readable admission contract is
[`configs/task_contract_v0_2.json`](configs/task_contract_v0_2.json). Historical
Part D feasibility and model-gate inputs remain immutable under
`results/generated/`; raw CMS snapshots remain external.

### CMS Medicare Part D v0.2 admission

Part D is admitted as the primary v0.2 cross-domain replication task. The
positive is a first observed published provider-drug relationship. The primary
identity is exact trimmed `generic_name`; candidates are all globally prior
drugs absent from the target provider's entire prior history. The validation
target is 2023 after 2019--2022 history; the held-out target is 2024 after
2019--2023 history. Each target cohort contains up to 2,000 providers selected
from pre-target observations. CMS suppression at 10 or fewer claims makes
absence non-observation subject to left censoring.

The common interface consumes the verified model-gate artifact without
rewriting it:

```bash
PYTHONPATH=. python scripts/build_partd_execution_v0_2.py \
  --model-gate-dir results/generated/partd-v0_2-model-gate-run-003 \
  --output results/partd_execution_v0_2_20260916.json
```

The compact execution record and unified v0.2 table are
[`results/partd_execution_v0_2_20260916.json`](results/partd_execution_v0_2_20260916.json),
[`results/benchmark_summary_v0_2.csv`](results/benchmark_summary_v0_2.csv), and
[`results/relational_value_v0_2.json`](results/relational_value_v0_2.json).

### ClinicalTrials.gov/AACT feasibility gate

ClinicalTrials.gov remains an exploratory candidate outside the frozen
benchmark. The gate predicts whether an interventional trial with an actual
primary completion date 0--90 days before a historical snapshot will have a
`results_first_posted_date` within the following 365 days. It uses only the
historical AACT snapshot at origin; this is a registry-publication target, not
a legal-compliance label.

The frozen AACT inputs are first-of-month archives from 2019-01-01 through
2025-02-01. The 2019--2022 origins are training, 2023 is validation, 2024 is
held-out test, and 2025 supplies future observation only. Exact trimmed,
case-folded, whitespace-normalized source names are used for sponsor,
condition, intervention, facility, and collaborator relations; no entity
resolution is asserted. Trials missing from the paired future archive, or
whose future result date is at or before the blank origin state, are excluded
from labeled evaluation rather than labeled untimely.

Keep the raw ZIP archives under an external directory and run the separate
feasibility commands:

```bash
AACT_ROOT=/path/to/healthgraphbench-data/clinical-trials-v0_2
PYTHONPATH=. python scripts/download_aact.py \
  --output "$AACT_ROOT" \
  --manifest data/manifests/clinical_trials_feasibility_v0_2.json
PYTHONPATH=. python scripts/run_clinical_trials_gate.py \
  --source-root "$AACT_ROOT" \
  --manifest data/manifests/clinical_trials_feasibility_v0_2.json \
  --output-dir results/generated/clinical-trials-v0_2-feasibility-run-002
```

The corrected official output is
`results/generated/clinical-trials-v0_2-feasibility-run-002/`. It records
`decision: REVIEW_REQUIRED`, `status: exploratory`,
`admission_status: deferred`, and
`graph_model_status: no_go_for_escalation`. The earlier `run-001` output is
preserved as an immutable superseded diagnostic artifact; use `run-002` for interpretation.

| origin/model | ROC-AUC | average precision | Brier | log loss | top-decile precision | top-decile recall |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| validation / trial-local | 0.782977 | 0.316535 | 0.113463 | 0.479275 | 0.392000 | 0.328859 |
| validation / sponsor history | 0.819718 | 0.355488 | 0.111895 | 0.458759 | 0.424000 | 0.355705 |
| validation / heterogeneous context | 0.780505 | 0.326306 | 0.112496 | 0.478612 | 0.368000 | 0.308725 |
| held-out test / trial-local | 0.774702 | 0.315710 | 0.114862 | 0.418183 | 0.367647 | 0.284091 |
| held-out test / sponsor history | 0.843830 | 0.365784 | 0.109672 | 0.374544 | 0.389706 | 0.301136 |
| held-out test / heterogeneous context | 0.856241 | 0.418027 | 0.103204 | 0.347487 | 0.441176 | 0.340909 |

The held-out heterogeneous-context model improves average precision by
0.102317 over trial-local features and 0.052243 over sponsor history. The
validation-origin increments are +0.009771 and -0.029182, respectively, so
the heterogeneous signal is not reproducible across the bounded rolling
origins. The report also contains pooled metrics, per-entity relation/history
coverage, isolated-target counts, source hashes, and row-level predictions.
Coverage ranges across origins were 100% for sponsor and condition relation
presence, 100% for intervention relation presence, 93.8--99.2% for facility
relation presence, and 30.1--33.5% for collaborator relation presence; history
coverage was lower, especially for interventions and collaborators. Isolated
target trials ranged from 1 to 6 per origin. No graph neural model is
justified by this gate without a separate review.

### ClinicalTrials.gov/AACT stability gate

The bounded stability gate is complete, but candidate admission remains
deferred. It evaluates five rolling origins, fitting each origin only on
labeled examples from strictly earlier origins. The relational context is
decomposed into sponsor, condition, facility, intervention, and collaborator
ablations; the all-context model includes all five entity types. The official
command is:

```bash
PYTHONPATH=. python scripts/run_clinical_trials_stability.py \
  --source-root /path/to/healthgraphbench-data/clinical-trials-v0_2 \
  --manifest data/manifests/clinical_trials_feasibility_v0_2.json \
  --output-dir results/generated/clinical-trials-v0_2-stability-run-001
```

The per-origin average-precision results are:

| origin | trials / positives | trial-local | local + sponsor | all entity context | sponsor − local | all context − sponsor |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2020-01-01 | 939 / 158 | 0.368399 | 0.472921 | 0.487943 | +0.104522 | +0.015022 |
| 2021-01-01 | 947 / 137 | 0.375904 | 0.409251 | 0.378173 | +0.033348 | -0.031079 |
| 2022-02-01 | 1,117 / 98 | 0.290692 | 0.241920 | 0.226297 | -0.048773 | -0.015623 |
| 2023-02-01 | 1,243 / 149 | 0.316535 | 0.355488 | 0.247411 | +0.038953 | -0.108077 |
| 2024-02-01 | 1,353 / 176 | 0.315710 | 0.365784 | 0.353906 | +0.050074 | -0.011878 |

Each AP difference has a separate paired percentile bootstrap interval using
1,000 trial-cluster resamples; undefined resamples are omitted and counted,
not converted to zero. The sponsor-minus-trial-local 95% intervals were
[+0.041160, +0.170611], [-0.030384, +0.098740],
[-0.088028, -0.021689], [+0.019729, +0.057229], and
[+0.026271, +0.075609] in chronological order. The all-context-minus-sponsor
intervals were [-0.022369, +0.060294], [-0.087890, +0.028991],
[-0.069626, +0.044298], [-0.171780, -0.049169], and
[-0.054550, +0.030322].

Across-origin relation increments over the sponsor model were: condition
positive in 0/5 origins (mean -0.015417; range -0.023950 to -0.001240),
facility positive in 4/5 (mean -0.005130; range -0.062158 to +0.016780),
intervention positive in 2/5 (mean -0.002313; range -0.012844 to +0.011852),
and collaborator positive in 1/5 (mean -0.009482; range -0.025141 to
+0.003535). These are descriptive summaries across separate origins, not a
pooled AP claim; the report retains every model metric, delta, interval,
relation-coverage audit, and future-label audit separately by origin.

Sponsor history improves trial-local AP in 4/5 origins, but the 2022-origin
increment is negative with a wholly negative interval. Broader heterogeneous
context improves sponsor history in only 1/5 origins and is materially
negative in the 2023 origin. No stable heterogeneous value is established.
The candidate therefore remains
`status: stability_gate_pending`, `benchmark_admission: deferred`, and
`graph_model_status: paused`; no graph neural model is admitted by this gate.
The immutable official artifacts are
`results/generated/clinical-trials-v0_2-stability-run-001/`,
with `predictions.jsonl` SHA-256
`0ef619748cdd7bc74580c0ef6799565a4cde5892d47fd5aaef7911f4c6365fd1` and
`report.json` SHA-256
`b93f187acf5d17991738892353dcebab735cdb1fb9cc970d63abce811b159c8a`.


## Repository map

```text
healthgraphbench/
  core.py                         common task/model interface
  tasks/maude/                    MAUDE ingestion, temporal ranking, baselines
  tasks/cms_nursing/              CMS preparation, features, baselines
  tasks/partd/                    Part D admitted replication adapter
  evaluation/                     metrics and entity-clustered bootstrap
  controls/                       positive and zero-signal topology controls
configs/task_contract_v0_1.json   frozen v0.1 task contract
configs/task_contract_v0_2.json   admitted Part D v0.2 contract
data/manifests/v0.1.json          official URLs and frozen source hashes
docs/benchmark_report_v0_2.md     v0.2 research report
docs/HealthGraphBench_Specification.tex
docs/HealthGraphBench_Specification.pdf
docs/project_history.md            historical feasibility and selection record
scripts/                          download, verify, rebuild, and analysis commands
results/                          versioned benchmark result artifacts
```

The historical record is intentionally a concise, self-contained summary.
Private review material, patient-level data, medical narratives, raw source
archives, and abandoned application artifacts are not included.

## Installation

Frozen v0.1 task code keeps its standard-library numerical implementations.
The v0.2 path adds NumPy (`numpy>=2.0,<3`) for new evaluation and
candidate-model numerical code. The frozen v0.1 artifacts and release packages
remain unchanged.
Install it from the repository root:

```bash
python -m pip install .
```

Python 3.11 or newer is required.

## Deterministic ranking contract

The v0.2 candidate contract orders every candidate ranking by score
descending, then canonical candidate ID ascending for equal effective scores.
Methods that explicitly use support or popularity as a precedence key apply it
before the final candidate-ID key; the candidate ID remains the final tie
breaker. Array-based metrics receive no IDs, so callers must supply rows in
canonical candidate-ID order before numerical ranking. Stable numerical
sorting then preserves that order for equal scores.

Canonical IDs are the MAUDE problem code, the ISO target inspection date
followed by CMS CCN, the source-native Part D drug identity, the ClinicalTrials
NCT ID, and the source-native FAERS drug/reaction edge identifier. The
machine-readable policy is
[`configs/task_candidates_v0_2.json`](configs/task_candidates_v0_2.json).
Frozen v0.1 interfaces and artifacts are unchanged.

## Source data

Raw FDA and CMS data are not vendored or relicensed. Download them into a
user-managed directory and verify the exact frozen snapshot before building.
The manifest records official dataset pages, retrieval URLs, byte counts, and
SHA-256 hashes.

```bash
python scripts/download_maude.py --output /path/to/healthgraphbench-data/maude
python scripts/download_cms.py --output /path/to/healthgraphbench-data/cms
python scripts/verify_sources.py --data-root /path/to/healthgraphbench-data
```

The CMS builder requires `chow_owners_full.json`, the complete CHOW owner
snapshot. An incomplete owner query must not be substituted.

A changed official current release fails hash verification rather than being
silently accepted as the frozen v0.1 input. If a source publisher replaces a
file, record a new benchmark version instead of editing this manifest in
place.

All admitted tasks expose the same rolling-safe interface:

```python
from healthgraphbench import load_task
from healthgraphbench.models import FacilityHistory

task = load_task("cms_nursing", "/path/to/healthgraphbench-data")
train = task.get_split("train")
validation = task.get_split("validation")
test = task.get_split("test")
predictions = FacilityHistory().fit_predict(train, validation, test)
metrics = task.evaluate(predictions)
```

The Part D adapter consumes its verified model-gate result through the same
interface:

```python
task = load_task("partd", "results/generated/partd-v0_2-model-gate-run-003")
```

The task owns entity definitions, temporal cutoffs, candidate/episode
selection, feature availability, and evaluation. Models select only a frozen
method name. Neo4j is not required.

## Rebuild the exploratory tables

```bash
python scripts/build_benchmark.py \
  --data-root /path/to/healthgraphbench-data \
  --task all \
  --output results/exploratory_v0_1_run_20260915T000000Z.json
```

The runner refuses to overwrite an existing result path, including the
committed exploratory files. Use a new versioned filename for every execution.
Each new result records the source commit, manifest hash, UTC execution
timestamps, verified source-file hashes, model wrappers, and seed semantics.

The comparison suite is:

- global popularity;
- neighbor frequency;
- logistic/tabular ranking;
- boosted stumps;
- spectral factorization;
- BPR embeddings followed by fixed one-hop neighbor averaging (historical
  relational baseline, not an end-to-end GNN);
- one-layer bipartite GraphSAGE link prediction trained with BPR and
  deterministic fixed-fanout neighbor sampling.

The frozen CMS suite is:

- prevalence;
- facility history;
- facility plus combined ownership aggregates.

The GraphSAGE implementation is the sole genuine learned message-passing
baseline in this milestone. No architecture sweep is included.

GraphSAGE is deterministic end to end: it uses sorted node order, stable
hash-derived neighbor and negative sampling, and no runtime random generator.
Its execution metadata records `seed: null` and `deterministic: true`; no
artificial multi-seed sweep is reported.

## Post-baseline execution artifacts

The following commands generated the committed post-baseline artifacts. Their
output paths already exist in this checkout and are immutable; use the clean-
clone sequence below, with an external output directory, to rerun them. The
post-baseline runs retain row-level predictions for the clustered analyses:

```bash
PYTHONPATH=. python scripts/build_benchmark.py \
  --data-root /tmp/healthgraphbench-data \
  --task cms_nursing \
  --output results/cms_execution_v0_1_20260915.json

PYTHONPATH=. python scripts/build_benchmark.py \
  --data-root /tmp/healthgraphbench-data \
  --task maude \
  --output results/maude_execution_v0_1_20260915.json

PYTHONPATH=. python scripts/run_controls.py \
  --data-root /tmp/healthgraphbench-data \
  --output results/synthetic_controls_execution_v0_1_20260915.json

PYTHONPATH=. python scripts/analyze_execution.py \
  --maude-input results/maude_execution_v0_1_20260915.json \
  --cms-input results/cms_execution_v0_1_20260915.json \
  --output results/analysis_execution_v0_1_20260915.json
PYTHONPATH=. python scripts/combine_execution.py \
  --maude results/maude_execution_v0_1_20260915.json \
  --cms results/cms_execution_v0_1_20260915.json \
  --controls results/synthetic_controls_execution_v0_1_20260915.json \
  --analysis results/analysis_execution_v0_1_20260915.json \
  --output results/execution_v0_1_20260915.json

PYTHONPATH=. python scripts/render_summary.py \
  --input results/execution_v0_1_20260915.json \
  --output-json results/benchmark_summary_v0_1.json \
  --output-csv results/benchmark_summary_v0_1.csv \
  --output-svg results/benchmark_summary_v0_1.svg
```

For a clean-clone rebuild, keep generated files outside the checkout (the
checked-in result paths are immutable) and run this sequence after placing the
manifest-matching snapshots under `DATA_ROOT`:

```bash
python -m pip install .
DATA_ROOT=/path/to/healthgraphbench-data
OUT=/tmp/healthgraphbench-v0_1-rebuild
mkdir -p "$OUT"
python scripts/verify_sources.py --data-root "$DATA_ROOT"
PYTHONPATH=. python scripts/build_benchmark.py --data-root "$DATA_ROOT" \
  --task cms_nursing --output "$OUT/cms.json"
PYTHONPATH=. python scripts/build_benchmark.py --data-root "$DATA_ROOT" \
  --task maude --output "$OUT/maude.json"
PYTHONPATH=. python scripts/run_controls.py --data-root "$DATA_ROOT" \
  --output "$OUT/controls.json"
PYTHONPATH=. python scripts/analyze_execution.py \
  --maude-input "$OUT/maude.json" --cms-input "$OUT/cms.json" \
  --output "$OUT/uncertainty.json"
PYTHONPATH=. python scripts/combine_execution.py --maude "$OUT/maude.json" \
  --cms "$OUT/cms.json" --controls "$OUT/controls.json" \
  --analysis "$OUT/uncertainty.json" --output "$OUT/benchmark_summary.json"
PYTHONPATH=. python scripts/render_summary.py --input "$OUT/benchmark_summary.json" \
  --output-json "$OUT/summary.json" --output-csv "$OUT/summary.csv" \
  --output-svg "$OUT/summary.svg"
```

`analyze_execution.py` reports primary-metric intervals aligned with the
headline comparisons: product-clustered GraphSAGE-versus-neighbor-frequency
intervals for MAUDE Recall@10, macro Recall@10, and MRR; CCN-clustered
ownership-versus-facility-history intervals for CMS ROC AUC and average
precision, plus Brier score. It also reports secondary pairwise-ranking
uncertainty, MAUDE quarterly/support slices, CMS annual/facility-history
slices, and the relational-versus-nonrelational ownership ablation. Its
outputs record input hashes, the source commit, the manifest hash, timestamps,
and bootstrap configuration.

The available CMS snapshot has one or two prior inspections per retained
target row, so its history slices are reported as `sparse_1` versus the
dataset-relative `higher_history_2+` band rather than implying a long-history
population.

## v0.2 publication artifacts

The v0.2 publication step consumes the immutable v0.1 task outputs and the
existing Part D model-gate result. It writes only new versioned paths:

```bash
PYTHONPATH=. python scripts/build_partd_execution_v0_2.py \
  --model-gate-dir results/generated/partd-v0_2-model-gate-run-003 \
  --output results/partd_execution_v0_2_20260916.json
PYTHONPATH=. python scripts/render_summary_v0_2.py \
  --output-json results/benchmark_summary_v0_2.json \
  --output-csv results/benchmark_summary_v0_2.csv \
  --output-svg results/benchmark_summary_v0_2.svg
PYTHONPATH=. python scripts/analyze_relational_value_v0_2.py \
  --output results/relational_value_v0_2.json
PYTHONPATH=. python scripts/combine_execution_v0_2.py \
  --output results/execution_v0_2_20260916.json
```

The unified table preserves task-local scopes and denominators instead of
pooling incomparable metrics. The relational-value analysis selects MAUDE
Recall@10, CMS ROC AUC, and Part D micro Recall@10 as the task-primary
held-out metrics. Part D has no local-only admitted comparator; its conclusion
is therefore heuristic-versus-learned, not local-versus-relational.

## Verified v0.1 exploratory results

These values are regenerated from the frozen snapshots listed in
`data/manifests/v0.1.json`. They are rounded to six decimal places for display;
the JSON result files retain full precision.

### MAUDE

| method | Recall@10 | macro Recall@10 | MRR |
| --- | ---: | ---: | ---: |
| global popularity | 0.184454 | 0.213349 | 0.157565 |
| neighbor frequency | 0.192045 | 0.224447 | 0.164092 |
| logistic/tabular | 0.184530 | 0.214743 | 0.154591 |
| boosted stumps/tabular | 0.182784 | 0.211871 | 0.156196 |
| spectral factorization | 0.174890 | 0.202450 | 0.136206 |
| BPR + fixed neighbor average | 0.183847 | 0.208820 | 0.161307 |
| GraphSAGE link prediction | 0.172840 | 0.196565 | 0.145143 |

### CMS nursing-home inspections

| method | ROC AUC | average precision | top-decile precision | top-decile recall | Brier |
| --- | ---: | ---: | ---: | ---: | ---: |
| prevalence | 0.472568 | 0.121754 | 0.114797 | 0.089971 | 0.111487 |
| facility history | 0.619975 | 0.196023 | 0.254871 | 0.199752 | 0.109407 |
| facility + combined ownership | 0.621293 | 0.197272 | 0.250132 | 0.196038 | 0.109538 |
The CMS table pools 2024 and 2025 predictions after annual expanding-window
fits. Neighbor frequency remains the strongest MAUDE method on Recall@10;
GraphSAGE is lower. Ownership augmentation changes CMS performance only
marginally. Neither table is a claim of clinical utility or confirmatory
generalization.

## Synthetic controls and uncertainty

Run the real-topology positive and zero-signal controls with a new output path
(the committed `results/synthetic_controls_v0_1.json` path is immutable):

```bash
python scripts/run_controls.py \
  --data-root /path/to/healthgraphbench-data \
  --output results/synthetic_controls_run_20260915T000000Z.json
```

The controls use synthetic node covariates/outcomes on a pre-cutoff ownership
topology. They test implementation capability only; they do not imply that
relational features should improve real CMS prediction.

For paired prediction rows containing `cluster`, `label`, `score_a`, and
`score_b`, use the clustered bootstrap command:

```bash
python scripts/bootstrap_compare.py \
  --input predictions.json \
  --metric auc \
  --resamples 1000 \
  --seed 0 \
  --output results/bootstrap.json
```

MAUDE uncertainty is clustered by product code; CMS uncertainty is clustered
by CCN. Network links can leave residual dependence between clusters.
Intervals spanning zero do not establish equivalence.

### Primary clustered intervals

Intervals use 1,000 resamples and preserve products/CCNs as the bootstrap
clusters. For ranking and discrimination metrics, positive differences favor
the first method named; Brier is a loss, so negative differences favor the
first method.

| comparison | metric | difference | 95% CI | clusters |
| --- | --- | ---: | ---: | ---: |
| GraphSAGE − neighbor frequency (MAUDE) | Recall@10 | -0.019204 | [-0.023578, -0.014845] | 2,026 products |
| GraphSAGE − neighbor frequency (MAUDE) | macro Recall@10 | -0.027883 | [-0.033630, -0.022316] | 2,026 products |
| GraphSAGE − neighbor frequency (MAUDE) | MRR | -0.018949 | [-0.023026, -0.014850] | 2,026 products |
| ownership − facility history (CMS) | ROC AUC | +0.001318 | [-0.001458, +0.004329] | 13,889 CCNs |
| ownership − facility history (CMS) | average precision | +0.001249 | [-0.001186, +0.003570] | 13,889 CCNs |
| ownership − facility history (CMS) | Brier | +0.000132 | [-0.000038, +0.000303] | 13,889 CCNs |

The MAUDE intervals directly quantify the headline ranking metrics. The CMS
intervals include zero for all three metrics; ownership augmentation therefore
does not show a clear predictive gain.

## Interpretation boundary

The v0.1 and v0.2 evaluation periods were inspected during development and
remain exploratory, not untouched confirmatory tests. Across tasks, simple
relational heuristics improve the selected point metric where a local reference
exists, while the selected learned-relational methods do not consistently
improve beyond those heuristics. Part D has no local-only admitted comparator,
and its CMS publication labels remain subject to suppression and left censoring.

See [`docs/benchmark_report_v0_2.md`](docs/benchmark_report_v0_2.md) for the
v0.2 report,
[`results/benchmark_summary_v0_2.csv`](results/benchmark_summary_v0_2.csv),
[`results/benchmark_summary_v0_2.json`](results/benchmark_summary_v0_2.json),
[`results/benchmark_summary_v0_2.svg`](results/benchmark_summary_v0_2.svg), and
[`results/relational_value_v0_2.json`](results/relational_value_v0_2.json).
The frozen v0.1 report and artifacts remain documented at
[`docs/benchmark_report_v0_1.md`](docs/benchmark_report_v0_1.md) and
[`results/benchmark_summary_v0_1.json`](results/benchmark_summary_v0_1.json).
The v0.2 contracts are
[`configs/task_contract_v0_2.json`](configs/task_contract_v0_2.json) and
[`configs/task_candidates_v0_2.json`](configs/task_candidates_v0_2.json).
