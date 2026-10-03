# Manuscript RC2.1 source overlay

RC2.1 is the documentary correction of audited RC2: Figure 2 caption describes validation recall only, with losses in S11; the common bibliography's evidence map points to S2. The French caption is canonical, then translated. No new scientific calculation. RC1, earlier RC2 archives and historical results are immutable. RC2.1 is not author-approved or submitted; no manuscript DOI, tag or editorial acceptance is claimed.

## Sources and assembly

`overlay/` contains revised LaTeX, guides, package contracts and added compact evidence/figures, preserving package-relative paths. Unchanged historical data, tables, figures and replay tools are inherited from the attested RC1 ZIP. `external_files.json` identifies nine inference checkpoints by original repository path and SHA-256; they remain local, are not stored in Git, and are bundled by the assembler. Full prediction streams are not bundled.

```bash
python scripts/build_manuscript_rc2.py \
  --source-zip "$HOME/Downloads/HealthGraphBench_FAIA_LaTeX_RC1.zip" \
  --output-dir /tmp/hgb-rc2-1-rebuild/HealthGraphBench_RC2_1 \
  --archive-path /tmp/HealthGraphBench_FAIA_LaTeX_RC2_1_rebuilt.zip
```

Both output paths must be new. A clone alone lacks the original ZIP and local checkpoints; missing or changed evidence causes failure rather than fabrication. `--evidence-root` may point to another root retaining the indexed repository-relative paths. The assembler checks the source digest, applies the overlay, adds pinned checkpoints, compiles all five reading-layout PDFs, checks retained bytes and numerical identities, and creates a fresh integrity manifest and ZIP. Rebuilt PDF/archive hashes may differ due to compiler metadata; they do not replace a delivered candidate.

LaTeX, `latexmk`, BibTeX and Poppler are required. `render_figures.py --root <assembled-root>` uses Matplotlib/NumPy to render four bilingual figures from completed metrics/epoch CSVs; no fits or score recomputation. Delivered figures are included in the overlay, so plotting is not required for compilation.

## Scientific and editorial contract

Main manuscripts use readable scholarly prose, descriptive analysis names, explicit comparison units and restrained conclusions. Operational C/D1 identifiers, lock dates, source hashes, exhaustive audit counts and memory reservations are primarily in supplement S11 and provenance, rather than repeated throughout the main argument. French is canonical: the English manuscript, supplement, captions and declarations are faithful translations, not independent redrafts. Structure, content, mathematical meaning, numerical results and scientific scope must agree; natural English syntax and localized number formatting are permitted.

Historical GraphSAGE at three epochs remains distinct from C30 and its retained reuse in D1. C is the primary added experiment; D1 is a secondary fixed-setting diagnostic, not a causal aggregation demonstration. Its self-only identity vectors still learn relational edges through BPR; duration was selected for mean and imposed on none, whose data loss stays near ln(2). Capacity differences do not establish the cause. Previously consulted periods remain exploratory. A new conditional C30–historical-neighbors interval was explicitly authorized on 3 October; it excludes selection/training uncertainty and does not remove all network dependence. No new fit, tuning, D2 or successful historical scientific audit is rerun.

The Q1/Q2-level editorial aim is clarity and scientific precision, not guaranteed acceptance or verified compliance with an unspecified journal. Authors, affiliations, declarations, bibliographic approval, venue choice, final publisher template and submission authorization remain human gates. The supplied FAIA-oriented name and IOS entry points do not constitute a journal selection. Preview PDFs are reading layouts only.

The preceding translation candidate, requested on 3 October 2026, preserved all French scientific LaTeX sources. Its dated report `overlay/verification/rc2_translation/language_concordance.json` records 26 bilingual pairs; four translated-header tables preserved protected historical originals. Its English PDFs were 15 and 20 pages and its distinct archive was `HealthGraphBench_FAIA_LaTeX_RC2_traduction_FR.zip`. Those statements describe that earlier delivery, not the targeted scientific revision below.

## Targeted MAUDE consolidation — 3 October 2026

The current candidate is `HealthGraphBench_FAIA_LaTeX_RC2_consolidation_MAUDE.zip`; both preceding RC2 candidates remain immutable. French scientific text is revised first, then translated into English. The 27-pair current concordance report is `overlay/verification/rc2_paired/language_concordance.json`; the earlier translation report is dated evidence, not a claim about these newly revised French sources.

The main manuscript shows the validation-duration curve and a separate paired-results table. The supplement starts with methods (S1) and the evidence map (S2), keeps a short chronology in S4 and the detailed version registry in provenance. S11 separates calculation-path comparison, the newly authorized paired interval, and complete secondary D1 results.

`scripts/analyze_maude_paired_comparison.py` reads retained ranks and historical entity contributions. The frozen protocol is `results/maude_paired_protocol_20261003.json`; the observed result is `results/maude_C30_neighbors_paired_20261003.json`. C30 retrieves 2,775/13,174 links, neighbors 2,530/13,174; delta 0.018597236982, conditional 95% interval [0.011975077183, 0.025570110820], 1,000 product-cluster draws, seed 20261003. Original historical full candidate lists were not exported; the documented verification uses reconstruction from pinned history, recorded historical counts and positive IDs. No intersection-only cohort or score recomputation.

The package includes the contribution CSV, protocol, draws, original executed source snapshot and a current compact-replay runner. With NumPy, from the extracted root:

```bash
PYTHONPATH=vendor/post_rc1 python scripts/analyze_maude_paired_comparison.py \
  --protocol data/post_rc1/paired_protocol.json \
  --replay-contributions data/post_rc1/paired_contributions.csv \
  --output-dir /tmp/hgb-new-paired-replay
```

Use a new output directory. Compact replay does not recheck original candidate identities. The first calculation attempt failed before draws because an unintended address-space restriction was confused with RSS; its failure record is preserved, statistical protocol and declared limits unchanged.


## RC2.1 — two documentary corrections after the received audit

Current archive: `HealthGraphBench_FAIA_LaTeX_RC2_1_consolidation_MAUDE.zip`; audited RC2 remains unchanged. `overlay/verification/rc2_minor/external_audit_received.md` is the user-transmitted report, not a new assistant execution, prospective validation, author approval or editorial decision. Its 61 packaged tests are distinct from the upstream 64-test repository run. No fits, scores, bootstrap or successful scientific audits are repeated in this pass.

The original bibliography is retained at `history/RC1/references.bib` with its original pinned hash; the active common bibliography changes only the S1-to-S2 source-map note. The protected registry therefore retains 105 original paths and one archived bibliography. `language_delta.json` checks four modified bilingual pairs (caption/version labels) and records the 23 unchanged pairs; the earlier 27-pair report remains dated evidence.

