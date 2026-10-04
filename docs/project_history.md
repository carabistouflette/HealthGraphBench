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


## RC2.1 close-out toward submission — 2026-10-03

The user-provided RC2.1 roadmap proposes a bounded, indicative five-to-ten-working-day editorial close-out, conditional on access to the exact package and author availability. It does not restart the earlier RC1 cycle, guarantee a submission date, or require a new scientific campaign. The [received roadmap](ROADMAP_HealthGraphBench_RC2_1.md) and earlier [RC1 roadmap](ROADMAP_HealthGraphBench.md) remain separate records.

The [close-out evidence matrix](consolidation-post-RC1/verification_cloture.md) distinguishes prior technical checks, the already recorded standalone compact replay, the received user audit performed without importing project modules, and the assistant's focused RC2.1 PDF review. The replay matches the delivered conditional interval and bootstrap draws but does not reverify original candidate identities. The received audit is reported evidence, not a new assistant execution or prospective validation. The RC2.1 delivery manifest records package integrity and preservation; no scientific result, checkpoint, source ledger, or historical account was rewritten for this close-out.

RC2.1 remains not author-approved and not submitted. The PDFs are for review/reading layout, not a chosen journal's final format. Support selection, author identities and roles, CRediT contributions, funding, conflicts, ethics/data-use position, AI declaration, reference approval, license, archive decision and author approval remain open in the [author checklist](consolidation-post-RC1/submission_checklist_RC2_1.md). Proposed RC2.2 edits preserve results and distinguish deterministic separate training resets from independent random replications, and historical three-epoch GraphSAGE from GraphSAGE30. D2 and further `none30` tuning are not requirements. DOI `10.5281/zenodo.22796551` identifies benchmark v0.2.0 only, not a manuscript deposit.

## RC2.2 targeted editorial closure — 2026-10-03

Canonical French revised before English: separate deterministic resets without warm start, not independent random replications; historical three-epoch GraphSAGE distinct from GraphSAGE30. Protected cutoff figures are unchanged; separately named historical3 derivatives preserve every plotted point/interval/axis limit. Only C curve titles change among the prior 84 tracked scientific paths; 82 retain identical bytes.

Five PDFs compiled, 17/16/23/22/2 pages; 13 selected pages and four relevant bilingual figures inspected. Final method-name cells corrected and reinspected. Seven bilingual source pairs modified, 20 retained; mathematical units and references unchanged. Four scientific logs have no LaTeX warning, overfull box or unresolved reference; supplements retain 13/12 underfull diagnostics. No new medical training, score, tuning, bootstrap, D2 or previously successful scientific audit. The latest PDF-only roadmap remains distinct from the earlier executable audit received.

Portable evidence matrix and author checklist bundled under `submission/`. Archive: `HealthGraphBench_FAIA_LaTeX_RC2_2_cloture.zip`; manifest: `results/manuscript_rc2_2_20261003.json`. Earlier deliveries and ledgers remain immutable. PR #4 stays draft/develop, dependent on #3; no merge/tag. Author/venue/declaration/license/archive/submission gates remain open; no manuscript Zenodo deposit or benchmark republication.

## Scientific Q2 cycle: protocol and software preflight — 2026-10-03

The user authorized a scientific cycle after RC2.2, not another editorial revision. The separate [French protocol](q2-scientific-cycle/protocol_fr.md) fixes six configurations per tunable family, paired seeds103/211/307, validation-only selection, conditional HGB repetitions and enforced budgets. MAUDE `none` must change its checkpoint and reduce a fixed historical BPR probe loss by at least1% for every seed before selection and after selected refits. Different active capacities prevent a capacity-equal causal aggregation claim.

Part D now prepares verified raw inputs, fits only the requested model, produces new scores and recalculates evaluation. Replay-only model-gate entry points were removed; historical outputs and packages were not overwritten. An out-of-package cosine top50 implementation exercises the public history/ranker API; [migration and human-participant requirements](q2-scientific-cycle/reuse_fr.md) distinguish assistant-authored software evidence from actual external human reuse.

The nonmedical preflight found and corrected missing Numba helper registration and the sign convention in the numerical-gradient report, not an established historical D1 optimizer bug. All36 parameter-coordinate derivatives passed; maximum absolute errors were1.11e-10 (`mean`) and5.55e-11 (`none`). Actual synthetic HTTP pagination preserved compact UTF8 bytes and refused a wrong digest; timeout, RSS, output and worker-error stops were exercised. A synthetic4000-provider source supported a disjoint2000-provider delayed-evaluation fixture with seven actual model runs and known Recall@10=.5/Recall@20=1; publication-race and altered-score gates rejected invalid evaluations. These are software fixtures, not medical metrics, public-source availability evidence or independent evaluation.

The integrated repository suite passed78 tests. No new medical fit had run at this preflight boundary. Prospective Part D requires fresh complete public recaptures and catalogue gates both after input capture and after fits; official target bytes must match their2025 node/primary-file metadata. Local timestamps alone are not an external prepublication anchor. Real2025 data and human nonconsultation/reuse evidence remain separate unmet prerequisites. RC2.2, C/D1, their environments and ledgers, and the four user documents remain outside this cutover; no merge, tag, manuscript submission or Zenodo publication is implied.

### CMS first-run compatibility correction

The first medical CMS run was retained incomplete: six facility-history logistic validation fits completed, but HGB rejected the JSON integer `max_features=1` before its first fit. The CMS adapter now converts that fixed value to float, as the other Q2 adapters already do; protocol bytes, grids, seeds and budgets are unchanged. A supervised synthetic fit learned the strictly prior relation and scored the deliberately inverted target labels without target fitting. Its preflight and regression are published before restarting the full CMS comparison in a new output root; no incomplete-grid selection or overwriting is permitted. Other active runs retain their original source snapshots.

### MAUDE post-validation serialization correction

All84 MAUDE validation fits and the six complete grids were preserved with a locked selection before test scoring. The first2024 heuristic worker rejected an escaped backslash-n as a gzip text newline value. Only the two serialization literals changed; numerical implementations are byte-identical to the validation snapshot after these exact replacements. A real synthetic heuristic worker decoded two known product/problem/rank records for both baselines, and the temporal regression passed four tests.

The published controller can finish from complete locked validation in a new root, checking source lineage, every configuration/seed/result and validation-only selection. It does not refit successful validation runs; prior wall time and output bytes remain charged against the original cumulative budgets. The incomplete root, original preparation, checkpoints and error are retained. Protocol bytes and SHA256 remain unchanged; selected test refits retain their learning gates. This correction is published before any resumed medical test fit.

### Q2 comparisons and technical reuse completed

The three exploratory comparisons completed with150 validation fits and43 selected test refits,193 preserved checkpoints. MAUDE reused its84 complete validation fits after the serialization fix, then completed28 test refits; all12 selected GraphSAGE refits passed the fixed learning gate before scoring. Mean/none capacities and separately selected configurations remain unequal, and none’s seed spread is reported rather than selecting a favorable seed. CMS completed24 validation fits and8 test refits. Part D completed42 validation fits and7 test refits, with HGB training counts337702/349460 requiring all three seeds.

Separate CMS, MAUDE and Part D evidence/ledgers/archives preserve losses, checkpoints, scores, source snapshots and measured budgets, without original FDA/CMS raw files. Part D’s derived edges.csv is included, consistent with the CMS derived preparation and the reuse witness. Historical files/packages remain unchanged. Runtime/resource observations are not dedicated-machine timing or equal compute.

The clean-wheel witness completed verified raw-to-new-fits-to-scores-to-public-evaluation, including an out-of-package cosine model and reloaded checkpoints. Its SDK logistic baseline is not renamed as the selected Q2 LBFGS comparator. The final local suite passed80 tests, and the completed MAUDE CLI plus archive extraction were exercised. See [French results](q2-scientific-cycle/results_fr.md) and `results/q2_runtime_verification_20261003.json`. Assistant-authored reuse is not an external human study; the independent2025 target evaluation and human attestations remain separate gates.

### Part D public forecast anchor

The prospective runner completed fresh full public recaptures of all six2019–24 sources, three official catalogue gates, a disjoint2000-provider cohort and seven learned fits plus two heuristic score outputs. Origin and forecast were sealed at22:10:50 and22:28:54UTC on2026-10-03, with no official annual2025 node listed. Exact forecast/origin records and all nine score hashes were pushed publicly under2a59324003fe8b9c89a5f1e9ff6464f2a76f6ab2; repository visibility was observed public. A further official catalogue capture after external publication at22:43:54UTC still listed no2025 node, and its response body is preserved separately.

This is a real sealed forecast with public-input and external hash-anchor evidence, not a completed independent evaluation. No official2025 outcome file or target metric was acquired/computed. Human nonconsultation and an external human reuse study remain unknown/unmet. No merge/tag, manuscript deposit or journal acceptance/quartile claim is implied.

## RC3 manuscript integration of completed Q2 evidence — 2026-10-04

The user authorized a distinct RC3 after the experimental cycle. Canonical
French was stabilized before faithful English translation; historical RC1,
C/D1, RC2.2 and ClinicalTrials remain distinguished from new Q2 comparisons.
The main manuscript integrates validation-only model selection and three
comparison tables. Supplement S12 records grids, learning gates, seed spans,
resources and retained failures; S13 documents the sealed, unevaluated Part D
forecast; S14 describes actual API/wheel reuse; S15 retains human gates.

Five reading-layout PDFs compiled after a missing math delimiter was corrected
in both supplements. Assembly QA passed765 checks across34 bilingual source
pairs; final sealed-package QA passed1520 checks. Main FR/EN PDFs have20/19
pages and supplements32/31. All102 scientific pages were visually observed on
contact sheets, with10 additional full-page reads;296 printed Q2 decimal cells
were checked. No overfull box, unresolved reference or LaTeX warning remains;
supplements retain34/29 underfull diagnostics. Actual ZIP CRC and included-PDF
hashes passed. No historical successful scientific audit or medical
fit/score/bootstrap/source acquisition was rerun.

Delivery: `HealthGraphBench_LaTeX_RC3.zip` plus four standalone RC3 PDFs in
Downloads. Manifest and surface evidence:
`results/manuscript_rc3_20261004.json` and
`results/manuscript_rc3_surface_review_20261004.json`.
Every parent byte is retained; replaced members are under `history/RC2.2/`.
Four consumed-source archives remain distinct from the later integration
snapshot. The exact reuse wheel and two cosine NPZ inputs are packed locally,
not committed as derived data. Five heavy experimental archives remain
separately hash-indexed. The four protected user documents retain their
initial SHA-256 fingerprints.

Q2 periods remain exploratory. Selected mean/none dimensions/configurations
and capacities differ, so no capacity-matched causal aggregation effect is
claimed; D1's nearly flat loss does not establish a historical optimizer bug.
No official Part D2025 target or metric was acquired/computed. Human
nonconsultation is unknown and external-human reuse remains unperformed.
Authors, declarations, manuscript license, venue, final template and submission
approval remain open. No merge/tag/Zenodo/submission or Q2 acceptance guarantee.

## RC3.1 targeted relational-information protocol — 2026-10-04

After documentary RC3 closeout, the user explicitly chose targeted new experiments
before RC3.1. The [canonical French protocol](rc31-relational/protocol_fr.md)
separates common Part D comparisons (common-count/Jaccard/cosine/BPR/GraphSAGE)
from MAUDE fanout, aggregation-only reassignment and same-state BPR inference
smoothing, plus matched-row CMS owner-representation contrasts. Successful
historical BPR fits are reused, not retrained. All declared pre-target strata,
zero-positive review workloads and conditional entity-cluster uncertainty remain
exploratory; model/seed selection and actual cumulative budgets are locked.

The new synthetic regression subset passed44 tests in3.723s; the new CLI preflight
exercised adapters, persistent checkpoints, degree-preserving intervention and
denominators without health fits/scores or replaying old gradient audits.
A fresh metadata-only CMS catalogue capture at19:58:26.587211UTC still listed
2013–24, not service2025; body and provenance are preserved in
`results/rc31_catalog_20261004.json` and `results/rc31_availability_20261004.json`.
The original forecast stays unchanged. Real temporal confirmation and an actual
outside team remain gated by unavailable target/human evidence, documented
[separately](rc31-relational/independence_and_reuse_fr.md). No medical result,
external human success, manuscript approval or submission is asserted at this
preflight boundary; RC3 and all historical/user files remain outside the change.

## RC3.1 targeted experiments completed — 2026-10-05

The pre-fit lock was published as `dde6a2facf83a493c23ea4797ff5da9e90138452`
on draft [PR7](https://github.com/carabistouflette/HealthGraphBench/pull/7),
dependent on PR6. Its observed CI passed before the medical run.
`experiment-001` completed75 new fits and126 phases in9,243.60s, with zero
historical BPR retraining. All57 new GraphSAGE fits changed persisted state
and passed the fixed-probe gate; minimum relative loss reduction47.09%.
The [French results](rc31-relational/results_fr.md) distinguish36 overall
contrasts and300 strata records:296 defined with2,000 valid draws,40 undefined.

Part D cosine k50 has test2024 micro-recall@10 .258583 versus reused BPR .236182;
paired conditional difference+.022401[+.014212;+.030800]. The aggregate gain
reverses for rare/weak-neighbor-support candidates. MAUDE real aggregation
outperforms bounded degree-preserving reassignment under fixed settings, but
fanout and same-state BPR smoothing gains vary by year. CMS owner restriction
does not restore a consistent gain over local history; documentation is not
ownership ground truth. Zero-positive observations remain in workload measures.

Actual results, layouts, states and resource bounds are retained in
`results/rc31_execution_20261004.json`, the pinned registry and the separate
full-output/input TAR. Its Part D selection metadata is explicitly external
to that TAR. Canonical French and faithful English are bound to actual analysis
SHA256 `2a569d2aa0c1a09befa2fbc9fcc2b5f5fe6899e8889798fb6b2bef90cb4a44c8`.
New paper assets were actually rendered; parent RC3 bytes remain under
`history/RC3`. PDF compilation/visual inspection/sealing are separate gates.

All new results remain exploratory on previously consulted periods. The sealed
Part D forecast is unchanged; no Part D2025 target was acquired/evaluated.
Temporal confirmation, actual outside-human reproduction, clinical utility,
authors/declarations/license/venue and submission approval remain unperformed
or unknown. No old scientific audit, merge, tag, Zenodo or submission.

## RC3.1 bilingual manuscript sealed — 2026-10-05

Canonical French and faithful English were assembled from the completed run,
without another medical fit or bootstrap. Four current PDFs compiled cleanly:
15 pages per main manuscript and100 per supplement. Two AI technical reviewers
actually inspected all230 rasterized pages, with13 additional enlarged views;
no surface finding remains. This is not an outside-human reproduction or author
approval. Compilation, attributed surface reports and delivery evidence are
preserved in `results/rc31_{compilation,surface_review,delivery}_20261005.json`.

The sealed package QA passed numerical derivation, bilingual assets, consumed
sources, resource limits, parent-byte retention, four actual visual reviews,
LaTeX diagnostics and manifest integrity. The exported ZIP passed CRC inspection;
all four standalone PDF bytes match their ZIP members. Delivery is distinct:
`HealthGraphBench_LaTeX_RC3_1.zip` (45,213,511 bytes), SHA256
`4af00f95ebc6c92cc15ad1d83d2b83fc32713c0e954cce12b7f4d36c58376427`,
and four RC3_1 FR/EN PDFs in Downloads. RC3 and earlier deliveries remain retained.

The separate6,803,096,874-byte experiment/input TAR remains unchanged, SHA256
`f9a43842601a9e376c72db932b2b9aba30a3e1d4764dd5e35636b457155042d1`.
The2,429-byte actually consumed Part D BPR selection metadata is outside that
TAR but included byte-exact in the manuscript ZIP at
`data/reused_inputs/partd_selection.json`. Neither ZIP alone nor this split
delivery claims an autonomous rebuild from every original raw input.

All new results remain exploratory. No Part D2025 target was acquired/evaluated,
and the sealed Q2 forecast is unchanged. Independent temporal confirmation,
outside-human reproduction, clinical utility, author/declaration/license/venue
and submission gates remain open. No merge, tag, Zenodo or submission.

The sealed manuscript/source evidence was published as
`45f41cbb22b9e350e0da1d21cc3892c51f7f67e1` on draft PR7. Its observed
[CI run37244132661](https://github.com/carabistouflette/HealthGraphBench/actions/runs/37244132661)
passed Gitflow direction, editable package installation, regression suite and
installed CLI in32s. The attributed API response is retained in
`results/rc31_publication_ci_20261005.json`. This software verification does not
close the independent temporal, human, clinical or submission gates above.

