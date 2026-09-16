# ClinicalTrials Stability Decision Memo

**Artifact:** `results/generated/clinical-trials-v0_2-stability-run-001/report.json`  
**Decision:** `DEFER_TASK`  
**Candidate state:** `stability_gate_pending`; `benchmark_admission: deferred`; `graph_model_status: paused`

The stability gate evaluates five exact historical origins. Each origin is fit
only with labeled examples from strictly earlier origins: 2019 for the 2020
origin; 2019--2020 for 2021; 2019--2021 for 2022; 2019--2022 for 2023; and
2019--2023 for 2024. No later snapshot is used to reconstruct an earlier
prediction point, and no pooled stability AP is reported.

## Per-origin predictive results

AP deltas are relative to the immediately preceding model except for the full
heterogeneous column, which is relative to local plus sponsor. The interval is
the 95% paired percentile bootstrap interval for the full heterogeneous AP
difference versus sponsor; all intervals use 1,000 trial-cluster resamples.

| Origin | Local AP | +Sponsor ΔAP | +Condition ΔAP | +Facility ΔAP | +Intervention ΔAP | +Collaborator ΔAP | Full hetero ΔAP vs sponsor | 95% CI |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 2020-01-01 | 0.368399 | +0.104522 | -0.008890 | +0.008248 | -0.009481 | +0.003535 | +0.015022 | [-0.022369, +0.060294] |
| 2021-01-01 | 0.375904 | +0.033348 | -0.023829 | +0.003839 | +0.011852 | -0.005522 | -0.031079 | [-0.087890, +0.028991] |
| 2022-02-01 | 0.290692 | -0.048773 | -0.001240 | +0.007641 | +0.003817 | -0.019656 | -0.015623 | [-0.069626, +0.044298] |
| 2023-02-01 | 0.316535 | +0.038953 | -0.019178 | -0.062158 | -0.012844 | -0.025141 | -0.108077 | [-0.171780, -0.049169] |
| 2024-02-01 | 0.315710 | +0.050074 | -0.023950 | +0.016780 | -0.004907 | -0.000626 | -0.011878 | [-0.054550, +0.030322] |

## Eligibility and relation coverage

“Eligible / labeled” distinguishes the selected origin cohort from trials with
an observed, temporally valid label in the paired future snapshot. Prevalence
is calculated over labeled trials. Bootstrap undefined counts are zero for all
11 AP comparisons at every origin; resamples with undefined AP would otherwise
have been omitted rather than converted to zero.

| Origin | Eligible / labeled | Positive prevalence | Sponsor | Condition | Facility | Intervention | Collaborator | Isolated trials | Undefined resamples |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2020-01-01 | 940 / 939 | 0.168264 | 100.0% | 100.0% | 97.6% | 100.0% | 30.1% | 1 | 0 / 11,000 |
| 2021-01-01 | 947 / 947 | 0.144667 | 100.0% | 100.0% | 98.7% | 100.0% | 32.6% | 2 | 0 / 11,000 |
| 2022-02-01 | 1,117 / 1,117 | 0.087735 | 100.0% | 100.0% | 99.1% | 100.0% | 30.6% | 1 | 0 / 11,000 |
| 2023-02-01 | 1,244 / 1,243 | 0.119871 | 100.0% | 100.0% | 99.3% | 100.0% | 33.5% | 3 | 0 / 11,000 |
| 2024-02-01 | 1,353 / 1,353 | 0.130081 | 100.0% | 100.0% | 99.2% | 100.0% | 32.7% | 4 | 0 / 11,000 |

## Decision

Sponsor history is positive in four of five origins, but the 2022 increment is
negative and its interval is wholly below zero (`[-0.088028, -0.021689]`). It
therefore fails a strict consistency gate even though sponsor history is often
useful. The broader heterogeneous context improves sponsor history in only one
origin and is negative in the other four; the 2023 decrement is materially
negative with an interval excluding zero. Relation-specific context is also
unstable: condition is negative at every origin, facility is positive at four
origins but sharply negative in 2023, intervention is positive only in 2021 and
2022, and collaborator is positive only in 2020.

The earlier held-out heterogeneous gain is therefore period-specific rather
than a stable relational result. ClinicalTrials is **deferred** from v0.2, and
no graph-model experiment is justified by this gate. A future admission review
would need a new, pre-specified stability criterion and additional historical
support; this memo does not change any frozen v0.1 artifact.
