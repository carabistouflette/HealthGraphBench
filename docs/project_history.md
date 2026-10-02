# HealthGraphBench project history

This document preserves the project-selection context needed to interpret
HealthGraphBench v0.1. It is a concise historical record, not a second task
specification. The active benchmark is defined by
[`configs/task_contract_v0_1.json`](../configs/task_contract_v0_1.json).

## Why this benchmark exists

The project began with several public-data feasibility directions. The work
below tested whether each direction had a defensible data contract, temporal
linkage, and an observable predictive question. The resulting decisions are
preserved so that negative or inconclusive findings are not mistaken for
omissions.

| Direction | Historical finding | v0.1 treatment |
| --- | --- | --- |
| MAUDE product/problem prediction | A temporal relationship-prediction task could be built from official MAUDE files. Neighbor frequency was stronger than the retained BPR-plus-averaging model on the inspected periods. | Retained as the MAUDE benchmark task and baseline suite. |
| CMS nursing-home serious deficiencies | A temporally aligned serious-deficiency task and ownership aggregates could be built. Ownership augmentation was small and statistically compatible with zero under CCN-clustered uncertainty. | Retained as the CMS benchmark task and baseline suite. |
| FDA label propagation | Application/product/label linkage and temporal semantic comparisons did not establish a sufficiently defensible predictive application. The lexical comparison was 13/13 post-version preferences versus 12/13 for the semantic comparison; this was not validated semantic accuracy. | Not an active task. No label histories or downloaded application artifacts are required by v0.1. |
| Human-gated evidence direction | Technical evidence-packet preparation recorded provenance questions, but the required independent human review and protocol approval were not completed. | Not an active task. Reviewer packets and unapproved protocol records are not included. |
| Generic public-data and identifier-linkage explorations | Several early directions were screened for source integrity, identity/linkage quality, and a concrete predictive contract. They did not meet the active benchmark scope. | Preserved here as selection context only; no raw exploratory material is needed to rebuild v0.1. |

## Interpretation of the retained evidence

The retained results answer a narrow project-selection question: whether the
benchmark can compare local and relational information under explicit temporal
contracts. They do not establish that graph models should win.

The topology control implementation projects all valid current ownership associations strictly before the `2024-01-01` cutoff into an undirected shared-owner graph. On the frozen source snapshot this produced 11,601 non-isolated CCN nodes and 291,280 undirected links.

- On MAUDE, the neighbor-frequency baseline achieved Recall@10 of
  `0.192045`; the original BPR-plus-fixed-neighbor-averaging method achieved
  `0.183847`. The latter is not an end-to-end message-passing GNN.
- On CMS, facility history achieved ROC AUC `0.619975`; the original combined
  ownership model achieved `0.621293`. The CCN-clustered AUC interval for the
  difference was `[-0.001478, +0.004258]`.
- Synthetic positive and zero-signal controls on a real ownership topology
  showed that the aggregate feature path can use relational signal when the
  data-generating process contains it. Those controls are implementation
  diagnostics, not healthcare evidence.

The inspected 2023--2025 periods remain exploratory and
benchmark-development results. They are not untouched confirmatory tests.
Future model selection must disclose that exposure. A future holdout may be
added later, but waiting for one is not required to reproduce this release.

## Preservation boundary

This repository preserves historical decisions and their interpretation, not
the complete private working archive. The v0.1 release intentionally excludes:

- raw FDA/CMS source rows and downloaded source archives;
- patient-level data, medical narratives, and reviewer identities;
- incomplete human-review packets and unapproved protocol records;
- superseded task contracts and exploratory feature variants;
- application-specific experiments that are not one of the two active tasks.

Official source URLs, frozen hashes, transformation code, task contracts, and
rebuild commands are the reproducibility boundary. A reader can verify and
rebuild the active tasks without relying on a disappearing project archive.

## Post-RC1 organization — 2026-10-02

The unpublished manuscript RC1 package remains distinct from benchmark v0.2.0.
Its ZIP and four PDFs were copied read-only into the ignored local output area;
their hashes and an inventory are prepared for version control. No historical
result, published asset, benchmark tag or original manuscript file was replaced.

Local `develop` and `chore/consolidation-post-rc1` branches now isolate the
consolidation work. The [Gitflow guide](../CONTRIBUTING.md#gitflow), PR template
and CI configuration define release/hotfix back-merges and PR boundaries.
No commit, push, manuscript tag or server protection was created implicitly.

The [imported roadmap](ROADMAP_HealthGraphBench.md) keeps the four-week scientific
cycle proposed, not started. The [consolidation index](consolidation-post-RC1/README.md)
records roles and resources still to decide, artifact availability and submission
gates. The organization smoke passed, as did all 41 unit tests; this is not a new
health-data training run, scientific replay, independent confirmation or author
approval.

## RC1 consolidation: verification of retained analyses

At the user's request, technical A/B work proceeded on
`feature/post-rc1-verification`, with separate replay and claims-audit subagents.
A new Python 3.13.5 environment used the RC1 analysis requirements. Ten replay
checks and 609 arithmetic/manifest checks passed; 66 archived metric keys agreed
with the canonical summary at their declared precision. The evidence matrix
records 42 claims and their populations, conventions, calculations and limits.

Final verification passed 747 package checks, compared 16 vendored GraphSAGE
definitions with the pinned source, and ran all 41 repository tests in the clean
environment. These are retained-output and code/document checks, not new
health-model training, raw-data reconstruction or independent confirmation.

The [compact verification manifest](../results/consolidation_core_verification_20261002.json)
persists the observed checks and provenance. The integration record covers the
27-artifact inventory, the 42-claim evidence matrix and local documentation links;
large execution records remain in the ignored local run directory.

The MAUDE duration protocol and prepared-input feasibility are documented;
no duration has been selected and the real-data diagnostic has not run.
Author approvals, historical public availability, editorial target and final
submission remain unresolved. Historical source packages and scores are intact.

## Bounded MAUDE GraphSAGE duration diagnostic

The implementation was committed and pushed as
`4a22c2addc8203efd2b38a60c416270855c3bf3b` before health-data training.
Draft [PR #2](https://github.com/carabistouflette/HealthGraphBench/pull/2)
targets `develop` and depends on the draft A/B PR; neither is a delivery merge.
The preflight passed 53 tests and exactly matched the pinned RC1 core's
representations and 364 pair scores on four non-health fixtures at three epochs.

The new run `maude-duration-20261002T172405Z` completed the independent
0/3/10/30-epoch validation grid on prepared MAUDE snapshots. Recall@10 was
`0.022193 / 0.171577 / 0.166905 / 0.205062`. Thirty epochs were locked before
the new 2024 and 2025 evaluations. Their pooled result was
`2775 / 13174 = 0.210642`, over 6370 positive product-quarter observations.
All three phases respected their 900-second, 512-MiB aggregate-RSS and
512-MiB output limits; total run wall time was about 1168 seconds.

This changes the interpretation of the retained three-epoch GraphSAGE
underperformance: it does not characterize every duration. The new point
estimate exceeds historical GraphSAGE (`0.172840`) and neighbor frequency
(`0.192045`), without a new interval or matched historical compute budgets.
The controlled duration comparison is on validation; the three-epoch test
reference is historical, not a new C test fit. There is no independent
confirmation, robustness/optimality claim or aggregation ablation.

The [C report and curves](consolidation-post-RC1/verification/maude_duration_diagnostic.md)
and [separate compact manifest](../results/maude_duration_diagnostic_20261002T172405Z.json)
preserve observations and provenance. Raw sources were not reacquired;
the exact pre-run protocol is retained separately from its later status update.
Historical outputs, RC1, tags and `main` remain unchanged. A/B human gates,
the optional single D analysis, authors' declarations, editorial choice,
E/F and submission remain open.
