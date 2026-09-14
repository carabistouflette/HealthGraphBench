# HealthGraphBench

HealthGraphBench studies when relational information adds predictive value
beyond strong entity-local and relational baselines in public
health/regulatory ML. It does not assume that graph methods should
outperform non-graph methods.

Version **0.1** is a reproducible benchmark-development release. It freezes
two temporal tasks, source manifests, feature availability rules, baseline
families, metrics, and dependence-aware evaluation utilities. It does not
include an end-to-end message-passing model yet.

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
results/                          regenerated compact result tables
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
```

`analyze_execution.py` reports product-clustered pairwise-ranking and
CCN-clustered Brier-score intervals, MAUDE quarterly/support slices, CMS
annual/facility-history slices, and the relational-versus-nonrelational
ownership ablation. Its outputs record input hashes, the source commit, the
manifest hash, timestamps, and bootstrap configuration.

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

### CMS nursing-home inspections

| method | ROC AUC | average precision | top-decile precision | top-decile recall | Brier |
| --- | ---: | ---: | ---: | ---: | ---: |
| prevalence | 0.472568 | 0.121754 | 0.114797 | 0.089971 | 0.111487 |
| facility history | 0.619975 | 0.196023 | 0.254871 | 0.199752 | 0.109407 |
| facility + combined ownership | 0.621293 | 0.197272 | 0.250132 | 0.196038 | 0.109538 |

The CMS table pools 2024 and 2025 predictions after annual expanding-window
fits. The MAUDE table reports the aggregate temporal-gate metrics. Neither
table is a claim of clinical utility or confirmatory generalization.

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

## Interpretation boundary

Existing 2023--2025 results were inspected during development and remain
exploratory. They are not untouched confirmatory tests. The benchmark asks
where relational information pays for itself, including cases where a simple
relational heuristic beats a learned graph representation or where the
increment is compatible with zero.

See [`docs/HealthGraphBench_Specification.pdf`](docs/HealthGraphBench_Specification.pdf),
[`configs/task_contract_v0_1.json`](configs/task_contract_v0_1.json), and
[`docs/project_history.md`](docs/project_history.md) for the complete v0.1
contract and project-selection context.
