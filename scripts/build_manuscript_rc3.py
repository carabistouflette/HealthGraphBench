#!/usr/bin/env python3
"""Assemble RC3 from attested RC2.2, then seal only after actual PDF review.

No experiment, score, bootstrap, source acquisition or historical audit runs.
All deliveries are exclusive creations. The original parent remains unchanged.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import sys
import zipfile

REPO = Path(__file__).resolve().parents[1]
OVERLAY = REPO / 'manuscript/rc3/overlay'
PARENT_SHA256 = 'a1731aa9eb02d8f31179adfea62d1d70a168594910aa2002780aa66e8f83c4f9'
TEMP_SUFFIXES = {'.aux', '.out', '.bbl', '.blg', '.fdb_latexmk', '.fls'}
PDF_OUTPUTS = {'main_fr.pdf': 'HealthGraphBench_RC3_manuscrit_FR.pdf',
               'main_en.pdf': 'HealthGraphBench_RC3_manuscript_EN.pdf',
               'supplement_fr.pdf': 'HealthGraphBench_RC3_supplement_FR.pdf',
               'supplement_en.pdf': 'HealthGraphBench_RC3_supplement_EN.pdf'}


def digest(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def run_check(root, name, *flags):
    checked = subprocess.run([sys.executable, str(root / 'scripts/check_review_package.py'), *flags],
                             cwd=root, capture_output=True, text=True)
    (root / 'verification/rc3' / (name + '.log')).write_text(checked.stdout + checked.stderr)
    report = json.loads(checked.stdout)
    write_json(root / 'verification/rc3' / name, report)
    if checked.returncode:
        print(checked.stdout + checked.stderr, file=sys.stderr)
        raise RuntimeError('RC3 package QA failed: ' + name)
    return report


def diagnostics(root):
    import re
    records = {}
    for path in root.glob('*.log'):
        text = path.read_bytes().decode('utf-8', errors='backslashreplace')
        records[path.stem] = {'LaTeX_warnings': len(re.findall(r'LaTeX Warning:', text)),
                              'overfull': len(re.findall(r'Overfull \\[hv]box', text)),
                              'underfull': len(re.findall(r'Underfull \\[hv]box', text)),
                              'undefined': len(re.findall(r'(?i)(?:reference|citation).*undefined|undefined references', text))}
        shutil.copyfile(path, root / 'verification/rc3' / path.name)
        path.unlink()
    for path in root.iterdir():
        if path.suffix in TEMP_SUFFIXES:
            path.unlink()
    return records


def assemble(args):
    root = args.output_dir.resolve()
    if root.exists():
        raise FileExistsError('RC3 assembly root must be new: ' + str(root))
    if root.name != 'HealthGraphBench_RC3':
        raise ValueError('Assembly root must be named HealthGraphBench_RC3')
    if digest(args.source_zip) != PARENT_SHA256:
        raise ValueError('Source is not the attested RC2.2 ZIP')
    pins = json.loads((REPO / 'manuscript/rc3/evidence_files.json').read_text())
    inputs = []
    for row in pins:
        relative = PurePosixPath(row['target'])
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Unsafe evidence destination: ' + row['target'])
        path = OVERLAY / row['target']
        if not path.is_file():
            path = args.evidence_root / row['source']
        if not path.is_file() or digest(path) != row['sha256']:
            raise ValueError('Missing or changed compact evidence: ' + str(path))
        inputs.append((path, row['target']))
    root.mkdir(parents=True)
    retention = []
    with zipfile.ZipFile(args.source_zip) as source:
        for info in source.infolist():
            if info.is_dir():
                continue
            name = PurePosixPath(info.filename)
            if name.is_absolute() or '..' in name.parts or '\\' in info.filename or name.parts[0] != 'HealthGraphBench_RC2_2' or stat.S_ISLNK(info.external_attr >> 16):
                raise ValueError('Unsafe or unexpected parent member: ' + info.filename)
            relative = Path(*name.parts[1:])
            replaced = (OVERLAY / relative).exists() or relative == Path('SHA256SUMS') or (relative.suffix == '.pdf' and len(relative.parts) == 1)
            retained = Path('history/RC2.2') / relative if replaced else relative
            target = root / retained
            if target.exists():
                raise FileExistsError('Parent archive has colliding retained paths: ' + str(target))
            target.parent.mkdir(parents=True, exist_ok=True)
            payload = source.read(info)
            target.write_bytes(payload)
            retention.append({'original_path': str(relative), 'retained_path': str(retained),
                              'sha256': hashlib.sha256(payload).hexdigest(), 'bytes': len(payload),
                              'scope': 'Byte retention only, not historical scientific audit rerun'})
    shutil.copytree(OVERLAY, root, dirs_exist_ok=True)
    for source, name in inputs:
        target = root / name
        if source.resolve() != target.resolve():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    # Deliver the exact assembler sources as documentary evidence; rebuild from
    # the tracked repository, not by guessing repository paths inside the ZIP.
    shutil.copyfile(Path(__file__), root / 'scripts/build_manuscript_rc3.py')
    shutil.copyfile(REPO / 'manuscript/rc3/evidence_files.json', root / 'release/evidence_files_RC3.json')
    write_json(root / 'release/parent_payload_RC2_2.json', {'parent_archive_sha256': PARENT_SHA256, 'files': retention})
    evidence = root / 'verification/rc3'
    evidence.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, str(root / 'scripts/compile_pdfs.py')]
    compiled = subprocess.run(command, cwd=root, capture_output=True)
    (evidence / 'compilation.log').write_bytes(compiled.stdout + compiled.stderr)
    if compiled.returncode:
        print((compiled.stdout + compiled.stderr).decode('utf-8', errors='backslashreplace'), file=sys.stderr)
        raise RuntimeError('RC3 PDF compilation failed')
    logs = diagnostics(root)
    write_json(evidence / 'compilation_diagnostics.json', logs)
    for directory in root.rglob('__pycache__'):
        shutil.rmtree(directory)
    for name in ('provenance.json', 'data/revision_status_RC3.json'):
        state = json.loads((root / name).read_text())
        state['current_operations']['pdfs_recompiled'] = True
        write_json(root / name, state)
    report = run_check(root, 'assembly_QA.json', '--skip-manifest', '--allow-unsealed')
    write_json(evidence / 'assembly.json', {'parent_archive': str(args.source_zip.resolve()), 'parent_sha256': PARENT_SHA256,
               'parent_unchanged': digest(args.source_zip) == PARENT_SHA256, 'compiled_documents': list(logs),
               'package_checks': len(report['checks']), 'sealed': False})
    print(json.dumps({'root': str(root), 'compiled_documents': list(logs), 'assembly_passed': report['passed'],
                      'next': 'Review actual PDF pages, then seal with the matching surface-review report'}, indent=2))


def seal(args):
    root = args.root.resolve()
    archive_path = args.archive_path.resolve()
    if not root.is_dir() or root.name != 'HealthGraphBench_RC3':
        raise ValueError('Use the completed HealthGraphBench_RC3 assembly')
    if archive_path.exists() or archive_path.with_suffix(archive_path.suffix + '.sha256').exists():
        raise FileExistsError('Archive and checksum paths must be new')
    standalone_paths = [args.pdf_output_dir / name for name in PDF_OUTPUTS.values()]
    if any(path.exists() for path in standalone_paths):
        raise FileExistsError('Standalone RC3 PDF paths must all be new')
    assembly = json.loads((root / 'verification/rc3/assembly.json').read_text())
    if assembly['sealed']:
        raise ValueError('Assembly is already sealed; do not mutate a delivery')
    parent = Path(assembly['parent_archive'])
    if digest(parent) != PARENT_SHA256:
        raise ValueError('Original RC2.2 parent changed since assembly')
    review = json.loads(args.surface_report.read_text())
    for name in PDF_OUTPUTS:
        row = review['documents'][name]
        if row['sha256'] != digest(root / name) or not row['visual_review_completed'] or not row['reviewed_pages']:
            raise ValueError('Missing or stale actual surface review: ' + name)
        if row['blank_pages'] or row['unresolved_references']:
            raise ValueError('Unresolved PDF surface defect: ' + name)
    diagnostics_report = json.loads((root / 'verification/rc3/compilation_diagnostics.json').read_text())
    if any(row['overfull'] or row['undefined'] for row in diagnostics_report.values()):
        raise ValueError('Resolve overfull boxes and undefined references before sealing')
    write_json(root / 'verification/rc3/surface_review.json', review)
    for name in ('provenance.json', 'data/revision_status_RC3.json'):
        state = json.loads((root / name).read_text())
        state['current_operations']['surfaces_visually_inspected'] = True
        state['current_operations']['package_checks_executed'] = True
        write_json(root / name, state)
    release = json.loads((root / 'release.json').read_text())
    release['readiness']['technical_verification_complete'] = True
    release['readiness']['ready_for_review'] = True
    write_json(root / 'release.json', release)
    for directory in root.rglob('__pycache__'):
        shutil.rmtree(directory)
    report = run_check(root, 'package_QA_without_manifest.json', '--skip-manifest')
    # Running the checker imports the table renderer: its cache is not payload.
    for directory in root.rglob('__pycache__'):
        shutil.rmtree(directory)
    assembly['sealed'] = True
    write_json(root / 'verification/rc3/assembly.json', assembly)
    files = sorted(path for path in root.rglob('*') if path.is_file() and path != root / 'SHA256SUMS')
    (root / 'SHA256SUMS').write_text(''.join(f'{digest(path)}  {path.relative_to(root)}\n' for path in files))
    # Suppress bytecode so final verification cannot change the sealed payload.
    checked = subprocess.run([sys.executable, '-B', str(root / 'scripts/check_review_package.py')], cwd=root, capture_output=True, text=True)
    if checked.returncode:
        print(checked.stdout + checked.stderr, file=sys.stderr)
        raise RuntimeError('Final RC3 manifest QA failed')
    final_report = json.loads(checked.stdout)
    write_json(root.parent / 'RC3_delivery_check.json', final_report)
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(root.rglob('*')):
            if path.is_file():
                archive.write(path, root.name + '/' + str(path.relative_to(root)))
    archive_hash = digest(archive_path)
    archive_path.with_suffix(archive_path.suffix + '.sha256').write_text(archive_hash + '  ' + archive_path.name + '\n')
    args.pdf_output_dir.mkdir(parents=True, exist_ok=True)
    outputs = []
    for source, name in PDF_OUTPUTS.items():
        target = args.pdf_output_dir / name
        with target.open('xb') as destination, (root / source).open('rb') as pdf:
            shutil.copyfileobj(pdf, destination)
        outputs.append({'path': str(target.resolve()), 'sha256': digest(target)})
    delivery = {'revision': 'RC3', 'archive': {'path': str(archive_path), 'sha256': archive_hash},
                'standalone_pdfs': outputs, 'root': str(root), 'checks': len(final_report['checks']),
                'package_passed': final_report['passed'], 'surface_report': str(root / 'verification/rc3/surface_review.json'),
                'parent_RC2_2_unchanged': digest(parent) == PARENT_SHA256,
                'scientific_gates': release['scientific_gates'], 'submission_performed': False}
    write_json(root.parent / 'RC3_delivery_manifest.json', delivery)
    print(json.dumps(delivery, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    build = commands.add_parser('assemble', help='Create a new RC3 source tree, compile and run manuscript QA')
    build.add_argument('--source-zip', type=Path, required=True)
    build.add_argument('--output-dir', type=Path, required=True)
    build.add_argument('--evidence-root', type=Path, default=REPO)
    publish = commands.add_parser('seal', help='Seal after reviewing actual compiled PDF surfaces')
    publish.add_argument('--root', type=Path, required=True)
    publish.add_argument('--surface-report', type=Path, required=True)
    publish.add_argument('--archive-path', type=Path, required=True)
    publish.add_argument('--pdf-output-dir', type=Path, required=True)
    args = parser.parse_args()
    try:
        (assemble if args.command == 'assemble' else seal)(args)
    except (OSError, ValueError, RuntimeError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
