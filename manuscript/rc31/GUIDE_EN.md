# RC3.1 — distinct assembly, actual evidence and sealing

RC3.1 is a manuscript revision for targeted exploratory experiments on previously consulted 2023–2025 periods. The question is incremental relational information beyond individual history and popularity, and the complexity needed to exploit it—not another general winner league. This guide announces no result and closes no scientific or editorial gate.

French supplied by the analysis owner is canonical; English is its faithful translation. Author approval, declarations, licences and venue compliance remain unknown. Independent temporal evaluation and external human reproduction are not completed. DOI `10.5281/zenodo.22796551` remains the DOI of benchmark **v0.2.0**, not RC3.1. These tools perform no submission, Zenodo publication, merge or tag.

## Retention and dependencies

The only consumed parent is the RC3 ZIP with SHA-256 `6cc3005a46ac2c906daf42a7c27781dfae8953b5eaa78c874e41b622014dd402`. Every parent file is retained byte-for-byte under `history/RC3/`, including historical results and interval origins. RC3 and RC2.2 are never changed. Parent checks concern byte consumption/retention only, not reruns of historical scientific audits.

The new main manuscript includes historical MAUDE/CMS/Part D tables and the complete historical interval table, with original RC3 captions/origins, in its historical-context section. The supplement reuses C/D1/Q2 tables without recomputation. Task definitions, cohort filters and dataset limitations must be explained in the supplied scientific text; complete historical sources remain accessible, without silently dropping numerical context.

Python 3.11 or newer; Matplotlib 3.7 or newer for figures only. Compilation reuses the parent's `scripts/compile_pdfs.py`, adapted to the four RC3.1 documents, and requires latexmk, BibTeX and the parent's LaTeX packages. Sealing requires `pdfinfo` (Poppler) to compare the actual page count with the visual report. No tool fits, scores or recomputes an interval.

## Actual scientific inputs

`--run-root` identifies the actual completed directory from `healthgraphbench.rc31.run`, for example `results/generated/rc31-cycle-20261004/experiment-001`. Required root files are:

- `partd_experiments.json`, `maude_experiments.json`, `cms_experiments.json`;
- `analysis.json`, `cycle.json` with `status=completed_exploratory`;
- `protocol_executed.json`, `source_provenance.json`, `resource_ledger.json`.

Rendering rejects missing data, an absent required method/year/seed, inconsistent inputs or an incomplete cycle. There are no fallback values or synthetic results. Actual null values for undefined denominators/contrasts appear as dashes without imputation. Training-seed min–max ranges are descriptive and separate from paired intervals conditional on fixed fits; intervals cover neither configuration selection nor independence of periods/networks. The 0.01 margin is not a clinical threshold. CMS remains conditional on an inspection. Observed links and proposal workload do not establish clinical correctness.

The renderer writes FR then EN tables, recall/precision workload curves over K and contrasts across predefined strata. `numeric_records.json` and `plot_records.json` contain all consumed numbers/points. `asset_manifest.json` pins all eight inputs, the renderer, consumed scientific sources and every asset. Numeric records retain resources, configurations, learning diagnostics and state sizes; a time/parameter/gate table reports available fields only.

## Text supplied by the analysis owner

The exact machine schema is `manuscript/rc31/narrative.schema.json` in the repository and `release/narrative.schema.json` in the package. Extra fields are not accepted at root, in `fr`/`en`, or in section objects; the assembler also verifies bilingual ordering and the hash bindings described below.

`--narrative-json` is actual JSON written **after** completed analysis, not a demonstration file. It contains:

- `canonical_language`: `fr`; `english_role`: `faithful_translation`;
- `analysis_sha256`: SHA-256 of actual `analysis.json` bytes;
- `translation_of_fr_sha256`: UTF-8 SHA-256 of `json.dumps(value['fr'], ensure_ascii=False, sort_keys=True, separators=(',', ':'))`;
- `fr` and `en`, each with `title`, `abstract`, `sections`, `supplement`.

Each section list contains objects with `id`, `heading` and **exactly one** of `paragraphs` (a nonempty list of text paragraphs, escaped for LaTeX) or `latex` (nonempty actual LaTeX content, including equations/citations as needed). Titles and abstracts are plain text. Section identifiers/order must match between French and English, without duplicates. Required main-section identifiers are `question`, `data`, `methods`, `historical_context`, `results`, `interpretation`, `limits`; additional sections are allowed. The supplement also requires actual scientific text. Structural checks and hash bindings do not certify scientific/translation fidelity; actual content review remains necessary.

Historical tables are inserted after the `historical_context` text. RC3.1 tables are automatically included: do not duplicate or invent them in the supplied prose. Templates add technical version/gate statements and scope warnings. All scientific prose, task definitions, cohorts, historical availability, conclusions and result interpretation belong to the supplied text. The parent's `references.bib` supports LaTeX citations. Unresolved references/citations prevent sealing.

## Full-output and input registry

`--evidence-registry` must be actual JSON with `scope=external_full_outputs_and_inputs`, and nonempty `full_outputs` and `inputs` lists. Every entry has `role`, `path`, `bytes`, `sha256`. Existing files are checked at assembly and paths retained as absolute paths. Raw files/TAR archives are not copied into the manuscript ZIP.

Exactly one `full_outputs` entry has `role=rc31_run` and `run_prefix`: the actual run directory prefix in the TAR, or an empty string when its files are at archive root. TAR, TAR.GZ/TGZ, TAR.XZ and TAR.BZ2 are supported. The assembler checks exact hashes of all eight root JSON members in this TAR and writes `consumed_run_members_sha256`. This consumption check neither opens checkpoints for a new scientific audit nor reruns science. Other entries may pin historical scientific archives actually reused. `inputs` pins genuinely necessary prepared/raw files; additional registry fields describe provenance/scope. These paths may be unavailable elsewhere: this is deliberately a **compact-evidence package with pinned external paths**, not a self-contained raw-data training archive.

`--source-root` must expose scientific sources **actually consumed**, at paths and hashes in `source_provenance.json`. A matching current tree or exact snapshots are acceptable; no global HEAD check, new-paper-tool check or user-document check is imposed. Consumed source snapshots are delivered. Every ledger phase requires `result.json`, `worker_status.json` and `supervisor_status.json`, copied as compact evidence.

The `inputs` entry with role `partd_historical_bpr_selection` is required and unique. Its 2,429 bytes of actually consumed selection metadata are copied unchanged to `data/reused_inputs/partd_selection.json`, with hash and ZIP member recorded in the delivered registry. This small JSON closes the input absent from the companion TAR; it neither retrains BPR nor retroactively adds a forecast comparator. To replay the protocol, restore this copy at the historical path specified by the registry, together with other TAR inputs and a clone of the pinned sources. The manuscript ZIP alone remains non-autonomous for all raw data or fits.

## Complete commands — run only with actual inputs

```bash
python -B manuscript/rc31/render_assets.py \
  --run-root results/generated/rc31-cycle-20261004/experiment-001 \
  --output-assets /tmp/hgb-rc31-assets

python -B scripts/build_manuscript_rc31.py assemble \
  --source-zip "$HOME/Downloads/HealthGraphBench_LaTeX_RC3.zip" \
  --output-dir /tmp/hgb-rc31/HealthGraphBench_RC3_1 \
  --run-root results/generated/rc31-cycle-20261004/experiment-001 \
  --assets-dir /tmp/hgb-rc31-assets \
  --narrative-json /actual/path/narrative_rc31.json \
  --evidence-registry /actual/path/evidence_registry_rc31.json \
  --source-root /actual/consumed-source-tree

python -B scripts/build_manuscript_rc31.py compile \
  --root /tmp/hgb-rc31/HealthGraphBench_RC3_1 --timeout 120

python -B manuscript/rc31/check_package.py \
  --root /tmp/hgb-rc31/HealthGraphBench_RC3_1
```

The assets directory and assembly root must be new. `assemble` does not compile. `compile` records source/figure/PDF/log hashes and rejects overfull boxes or unresolved references/citations. LaTeX corrections before delivery require new compilation and new inspection of all four PDFs, never merely repinning an old report. Packaged `scripts/` also supports `compile`, `seal` and QA with `python -B`.

## Actual visual review and sealing

`--surface-report` is JSON with `revision=RC3.1`, `reviewer`, `reviewed_at_utc`, and `documents` containing the four keys `main_fr.pdf`, `main_en.pdf`, `supplement_fr.pdf`, `supplement_en.pdf`. Each object supplies the actual PDF `sha256`, `visual_review_completed=true`, actual `page_count`, `reviewed_pages` as every page in ascending order from 1 to `page_count`, and empty lists `blank_pages`, `unresolved_references`, `overfull_boxes` after correction. Every page must actually be inspected; writing the JSON alone is not a review.

```bash
python -B scripts/build_manuscript_rc31.py seal \
  --root /tmp/hgb-rc31/HealthGraphBench_RC3_1 \
  --surface-report /actual/path/surface_review_rc31.json \
  --archive-path "$HOME/Downloads/HealthGraphBench_LaTeX_RC3_1.zip" \
  --pdf-output-dir "$HOME/Downloads"

python -B manuscript/rc31/check_package.py \
  --root /tmp/hgb-rc31/HealthGraphBench_RC3_1 --sealed
```

Sealing checks actual hashes/page counts, current diagnostics, JSON-derived assets and the full manifest. Missing/stale reviews and unresolved references/overfull boxes are rejected. ZIP, checksum, four PDF and delivery-manifest destinations must be new and outside the sealed root. ZIP members have exclusively the `HealthGraphBench_RC3_1/` root. Outputs:

- `HealthGraphBench_LaTeX_RC3_1.zip` and `.zip.sha256`;
- `HealthGraphBench_RC3_1_manuscrit_FR.pdf`;
- `HealthGraphBench_RC3_1_manuscript_EN.pdf`;
- `HealthGraphBench_RC3_1_supplement_FR.pdf`;
- `HealthGraphBench_RC3_1_supplement_EN.pdf`;
- `RC3_1_delivery_manifest.json` beside the assembly root.

RC3.1 QA verifies current numeric derivations, plot points/assets, consumed sources, gates/limits, the ledger and parent retention; sealed QA adds all four reviews and integrity. It runs no old scientific audit or historic-prose repinning test. Technical readiness for review is not independent scientific, human, author or venue approval.
