# HealthGraphBench

HealthGraphBench studies when relational information adds predictive value
beyond strong entity-local and relational baselines in public
health/regulatory ML. It does not assume that graph methods should
outperform non-graph methods.

Version **0.1** is a reproducible benchmark release. The immutable `v0.1.0`
commit/tag records the pre-message-passing baseline definition. The completed
post-baseline execution freeze adds exactly one genuine GraphSAGE model,
primary-metric uncertainty, and versioned task/control artifacts without
changing the frozen source manifest or baseline result files.

The main research report is
[`docs/benchmark_report_v0_1.md`](docs/benchmark_report_v0_1.md). Its expanded
post-release text explains the contribution and bounded negative/conditional
findings; it does not change the frozen evaluation. Graph complexity must be
justified empirically, not presumed beneficial.

## Release downloads and citation

The [v0.1.1 GitHub Release](https://github.com/carabistouflette/HealthGraphBench/releases/tag/v0.1.1)
provides the report PDF and Markdown source, summary CSV/JSON/SVG, compressed
combined results, source manifest, task contract, `CITATION.cff`, and
`SHA256SUMS`. The report is explicitly a documentation supplement prepared
after the tag; the result payload is byte-identical to the tagged execution.
[`results/release_assets_v0_1_1.json`](results/release_assets_v0_1_1.json)
records download URLs, byte sizes, SHA-256 hashes, and packaging provenance.

Download into a new external directory and verify before decompressing:

```bash
mkdir healthgraphbench-v0.1.1-download
gh release download v0.1.1 --repo carabistouflette/HealthGraphBench \
  --dir healthgraphbench-v0.1.1-download
(cd healthgraphbench-v0.1.1-download && sha256sum -c SHA256SUMS)
gzip -dk healthgraphbench-v0.1.1-download/large-results.json.gz
sha256sum healthgraphbench-v0.1.1-download/large-results.json
```

The uncompressed SHA-256 must equal `compression.uncompressed_sha256` in the
asset manifest. `large-results.json.gz` contains the combined execution
artifact, including task results, analyses, and synthetic controls; it is not
a new run. The compression preserves original provenance fields.

For citation, use [`CITATION.cff`](CITATION.cff) and the versioned release URL.
No Zenodo DOI has been registered. DOI publication requires a repository
owner's Zenodo account/integration and verified deposition metadata; do not
substitute an invented DOI or recreate the existing tag to trigger archiving.

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

The research design and model suite remain frozen. Additional models require
a specific reviewer question and a separately versioned analysis.

## Repository map

```text
healthgraphbench/
  core.py                         common task/model interface
  tasks/maude/                    MAUDE ingestion, temporal ranking, baselines
  tasks/cms_nursing/              CMS preparation, features, baselines
  evaluation/                     metrics and entity-clustered bootstrap
  controls/                       positive and zero-signal topology controls
configs/task_contract_v0_1.json   model-independent benchmark contract
data/manifests/v0.1.json          official URLs and frozen source hashes
docs/HealthGraphBench_Specification.tex
 docs/HealthGraphBench_Specification.pdf
 docs/project_history.md          historical feasibility and selection record
scripts/                          download, verify, rebuild, and control commands
results/                          regenerated benchmark result artifacts
```

The historical record is intentionally a concise, self-contained summary.
Private review material, patient-level data, medical narratives, raw source
archives, and abandoned application artifacts are not included.

## Installation

The package uses only the Python standard library for the v0.1 tasks.
Install it from the repository root:

```bash
python -m pip install .
```

Python 3.11 or newer is required.

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

## Common interface

Both tasks expose the same rolling-safe interface:

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

The post-baseline runs use distinct paths and retain row-level predictions for
the clustered analyses:

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

Run the real-topology positive and zero-signal controls with:

```bash
python scripts/run_controls.py \
  --data-root /path/to/healthgraphbench-data \
  --output results/synthetic_controls_v0_1.json
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
clusters. Positive differences favor the first method named in the comparison.

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

Existing 2023--2025 results were inspected during development and remain
exploratory. They are not untouched confirmatory tests. The benchmark asks
where relational information pays for itself, including cases where a simple
relational heuristic beats a learned graph representation or where the
increment is compatible with zero.

See [`docs/benchmark_report_v0_1.md`](docs/benchmark_report_v0_1.md) for the
research write-up and [`results/benchmark_summary_v0_1.csv`](results/benchmark_summary_v0_1.csv),
[`results/benchmark_summary_v0_1.json`](results/benchmark_summary_v0_1.json), and
[`results/benchmark_summary_v0_1.svg`](results/benchmark_summary_v0_1.svg) for
the rendered result table and plot. The formal contract remains in
[`docs/HealthGraphBench_Specification.pdf`](docs/HealthGraphBench_Specification.pdf),
[`configs/task_contract_v0_1.json`](configs/task_contract_v0_1.json), and
[`docs/project_history.md`](docs/project_history.md).
