"""Develop on twelve matches, lock a revision, then evaluate eight reused matches."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.download_skillcorner import digest
from scripts.validate_skillcorner import verify_source
from src.skillcorner_validation import load_match, native_config, evaluate_reference
from src.p3_sequence_model import run


def signatures():
    names = ['src/control_evidence.py', 'src/p3_sequence_model.py', 'src/p2_deadball_detector.py',
             'src/skillcorner_validation.py', 'scripts/validate_accumulated_control.py',
             'configs/accumulated_control_candidate.yaml', 'configs/skillcorner_protocol.json']
    return {name: digest(ROOT / name) for name in names}


def load_cached(folder, protocol, cache, tracking_sha):
    source = {name: digest(ROOT / name) for name in ('src/skillcorner_validation.py',
                'src/p2_deadball_detector.py', 'configs/skillcorner_protocol.json')}
    expected = {'sources': source, 'tracking': tracking_sha,
                'metadata': digest(folder / 'match.json')}
    cache.mkdir(parents=True, exist_ok=True)
    manifest = cache / 'inputs.json'
    files = {kind: cache / (kind + '.parquet') for kind in ('spatial', 'deadball', 'reference')}
    if manifest.exists():
        saved = json.loads(manifest.read_text())
        if (saved['source'] == expected and all(path.exists() and digest(path) == saved['files'][kind]
                                                for kind, path in files.items())):
            return (pd.read_parquet(files['spatial']), pd.read_parquet(files['deadball']),
                    pd.read_parquet(files['reference']).reference)
    a, b, reference, _ = load_match(folder, protocol)
    for kind, table in [('spatial', a), ('deadball', b), ('reference', reference.to_frame())]:
        table.to_parquet(files[kind])
    manifest.write_text(json.dumps({'source': expected,
                                    'files': {kind: digest(path) for kind, path in files.items()}}, indent=2))
    return a, b, reference


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=['development', 'test'], default='development')
    parser.add_argument('--freeze', action='store_true')
    args = parser.parse_args()
    out = ROOT / 'artifacts/accumulated_validation'
    out.mkdir(exist_ok=True)
    protocol = json.loads((ROOT / 'configs/skillcorner_protocol.json').read_text())
    blobs = json.loads((ROOT / 'configs/skillcorner_source_blobs.json').read_text())
    candidate = yaml.safe_load((ROOT / 'configs/accumulated_control_candidate.yaml').read_text())
    source = signatures()
    lock_path = out / 'frozen_revision.json'
    if args.freeze:
        dev = json.loads((out / 'development_report.json').read_text())
        if dev['sources'] != source or len(dev['matches']) != 12:
            raise ValueError('Freeze requires complete development results for this exact revision')
        lock_path.write_text(json.dumps({'sources': source, 'settings': candidate['control'],
                                        'development': dev['summary'], 'public_or_test_scored': False}, indent=2))
        print('Revision frozen before public and eight-match evaluation.')
        return
    if args.stage == 'test':
        lock = json.loads(lock_path.read_text())
        if lock['sources'] != source:
            raise ValueError('Revision changed after freeze')
    records = []
    for match in protocol[args.stage + '_matches']:
        destination = out / (args.stage + '_' + match + '.json')
        folder = ROOT / 'artifacts/external/skillcorner' / match
        tracking = verify_source(folder, match, protocol, blobs)
        signature = {'sources': source, 'tracking': tracking}
        if destination.exists():
            saved = json.loads(destination.read_text())
            if saved['signature'] == signature:
                records.append(saved)
                print(match + ': verified cached result', flush=True)
                continue
        a, b, reference = load_cached(folder, protocol,
                                      out / 'feature_cache' / match, tracking)
        results = {}
        for mode in ('sustained_control', 'accumulated_control'):
            cfg = native_config(protocol, 'sustained_control')
            if mode == 'accumulated_control':
                cfg['hmm']['team_evidence'] = mode
                cfg['control'] = dict(candidate['control'], fps=protocol['source_fps'])
            prediction = run(cfg, a, b)
            result = evaluate_reference(reference, prediction.raw_label, a.half, protocol['source_fps'])
            at_half = result['per_iou'][.5]
            result.update(spell_precision_05=at_half['precision'], spell_recall_05=at_half['recall'],
                          missed_spells_05=at_half['n_missed'], spurious_spells_05=at_half['n_spurious'])
            results[mode] = result
        # Confirm that the old method has not changed since the prior benchmark.
        prior = json.loads((ROOT / 'artifacts/skillcorner_validation' / (match + '.json')).read_text())
        for key in ('partial_reference_spellF1', 'macroF1_HA'):
            if not np.isclose(results['sustained_control'][key], prior['models']['sustained_control'][key],
                              rtol=0, atol=1e-12):
                raise RuntimeError('Baseline no longer reproduces the prior benchmark')
        record = {'match': match, 'stage': args.stage, 'signature': signature, 'models': results}
        destination.write_text(json.dumps(record, indent=2))
        records.append(record)
        print(match + ': evaluated both methods on ' + args.stage, flush=True)
    if source != signatures():
        raise RuntimeError('Revision changed during evaluation')
    rows = []
    for record in records:
        for mode, metrics in record['models'].items():
            rows.append({'match': record['match'], 'model': mode,
                         **{key: value for key, value in metrics.items() if not isinstance(value, dict)}})
    frame = pd.DataFrame(rows)
    keys = ['partial_reference_spellF1', 'macroF1_HA', 'fragmentation', 'spell_count_ratio',
            'spell_precision_05', 'spell_recall_05', 'missed_spells_05', 'spurious_spells_05']
    summary = frame.groupby('model')[keys].mean().reset_index().to_dict(orient='records')
    comparisons = {}
    for key in ('partial_reference_spellF1', 'macroF1_HA'):
        pivot = frame.pivot(index='match', columns='model', values=key)
        delta = (pivot.accumulated_control - pivot.sustained_control).to_numpy()
        rng = np.random.default_rng(0)
        draws = rng.choice(delta, (10000, len(delta))).mean(axis=1)
        comparisons[key] = {'mean_difference': float(delta.mean()), 'wins': int((delta > 0).sum()),
                            'paired_match_bootstrap_90pct': np.quantile(draws, [.05, .95]).tolist()}
    report = {'sources': source, 'stage': args.stage, 'matches': [r['match'] for r in records],
              'summary': summary, 'comparisons': comparisons,
              'reference_scope': 'Partial provider H/A reference; no D labels',
              'reused_test_set': args.stage == 'test'}
    frame.to_csv(out / (args.stage + '_per_match.csv'), index=False)
    (out / (args.stage + '_report.json')).write_text(json.dumps(report, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
