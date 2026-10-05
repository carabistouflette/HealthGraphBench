# RC3 manuscript source overlay

Canonical French, then faithful English; completed Q2 evidence only. Parent: attested RC2.2 ZIP, SHA-256 `a1731aa9eb02d8f31179adfea62d1d70a168594910aa2002780aa66e8f83c4f9`. Previous packages/scientific artefacts/user documents remain outside this change.

`overlay/` replaces active sources/guides/metadata in a new parent extraction. `evidence_files.json` pins received Q2 files; `overlay/data/q2/source_snapshots/index.json` pins consumed-source archives. Wheel and two derived cosine NPZ inputs are ignored in Git and packed locally by the assembler from their pinned original paths (or an `--evidence-root` laid out as those paths). No raw or large scientific output is committed. Four pure-code Git archives and compact metrics/ledgers remain tracked. This is not a self-contained training repository.

```bash
python scripts/build_manuscript_rc3.py assemble \
  --source-zip "$HOME/Downloads/HealthGraphBench_FAIA_LaTeX_RC2_2_cloture.zip" \
  --output-dir /tmp/hgb-rc3-20261004/HealthGraphBench_RC3
```

Assembly verifies received bytes, retains every parent member (replaced members in `history/RC2.2/`), compiles five reading PDFs and runs the new checker. No scientific fitting/scoring/replay/bootstrap is invoked. After actual inspection of the four scientific PDFs, provide a SHA-matching report and seal:

```bash
python scripts/build_manuscript_rc3.py seal \
  --root /tmp/hgb-rc3-20261004/HealthGraphBench_RC3 \
  --surface-report /tmp/hgb-rc3-20261004/surface_review.json \
  --archive-path "$HOME/Downloads/HealthGraphBench_LaTeX_RC3.zip" \
  --pdf-output-dir "$HOME/Downloads"
```

All output paths must be new. Sealing produces ZIP/SHA, four standalone PDFs and external delivery manifests. Recompilation requires a new surface inspection; never repin old scientific ledgers. Technical readiness does not close independent 2025 evaluation, external-human study, author/declaration/license/venue or submission gates. DOI `10.5281/zenodo.22796551` remains benchmark v0.2.0 only.

Package guides: `overlay/README_FR.md`, `overlay/README_EN.md`. Final observed delivery evidence is recorded separately under `results/` after smoke proof. No merge, tag, Zenodo or manuscript submission.
