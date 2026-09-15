# HealthGraphBench v0.1 benchmark report

## 1. Motivation

Relational structure is common in public-health and regulatory data, but its
presence does not establish that a learned graph model will improve prediction.
HealthGraphBench evaluates that question against strong entity-local and
relational baselines rather than assuming that graph complexity should win.

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

Primary uncertainty uses 1,000-resample entity-clustered bootstrap intervals:
products for MAUDE and CCNs for CMS. MAUDE intervals are computed directly on
per-product/per-quarter ranking contributions. CMS intervals use all retained
target inspection rows. Network links may leave residual dependence between
clusters.

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
in the negative direction. All CMS intervals include zero.

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

## 8. Controlled relational validation

On the real pre-cutoff ownership topology, the zero-signal relational control
has mean relational AUC 0.503087 across three seeds. Injecting relational
signal with `beta=2.5` raises mean relational AUC to 0.817456. The controls
support the narrower conclusion that the relational implementation can exploit
neighborhood signal when it is present; they do not imply that the real CMS
ownership features should improve prediction.

## 9. Interpretation and limitations

The result is not that graphs are intrinsically useless. In these two public
regulatory tasks, additional learned graph complexity does not currently beat
stronger simpler relational baselines, while the controlled experiment shows
that the machinery can recover injected graph signal.

Limitations include two tasks, passive/regulatory labels rather than clinical
outcomes, reporting and coding bias, limited CMS history depth, and development
inspection of the evaluation periods. Future prospective data could support a
truly untouched validation, but that is outside this frozen exploratory
release.

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
