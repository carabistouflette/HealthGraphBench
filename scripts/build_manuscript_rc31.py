#!/usr/bin/env python3
"""Distinct RC3.1 assemble/compile/seal; consume RC3 bytes, never rerun its science."""
import argparse
import hashlib
import json
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path, PurePosixPath

REPO = Path(__file__).resolve().parents[1]
SOURCES = REPO / 'manuscript/rc31' if (REPO / 'manuscript/rc31').is_dir() else Path(__file__).resolve().parent
sys.path.insert(0, str(SOURCES))
from render_assets import INPUTS, LIMITS, DOI, digest, dump, load, tex
from check_package import DOCUMENTS, check, check_assets, relative, require

PARENT_SHA256 = '6cc3005a46ac2c906daf42a7c27781dfae8953b5eaa78c874e41b622014dd402'
PDF_OUTPUTS = {'main_fr.pdf': 'HealthGraphBench_RC3_1_manuscrit_FR.pdf',
               'main_en.pdf': 'HealthGraphBench_RC3_1_manuscript_EN.pdf',
               'supplement_fr.pdf': 'HealthGraphBench_RC3_1_supplement_FR.pdf',
               'supplement_en.pdf': 'HealthGraphBench_RC3_1_supplement_EN.pdf'}


def new_root(path):
    root = Path(path).resolve()
    require(root.name == 'HealthGraphBench_RC3_1', 'Exclusive root must be HealthGraphBench_RC3_1')
    return root


def validate_narrative(value):
    require(isinstance(value, dict) and set(value) == {'canonical_language', 'english_role', 'analysis_sha256', 'translation_of_fr_sha256', 'fr', 'en'}, 'Narrative must match narrative.schema.json root fields')
    require(value['canonical_language'] == 'fr' and value['english_role'] == 'faithful_translation', 'Canonical French then faithful English required')
    require(value['analysis_sha256'] and value['translation_of_fr_sha256'], 'Narrative must pin the actual analysis and canonical French')
    canonical = hashlib.sha256(json.dumps(value['fr'], ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    require(value['translation_of_fr_sha256'] == canonical, 'English translation does not identify the canonical French payload')
    for lang in ('fr', 'en'):
        text = value[lang]
        require(isinstance(text, dict) and set(text) == {'title', 'abstract', 'sections', 'supplement'}, 'Language narrative must match exact schema fields')
        require(isinstance(text['title'], str) and text['title'].strip() and isinstance(text['abstract'], str) and text['abstract'].strip(), 'Empty supplied title/abstract')
        for collection in ('sections', 'supplement'):
            require(isinstance(text[collection], list) and text[collection], 'Supplied manuscript section lists required')
            for section in text[collection]:
                require(isinstance(section, dict) and {'id', 'heading'} <= set(section) <= {'id', 'heading', 'latex', 'paragraphs'}, 'Section must match exact schema fields')
                require(isinstance(section['id'], str) and section['id'] and isinstance(section['heading'], str) and section['heading'].strip(), 'Missing supplied section identity/heading')
                require(('latex' in section) != ('paragraphs' in section), 'Supply exactly latex or paragraphs for each section')
                if 'latex' in section:
                    require(isinstance(section['latex'], str) and section['latex'].strip(), 'Empty actual narrative section')
                else:
                    require(isinstance(section['paragraphs'], list) and section['paragraphs'] and all(isinstance(p, str) and p.strip() for p in section['paragraphs']), 'Empty actual narrative paragraphs')
        require({'question', 'data', 'methods', 'historical_context', 'results', 'interpretation', 'limits'} <= {section['id'] for section in text['sections']}, 'Narrative must supply question/data/methods/historical_context/results/interpretation/limits')
    for collection in ('sections', 'supplement'):
        a = [section['id'] for section in value['fr'][collection]]
        b = [section['id'] for section in value['en'][collection]]
        require(a == b and len(a) == len(set(a)), 'Faithful English must retain unique canonical section ordering')


def narrative_sections(sections, lang):
    result = []
    for section in sections:
        result.append('\\section{' + tex(section['heading']) + '}\n')
        result.append(section['latex'] if 'latex' in section else '\n\n'.join(tex(p) for p in section['paragraphs']))
        result.append('\n\n')
        if section['id'] == 'historical_context':
            result.append('\\input{sections/historical_context_' + lang + '}\n\n')
    return ''.join(result)


def historical_assets(root, lang):
    """Retain original numerical tables/captions, not a new historical audit."""
    source = root / 'history/RC3/sections' / ('body_' + lang + '.tex')
    text = source.read_text(encoding='utf-8')
    blocks = []
    for label in ('tab:maude', 'tab:cms', 'tab:partd', 'tab:ci'):
        marker = '\\label{' + label + '}'
        require(text.count(marker) == 1, 'Historical source table identity ambiguous: ' + label)
        index = text.index(marker)
        start = text.rfind('\\begin{table}', 0, index)
        finish = text.find('\\end{table}', index)
        require(start >= 0 and finish >= 0, 'Historical table source block missing')
        block = text[start:finish + len('\\end{table}')]
        blocks.append(block.replace('\\input{tables/', '\\input{history/RC3/tables/'))
    directory = root / 'sections'
    directory.mkdir(exist_ok=True)
    (directory / ('historical_context_' + lang + '.tex')).write_text('\n\n'.join(blocks) + '\n', encoding='utf-8')
    fr = lang == 'fr'
    context = '\\section{' + ('Contexte numérique historique C/D1/Q2 conservé' if fr else 'Retained historical C/D1/Q2 numerical context') + '}\n'
    context += tex('Ces tables sont reprises sans recalcul de RC3. Les configurations, périodes et origines des IC restent celles des analyses historiques, pas des expériences RC3.1. Les plages Q2 sont des plages de graines, pas des IC ; D1 n’a pas d’IC. Les méthodes, filtres de cohorte, dénominateurs et limites d’origine figurent dans les sources et suppléments complets history/RC3.' if fr else
                   'These tables are reproduced without recomputation from RC3. Configurations, periods and CI origins remain those of historical analyses, not RC3.1 experiments. Q2 ranges are seed ranges, not CIs; D1 has no CI. Original methods, cohort filters, denominators and limitations are retained in the complete sources and supplements under history/RC3.') + '\n\n'
    names = ('maude_duration_RC2', 'maude_aggregation_RC2', 'maude_paired_RC2', 'q2_partd', 'q2_maude', 'q2_cms', 'q2_seed_sensitivity')
    for name in names:
        historical = root / 'history/RC3/tables' / (name + '_' + lang + '.tex')
        require(historical.is_file(), 'Historical numeric context missing: ' + name)
        context += '\\subsection{' + tex(name.replace('_', ' ')) + '}\n'
        context += '\\begin{center}\\footnotesize\\input{history/RC3/tables/' + name + '_' + lang + '.tex}\\end{center}\n'
    context += tex('L’IC C GraphSAGE30–voisins est apparié par produit, conditionnel aux prédictions C sélectionnées : 1 000 tirages, graine 20261003 ; il ne concerne ni GraphSAGE historique à trois époques ni RC3.1. Les IC historiques publiés et complémentaires gardent leurs origines distinctes dans le tableau historique du manuscrit et dans le supplément RC3 conservé.' if fr else
                   'The C GraphSAGE30–neighbors CI is product-paired, conditional on selected C predictions: 1,000 draws, seed 20261003; it concerns neither historical three-epoch GraphSAGE nor RC3.1. Published and complementary historical CIs retain their distinct origins in the manuscript historical table and retained RC3 supplement.') + '\n'
    (directory / ('historical_supplement_' + lang + '.tex')).write_text(context, encoding='utf-8')


def document(narrative, lang, supplement, plot_manifest):
    fr = lang == 'fr'
    state = ('RC3.1 — expériences ciblées exploratoires ; validation des auteurs inconnue' if fr else
             'RC3.1 — targeted exploratory experiments; author approval unknown')
    gates = ('Évaluation temporelle indépendante et reproduction humaine externe non réalisées. Approbations des auteurs, déclarations, licences et conformité à la revue inconnues. Aucune soumission. '
             'Le DOI 10.5281/zenodo.22796551 désigne uniquement le benchmark v0.2.0.' if fr else
             'Independent temporal evaluation and external human reproduction not completed. Author approvals, declarations, licences and venue compliance unknown. No submission. '
             'DOI 10.5281/zenodo.22796551 identifies benchmark v0.2.0 only.')
    limitations = ('Les plages min–max des graines sont descriptives, séparées des intervalles conditionnels appariés par fournisseur, produit ou établissement. '
                   'Ces intervalles sont conditionnels aux ajustements sélectionnés ; ils ne couvrent ni sélection, ni indépendance des périodes ou réseaux. '
                   'La marge absolue 0,01 est un repère analytique, pas un seuil d’utilité clinique. CMS reste conditionnel à une inspection. '
                   'Les liens publiés observés et propositions à examiner ne certifient pas la justesse clinique ; leur absence ne constitue pas une erreur clinique.' if fr else
                   'Training-seed min–max ranges are descriptive and separate from paired conditional provider, product or facility intervals. '
                   'Intervals condition on selected fits; they cover neither selection nor independence of periods or networks. '
                   'The absolute 0.01 margin is an analytic yardstick, not a clinical utility threshold. CMS remains conditional on an inspection. '
                   'Observed published links and proposals to review do not establish clinical correctness; absent links are not clinical errors.')
    title = narrative['title'] + (' — Supplément scientifique' if fr else ' — Scientific supplement') if supplement else narrative['title']
    result = (r'\documentclass[10pt,a4paper]{article}' + '\n' + r'\input{metadata_' + lang + '}\n'
              + r'\usepackage{hgb_preview}' + '\n' + r'\usepackage[' + ('french' if fr else 'english') + ']{babel}\n'
              + r'\begin{document}' + '\n' + r'\begin{center}{\small ' + tex(state) + r'\par}\vspace{8pt}' + '\n'
              + r'{\LARGE\bfseries ' + tex(title) + r'\par}\end{center}' + '\n'
              + tex(gates) + '\n\n')
    if not supplement:
        result += r'\begin{abstract}' + '\n' + tex(narrative['abstract']) + '\n' + r'\end{abstract}' + '\n'
    for section in narrative['supplement' if supplement else 'sections']:
        result += narrative_sections([section], lang)
        if not supplement and section['id'] == 'results':
            for name in ('partd', 'maude', 'cms', 'contrasts'):
                result += '\\subsection{' + tex(name.upper()) + '}\\label{sec:rc31-' + name + '}\n\\input{assets/rc31/tables/' + name + '_' + lang + '.tex}\n'
            for spec in plot_manifest:
                if spec['kind'] != 'strata' or spec['domain'] != 'partd' or spec['year'] != '2024' or spec['method'] != 'cosine_minus_bpr_reuse':
                    continue
                caption = ('Cosinus moins BPR réutilisé, rappel micro à dix propositions, Part D 2024. Les familles de strates se chevauchent et ne doivent pas être additionnées. Soutien voisin selon le cosinus top50 historique fixe. Intervalles bootstrap appariés conditionnels aux fits/configurations, pas à leur sélection ni à une utilité clinique.' if fr else
                           'Cosine minus reused BPR, micro recall at ten proposals, Part D 2024. Stratum families overlap and must not be added together. Neighbor support uses the fixed historical cosine top50. Paired bootstrap intervals condition on fits/configurations, not their selection or clinical utility.')
                result += (r'\begin{figure}[!htbp]\centering' + '\n' + r'\includegraphics[width=\linewidth]{assets/rc31/figures/'
                           + spec['name'] + '_' + lang + '.pdf}\n' + r'\caption{' + tex(caption) + '}\n'
                           + r'\label{fig:rc31-partd-conditional}\end{figure}' + '\n')
    result += '\\section{' + ('Périmètre des preuves' if fr else 'Evidence scope') + '}\n' + tex(limitations) + '\n\n'
    result += tex('Tous les résultats historiques RC3, tables et origines des IC sont conservés sans changement sous history/RC3 ; aucune nouvelle vérification scientifique historique.' if fr else
                  'All historical RC3 results, tables and interval origins are retained unchanged under history/RC3; no historic scientific audit is rerun.') + '\n\n'
    result += tex('La question est l’information relationnelle incrémentale par rapport à l’historique individuel et à la popularité, non un nouveau classement de vainqueurs.' if fr else
                  'The question is incremental relational information beyond individual history and popularity, not another winner league.') + '\n\n'
    if supplement:
        for name in ('population', 'selection', 'strata', 'workload', 'resources'):
            result += '\\subsection{' + tex(name.upper()) + '}\\label{sec:rc31-' + name + '}\n\\input{assets/rc31/tables/' + name + '_' + lang + '.tex}\n'
        result += '\\input{sections/historical_supplement_' + lang + '}\n'
        result += '\\section{' + ('Charge de revue et strates prédéfinies' if fr else 'Review workload and predefined strata') + '}\n'
        for spec in plot_manifest:
            result += (r'\begin{figure}[!htbp]\centering' + '\n' + r'\includegraphics[width=\linewidth,height=.72\textheight,keepaspectratio]{assets/rc31/figures/'
                       + spec['name'] + '_' + lang + '.pdf}\n' + r'\caption{' + tex(spec['domain'].upper() + ' ' + spec['year'] + ' / ' + spec['metric']) + '}\n'
                       + r'\end{figure}' + '\n' + r'\clearpage' + '\n')
        result += '\\section{' + ('Traçabilité et disponibilité' if fr else 'Traceability and availability') + '}\n'
        result += tex('Les JSON compacts consommés, le protocole exécuté, les empreintes des sources et le registre de ressources sont dans data/rc31. Les sorties scientifiques complètes TAR et les entrées sont référencées par chemins, tailles et SHA-256 dans release/evidence_registry.json. Ce paquet ne redistribue pas toutes les données brutes et ne constitue pas une archive d’entraînement autonome.' if fr else
                      'Consumed compact JSON, executed protocol, source hashes and the resource ledger are in data/rc31. Full scientific TAR outputs and inputs are pinned by paths, byte counts and SHA-256 in release/evidence_registry.json. This package does not redistribute all raw data and is not a self-contained training archive.') + '\n'
    result += r'\nocite{hgbcode,hgbresults}\bibliographystyle{unsrtnat}\bibliography{references}' + '\n' + r'\end{document}' + '\n'
    return result


def verify_registry(path, run_root):
    value = load(path)
    require(value['scope'] == 'external_full_outputs_and_inputs' and value['full_outputs'] and value['inputs'], 'Full TAR and input registry required')
    run_archives = [row for row in value['full_outputs'] if row['role'] == 'rc31_run']
    require(len(run_archives) == 1, 'Exactly one full TAR must identify the consumed RC3.1 run')
    for row in value['full_outputs'] + value['inputs']:
        actual = Path(row['path']).resolve(strict=True)
        require(actual.is_file() and actual.stat().st_size == row['bytes'] and digest(actual) == row['sha256'], 'External evidence pin mismatch: ' + str(actual))
        if row in value['full_outputs']:
            require(actual.name.endswith(('.tar', '.tar.gz', '.tgz', '.tar.xz', '.tar.bz2')), 'Full scientific outputs must identify an actual readable TAR archive')
        row['path'] = str(actual)
    run_archive = run_archives[0]
    prefix = relative(run_archive['run_prefix']).as_posix() if run_archive['run_prefix'] else ''
    expected = {(prefix + '/' if prefix else '') + name: digest(Path(run_root) / name) for name in INPUTS}
    found = {}
    with tarfile.open(run_archive['path'], 'r:*') as archive:
        for member in archive:
            name = member.name.removeprefix('./')
            if name in expected:
                require(member.isfile() and name not in found, 'Non-regular/duplicate consumed TAR JSON member')
                with archive.extractfile(member) as stream:
                    found[name] = hashlib.file_digest(stream, 'sha256').hexdigest()
    require(found == expected, 'Full TAR does not contain exact consumed completed-run JSON')
    value['consumed_run_members_sha256'] = found
    return value


def assemble(args):
    root = new_root(args.output_dir)
    require(not root.exists(), 'Assembly output must be new')
    require(digest(args.source_zip) == PARENT_SHA256, 'Not the exact consumed RC3 ZIP')
    data = check_assets(args.assets_dir, args.run_root)
    narrative = load(args.narrative_json)
    validate_narrative(narrative)
    require(narrative['analysis_sha256'] == digest(args.run_root / 'analysis.json'), 'Narrative not bound to actual completed analysis')
    registry = verify_registry(args.evidence_registry, args.run_root)
    snapshots = data['source_provenance.json']['source_sha256']
    for name, sha in snapshots.items():
        require(digest(args.source_root / relative(name)) == sha, 'Current source is not the actual consumed source: ' + name)
    root.mkdir(parents=True)
    retention, seen = [], set()
    with zipfile.ZipFile(args.source_zip) as source:
        for info in source.infolist():
            if info.is_dir():
                continue
            name = PurePosixPath(info.filename)
            require(name.parts[0] == 'HealthGraphBench_RC3' and not stat.S_ISLNK(info.external_attr >> 16), 'Unexpected or symbolic parent member')
            original = relative('/'.join(name.parts[1:])).as_posix()
            require(original not in seen, 'Duplicate parent ZIP member')
            seen.add(original)
            retained = 'history/RC3/' + original
            path = root / retained
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = source.read(info)
            path.write_bytes(payload)
            retention.append({'original_path': original, 'retained_path': retained, 'bytes': len(payload),
                              'sha256': hashlib.sha256(payload).hexdigest()})
    # All parent material is historical; no obsolete RC3 prose or checks become active.
    for name in ('hgb_preview.sty', 'references.bib', 'scripts/compile_pdfs.py'):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / 'history/RC3' / name, path)
    compiler = root / 'scripts/compile_pdfs.py'
    old = "DOCUMENTS = ('main_fr', 'main_en', 'supplement_fr', 'supplement_en', 'response_reviewers_fr')"
    text = compiler.read_text()
    require(text.count(old) == 1, 'Unexpected parent compiler interface')
    compiler.write_text(text.replace(old, 'DOCUMENTS = ' + repr(DOCUMENTS)).replace('Compile all five reading-layout PDFs.', 'Compile the four RC3.1 reading-layout PDFs.'))
    style = root / 'hgb_preview.sty'
    style.write_text(style.read_text().replace('HealthGraphBench manuscript RC3; historical evidence and completed exploratory comparisons; sealed forecast not evaluated; working reading layout',
                                           'HealthGraphBench manuscript RC3.1; targeted exploratory experiments; independent, human, author and venue gates open; working reading layout'))
    for name in ('render_assets.py', 'check_package.py'):
        shutil.copyfile(SOURCES / name, root / 'scripts' / name)
    shutil.copyfile(Path(__file__), root / 'scripts/build_manuscript_rc31.py')
    for name in ('GUIDE_FR.md', 'GUIDE_EN.md'):
        guide = SOURCES / name if (SOURCES / name).is_file() else REPO / name
        shutil.copyfile(guide, root / name)
    schema = SOURCES / 'narrative.schema.json' if (SOURCES / 'narrative.schema.json').is_file() else REPO / 'release/narrative.schema.json'
    (root / 'release').mkdir(exist_ok=True)
    shutil.copyfile(schema, root / 'release/narrative.schema.json')
    compact = root / 'data/rc31'
    compact.mkdir(parents=True)
    for name in INPUTS:
        shutil.copyfile(args.run_root / name, compact / name)
    shutil.copyfile(args.narrative_json, compact / 'narrative.json')
    selection_inputs = [item for item in registry['inputs'] if item['role'] == 'partd_historical_bpr_selection']
    require(len(selection_inputs) == 1, 'The actually consumed historical Part D selection metadata is required')
    selection = selection_inputs[0]
    selection_member = 'data/reused_inputs/partd_selection.json'
    target = root / selection_member
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(selection['path'], target)
    require(digest(target) == selection['sha256'], 'Consumed Part D selection metadata copy changed')
    selection['manuscript_zip_member'] = selection_member
    selection['note'] = 'Byte-exact metadata is included in the manuscript ZIP; it remains outside the companion TAR.'
    for name, sha in snapshots.items():
        target = compact / 'sources' / relative(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(args.source_root / relative(name), target)
    # Preserve small actual phase result/worker/supervisor records, not massive predictions/checkpoints.
    phase_manifest = {}
    for phase in data['resource_ledger.json']['phases']:
        name = relative(phase['phase'])
        for filename in ('result.json', 'worker_status.json', 'supervisor_status.json'):
            source = args.run_root / name / filename
            require(source.is_file(), 'Missing actual compact phase evidence: ' + str(source))
            target = compact / 'phases' / name / filename
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            phase_manifest[target.relative_to(root).as_posix()] = digest(target)
    shutil.copytree(args.assets_dir, root / 'assets/rc31')
    plots = load(root / 'assets/rc31/plot_records.json')
    for lang in ('fr', 'en'):
        historical_assets(root, lang)
        text = narrative[lang]
        metadata = (r'\newcommand{\PaperTitle}{' + tex(text['title']) + '}\n'
                    + r'\newcommand{\DraftFooter}{RC3.1 — ' + ('validation des auteurs inconnue' if lang == 'fr' else 'author approval unknown') + '}\n')
        (root / ('metadata_' + lang + '.tex')).write_text(metadata)
        for supplement in (False, True):
            name = ('supplement_' if supplement else 'main_') + lang + '.tex'
            (root / name).write_text(document(text, lang, supplement, plots), encoding='utf-8')
    (root / 'VERSION').write_text('RC3.1\n')
    dump(root / 'release/parent_payload_RC3.json', {'parent_archive_sha256': PARENT_SHA256,
         'scope': 'Every parent file retained byte-for-byte; no historical scientific re-audit', 'files': retention})
    dump(root / 'release/source_snapshots.json', snapshots)
    dump(root / 'release/phase_records.json', phase_manifest)
    dump(root / 'release/evidence_registry.json', registry)
    dump(root / 'release.json', {'revision': 'RC3.1', 'evidence_level': data['protocol_executed.json']['evidence_level'],
         'question': data['protocol_executed.json']['question'], 'canonical_language': 'fr', 'english_role': 'faithful_translation',
         'scientific_gates': LIMITS, 'benchmark_doi': DOI, 'doi_scope': 'benchmark v0.2.0 only',
         'evidence_scope': 'compact evidence and pinned external full-output/input paths; not self-contained raw data',
         'narrative_sha256': digest(compact / 'narrative.json'), 'readiness': {'technical_verification_complete': False, 'ready_for_review': False}})
    dump(root / 'verification/rc31/assembly.json', {'revision': 'RC3.1', 'parent_archive': str(args.source_zip.resolve()),
         'parent_sha256': PARENT_SHA256, 'sealed': False, 'compiled': False,
         'run_root': str(args.run_root.resolve()), 'assembler_sha256': digest(Path(__file__))})
    report = check(root)
    dump(root / 'verification/rc31/assembly_QA.json', report)
    print(json.dumps({'root': str(root), 'passed': report['passed'], 'compiled': False, 'sealed': False}, indent=2))


def compilation_sources(root):
    return {path.relative_to(root).as_posix(): digest(path) for path in sorted(root.rglob('*'))
            if path.is_file() and not path.relative_to(root).parts[0] == 'history' and
            (path.suffix in ('.tex', '.sty', '.bib') or path.relative_to(root).parts[0] == 'assets')}


def compile_documents(args):
    root = new_root(args.root)
    assembly = load(root / 'verification/rc31/assembly.json')
    require(not assembly['sealed'], 'Never recompile sealed delivery')
    check(root)
    before = compilation_sources(root)
    evidence = root / 'verification/rc31'
    command = [sys.executable, '-B', str(root / 'scripts/compile_pdfs.py'), '--timeout', str(args.timeout)]
    result = subprocess.run(command, cwd=root, capture_output=True)
    (evidence / 'compilation.log').write_bytes(result.stdout + result.stderr)
    require(result.returncode == 0, 'RC3.1 LaTeX compilation failed; inspect verification/rc31/compilation.log')
    require(compilation_sources(root) == before, 'Inputs changed during compilation')
    records = {}
    for name in DOCUMENTS:
        log = root / (name + '.log')
        text = log.read_text(errors='replace')
        records[name] = {'pdf_sha256': digest(root / (name + '.pdf')), 'log_sha256': digest(log),
                         'overfull': re.findall(r'Overfull[^\n]*', text),
                         'undefined': re.findall(r'[^\n]*(?:undefined|Undefined|Rerun to get cross-references right|Label\(s\) may have changed)[^\n]*', text)}
    dump(evidence / 'compilation.json', {'documents': records, 'source_hashes': before,
         'compiler_sha256': digest(root / 'scripts/compile_pdfs.py'), 'command': command})
    assembly['compiled'] = True
    dump(evidence / 'assembly.json', assembly)
    require(not any(row['overfull'] or row['undefined'] for row in records.values()), 'Resolve actual overfull/reference diagnostics before visual review/seal')
    print(json.dumps({'compiled': list(records), 'sealed': False, 'next': 'Review every actual page of all four PDFs'}, indent=2))


def seal(args):
    root = new_root(args.root)
    archive_path = args.archive_path.resolve()
    require(archive_path.name == 'HealthGraphBench_LaTeX_RC3_1.zip', 'Distinct RC3.1 ZIP filename required')
    require(not archive_path.exists() and not archive_path.with_suffix('.zip.sha256').exists(), 'ZIP/checksum must be new')
    require(not any((args.pdf_output_dir / name).exists() for name in PDF_OUTPUTS.values()), 'Standalone PDF destinations must be new')
    require(not archive_path.is_relative_to(root) and not args.pdf_output_dir.resolve().is_relative_to(root), 'Delivery destinations must be outside the sealed root')
    require(not (root.parent / 'RC3_1_delivery_manifest.json').exists(), 'Delivery manifest must be new')
    assembly = load(root / 'verification/rc31/assembly.json')
    require(not assembly['sealed'] and assembly['compiled'], 'Require unsealed compiled RC3.1 assembly')
    require(digest(Path(assembly['parent_archive'])) == PARENT_SHA256, 'Consumed parent ZIP changed')
    check(root)
    review = load(args.surface_report)
    require(review['revision'] == 'RC3.1' and review['reviewer'] and review['reviewed_at_utc'], 'Actual attributed RC3.1 visual report required')
    compilation = load(root / 'verification/rc31/compilation.json')
    require(compilation['source_hashes'] == compilation_sources(root), 'Sources changed since compilation')
    for name in DOCUMENTS:
        filename = name + '.pdf'
        row = review['documents'][filename]
        diagnostic = compilation['documents'][name]
        require(row['sha256'] == digest(root / filename) == diagnostic['pdf_sha256'], 'Missing/stale visual report: ' + filename)
        require(row['visual_review_completed'] is True and row['page_count'] > 0 and
                row['reviewed_pages'] == list(range(1, row['page_count'] + 1)), 'Every actual page must be reviewed')
        pdfinfo = subprocess.run(['pdfinfo', str(root / filename)], capture_output=True, text=True, check=True)
        count = re.search(r'^Pages:\s+(\d+)\s*$', pdfinfo.stdout, re.MULTILINE)
        require(count is not None and int(count.group(1)) == row['page_count'], 'Visual report actual page count mismatch')
        require(not row['blank_pages'] and not row['unresolved_references'] and not row['overfull_boxes'], 'Unresolved surface defects')
        require(not diagnostic['overfull'] and not diagnostic['undefined'] and diagnostic['log_sha256'] == digest(root / (name + '.log')), 'Unresolved/stale LaTeX diagnostics')
    dump(root / 'verification/rc31/surface_review.json', review)
    release = load(root / 'release.json')
    release['readiness'] = {'technical_verification_complete': True, 'ready_for_review': True}
    dump(root / 'release.json', release)
    assembly['sealed'] = True
    dump(root / 'verification/rc31/assembly.json', assembly)
    # Cache and transient build products are not evidence; preserve all history bytes.
    for path in root.rglob('__pycache__'):
        if 'history' not in path.relative_to(root).parts:
            shutil.rmtree(path)
    for name in DOCUMENTS:
        for suffix in ('.aux', '.out', '.bbl', '.blg', '.fdb_latexmk', '.fls'):
            (root / (name + suffix)).unlink(missing_ok=True)
    files = sorted(path for path in root.rglob('*') if path.is_file() and path != root / 'SHA256SUMS')
    (root / 'SHA256SUMS').write_text(''.join(f'{digest(path)}  {path.relative_to(root).as_posix()}\n' for path in files))
    try:
        report = check(root, sealed=True)
    except (OSError, ValueError, KeyError, TypeError):
        assembly['sealed'] = False
        dump(root / 'verification/rc31/assembly.json', assembly)
        release['readiness'] = {'technical_verification_complete': False, 'ready_for_review': False}
        dump(root / 'release.json', release)
        (root / 'SHA256SUMS').unlink()
        raise
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files + [root / 'SHA256SUMS']:
            info = zipfile.ZipInfo(root.name + '/' + path.relative_to(root).as_posix(), date_time=(2026, 10, 4, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            with path.open('rb') as source, archive.open(info, 'w', force_zip64=True) as destination:
                shutil.copyfileobj(source, destination)
    sha = digest(archive_path)
    archive_path.with_suffix('.zip.sha256').write_text(sha + '  ' + archive_path.name + '\n')
    args.pdf_output_dir.mkdir(parents=True, exist_ok=True)
    outputs = []
    for name, destination in PDF_OUTPUTS.items():
        target = args.pdf_output_dir / destination
        with target.open('xb') as stream, (root / name).open('rb') as source:
            shutil.copyfileobj(source, stream)
        outputs.append({'path': str(target.resolve()), 'sha256': digest(target)})
    delivery = {'revision': 'RC3.1', 'archive': {'path': str(archive_path), 'sha256': sha}, 'standalone_pdfs': outputs,
                'package_QA': report, 'parent_RC3_unchanged': True, 'scientific_gates': LIMITS, 'submission_performed': False}
    dump(root.parent / 'RC3_1_delivery_manifest.json', delivery)
    print(json.dumps(delivery, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    build = commands.add_parser('assemble', help='Create a distinct source tree from actual assets and supplied bilingual interpretation; no compilation')
    build.add_argument('--source-zip', type=Path, required=True)
    build.add_argument('--output-dir', type=Path, required=True)
    build.add_argument('--run-root', type=Path, required=True)
    build.add_argument('--assets-dir', type=Path, required=True)
    build.add_argument('--narrative-json', type=Path, required=True)
    build.add_argument('--evidence-registry', type=Path, required=True)
    build.add_argument('--source-root', type=Path, default=REPO, help='Actual consumed source tree or exact snapshots matching source_provenance.json')
    compile_command = commands.add_parser('compile', help='Reuse parent compile_pdfs.py on the four new documents, recording current hashes/diagnostics')
    compile_command.add_argument('--root', type=Path, required=True)
    compile_command.add_argument('--timeout', type=int, default=120)
    publish = commands.add_parser('seal', help='Require matching all-page visual reports; seal distinct ZIP/four PDFs')
    publish.add_argument('--root', type=Path, required=True)
    publish.add_argument('--surface-report', type=Path, required=True)
    publish.add_argument('--archive-path', type=Path, required=True)
    publish.add_argument('--pdf-output-dir', type=Path, required=True)
    args = parser.parse_args()
    try:
        {'assemble': assemble, 'compile': compile_documents, 'seal': seal}[args.command](args)
    except (OSError, ValueError, RuntimeError, KeyError, TypeError, subprocess.SubprocessError, zipfile.BadZipFile, tarfile.TarError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
