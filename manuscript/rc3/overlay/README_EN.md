# HealthGraphBench — RC3, strengthened-comparison integration

**4 October 2026 · `manuscript-rc3` · reading layout, not submitted or author-approved.**
Archive: `HealthGraphBench_LaTeX_RC3.zip`; root: `HealthGraphBench_RC3/`.
The RC2.2 parent remains unchanged: SHA-256 `a1731aa9eb02d8f31179adfea62d1d70a168594910aa2002780aa66e8f83c4f9`.
French was stabilized before faithful English translation; RC3 compilation, concordance and reading evidence is in `verification/rc3/`.

## Documents and findings

- `main_fr.pdf`, `main_en.pdf`: methods, findings and limitations on MAUDE, CMS nursing-home inspections and Medicare Part D; historical tables distinguished from new Q2 fits.
- `supplement_fr.pdf`, `supplement_en.pdf`: historical S1–S11, S12 grids/selection/losses/resources, S13 sealed forecast, S14 API and reuse, S15 unresolved human decisions.
- `response_reviewers_fr.pdf`: **historical** R6 response, not a response to the Q2 cycle or RC3 approval.
- Bilingual LaTeX sources, tables and figures; inherited `submission_ios_*.tex` entry points are not compiled or validated for a selected journal.

The Q2 comparisons used 150 validation fits and 43 test refits completed before RC3. Selection compares six configurations per family on 2023 validation, not equal compute budgets. MAUDE/CMS 2024–2025 and Part D 2024 had already been consulted: findings remain exploratory.
Tuned BPR exceeds the fixed heuristics on MAUDE and Part D; the CMS ownership increment remains small and variable. Selected Q2 `mean` and `none` GraphSAGE fits pass their learning criteria, with different configurations, dimensions and capacities: no capacity-matched causal aggregation effect is identified. D1's nearly flat loss is retained without establishing a historical optimization bug. No new CI, bootstrap, fit or score was computed to prepare RC3.

The Part D forecast seals scores for future official publication of service-year 2025 relations. **No official 2025 target or 2025 metric was acquired/computed; no independent evaluation has passed.** Absence of the annual node is attested only at captured catalog times. Disjoint NPIs do not guarantee statistical independence. Human non-consultation attestations remain `unknown`.
Assistant-operated raw–wheel reuse demonstrates a real API workflow and an out-of-package cosine model, not an external-human study. No external participant is invented. ClinicalTrials remains historical and separate; D2 is not undertaken.

## Included evidence and separate archives

- `data/q2/`: exact protocol, received JSON reports and ledgers, forecast chronology/publication, evidence and external-archive indexes.
- `data/q2/source_snapshots/index.json`: four archives of Git sources actually consumed (MAUDE validation/Part D, MAUDE completion, CMS, wheel). `vendor/q2/` and `scripts/q2/` are the integration snapshot at commit `6b4ae00ebc4b701d757260616ccb0df16f51467b`, not a retrospective reassignment of runs.
- `data/q2/reuse/`: exact wheel, executed cosine driver and two witness NPZ checkpoints; their reloaded-score probes are dated Q2 evidence, not a new RC3 execution.
- `data/post_rc1/`, `verification/post_rc1/`, `vendor/post_rc1/` and RC2 audits remain historical. All parent bytes are retained under `release/parent_payload_RC2_2.json`; replaced files are under `history/RC2.2/`.
- Raw FDA/CMS data, the 193 comparison checkpoints and nine complete forecast score streams **are not included**. The five separate experimental archives are identified by size/SHA-256 in `data/q2/external_archive_registry.json`. Original manifest paths do not promise these files inside the manuscript ZIP.

## Check the received package

From the extracted root, before modification:

```bash
sha256sum -c SHA256SUMS
python -B scripts/check_review_package.py
```

The RC3 checker verifies byte retention, tables against received JSON, bilingual structures/numbers and hashes of inspected PDFs. It reruns no historical scientific audit. Older checkers/reports remain dated; the RC2.2 checker is archived under `history/RC2.2/scripts/`.

## Compile or render in a copy

With LaTeX, latexmk, BibTeX and Poppler:

```bash
BUILD=/tmp/hgb-manuscript-rc3-reading-copy
test ! -e "$BUILD" || exit 1
cp -a . "$BUILD"
cd "$BUILD"
python scripts/compile_pdfs.py
python -B scripts/check_review_package.py --skip-manifest --allow-unsealed
```

Recompilation may change PDF bytes: the sealed visual report and earlier hashes do not cover a new compilation. `--allow-unsealed` is only for checks before new surface inspection.
Q2 rendering uses dependencies in `requirements-rc3-render.txt`, followed by:

```bash
python scripts/render_q2_assets.py --evidence-dir data/q2 --output-root .
```

This creates six table pairs and two figure pairs solely from received results, without fits/scores/CIs. Seed min–max spans are not confidence intervals.

## Historical scientific reproduction

C/D1 and paired-bootstrap commands remain documented in `history/RC2.2/README_EN.md` and S6/S11; `scripts/analyze_maude_paired_comparison.py`, `scripts/verify_rc1_replays.py` and retained inputs are not rerun in RC3.
The initial GraphSAGE30–neighbors calculation compared C candidates with prepared history and historical cardinalities/positives: complete historical candidate lists had not been exported. The nine C/D1 checkpoints support inference, not training resumption. The D1 audit RSS caveat remains without certification of a global ceiling.
Q2-run commands are documented in S14 and `scripts/q2/`; scientific execution requires external raw inputs and a fresh destination. A new forecast run would have a new origin; it does not replace sealed outputs. Delayed evaluation must use original scores without refits and meet source/attestation requirements.

## Pre-submission gates

See `submission/author_gates_RC3.md`. Identities, affiliations, corresponding author, CRediT, funding, competing interests, ethics/data-use, actual AI disclosure, manuscript license/venue, journal and official instructions require human decisions/approval. No negative statement, exemption or approval is inferred.
DOI `10.5281/zenodo.22796551` identifies **benchmark v0.2.0**, not RC3 or Q2 additions. No new DOI/tag/Zenodo/merge/submission is created. No specific journal is selected; inherited FAIA/IOS reading layouts do not establish final compliance, Q2 ranking or acceptance.
