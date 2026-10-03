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

## Fixed-duration MAUDE aggregation comparison (D1)

D1 was chosen as the sole P2 after C; D2 remains excluded. Code, the pinned
protocol and preflight were committed and pushed as
`b14d878a78f559b65c70fc872a51a59af4c5ae85` before new health-data fits.
Draft [PR #3](https://github.com/carabistouflette/HealthGraphBench/pull/3)
targets `develop` and depends on #2; initial technical CI passed in 18 seconds.
The default mean path exactly matched 364 RC1 fixture scores. Only the
self-only, non-message-passing `none30` variant was newly trained; mean30 C
outputs and costs were reused without repeating its fits.

The complete run `maude-aggregation-20261002T205122Z` used the common duration
30 selected by C. Validation recall@10 was mean `0.205062` versus none
`0.031149`; the duration was locked at 20:53:30.842192 UTC before none's tests.
Pooled test recall@10 was `2775/13174 = 0.210642` versus
`469/13174 = 0.035600`, signed mean-minus-none `+0.175042`.
All three training/evaluation phases stayed under 900 seconds, 512 MiB
aggregate RSS and 512 MiB outputs, without retries.

All 4,593,744 new none scores were reconstructed from three raw checkpoints
and paired with C cohorts; 51,260,776 numeric checks found no discrepancy at
1e-12. The audit's final RSS readings disagree: VmHWM 118,292,480 bytes versus
ru_maxrss 571,580,416 bytes. No startup readings or global audit-RSS certification
are claimed. A non-health telemetry probe demonstrates distinct exec scopes,
not the certain source of the audit's historical peak; training supervision
remains a separate observation.

The [D1 report and inspected curves](consolidation-post-RC1/verification/maude_aggregation_ablation.md)
and [separate manifest](../results/maude_aggregation_ablation_20261002T205122Z.json)
retain both results and origins. Shared active transforms differ (128 versus
64 scalars); none losses remain near ln(2) under these common settings.
This is a specific exploratory contrast, not isolated aggregation causality,
general superiority, optimum or independent confirmation. No tuning,
additional seeds, bootstrap or interval was added. A/B human review, public
availability, author declarations/editorial choice, manuscript E and decision F
remain open; C/D1 do not complete the four-week cycle.

## Manuscript RC2: technical preparation

The RC1 archive supplied by the user is preserved byte-for-byte. RC2 is a
separate working revision, not author-approved or submitted. Branch
`feature/manuscript-rc2` starts from `develop` and explicitly merges the D1
dependency; `main` and the four existing tags remain untouched.

The French and English manuscripts and supplements now incorporate C/D1,
distinguish historical three-epoch GraphSAGE from C30, and keep the new
contrasts exploratory. The complete main text was revised for readability
and scientific precision; operational details are concentrated in S11.
Q1/Q2-level writing is an editorial aim, not an acceptance or venue-format
certification.

Five PDFs were compiled and visually examined: main FR/EN 16/14 pages,
supplements 21/19 pages, historical R6 response 2 pages. The final package
passed 642 checks, includes 484 manifest entries and nine inference
checkpoints, and matches its ZIP member-by-member. Sixteen new numeric table
rows agree with retained results; Gitflow passed and all 61 existing tests
passed. No new scientific fit, tuning, D2, bootstrap, interval or successful
scientific audit was run for RC2.

Sources and the assembler are described in
[`manuscript/rc2/README.md`](../manuscript/rc2/README.md); the
[compact RC2 manifest](../results/manuscript_rc2_20261002T214332Z.json) and
separate checksum ledger identify the delivered archive and PDFs. Older
C/D1 ledgers retain their dated documentary snapshots rather than being
rewritten to match current planning documents. The four pre-existing user
changes are excluded. Author approval, declarations, venue selection and
final formatting, public historical availability and decision F remain open.


## RC2 English translation from canonical French

The user requires English to be a translation of French, not a separate
redraft. The main manuscript and supplement were translated paragraph by
paragraph, preserving the scientific content, structure, captions and
declarations. The missing source/DOI paragraph in S1 was restored and
English-only additions removed.

Concordance passed for 26 file pairs: numbers, mathematics, structure and
citations/references. All 53 French LaTeX sources remain byte-identical;
extracted text of the three French PDFs is unchanged. The English PDFs
were compiled and visually examined (main 15 pages, supplement 20).
Four translated-header tables retain the protected historical originals.
The new translation ZIP is a separate candidate; the previous delivery,
scientific evidence and human approval gates remain unchanged.


## Targeted RC2 MAUDE consolidation after scientific feedback

On 3 October 2026, the user explicitly authorized revision, retained-prediction
pairing, and one conditional GraphSAGE C30–historical-neighbors interval.
No new medical fit, score, tuning, training seed, D2, or previously successful
scientific audit was run. The protocol was fixed before the new calculation,
not before prior result exposure or duration selection.

French scientific text was revised first, then translated. C is the main
addition; D1 remains a complete secondary fixed-setting diagnostic.
The main PDFs include the duration curve and a separate paired table.
Methods and the evidence map open the supplement; the version registry is
kept in provenance. Pairing is distinguished from causal duration control.
Historical full candidate lists were not exported; comparison relies on
reconstruction from pinned history, historical cardinalities and positive IDs.

Across 6,370 product–quarters and 2,026 products, C30 retrieves 2,775/13,174
links and neighbors 2,530/13,174. Delta is +0.018597236982; conditional 95%
CI [+0.011975077183; +0.025570110820], 1,000 product-level draws, seed
20261003. Selection/training uncertainty and all network dependence are
not covered. Compact replay outside the repository matches CI/draws exactly;
original candidate identities are not rechecked in that replay.

Concordance: 27 source pairs. Repository suite: 64 tests passed. Five PDFs
compiled; four scientific PDFs visually examined, main FR/EN 17/16 pages,
supplements 23/22. Both preceding RC2 archives and older scientific ledgers
remain preserved. New archive:
`HealthGraphBench_FAIA_LaTeX_RC2_consolidation_MAUDE.zip`.
PR #4 remains draft toward develop, dependent on #3; human approval,
declarations, venue, and submission remain open.


## RC2.1 documentary correction after the received MAUDE audit

On 3 October 2026, the user transmitted a favorable exploratory-resource
opinion, conditional on correcting Figure 2's caption and the common
bibliography's source-map reference to S2. The audit reports independent
checkpoint/inference/bootstrap reconstruction; it is not a new project
execution or prospective validation. Its 61 packaged tests differ from
the documented upstream 64-test repository run.

French caption corrected, then translated; no new scientific computation.
The user requested RC2.1 numbering. Titles/footers and package metadata
identify the distinct correction; audited RC2 and older ledgers are kept.
Original bibliography archived with its original hash, active note S1→S2.
Five PDFs recompiled, same 17/16/23/22/2 pages; corrected/version pages
visually inspected and four scientific logs without warnings. Author,
declaration, venue, permanent archive, submission, and new-review gates
remain open. Manifest: `results/manuscript_rc2_1_20261003.json`.

