# HealthGraphBench v0.2: When does relational structure add predictive value?

Research report for the v0.2 admitted replication extension. The MAUDE and CMS
nursing-home tasks and their v0.1 result artifacts remain frozen. v0.2 adds one
bounded CMS Medicare Part D prescriber-drug task; it does not add a new graph
architecture or reopen candidate-dataset search.

## Abstract

HealthGraphBench compares local, interpretable relational, tabular, and learned
relational methods under temporal prediction contracts. The v0.1 core contains
FDA MAUDE product/problem ranking and CMS nursing-home serious-deficiency
prediction. The v0.2 extension admits CMS Medicare Part D as a replication task:
rank exact trimmed generic drug names for providers' first observed published
provider-drug relationships.

On the frozen MAUDE test, neighbor frequency reaches Recall@10 `0.192045`,
while the learned GraphSAGE method reaches `0.172840`. On the frozen CMS test,
adding ownership aggregates changes ROC AUC by `+0.001318`; its clustered
interval includes zero. On the Part D 2024 held-out temporal test, specialty
popularity reaches micro Recall@10 `0.217860`, history overlap `0.210373`,
tabular logistic `0.168188`, and graph BPR `0.180789`. Thus the added task
replicates the narrower finding that interpretable specialty/history heuristics
can outperform the learned baselines in this bounded published-observation
setting. Part D has no admitted local-only comparator, so it cannot establish a
local-versus-relational increment by itself.

These are development-stage temporal evaluations. The target periods were
inspected during task development and are not untouched prospective confirmation.
The result is evidence about the specified contracts and source snapshots, not
clinical utility, causal effects, or universal graph-model performance.

## 1. Scope and research questions

The v0.2 benchmark keeps the v0.1 scientific question: when does relational
structure add predictive value over information local to an entity? The extension
asks one replication question without expanding the model search:

1. Does an interpretable specialty/history heuristic outperform tabular logistic
   and BPR-based ranking for first observed published provider-drug relationships?
2. Do simple relational heuristics show a consistent point advantage over the
   selected local reference where a local reference exists?
3. Does learned relational structure add value beyond the interpretable
   relational heuristic?

ClinicalTrials.gov remains deferred after its rolling-origin stability failure.
FAERS remains optional and is not part of v0.2.

## 2. Benchmark tasks

### 2.1 Frozen v0.1 tasks

- **MAUDE** predicts first observed product/problem-code relationships from prior
  quarterly history. Candidate problems have appeared globally before the scored
  quarter, and ranking covers all eligible candidates.
- **CMS nursing-home inspections** predicts an observed serious G--L deficiency
  at a later Health Standard inspection. Facility history is compared with
  ownership aggregates active at the target date.

Their source manifest, task contract, code paths, result payloads, and release
assets are preserved byte-for-byte. The v0.2 report consumes those artifacts;
it does not regenerate or rewrite them.

### 2.2 Admitted Part D replication task

The machine-readable admission contract is
[`configs/task_contract_v0_2.json`](../configs/task_contract_v0_2.json). The task
uses the CMS Medicare Part D Public Use Files and defines a positive in year
`t` when a provider-drug relationship is absent from every retained earlier CMS
Part D snapshot and is observable in the published file for year `t`. This is a
first observed **published relationship**, not a first prescription or verified
prescribing start.

The primary drug identity is the exact trimmed source `generic_name`. Exact
brand-plus-generic identity is not part of the admitted representation. For each
target year, the bounded cohort contains up to 2,000 providers first observed
strictly before that target year, selected by the smallest `(SHA-256 NPI, NPI)`
values. For an eligible provider, candidates are every drug observed globally in
the target cohort's strictly prior history except drugs in that provider's
entire prior history. Evaluation ranks every eligible candidate; no sampled
evaluation negatives are used.

The validation split uses 2019--2022 history and scores 2023. The held-out test
uses 2019--2023 history and scores 2024. Target rows are scored before the
history update. Ties are resolved by model score descending, prior global
provider support descending, then the canonical source-native drug key ascending.

The admitted methods are:

- `specialty_popularity`: an interpretable specialty-conditioned popularity
  heuristic;
- `history_overlap`: an interpretable peer-history overlap heuristic;
- `tabular_logistic`: the existing learned tabular baseline;
- `graph_bpr`: the existing provider--drug plus provider--specialty BPR model.

No message-passing escalation is justified by the model-gate evidence. CMS
suppresses provider-drug combinations with 10 or fewer Part D claims; absence is
therefore non-observation subject to suppression and left censoring.

## 3. Evaluation protocol

The v0.1 tasks retain their frozen metric scopes. The Part D primary metrics are
micro Recall@5/10/20, provider-macro Recall@5/10/20, and MRR on
positive-containing provider-years. All eligible provider-years additionally
report precision@5/10/20 and recommendation burden at each `K`, using actual
recommendation slots. Zero-positive provider-years remain in burden denominators.

The Part D result is consumed through the same `Split`, `PredictionSet`,
`BenchmarkTask`, and model-wrapper interface as the v0.1 tasks. Its compact
execution record is `results/partd_execution_v0_2_20260916.json`; the immutable
model-gate rankings and report remain under
`results/generated/partd-v0_2-model-gate-run-003/`.

The v0.2 unified table is long-form so that heterogeneous targets and metrics do
not get forced into one incomparable scalar. Each row records task, method,
method family, split, scope, denominator, direction, value, and source artifact:

- [`results/benchmark_summary_v0_2.csv`](../results/benchmark_summary_v0_2.csv)
- [`results/benchmark_summary_v0_2.json`](../results/benchmark_summary_v0_2.json)
- [`results/benchmark_summary_v0_2.svg`](../results/benchmark_summary_v0_2.svg)

## 4. Main results

### 4.1 MAUDE frozen test

The table uses the frozen 2024Q1--2025Q4 test scope and threshold 1.

| method | Recall@10 | macro Recall@10 | MRR |
| --- | ---: | ---: | ---: |
| global popularity | 0.184454 | 0.213349 | 0.157565 |
| neighbor frequency | 0.192045 | 0.224448 | 0.164092 |
| logistic/tabular | 0.184530 | 0.214743 | 0.154591 |
| boosted stumps/tabular | 0.182784 | 0.211871 | 0.156196 |
| spectral factorization | 0.174890 | 0.202450 | 0.136206 |
| BPR + fixed neighbor average | 0.183847 | 0.208820 | 0.161307 |
| GraphSAGE link prediction | 0.172840 | 0.196565 | 0.145143 |

### 4.2 CMS nursing-home frozen test

The table pools 2024--2025 test predictions.

| method | ROC AUC | average precision | top-decile precision | top-decile recall | Brier |
| --- | ---: | ---: | ---: | ---: | ---: |
| prevalence | 0.472568 | 0.121754 | 0.114797 | 0.089971 | 0.111487 |
| facility history | 0.619975 | 0.196023 | 0.254871 | 0.199752 | 0.109407 |
| facility + combined ownership | 0.621293 | 0.197272 | 0.250132 | 0.196038 | 0.109538 |

### 4.3 Part D 2024 held-out temporal test

The primary representation is exact trimmed generic identity. Recall and MRR
use positive-containing provider-years; precision and burden use all eligible
provider-years.

| method | micro Recall@10 | provider-macro Recall@10 | MRR | precision@10 | burden/provider-year@10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| specialty popularity | 0.217860 | 0.280229 | 0.313650 | 0.059650 | 10.000 |
| history overlap | 0.210373 | 0.245213 | 0.310751 | 0.057600 | 10.000 |
| tabular logistic | 0.168188 | 0.166448 | 0.217225 | 0.046050 | 10.000 |
| graph BPR | 0.180789 | 0.199590 | 0.264137 | 0.049500 | 10.000 |

At other cutoffs, the unified CSV preserves all Recall@5/10/20, macro Recall,
precision, burden, and MRR rows. The fixed top-K recommendation is a ranking
threshold, not calibrated confidence.

## 5. Cross-task relational-value analysis

The analysis selects one task-primary held-out metric per task: MAUDE Recall@10,
CMS ROC AUC, and Part D micro Recall@10. Values are not pooled across tasks.
The best simple relational heuristic exceeds the selected local reference on
both tasks with an available local reference. The Part D contract intentionally
has no local-only method, so its within-task evidence compares relational
heuristics with learned tabular and learned relational methods instead.

| task | local reference | best relational heuristic | best learned relational | heuristic minus local | learned relational minus heuristic |
| --- | --- | --- | --- | ---: | ---: |
| MAUDE | global popularity (0.184454) | neighbor frequency (0.192045) | BPR + fixed neighbor average (0.183847) | +0.007591 | -0.008198 |
| CMS nursing | facility history (0.619975) | facility + ownership (0.621293) | not admitted | +0.001318 | not_estimable |
| Part D | not_estimable | specialty popularity (0.217860) | graph BPR (0.180789) | not_estimable | -0.037071 |

Part D's specialty heuristic also exceeds tabular logistic by `+0.049671` micro
Recall@10. The result supports a bounded replication finding: simple relational
heuristics can carry useful signal, while the selected learned-relational
methods do not show a consistent gain beyond them. It does not support a
universal claim about graph learning. In particular, CMS's ownership comparison
is a feature-augmentation experiment rather than a learned graph-model test.

The machine-readable analysis is
[`results/relational_value_v0_2.json`](../results/relational_value_v0_2.json).

## 6. Uncertainty and interpretation boundary

The frozen v0.1 intervals remain unchanged. On MAUDE, the product-clustered
1,000-resample interval for GraphSAGE minus neighbor frequency Recall@10 is
`[-0.023578, -0.014845]`; the corresponding macro Recall@10 and MRR intervals
are also entirely negative. On CMS, the CCN-clustered interval for ownership
minus facility history ROC AUC is `[-0.001458, +0.004329]`, and the average
precision interval is `[-0.001186, +0.003570]`. These intervals quantify
resampling uncertainty for the specified comparisons, not model-selection bias
or deployment validity.

The admitted Part D model-gate artifact reports point metrics and paired
provider-year comparisons. This v0.2 publication step does not retrofit a new
uncertainty interval or treat the point differences as confirmatory evidence.
A future uncertainty analysis must be versioned separately and must not rewrite
the frozen inputs.

## 7. Limitations

- Part D labels are published observations. CMS suppression at 10 or fewer claims
  makes absence non-observation subject to left censoring.
- Generic names are exact source text, not RxNorm concepts, molecules, or
  clinical-equivalence classes.
- The Part D cohort is bounded and target-specific; national scalability and
  population representativeness are not established.
- The target is not a first prescription, prescribing start, or clinical outcome.
- Historical publication-time availability is not verified, so the retrospective
  service-year design is not deployment-valid next-calendar-year forecasting.
- Part D has no local-only admitted comparator; no local-versus-relational gain
  is claimed for that task.
- The task metrics and target semantics differ across MAUDE, CMS nursing, and
  Part D; cross-task comparisons are directional and task-local.
- Evaluation periods were inspected during development. Temporal ordering limits
  target-to-feature leakage but does not remove researcher exposure.

## 8. Reproduction and versioned artifacts

The v0.1 artifacts are immutable. Given the existing Part D model-gate artifact,
the v0.2 publication records are rebuilt with:

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

The common interface can inspect the admitted task directly:

```python
from healthgraphbench import load_task
from healthgraphbench.models import SpecialtyPopularity

task = load_task(
    "partd",
    "results/generated/partd-v0_2-model-gate-run-003",
)
train = task.get_split("train")
validation = task.get_split("validation")
test = task.get_split("test")
predictions = SpecialtyPopularity().fit_predict(train, validation, test)
metrics = task.evaluate(predictions)
```

The v0.2 release payload is listed in
[`results/release_assets_v0_2.json`](../results/release_assets_v0_2.json). No raw
source data are redistributed. The v0.1 report remains at
[`docs/benchmark_report_v0_1.md`](benchmark_report_v0_1.md) as the historical
release document.

## 9. Conclusion

Adding Part D makes the benchmark a small cross-domain replication rather than a
larger model catalog. Across the tasks with a local reference, simple relational
heuristics improve the selected point metric, while the learned-relational
method does not consistently improve beyond the heuristic. Part D independently
shows specialty/history heuristics above the existing tabular logistic and BPR
methods under a bounded generic-name publication contract. The result justifies
keeping graph escalation paused and prioritizing transparent relational
features, without claiming that graph models cannot work in other settings.
