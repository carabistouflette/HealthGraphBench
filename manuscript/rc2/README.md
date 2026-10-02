# Manuscript RC2 source overlay

Working scientific and editorial revision of the user-supplied `HealthGraphBench_FAIA_LaTeX_RC1.zip`. RC1 and historical results are immutable. RC2 is not author-approved or submitted; no manuscript DOI, tag or editorial acceptance is claimed.

## Sources and assembly

`overlay/` contains revised LaTeX, guides, package contracts and added compact evidence/figures, preserving package-relative paths. Unchanged historical data, tables, figures and replay tools are inherited from the attested RC1 ZIP. `external_files.json` identifies nine inference checkpoints by original repository path and SHA-256; they remain local, are not stored in Git, and are bundled by the assembler. Full prediction streams are not bundled.

```bash
python scripts/build_manuscript_rc2.py \
  --source-zip "$HOME/Downloads/HealthGraphBench_FAIA_LaTeX_RC1.zip" \
  --output-dir /tmp/hgb-rc2-rebuild/HealthGraphBench_RC2 \
  --archive-path /tmp/HealthGraphBench_FAIA_LaTeX_RC2_rebuilt.zip
```

Both output paths must be new. A clone alone lacks the original ZIP and local checkpoints; missing or changed evidence causes failure rather than fabrication. `--evidence-root` may point to another root retaining the indexed repository-relative paths. The assembler checks the source digest, applies the overlay, adds pinned checkpoints, compiles all five reading-layout PDFs, checks retained bytes and numerical identities, and creates a fresh integrity manifest and ZIP. Rebuilt PDF/archive hashes may differ due to compiler metadata; they do not replace a delivered candidate.

LaTeX, `latexmk`, BibTeX and Poppler are required. `render_figures.py --root <assembled-root>` uses Matplotlib/NumPy to render four bilingual figures from completed metrics/epoch CSVs; no fits or score recomputation. Delivered figures are included in the overlay, so plotting is not required for compilation.

## Scientific and editorial contract

Main manuscripts use readable scholarly prose, descriptive analysis names, explicit comparison units and restrained conclusions. Operational C/D1 identifiers, lock dates, source hashes, exhaustive audit counts and memory reservations are primarily in supplement S11 and provenance, rather than repeated throughout the main argument. French is canonical: the English manuscript, supplement, captions and declarations are faithful translations, not independent redrafts. Structure, content, mathematical meaning, numerical results and scientific scope must agree; natural English syntax and localized number formatting are permitted.

Historical GraphSAGE at three epochs remains distinct from new C30 and its retained reuse in D1. The self-only control is non-GNN, has different active capacity and near-ln(2) loss. Previously consulted periods remain exploratory; no new interval, causal aggregation isolation, independent confirmation, general graph superiority or clinical utility is claimed. No new fit, tuning, D2 or successful scientific audit is rerun for this revision.

The Q1/Q2-level editorial aim is clarity and scientific precision, not guaranteed acceptance or verified compliance with an unspecified journal. Authors, affiliations, declarations, bibliographic approval, venue choice, final publisher template and submission authorization remain human gates. The supplied FAIA-oriented name and IOS entry points do not constitute a journal selection. Preview PDFs are reading layouts only.

The translation revision requested on 3 October 2026 preserves all French scientific LaTeX sources. `overlay/verification/rc2_translation/language_concordance.json` records comparison of 26 bilingual file pairs, including the tables. Four translated-header tables use separate `*_translated_en.tex` inputs, preserving the protected historical originals. The translated English reading PDFs are 15 and 20 pages; differing pagination is not a content difference. The new delivery is `HealthGraphBench_FAIA_LaTeX_RC2_traduction_FR.zip`; the preceding RC2 ZIP remains an immutable prior candidate.
