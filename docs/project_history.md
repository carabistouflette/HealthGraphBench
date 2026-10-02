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
