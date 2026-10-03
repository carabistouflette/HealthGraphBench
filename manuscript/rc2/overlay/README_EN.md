# HealthGraphBench — RC2 working revision

**3 October 2026 • `manuscript-rc2` • not submitted or author-approved.**
Archive: `HealthGraphBench_FAIA_LaTeX_RC2_consolidation_MAUDE.zip`; root: `HealthGraphBench_RC2`.
The supplied RC1 remains unchanged (SHA-256 `2d066cfbbe1c50ed1f0dc021799d3bac631a70c428cf79d5d78b68af44e6b7be`).

**Targeted MAUDE consolidation.** C is the main addition; D1 remains a secondary diagnostic retained in full in the supplement. Canonical French is revised first, then faithfully translated into English. Current concordance of 27 pairs is in `verification/rc2_paired/language_concordance.json`; the earlier translation report remains dated evidence. Both preceding RC2 ZIPs are preserved, not overwritten.

## Contents and scope

- `main_fr.pdf`, `main_en.pdf`: separate historical benchmark and C exploration, validation curve and paired GraphSAGE30–neighbors table.
- `supplement_fr.pdf`, `supplement_en.pdf`: methods in S1, evidence map in S2, short history in S4; S11 documents the code comparison, new conditional CI, complete D1 and its RSS reservation; open items in S12.
- `response_reviewers_fr.pdf`: **historical** response to the R6 review, explicitly annotated; not a response to the current scientific feedback, RC2 approval, or submission.
- LaTeX sources, tables, figures and bibliography; author/affiliation fields in `metadata_*.tex` remain incomplete.
- `data/post_rc1/`: A/B/C/D1 manifests, CSVs, exact metrics and nine inference checkpoints. `verification/post_rc1/` retains protocols, audits and dated reports.
- `vendor/post_rc1/`: core and controller sources for inspection, not a standalone training distribution.
- `history/RC1/`: inherited packaging metadata/checker; their statuses remain historical.

C selects 30 epochs on 2023 validation before its tests; pooled 2024–2025 R@10 is 2775/13174 = 0.210642. The historical three-epoch test is not refitted in C. D1 reuses retained C `mean30` and adds only `none30`: 469/13174 = 0.035600, signed contrast +0.175042. `none` is self-only, non-GNN, with 64 versus 128 active shared-transformation coefficients and loss near ln(2). This is not a capacity-matched pure causal aggregation effect.

All periods had been consulted previously: exploratory analyses, without independent confirmation. Only the new conditional GraphSAGE30–neighbors CI is authorized and calculated in this pass: difference +0.018597, CI95 [ +0.011975; +0.025570 ], 1,000 product-level draws, seed 20261003. It covers neither selection, training, nor all network dependence. No new fit, tuning, D2, raw acquisition, or successful historical exhaustive audit is rerun.

All five PDFs are compiled; the four scientific documents were visually examined: FR/EN main PDFs 17/16 pages, supplements 23/22. The 64 repository tests pass; the new compact replay outside the repository reproduces the interval and all 1,000 draws exactly. Evidence: `verification/rc2_paired/visual_review.json`, `repository_tests.json`, and `compact_replay.json`. These technical checks do not constitute human approval.

## Verify delivery

From the extracted root, before modifying anything:

```bash
sha256sum -c SHA256SUMS
python scripts/check_review_package.py
```

The checker verifies identity, protected historical bytes, retained ratios/contrasts, checkpoints and PDFs. It runs no fits or scientific audits. `release/protected_payload.json` protects data, original tables/figures, bibliography and scientific tools; main scientific prose is deliberately revised.

## Build in a copy

With LaTeX, `latexmk`, BibTeX and Poppler:

```bash
BUILD="/tmp/hgb-manuscript-rc2-build"
test ! -e "$BUILD" || exit 1
cp -a . "$BUILD"
cd "$BUILD"
python scripts/compile_pdfs.py
python scripts/check_review_package.py --skip-manifest
```

All five PDFs use the **reading layout**, not an approved submission format. `submission_ios_*.tex` entry points are prepared but not compiled/validated for a final venue. Rebuilt PDF bytes may differ; do not apply the old delivery hashes to rebuilt files.

## Reproduction and limits

Historical compact outputs and prepared MAUDE snapshots remain included. Large C/D1 candidate-prediction streams and raw FDA/CMS archives **are not included**. C/D1 manifest paths refer to original repository runs, not files all promised inside this ZIP. Nine checkpoints support inference only, without training resumption; C/D1 are not fresh raw-data acquisitions.

The protocol, paired CSV, and `data/post_rc1/paired_*` draws permit replay of the new CI. From the package root, with NumPy and a new destination:

```bash
PYTHONPATH=vendor/post_rc1 python scripts/analyze_maude_paired_comparison.py \
  --protocol data/post_rc1/paired_protocol.json \
  --replay-contributions data/post_rc1/paired_contributions.csv \
  --output-dir /tmp/hgb-new-paired-replay
```

This replay does not recheck original candidates. The initial calculation compares C lists with prepared history and historical cardinalities/positives; full historical lists were not exported. Records include the initial pre-draw failure, corrected without changing the statistical protocol.

The D1 audit retains inconsistent RSS measurements: VmHWM 118292480 B and ru_maxrss 571580416 B, without startup readings. All three scientific phases separately passed their budgets; no global audit RSS ceiling is certified. The non-health `exec` probe demonstrates a possible difference in measurement scope, not the certain cause of the peak.

Historical replays remain available through `scripts/verify_rc1_replays.py`; its name denotes the inherited RC1 scope, not the current package version. They are not rerun merely to confirm already verified results.

## Before submission

Human scientific/bibliographic approval, identities, affiliations, corresponding author, contributions, funding, competing interests, ethics, data-use conditions, actual AI-assistance disclosure, venue and official instructions remain unresolved. No negative declaration or acceptance is inferred. DOI `10.5281/zenodo.22796551` identifies **benchmark v0.2.0**, not RC2. No new tag, DOI or publication deposit is created. Keep RC1 and RC2 separate; later corrections require a new revision and provenance.
