# HealthGraphBench — first publication-package release candidate

**RC1 • 30 September 2026 • identifier `manuscript-rc1`.** Scientific baseline: R6 after its two minor revisions. Main scientific prose, results, intervals, tables, figures, prepared inputs and computational code are preserved. This release changes delivery identification and packaging.

Archive: `HealthGraphBench_FAIA_LaTeX_RC1.zip`; root folder: `HealthGraphBench_RC1`. Identity: `release.json`; lineage and operations: `provenance.json`; retained scientific status: `data/revision_status_R6.json`.

**RC1 identifies the manuscript package, not benchmark v0.2.0.** No remote tag, GitHub Release, Zenodo deposit or DOI was created. Historical R2–R6 artifact names are retained for provenance. Editorial acceptance is not claimed.

## Documents

| File | Purpose |
|---|---|
| `main_fr.pdf` / `main_en.pdf` | French / English manuscript. |
| `supplement_fr.pdf` / `supplement_en.pdf` | Scientific supplements; S10 contains MAUDE training counts and representation coverage. |
| `response_reviewers_fr.pdf` | Response to the supplied R6 minor-revision review, subject to author approval. |
| `RELEASE_NOTES_FR.md` / `RELEASE_NOTES_EN.md` | RC1 scope, preservation and remaining editorial steps. |
| `verification/rc1/` | Checks executed for RC1 packaging, separate from historical evidence. |

Corresponding LaTeX sources are at the root, with `sections/`, `tables/`, `figures/` and `references.bib`. Author fields remain in `metadata_fr.tex` and `metadata_en.tex`. **They must still be completed: RC1 is not yet administratively ready for submission.**

## Verify before modifying

The analysis environment is recorded in `requirements-review.txt` and `verification/rc1/environment.json`. Poppler provides `pdftotext` and `pdfinfo`. From the extracted root:

```bash
sha256sum -c SHA256SUMS
python scripts/check_review_package.py
python -m unittest discover -s tests -v
```

The manifest covers delivered files, not later rebuilt PDFs. `release/protected_payload.json` freezes scientific payload hashes against the parent R6 archive. Tests do not replace data validation or author responsibility.

## Replay retained analyses offline

The orchestration script invokes the unchanged scientific scripts. It replays both bootstraps, CMS metrics, MAUDE descriptors and the coverage summary, and compares the outputs with their references. No health model is trained.

```bash
OUT="/tmp/hgb-manuscript-rc1-replay"
test ! -e "$OUT" || exit 1
python scripts/verify_rc1_replays.py --output-dir "$OUT"
```

The output directory must be new and outside the package. `checks.json` distinguishes numerical comparisons at absolute tolerance `1e-12` from the five byte-identical MAUDE outputs. Replay timestamps remain separate. Real compacts are in `data/real_R4/`; prepared MAUDE snapshots and descriptors are in `data/real_R6/maude_B/`.

For B1/B2 alone:

```bash
OUT="/tmp/hgb-manuscript-rc1-maude-B"
test ! -e "$OUT" || exit 1
python scripts/audit_maude_B.py replay   --input-dir data/real_R6/maude_B   --output-dir "$OUT"
```

**Scope.** Replay starts from the supplied contributions and prepared snapshots. It does not reacquire FDA/CMS archives, rerun the original parser, reverify remote sources or recover checkpoints. The historical R6 collection remains documented in `verification/real_R6/` and the bundle provenance; it is not reclassified as RC1 work. `README_MAUDE_B_FR.md` documents the separate upstream collection.

## Build in a copy

Install a LaTeX distribution with `latexmk`, BibTeX and the packages used. After verifying the received manifest:

```bash
BUILD="/tmp/hgb-manuscript-rc1-build"
test ! -e "$BUILD" || exit 1
cp -a . "$BUILD"
cd "$BUILD"
python scripts/compile_pdfs.py
python scripts/check_review_package.py --skip-manifest
```

Rebuilding may change PDF bytes without changing scientific content. Do not treat rebuilt PDFs as byte-identical delivery files when applying the original manifest. The retained `submission_ios_fr.tex` and `submission_ios_en.tex` entry points were not compiled here; RC1 PDFs use the reading layout.

## Freeze and distribution

Keep the RC1 ZIP and its external SHA-256 checksum. Do not silently replace an RC1 file: a later correction requires RC2 or another explicit identifier. Supply the complete package alongside the PDFs. `manuscript-rc1` is only a proposed tag name for future publication; it was not created remotely.

Before submission: human scientific and bibliographic approval, identities and affiliations, contributions, funding, competing interests, ethical position, data-use conditions, actual assistance disclosure, target-volume instructions and permanent archiving. No negative declaration or exemption is presumed. The declared benchmark DOI does not identify this manuscript package.
