# HealthGraphBench — RC2 working revision

**2 October 2026 • `manuscript-rc2`.** Parent: supplied RC1 ZIP, SHA-256 `2d066cfbbe1c50ed1f0dc021799d3bac631a70c428cf79d5d78b68af44e6b7be`, unchanged.

## Scientific-document changes

- French/English abstracts, methods, results, supplementary tables, discussion and conclusions incorporate completed MAUDE C/D1 analyses.
- Historical three-epoch GraphSAGE results, tables and intervals remain intact; new C30 is separate, not a newly paired 3-vs-30 test.
- D1 reuses retained C `mean30`; only `none30` was trained anew at the D1 stage. Common duration, active capacity 128/64, non-GNN control and near-ln(2) loss are explicit. No pure causal aggregation claim, new interval or independent confirmation.
- New supplement S11 covers dated selection, cohorts, metrics, losses/costs, audits and the D1 RSS reserve. S12 retains unresolved human/editorial gates.
- New figures use completed outputs, without new scientific computation or fits; nine inference checkpoints, CSVs, manifests and audits are added separately.

## Packaging and lineage

`release.json`, `provenance.json`, VERSION, guides and delivery checker identify RC2. Inherited RC1 metadata/checks are retained under `history/RC1`, with historical scope. Hashes of historical data, tables/figures, bibliography and scientific tools are protected in `release/protected_payload.json`. The R6 response is annotated as historical, unsent and not approval of RC2. The current checker reruns no successful scientific audits.

## Delivery limits and gates

Large candidate-score exports and raw FDA/CMS archives are not included; their manifest paths identify original runs. Nine checkpoints are inference-only, without training resumption. Historical public availability remains unproven. No global D1 audit RSS certification below 512 MiB is claimed. Previously consulted tests remain exploratory.

RC2 is a working revision for review, not a submission or author-approved article. Identities, affiliations, contributions, funding, competing interests, ethics, data use, AI disclosure, references, venue and approvals remain unresolved. The reading layout is not final IOS-format certification. No new tag, DOI, benchmark release or editorial submission. The benchmark DOI does not identify RC2.

## 3 October 2026 — English translated from the French reference

At the user's request, French becomes the canonical source. English is retranslated paragraph by paragraph, including abstracts, methods, results, discussion, conclusions, supplements, captions, and declarations; English additions without a French equivalent are removed and omissions restored. Textual mathematical subscripts are translated without changing the formulas. Protected historical originals remain intact; four derived tables translate their headers.

Concordance was verified across 26 file pairs: values, formulas, structure, and references. The 53 retained French LaTeX sources have not changed; text extracted from the three French PDFs is identical to that of the preceding delivery. The new English PDFs, compiled and examined, have 15 pages for the manuscript and 20 for the supplement. No scientific result or human gate changes. The new ZIP `HealthGraphBench_FAIA_LaTeX_RC2_traduction_FR.zip` is distinct from the preceding delivery.


## 3 October 2026 — targeted consolidation after scientific feedback

Canonical French is revised, then translated into English. C becomes the main addition: a non-monotonic grid, validation curve in the manuscript, and a new table explicitly separated from the historical benchmark. D1 remains complete in the supplement but secondary: no message passing ≠ no relational learning, duration selected for mean then imposed on none, nearly flat loss, and capacity not demonstrated to be the cause.

The code comparison distinguishes historical execution commit, benchmark source state, and C; instrumentation and extraction of the final calculation are described, with the limited scope of retained fixtures. Prediction pairing is no longer confused with causal control of duration.

Following the user's explicit choice, a new conditional GraphSAGE30–neighbors CI is calculated on retained outputs: 6,370 product–quarters, 2,026 products, 13,174 positives; 2,775 versus 2,530 retrieved links; delta +0.018597, CI95 [ +0.011975; +0.025570 ], 1,000 draws, seed 20261003. The protocol precedes this calculation, not examination of the results or selection. Limits from unexported historical lists and between-product dependence are declared. The initial pre-draw allocation failure is preserved, followed by correction of the address-space/RSS confusion without changing the protocol.

Methods in S1, evidence map in S2, short history in S4, detailed registry in provenance. CMS: records dated before the inspection, without proof of public availability. Concordance of 27 pairs; new ZIP `HealthGraphBench_FAIA_LaTeX_RC2_consolidation_MAUDE.zip`. No new fit, tuning, D2, previously completed historical audit, or approval; old evidence and both RC2 candidates preserved.


## 3 October 2026 — RC2.1, two documentary corrections after the audit

The received opinion favors the exploratory resource-article positioning subject to these corrections; it is neither author approval nor an editorial decision. Figure 2: caption limited to validation recall, independent 0/3/10/30 fits, and losses referred to S11; French corrected then translated. Common bibliography: evidence map in S2, not S1. No added panel, result, training, score, tuning, bootstrap, D2, or successful scientific audit rerun.

At the user's request, this correction is identified as **RC2.1** in metadata, PDF titles/footers, checker, and distinct ZIP `HealthGraphBench_FAIA_LaTeX_RC2_1_consolidation_MAUDE.zip`. Audited RC2 is preserved. Original bibliography archived byte-identically with its original hash; active bibliography modified only in one note. Incremental concordance: four modified pairs, 23 retained; earlier dated evidence preserved. The received audit's 61 tests are distinguished from the 64 upstream repository tests.

## 3 October 2026 — RC2.2, targeted editorial closure

The received RC2.1 roadmap is retained as a documentary review based on PDFs and some fractions, distinct from the earlier executable audit. Separate C training runs are deterministically reinitialized without warm start; they are not independent random repetitions. Historical three-epoch GraphSAGE and GraphSAGE30 are made explicit in relevant captions and labels; protected originals are retained and `historical3` derivatives identified. Plotted points and intervals are identical; only historical labels and C titles change.

Canonical French, then English. Executed-evidence matrix and author checklist in `submission/`. Exact venue, identities/declarations, approvals, license and archiving remain unresolved; historical FAIA names do not select a venue. New archive `HealthGraphBench_FAIA_LaTeX_RC2_2_cloture.zip`, never a replacement of RC2.1. No fit, score, tuning, bootstrap, D2 or successful scientific audit rerun; no tag, DOI, Zenodo deposit or submission.

