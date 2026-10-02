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

