#!/usr/bin/env python3
"""RC1 checks: frozen R6 science, publication-package identity, offline replay and PDFs.

The completed-R6 checker is preserved under history/R6_completee/scripts.
Original raw acquisition is received evidence, not repeated by this checker.
A pass is not author validation, editorial acceptance, or model retraining.
"""
from pathlib import Path
import argparse, ast, hashlib, json, re, subprocess, sys
from audit_maude_B import COMMIT, EVALUATION, REFITS, REFERENCE_SHA256, replay

ROOT=Path(__file__).resolve().parents[1]

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--skip-manifest',action='store_true')
    args=ap.parse_args()
    checks=[]
    def check(name,condition,detail=None):
        checks.append({'check':name,'passed':bool(condition),'detail':detail})
    status=json.loads((ROOT/'data/revision_status_R6.json').read_text())
    check('review_copy_revision',status['revision']=='RC1')
    check('scientific_revision_unchanged',status['scientific_revision']=='R6')
    check('ready_for_review',status['ready_for_review'] is True)
    check('submission_readiness_not_claimed',status['ready_for_submission'] is False)
    check('author_validation_not_invented',status['author_validation_complete'] is False)
    check('editorial_acceptance_not_claimed',status['editorial_acceptance_claimed'] is False)
    check('residual_requests_documented',status['residual_review_requests_documented'] is True)
    for request in ['B1','B2']:
        check('documented:'+request,
              status['requests'][request]['status']=='reviewer_reservation_lifted'
              and status['requests'][request]['result'] is not None)
    for request in ['B1','B2']:
        check('reviewer_lifted:'+request,status['requests'][request]['reviewer_assessment']=='lifted_in_supplied_R6_review')
    for request in ['minor_4_1','minor_4_2']:
        check('minor_applied:'+request,status['requests'][request]['status']=='applied')
    try:
        from summarize_maude_coverage import build_summary
        summary=build_summary(ROOT/'data/real_R6/maude_B')
        saved=json.loads((ROOT/'data/maude_coverage_periods_R6.json').read_text())
        check('coverage_summary_recomputed',summary==saved)
        test=summary['periods']['test_2024_2025']['metrics']
        check('test_only_pair_count',test['candidate_pairs']['numerator']==2902573 and test['candidate_pairs']['denominator']==2975156)
        check('test_only_full_lists',test['fully_covered_lists']['numerator']==1414 and test['fully_covered_lists']['denominator']==6370)
        all_lists=summary['periods']['validation_and_test_2023_2025']['metrics']['fully_covered_lists']
        check('all_period_full_lists',all_lists['numerator']==2331 and all_lists['denominator']==9853)
    except (OSError,ValueError,TypeError,KeyError) as exc:
        check('coverage_summary_recomputed',False,str(exc))
    for lang in ['fr','en']:
        body=(ROOT/f'sections/body_{lang}.tex').read_text()
        supp=(ROOT/f'supplement_{lang}.tex').read_text()
        additions=(ROOT/f'sections/supp_additions_{lang}.tex').read_text()
        table=(ROOT/f'tables/maude_B2_coverage_R6_{lang}.tex').read_text()
        phrase=("Aucune capacité de généralisation inductive" if lang=='fr' else 'Inductive generalization to nodes absent')
        check('inductive_wording:'+lang,phrase in body and phrase in supp)
        check('test_total_row:'+lang,'Test 2024--2025' in table)
        check('list_summary:'+lang,('22,20' if lang=='fr' else '22.20') in additions)
        check('new_coverage_script_cited:'+lang,'summarize_maude_coverage.py' in additions)
    inherited=json.loads((ROOT/status['inherited_collection_status']).read_text())
    for k in ['real_B1_B2_collection_executed','raw_data_reconstruction_executed']:
        check('recorded_collection:'+k,inherited['this_revision'][k] is True)
    for k in ['raw_archives_reacquired','raw_data_reconstruction_executed',
              'health_model_training_executed','new_predictions_computed',
              'new_scientific_analyses','remote_repository_modified',
              'submission_sent','new_DOI_created','data_and_figures_modified']:
        check('not_claimed_for_finishing:'+k,status['current_operations'][k] is False)
    provenance=json.loads((ROOT/'provenance.json').read_text())
    check('provenance_scope',provenance['revision']==status['revision']
          and provenance['current_operations']==status['current_operations'])
    check('parent_preserved',provenance['parent_archive']['modified'] is False)
    try:
        bundle=ROOT/'data/real_R6/maude_B'
        prepared,descriptors=replay(bundle)
        source=prepared['provenance']
        evidence=json.loads((bundle/'provenance.json').read_text())
        concordance=source['frozen_evaluation_concordance']
        check('real_B_offline_replay',True)
        check('B_source_commit',source['source_commit']==COMMIT)
        check('B_frozen_reference',source['reference_sha256']==REFERENCE_SHA256)
        check('B_collector_unchanged',evidence['script_sha256']==digest(ROOT/'scripts/audit_maude_B.py'))
        check('B_no_training',evidence['health_model_training_performed'] is False)
        check('B_three_refits',tuple(r['refit'] for r in descriptors['training_tabular'])==REFITS)
        check('B_twelve_quarters',tuple(r['quarter'] for r in descriptors['coverage_quarterly'])==EVALUATION)
        check('recorded_B_original_sampler',source['original_sampler_quarters_checked']==24)
        check('recorded_B_original_inventories',source['original_inventory_refits_checked']==3)
        check('recorded_B_frozen_population_concordance',concordance['passed']
              and concordance['product_quarters_matched']==len(descriptors['evaluation_membership'])==9853
              and concordance['methods_matched']==7)
        check('recorded_B_nine_verified_sources',len(source['raw_inputs'])==9
              and all(r['verified_here'] for r in source['raw_inputs']))
    except (OSError,ValueError,KeyError,TypeError,AssertionError) as exc:
        check('real_B_offline_replay',False,str(exc))
    retained=json.loads((ROOT/'verification/r6_completee/retained_input_files.json').read_text())
    for name,h in retained.items():
        check('retained:'+name,(ROOT/name).is_file() and digest(ROOT/name)==h)
    finishing_retained=json.loads((ROOT/'verification/r6_reviewable/retained_scientific_files.json').read_text())
    for name,h in finishing_retained.items():
        check('finishing_retained:'+name,(ROOT/name).is_file() and digest(ROOT/name)==h)
    # Terminology is changed only in human-readable labels, never result keys.
    bad_names=['BPR, propagation de messages','BPR avec propagation de messages',
               'BPR message passing','BPR with message passing']
    for lang in ['fr','en']:
        body=(ROOT/f'sections/body_{lang}.tex').read_text()
        check('main_prose_autonomous:'+lang,
              re.search(r'\bR[2-6]\b|\bB1\b|\bB2\b|A/C/D',body) is None)
        current=(ROOT/f'supplement_{lang}.tex').read_text()+'\n'+(ROOT/f'sections/supp_additions_{lang}.tex').read_text()
        current+='\n'+(ROOT/f'tables/maude_B1_graph_R6_{lang}.tex').read_text()
        check('BPR_name_unambiguous:'+lang,not any(s in current for s in bad_names))
        for name in [f'tables/maude_{lang}.tex',f'tables/maude_B1_graph_R6_{lang}.tex']:
            old=(ROOT/'history/R6_completee'/name).read_text()
            new=(ROOT/name).read_text()
            pattern=r'(?<![A-Za-z])[-+]?\d+(?:[.,]\d+)?'
            check('table_numbers_unchanged:'+name,re.findall(pattern,old)==re.findall(pattern,new))
    for stem in ['sections/body','sections/abstract','sections/supp_additions','supplement']:
        texts=[(ROOT/f'{stem}_{lang}.tex').read_text() for lang in ['fr','en']]
        keys=[]
        labels=[]
        for text in texts:
            keys.append({key.strip() for group in re.findall(r'\\cite(?:[a-z]*)\{([^}]+)\}',text) for key in group.split(',')})
            labels.append(set(re.findall(r'\\label\{([^}]+)\}',text)))
        check('bilingual_citation_keys:'+stem,keys[0]==keys[1])
        check('bilingual_labels:'+stem,labels[0]==labels[1])
    for lang in ['FR','EN']:
        readme=(ROOT/f'README_{lang}.md').read_text()
        check('manifest_before_compile:'+lang,readme.index('sha256sum -c SHA256SUMS')<readme.index('python scripts/compile_pdfs.py'))
    syntax=[]
    for p in list((ROOT/'scripts').glob('*.py'))+list((ROOT/'tests').glob('*.py')):
        try:ast.parse(p.read_text(),filename=p.name)
        except SyntaxError as e:syntax.append(str(e))
    check('python_syntax',not syntax,syntax)
    pdfs=[]
    for name in ['main_fr','main_en','supplement_fr','supplement_en','response_reviewers_fr']:
        p=ROOT/(name+'.pdf')
        try:
            text=subprocess.run(['pdftotext','-layout',str(p),'-'],capture_output=True,text=True,check=True).stdout
            info=subprocess.run(['pdfinfo',str(p)],capture_output=True,text=True,check=True).stdout
            count=int(re.search(r'^Pages:\s+(\d+)',info,re.M).group(1))
            pdfs.append({'file':p.name,'pages':count,'sha256':digest(p)})
            check('pdf_revision:'+name,'RC1' in text.split('\f')[0])
            first=text.split('\f')[0].lower()
            check('release_candidate_label:'+name,('release candidate' in first if name.endswith('_en') else 'candidate' in first))
            check('pdf_text_resolved:'+name,'??' not in text and '\ufffd' not in text)
            check('no_runtime_path:'+name,'/mnt/data/' not in text)
            if name.startswith('supplement'):
                check('ASCII_options:'+name,'--output' in text and '–output' not in text)
        except Exception as e:check('read_pdf:'+name,False,str(e))
    release=json.loads((ROOT/'release.json').read_text())
    check('release_identity',release['package_id']=='manuscript-rc1' and release['release_candidate']=='RC1'
          and (ROOT/'VERSION').read_text().strip()==release['package_id'])
    check('manuscript_not_benchmark_release',release['benchmark']['version']=='0.2.0'
          and release['benchmark']['source_commit']==COMMIT and not release['benchmark']['modified'])
    check('not_remotely_published',release['distribution_status']=='local_release_candidate_not_published'
          and release['tag_created'] is False and release['manuscript_package_DOI'] is None)
    check('release_parent_consistent',release['parent_archive']==provenance['parent_archive'])
    freeze=json.loads((ROOT/'release/protected_payload.json').read_text())
    check('frozen_payload_parent',freeze['parent_archive_sha256']==provenance['parent_archive']['sha256'])
    for name,h in freeze['files'].items():
        check('RC1_frozen:'+name,(ROOT/name).is_file() and digest(ROOT/name)==h)
    if not args.skip_manifest:
        for line in (ROOT/'SHA256SUMS').read_text().splitlines():
            h,n=line.split(None,1);n=n.lstrip('*')
            p=ROOT/n
            check('manifest:'+n,p.is_file() and digest(p)==h)
    fonts=[str(p.relative_to(ROOT)) for p in ROOT.rglob('*') if p.suffix.lower() in ['.ttf','.otf','.woff','.woff2','.ttc','.pfb','.pfa']]
    check('no_standalone_fonts',not fonts,fonts)
    report={'revision':'RC1','scope':'First publication release candidate with frozen R6 scientific payload, package identity, local MAUDE bundle replay and document checks. Raw source acquisition and source concordance are retained evidence, not repeated. No health-model fitting or new scientific analysis.',
            'passed':all(c['passed'] for c in checks),'ready_for_review':True,'ready_for_submission':False,
            'manifest_skipped':args.skip_manifest,'checks':checks,'pdfs':pdfs}
    print(json.dumps(report,indent=2,ensure_ascii=False))
    return 0 if report['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
