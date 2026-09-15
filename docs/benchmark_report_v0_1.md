# HealthGraphBench: When does relational structure add predictive value?

Research report accompanying the v0.1.1 frozen exploratory benchmark.
This expanded report is a post-release documentation supplement; the tagged
code, design, source manifest, and result bytes remain unchanged.

## Abstract

HealthGraphBench evaluates the incremental predictive value of relational
structure against strong non-graph and simple relational baselines under
temporally valid health-regulatory prediction tasks. We study first-observed
product/problem-code relationships in FDA MAUDE and serious deficiencies at
later CMS nursing-home inspections. Historical features precede target
observations; the comparison suite and source snapshots are frozen.
On MAUDE, neighbor frequency achieves Recall@10 of 0.192045 versus 0.172840
for a deterministic GraphSAGE link predictor. The paired product-clustered
95% interval for GraphSAGE minus neighbor frequency is
[-0.023578, -0.014845]. On CMS, ownership augmentation changes facility-history
ROC AUC by +0.001318, with a CCN-clustered interval of
[-0.001458, +0.004329]. Synthetic controls recover injected relational signal
but provide no health-outcome evidence. These are exploratory
benchmark-development results: the temporal evaluation periods were inspected
during development, not reserved for untouched prospective confirmation.
The contribution is a reproducible comparison in which graph complexity must
earn its place, rather than an assertion that graphs do not work.

## 1. Motivation

Relational structure is common in public-health and regulatory data, but its
presence does not establish that a learned graph model will improve prediction.
HealthGraphBench evaluates that question against strong entity-local and
relational baselines rather than assuming that graph complexity should win.

The core contribution is the benchmark's controlled comparison of incremental
relational value, not a new graph architecture. It combines two temporal
prediction contracts, non-graph and simple relational baselines, one learned
message-passing model, paired uncertainty on headline metrics, and synthetic
implementation checks. This makes a negative or conditional outcome an
informative result rather than a failed model demonstration.

The research questions are deliberately narrow:

1. Does learned message passing improve MAUDE ranking over a simple
   historical relational heuristic?
2. Does ownership-network information add predictive value beyond a facility's
   own inspection history?
3. Can the control implementation recover relational signal when it is
   injected under a known data-generating mechanism?

The third question is an implementation check, not a third health task.

## 2. Benchmark

The benchmark contains two temporal tasks:

- **MAUDE**: predict first observed product/problem-code relationships using
  prior quarterly history. The evaluation uses historical candidate problems,
  no random edge split, and ranking metrics.
- **CMS nursing-home inspections**: predict serious G–L deficiencies at later
  inspections using expanding-window facility history, with an ownership-
  aggregate ablation.

The source manifest is `data/manifests/v0.1.json`. Raw FDA and CMS snapshots
remain external. The immutable `v0.1.0` tag records the pre-message-passing
baseline definition; the post-baseline execution is frozen as benchmark
version 0.1 in the versioned artifacts listed below.

For MAUDE, an eligible product has prior reports, a candidate problem has
appeared globally before the scored quarter, and the product/problem edge
has not previously appeared in retained history. A positive is first observed
within the retained collection window, not necessarily first ever. A negative
is temporal non-observation, not proof that no underlying failure exists.
Ranking covers all eligible candidates rather than sampled evaluation negatives.

For CMS, eligible Health Standard inspection episodes have at least one prior
such inspection. The target is an observed G–L Standard Deficiency at the
target episode. A negative is not evidence that a facility is safe.
Ownership associations are restricted to those active at the target date;
historical features and change-of-ownership counts exclude the target episode.

## 3. Methods

MAUDE compares global popularity, neighbor frequency, logistic/tabular
ranking, boosted stumps, spectral factorization, the existing BPR model with
fixed one-hop neighbor averaging, and one genuine learned message-passing
model: a one-hop bipartite GraphSAGE link predictor trained with BPR.

GraphSAGE uses trainable node inputs, shared self and mean-neighbor transforms,
`tanh` propagation, deterministic fixed-fanout neighbor sampling, and stable
hash-derived BPR negatives. It has no runtime random generator. The execution
metadata therefore records `seed: null` and `deterministic: true`; no seed sweep
was manufactured.

CMS compares prevalence, facility history, and facility history plus combined
ownership aggregates. No additional architecture was selected after the
GraphSAGE comparison.

## 4. Evaluation protocol

The reported results are a **frozen exploratory temporal evaluation**. The
2023–2025 periods were inspected during development and are not untouched
confirmatory holdouts. They should not be described as final unbiased clinical
performance.

The frozen contract assigns 2019–2022 to initial training history, 2023 to
validation, and 2024–2025 to test evaluation for both tasks. MAUDE advances
quarterly, scoring before adding the current quarter to history and refitting
learned rankers only at the frozen refit quarters using prior rows. CMS uses
expanding training rows ending before each target year. The annual and
quarterly diagnostics below include validation periods; they must not be
confused with the pooled 2024–2025 test tables.

Temporal ordering prevents the specified target-to-feature leakage; it does
not undo researcher exposure to evaluation results. The intervals quantify
resampling uncertainty for the frozen comparisons, not model-selection bias,
future distribution shift, or clinical deployment validity.

Primary uncertainty uses 1,000-resample entity-clustered bootstrap intervals:
products for MAUDE and CCNs for CMS. MAUDE intervals are computed directly on
per-product/per-quarter ranking contributions. CMS intervals use all retained
target inspection rows. Network links may leave residual dependence between
clusters.

Resampling preserves each entity's retained observations and pairs methods
within the same clusters. Reported differences are GraphSAGE minus neighbor
frequency for MAUDE and ownership augmentation minus facility history for
CMS. Higher ranking/discrimination metrics are better; lower Brier is better.
Micro Recall@10 pools recovered positives over eligible positives; macro
Recall@10 weights eligible entity/quarter recalls equally. MRR summarizes
reciprocal first-relevant ranks over eligible entity/quarter observations.

## 5. Main results

MAUDE test metrics use threshold 1:

| method | Recall@10 | macro Recall@10 | MRR |
| --- | ---: | ---: | ---: |
| global popularity | 0.184454 | 0.213349 | 0.157565 |
| neighbor frequency | 0.192045 | 0.224448 | 0.164092 |
| logistic/tabular | 0.184530 | 0.214743 | 0.154591 |
| boosted stumps/tabular | 0.182784 | 0.211871 | 0.156196 |
| spectral factorization | 0.174890 | 0.202450 | 0.136206 |
| BPR + fixed neighbor average | 0.183847 | 0.208820 | 0.161307 |
| GraphSAGE link prediction | 0.172840 | 0.196565 | 0.145143 |

CMS metrics pool the 2024–2025 test predictions:

| method | ROC AUC | average precision | Brier |
| --- | ---: | ---: | ---: |
| prevalence | 0.472568 | 0.121754 | 0.111487 |
| facility history | 0.619975 | 0.196023 | 0.109407 |
| facility + combined ownership | 0.621293 | 0.197272 | 0.109538 |

The strongest MAUDE method is the simple historical neighbor-frequency
baseline. GraphSAGE is lower on all three primary aggregate metrics. Ownership
augmentation changes CMS discrimination only marginally and slightly worsens
Brier score.

## 6. Primary uncertainty

| comparison | metric | difference | 95% CI | clusters |
| --- | --- | ---: | ---: | ---: |
| GraphSAGE − neighbor frequency | Recall@10 | -0.019204 | [-0.023578, -0.014845] | 2,026 products |
| GraphSAGE − neighbor frequency | macro Recall@10 | -0.027883 | [-0.033630, -0.022316] | 2,026 products |
| GraphSAGE − neighbor frequency | MRR | -0.018949 | [-0.023026, -0.014850] | 2,026 products |
| ownership − facility history | ROC AUC | +0.001318 | [-0.001458, +0.004329] | 13,889 CCNs |
| ownership − facility history | average precision | +0.001249 | [-0.001186, +0.003570] | 13,889 CCNs |
| ownership − facility history | Brier | +0.000132 | [-0.000038, +0.000303] | 13,889 CCNs |

The MAUDE intervals directly quantify the headline comparison and exclude zero
in the negative direction: the Recall@10 difference is approximately -1.92
percentage points. All CMS intervals include zero. This is no clear evidence
of an ownership gain under this design, not an equivalence test or proof that
the true increment is exactly zero.

## 7. Temporal and history slices

The analysis artifact contains all MAUDE quarterly metrics from 2023Q1 through
2025Q4. GraphSAGE Recall@10 ranges from 0.153239 in 2025Q1 to 0.192616 in
2025Q4.

For low-support MAUDE row-level slices, the sampled-row ROC AUC for GraphSAGE
versus BPR is:

| history-support band | BPR | GraphSAGE |
| --- | ---: | ---: |
| 1–9 | 0.891627 | 0.940847 |
| 10–49 | 0.940015 | 0.962668 |
| 50–199 | 0.942777 | 0.953313 |
| 200+ | 0.903985 | 0.904100 |

These slice values use each eligible positive plus one deterministic
historically-known non-positive candidate per positive; they are diagnostic
row-level slices, not replacements for the all-candidate MAUDE ranking table.

CMS annual ROC AUC values are:

| year | facility history | facility + ownership |
| --- | ---: | ---: |
| 2023 | 0.654342 | 0.657552 |
| 2024 | 0.621884 | 0.622429 |
| 2025 | 0.628444 | 0.628356 |

The retained CMS rows have one or two prior inspections. The history analysis
therefore uses the dataset-relative bands `sparse_1` and
`higher_history_2+`, not a claim of long facility history.

## 8. Synthetic implementation sanity checks

On the real pre-cutoff ownership topology, the zero-signal relational control
has mean relational AUC 0.503087 across three seeds. Injecting relational
signal with `beta=2.5` raises mean relational AUC to 0.817456. The controls
support the narrower conclusion that the relational implementation can exploit
neighborhood signal when it is present; they do not imply that the real CMS
ownership features should improve prediction.

The labels in these controls are synthetic. Their performance does not
validate health labels, establish a causal ownership effect, or certify every
component of the MAUDE GraphSAGE implementation. It only shows sensitivity to
the injected signal in the exercised control pipeline and topology.

## 9. Interpretation and limitations

The result is not “graphs do not work.” Graph complexity must be justified
empirically; in these tasks, simpler relational structure captured as much or
more predictive value. MAUDE directly compares learned message passing with a
simple relational heuristic. CMS instead tests ownership-feature augmentation,
not a GNN-versus-tabular architecture comparison. Neither experiment warrants
a universal claim about graph learning.

Limitations include two tasks, passive/regulatory labels rather than clinical
outcomes, reporting and coding bias, limited CMS history depth, and development
inspection of the evaluation periods. Future prospective data could support a
truly untouched validation, but that is outside this frozen exploratory
release.

The deterministic GraphSAGE run establishes the behavior of one fixed
implementation and configuration, not the best attainable performance of all
graph models. Its bootstrap intervals do not include training-seed
variability. Sparse facility history and incomplete historical ascertainment
also constrain the CMS comparison. Cluster resampling cannot remove all
dependence induced by shared manufacturers, owners, or problem codes.

The design is frozen. No further model search is planned for this release.
A specific reviewer question may motivate a separately versioned analysis,
but must not retroactively alter this comparison or turn inspected periods
into purported untouched confirmation.

## 10. Reproduction and artifacts

From a clean clone, provide manifest-matching snapshots externally, run the
sequence in the root `README.md`, and write generated files outside the
checkout. The canonical committed artifacts are:

- `results/maude_execution_v0_1_20260915.json`
- `results/cms_execution_v0_1_20260915.json`
- `results/synthetic_controls_execution_v0_1_20260915.json`
- `results/analysis_execution_v0_1_20260915.json`
- `results/execution_v0_1_20260915.json`
- `results/benchmark_summary_v0_1.json`
- `results/benchmark_summary_v0_1.csv`
- `results/benchmark_summary_v0_1.svg`

The suite is frozen: no additional GNN architectures, Neo4j backend, frontend,
or LLM component is part of this release.

## 11. Conclusion

HealthGraphBench provides an exploratory benchmark-development result about
incremental relational value: a simple relational baseline outperforms the
frozen learned graph model on MAUDE, and CMS ownership augmentation has no
reliable measured gain over facility history. Synthetic controls provide a
separate implementation sanity check. The next research step is communicating
and scrutinizing these bounded findings, not expanding the model suite.

## Source and method references

- FDA, MAUDE database: https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfmaude/search.cfm
- CMS, Provider Data Catalog: https://data.cms.gov/provider-data/
- Exact snapshot URLs, retrieval records, and checksums:
  `data/manifests/v0.1.json`.
- Frozen task definitions: `configs/task_contract_v0_1.json`.
- Hamilton, Ying, and Leskovec (2017), *Inductive Representation Learning on
  Large Graphs*: https://arxiv.org/abs/1706.02216. The benchmark uses the
  documented one-hop implementation, not an exhaustive reproduction of all
  configurations in that work.
- Rendle et al. (2009), *BPR: Bayesian Personalized Ranking from Implicit
  Feedback*: https://arxiv.org/abs/1205.2618.
