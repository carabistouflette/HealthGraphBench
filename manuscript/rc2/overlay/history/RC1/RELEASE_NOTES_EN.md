# HealthGraphBench — publication package RC1

**Date: 30 September 2026.** Identifier: `manuscript-rc1`. Scientific baseline: **R6 after minor revisions**. Archive: `HealthGraphBench_FAIA_LaTeX_RC1.zip`.

## Release scope

RC1 is the first manuscript-package release candidate, prepared after the MAUDE coverage and inductive-wording corrections. It bundles both manuscripts, both scientific supplements, the latest reviewer response, LaTeX sources and executable evidence. The benchmark remains version 0.2.0 at commit `b010d5a49eae56837a920b2e30dece41c42c0c44`.

Nothing was published to GitHub or Zenodo. No tag or DOI was created, editorial acceptance is not claimed and the source repository was not modified.

## Changes from corrected R6

All five documents, PDF metadata and reader guides identify RC1. `release.json` separates manuscript identity from benchmark identity. `VERSION`, these notes and the manifest identify the delivery unambiguously. Previous versions of modified files are retained under `history/R6_minor/`.

Results, intervals, tables, figures, prepared data, scientific scripts and main scientific prose are unchanged. `release/protected_payload.json` records their baseline hashes. No health-model training, new prediction or new scientific effect is introduced.

`scripts/verify_rc1_replays.py` orchestrates the existing replay scripts without replacing their scientific functions. RC1 checks are stored separately under `verification/rc1/`.

## Candidate freeze

Verify `SHA256SUMS` before modifying or compiling. Build PDFs in a copy. Recompilation timestamps and metadata can change bytes; the delivered archive and its external checksum define RC1. Any later correction needs a new identifier rather than silent replacement.

Prepared inputs enable offline replay; they do not constitute a new FDA/CMS ingestion. Historical collection evidence retains its original scope. Automated checks do not replace human validation.

## Before submission

Author identities, affiliations, contributions and declarations have not been completed or signed on the authors' behalf. Scientific and bibliographic approval, venue requirements and permanent archiving remain to be finalized. PDFs use a reading layout; final IOS-format compliance is not certified. The declared benchmark DOI is not an identifier for RC1.

**Status: candidate for review and archiving; not submitted and not published.**
