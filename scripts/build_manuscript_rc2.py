#!/usr/bin/env python3
"""Assemble, compile and package RC2 from immutable RC1 and the tracked overlay.

Needs the supplied RC1 ZIP and local checkpoint evidence listed in external_files.json.
No scientific experiment or audit is executed. Existing output/archive paths are rejected.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

REPO = Path(__file__).resolve().parents[1]
OVERLAY = REPO / 'manuscript/rc2/overlay'
SOURCE_SHA256 = '2d066cfbbe1c50ed1f0dc021799d3bac631a70c428cf79d5d78b68af44e6b7be'
TEMP_SUFFIXES = {'.aux', '.out', '.bbl', '.blg', '.fdb_latexmk', '.fls'}


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-zip', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True, help='New root named by overlay/release.json archive_root')
    parser.add_argument('--archive-path', type=Path, required=True, help='New ZIP path')
    parser.add_argument('--evidence-root', type=Path, default=REPO)
    args = parser.parse_args()
    root = args.output_dir.resolve()
    archive_path = args.archive_path.resolve()
    if root.exists() or archive_path.exists():
        parser.error('Output directory and archive must both be new; immutable deliveries are never overwritten.')
    expected_root = json.loads((OVERLAY / 'release.json').read_text())['archive_root']
    if root.name != expected_root:
        parser.error('Output root must be named ' + expected_root + '.')
    if digest(args.source_zip) != SOURCE_SHA256:
        parser.error('Source is not the supplied, attested RC1 archive.')
    external = json.loads((REPO / 'manuscript/rc2/external_files.json').read_text())
    for row in external:
        path = args.evidence_root / row['source']
        if not path.is_file() or digest(path) != row['sha256']:
            parser.error('Missing or changed checkpoint evidence: ' + str(path))
    root.mkdir(parents=True)
    with zipfile.ZipFile(args.source_zip) as source:
        for info in source.infolist():
            if info.is_dir():
                continue
            name = Path(info.filename)
            if name.is_absolute() or '..' in name.parts or name.parts[0] != 'HealthGraphBench_RC1':
                raise ValueError('Unsafe or unexpected RC1 member: ' + info.filename)
            relative = Path(*name.parts[1:])
            # Never pass inherited RC1 PDFs off as regenerated RC2 PDFs.
            if relative.suffix == '.pdf' and len(relative.parts) == 1:
                continue
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read(info))
    shutil.copytree(OVERLAY, root, dirs_exist_ok=True)
    for row in external:
        target = root / row['target']
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(args.evidence_root / row['source'], target)
    evidence = root / 'verification/rc2'
    evidence.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, str(root / 'scripts/compile_pdfs.py')]
    # pdfLaTeX/latexmk console output may mix UTF-8 with TeX's single-byte accents.
    # Preserve the original log bytes instead of guessing a decoding.
    compiled = subprocess.run(command, cwd=root, capture_output=True)
    (evidence / 'compilation.log').write_bytes(compiled.stdout + compiled.stderr)
    if compiled.returncode:
        print((compiled.stdout + compiled.stderr).decode('utf-8', errors='backslashreplace'), file=sys.stderr)
        return compiled.returncode
    for path in list(root.iterdir()):
        if path.suffix == '.log':
            shutil.copyfile(path, evidence / path.name)
            path.unlink()
        elif path.suffix in TEMP_SUFFIXES:
            path.unlink()
    for directory in root.rglob('__pycache__'):
        shutil.rmtree(directory)
    for name in ('provenance.json', 'data/revision_status_RC2.json'):
        path = root / name
        state = json.loads(path.read_text())
        state['current_operations']['pdfs_recompiled'] = True
        state['current_operations']['package_checks_executed'] = True
        path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n')
    release_path = root / 'release.json'
    release = json.loads(release_path.read_text())
    release['readiness']['technical_verification_complete'] = True
    release_path.write_text(json.dumps(release, ensure_ascii=False, indent=2) + '\n')
    # Report without the integrity manifest is included; final manifest verification is external,
    # avoiding a self-referential report -> checksum -> report cycle.
    check_command = [sys.executable, str(root / 'scripts/check_review_package.py')]
    checked = subprocess.run(check_command + ['--skip-manifest'], capture_output=True, text=True)
    (evidence / 'package_check_without_manifest.json').write_text(checked.stdout)
    if checked.returncode:
        print(checked.stdout + checked.stderr, file=sys.stderr)
        return checked.returncode
    files = sorted(path for path in root.rglob('*') if path.is_file() and path != root / 'SHA256SUMS')
    (root / 'SHA256SUMS').write_text(''.join(f'{digest(path)}  {path.relative_to(root)}\n' for path in files))
    checked = subprocess.run(check_command, capture_output=True, text=True)
    report_path = root.parent / 'RC2_delivery_check.json'
    report_path.write_text(checked.stdout)
    if checked.returncode:
        print(checked.stdout + checked.stderr, file=sys.stderr)
        return checked.returncode
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(root.rglob('*')):
            if path.is_file():
                archive.write(path, root.name + '/' + str(path.relative_to(root)))
    checksum = digest(archive_path)
    archive_path.with_suffix(archive_path.suffix + '.sha256').write_text(checksum + '  ' + archive_path.name + '\n')
    print(json.dumps({'archive': str(archive_path), 'sha256': checksum,
                      'root': str(root), 'check_report': str(report_path),
                      'rc1_unchanged': digest(args.source_zip) == SOURCE_SHA256}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
