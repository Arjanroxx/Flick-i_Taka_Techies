"""Freeze a development-selected boundary candidate; run comparisons without tuning."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.download_skillcorner import digest
from scripts.validate_skillcorner import verify_source
from src.learned_control_cache import load_cached
from src.skillcorner_validation import native_config, evaluate_reference
from src.p3_sequence_model import run
from src.contracts import read, write

OUT = ROOT / 'artifacts/contact_boundaries'
CONFIG = ROOT / 'configs/contact_transition_candidate.yaml'


def signatures(report):
    names = set(report['sources']) | {'scripts/validate_contact_transitions.py',
        'configs/contact_transition_candidate.yaml', 'src/p1_spatial_features.py',
        'src/p4_arbiter_and_eval.py', 'src/contracts.py', 'scripts/run_full_pipeline.py',
        'evaluation/possession_metrics.py', 'evaluation/validate_submission.py',
        'evaluation/run_evaluation.py'}
    return {name: digest(ROOT / name) for name in sorted(names)}


def external(protocol, blobs, candidate):
    rows = []
    for match in protocol['test_matches']:
        folder = ROOT / 'artifacts/external/skillcorner' / match
        tracking = verify_source(folder, match, protocol, blobs)
        a, b, reference = load_cached(folder, protocol,
            ROOT / 'artifacts/learned_control/feature_cache' / match, tracking)
        for variant in ('original', 'contact'):
            cfg = native_config(protocol, 'sustained_control')
            if variant == 'contact':
                cfg['hmm']['contact_switch_probability'] = candidate['hmm']['contact_switch_probability']
            c = run(cfg, a, b)
            metrics = evaluate_reference(reference, c.raw_label, a.half, protocol['source_fps'])
            row = {'match': match, 'variant': variant}
            row.update({k: metrics[k] for k in ('partial_reference_spellF1', 'macroF1_HA',
                'fragmentation', 'spell_count_ratio')})
            row.update(precision_05=metrics['per_iou'][.5]['precision'], recall_05=metrics['per_iou'][.5]['recall'])
            rows.append(row)
        print(match + ': frozen eight-match comparison completed', flush=True)
        pd.DataFrame(rows).to_csv(OUT / 'comparison_per_match.csv', index=False)
    frame = pd.DataFrame(rows)
    comparisons = {}
    for key in ('partial_reference_spellF1', 'macroF1_HA'):
        pivot = frame.pivot(index='match', columns='variant', values=key)
        delta = (pivot.contact - pivot.original).to_numpy()
        interval = np.quantile(np.random.default_rng(0).choice(delta, (10000, len(delta))).mean(axis=1), [.05, .95])
        comparisons[key] = {'mean_gain': float(delta.mean()), 'wins': int((delta > 0).sum()),
            'paired_match_bootstrap_90pct': interval.tolist()}
    return {'reused_comparison_set': True, 'fresh_validation': False, 'promoted': False,
        'summary': frame.groupby('variant').mean(numeric_only=True).reset_index().to_dict(orient='records'),
        'comparisons': comparisons}


def competition(candidate):
    env = os.environ.copy()
    env['TEMP'] = env['TMP'] = str(ROOT / 'artifacts/tmp')
    env['MTAH_DATA_DIR'] = yaml.safe_load((ROOT / 'artifacts/local_config.yaml').read_text())['data']['directory']
    def call(name, args):
        with (OUT / (name + '.log')).open('w') as log:
            subprocess.run([sys.executable, *args], cwd=ROOT, env=env, stdout=log,
                           stderr=subprocess.STDOUT, check=True)
        print(name + ' passed', flush=True)
    def hashes():
        return {key: digest(ROOT / candidate['paths'][key]) for key in
                ('spatial', 'deadball', 'predictions', 'overrides', 'submission')}
    call('pipeline1', ['scripts/run_full_pipeline.py', '--config', str(CONFIG), '--skip-evaluation'])
    first = hashes()
    call('pipeline2', ['scripts/run_full_pipeline.py', '--config', str(CONFIG), '--skip-evaluation'])
    if first != hashes():
        raise RuntimeError('Candidate repeat hashes differ')
    original = yaml.safe_load((ROOT / 'configs/control_candidate.yaml').read_text())
    old_manifest = json.loads((ROOT / 'artifacts/control_candidate/verification.json').read_text())['hashes']
    old_csv = ROOT / original['paths']['submission']
    for key in ('spatial', 'deadball', 'predictions', 'overrides', 'submission'):
        path = ROOT / original['paths'][key]
        if digest(path).upper() != old_manifest[path.name]:
            raise RuntimeError('Original candidate changed: ' + key)
    # Verify the shared inference extension leaves the disabled original path byte-identical.
    baseline = run(original, read('spatial', ROOT / original['paths']['spatial']),
                   read('deadball', ROOT / original['paths']['deadball']))
    regenerated = OUT / 'original_regenerated.parquet'
    write('predictions', baseline, regenerated)
    if digest(regenerated).upper() != old_manifest['base_predictions.parquet']:
        raise RuntimeError('Disabled path changed original predictions')
    score = OUT / 'public_input'
    score.mkdir(exist_ok=True)
    shutil.copyfile(old_csv, score / 'original.csv')
    shutil.copyfile(ROOT / candidate['paths']['submission'], score / 'contact.csv')
    call('public_sanity', ['evaluation/run_evaluation.py', '--gt', 'public', '--results', str(score),
                          '--out', str(OUT / 'public_report'), '--bootstrap', '1000', '--no-detail'])
    return {'hashes': first, 'repeat_equal': True, 'original_predictions_byte_identical': True,
            'original_candidate_preserved': True, 'public_sanity_only': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--freeze', action='store_true')
    group.add_argument('--competition', action='store_true')
    args = parser.parse_args()
    report = json.loads((OUT / 'development_report.json').read_text())
    lock_path = OUT / 'frozen_candidate.json'
    if args.freeze:
        if report['sources'] != {name: digest(ROOT / name) for name in report['sources']}:
            raise ValueError('Development source changed')
        selected = max((row for row in report['summary'] if row['variant'] != 'original'),
                       key=lambda row: (row['partial_reference_spellF1'], row['macroF1_HA']))
        probability = selected['variant']
        if not report['comparisons'][probability]['development_gate_passed']:
            raise ValueError('Development gate failed')
        cfg = yaml.safe_load((ROOT / 'configs/control_candidate.yaml').read_text())
        cfg['hmm']['contact_switch_probability'] = float(probability)
        for key in ('spatial', 'deadball', 'predictions', 'overrides', 'submission',
                    'evaluation_results', 'evaluation_reports'):
            cfg['paths'][key] = 'artifacts/contact_transition_candidate/' + Path(cfg['paths'][key]).name
        CONFIG.write_text(yaml.safe_dump(cfg, sort_keys=False))
        lock_path.write_text(json.dumps({'sources': signatures(report), 'development_report_sha256':
            digest(OUT / 'development_report.json'), 'probability': float(probability),
            'comparison_or_public_scored_at_freeze': False}, indent=2))
        print('Selected configuration frozen before final comparisons.')
        return
    lock = json.loads(lock_path.read_text())
    if (signatures(report) != lock['sources'] or digest(OUT / 'development_report.json') !=
            lock['development_report_sha256']):
        raise ValueError('Candidate or development result changed after freeze')
    candidate = yaml.safe_load(CONFIG.read_text())
    if args.competition:
        result = competition(candidate)
        destination = OUT / 'competition_verification.json'
    else:
        protocol = json.loads((ROOT / 'configs/skillcorner_protocol.json').read_text())
        blobs = json.loads((ROOT / 'configs/skillcorner_source_blobs.json').read_text())
        result = external(protocol, blobs, candidate)
        destination = OUT / 'comparison_report.json'
    if signatures(report) != lock['sources']:
        raise RuntimeError('Source changed during comparison')
    result['sources'] = lock['sources']
    destination.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
