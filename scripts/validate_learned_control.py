"""Freeze a CV-qualified classifier, then evaluate the eight reused matches."""
import argparse
from copy import deepcopy
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
from src.learned_control_cache import load_cached
from src.skillcorner_validation import native_config, evaluate_reference
from src.p3_sequence_model import run


def signatures():
    names = ['src/learned_control.py', 'src/learned_control_cache.py', 'src/control_evidence.py',
             'src/p3_sequence_model.py', 'src/skillcorner_validation.py', 'src/p2_deadball_detector.py',
             'scripts/train_learned_control.py', 'scripts/validate_learned_control.py',
             'configs/skillcorner_protocol.json', 'configs/learned_control_protocol.json',
             'configs/learned_control_candidate.yaml', 'models/learned_control.json']
    return {name: digest(ROOT / name) for name in names}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze', action='store_true')
    args = parser.parse_args()
    out = ROOT / 'artifacts/learned_control'
    protocol = json.loads((ROOT / 'configs/skillcorner_protocol.json').read_text())
    report = json.loads((out / 'development_report.json').read_text())
    lock_path = out / 'frozen_candidate.json'
    if args.freeze:
        if not report['promotion_gate_passed']:
            raise ValueError('Classifier did not clear its development gate')
        if report['sources'] != {name: digest(ROOT / name) for name in report['sources']}:
            raise ValueError('Development source changed')
        if digest(out / 'candidate_model.json') != report['candidate_model_sha256']:
            raise ValueError('Candidate model changed after fitting')
        model = json.loads((out / 'candidate_model.json').read_text())
        model.update(source_revision=protocol['revision'], training_protocol_sha256=digest(
            ROOT / 'configs/learned_control_protocol.json'), development_report_sha256=digest(
                out / 'development_report.json'), feature_source_sha256=digest(ROOT / 'src/learned_control.py'))
        (ROOT / 'models').mkdir(exist_ok=True)
        model_path = ROOT / 'models/learned_control.json'
        model_path.write_text(json.dumps(model, indent=2))
        cfg = yaml.safe_load((ROOT / 'configs/control_candidate.yaml').read_text())
        cfg['hmm']['team_evidence'] = 'learned_control'
        cfg['learned_control'] = {'model_path': 'models/learned_control.json',
                                  'model_sha256': digest(model_path), 'confidence': report['confidence'], 'fps': 25}
        for kind in ('spatial', 'deadball', 'predictions', 'overrides', 'submission',
                     'evaluation_results', 'evaluation_reports'):
            cfg['paths'][kind] = 'artifacts/learned_control_candidate/' + Path(cfg['paths'][kind]).name
        (ROOT / 'configs/learned_control_candidate.yaml').write_text(yaml.safe_dump(cfg, sort_keys=False))
        lock_path.write_text(json.dumps({'sources': signatures(), 'development_gate_passed': True,
                                        'public_or_eight_scored_at_freeze': False}, indent=2))
        print('CV-qualified classifier and configuration frozen before final comparisons.')
        return
    lock = json.loads(lock_path.read_text())
    if signatures() != lock['sources']:
        raise ValueError('Candidate changed after freeze')
    candidate = yaml.safe_load((ROOT / 'configs/learned_control_candidate.yaml').read_text())
    blobs = json.loads((ROOT / 'configs/skillcorner_source_blobs.json').read_text())
    rows = []
    for match in protocol['test_matches']:
        destination = out / ('test_' + match + '.json')
        folder = ROOT / 'artifacts/external/skillcorner' / match
        tracking = verify_source(folder, match, protocol, blobs)
        signature = {'sources': lock['sources'], 'tracking': tracking}
        if destination.exists():
            record = json.loads(destination.read_text())
            if record['signature'] == signature:
                rows.extend(record['rows'])
                print(match + ': verified cached comparison', flush=True)
                continue
        a, b, reference = load_cached(folder, protocol, out / 'feature_cache' / match, tracking)
        matched = []
        for mode in ('sustained_control', 'learned_control'):
            cfg = native_config(protocol, 'sustained_control')
            if mode == 'learned_control':
                cfg['hmm']['team_evidence'] = mode
                cfg['learned_control'] = dict(candidate['learned_control'], fps=protocol['source_fps'])
            predictions = run(cfg, a, b)
            result = evaluate_reference(reference, predictions.raw_label, a.half, protocol['source_fps'])
            at_half = result['per_iou'][.5]
            row = {'match': match, 'model': mode,
                   **{key: value for key, value in result.items() if not isinstance(value, dict)},
                   'spell_precision_05': at_half['precision'], 'spell_recall_05': at_half['recall'],
                   'missed_spells_05': at_half['n_missed'], 'spurious_spells_05': at_half['n_spurious']}
            matched.append(row)
        destination.write_text(json.dumps({'signature': signature, 'rows': matched}, indent=2))
        rows.extend(matched)
        print(match + ': both frozen methods evaluated', flush=True)
    frame = pd.DataFrame(rows)
    keys = ['partial_reference_spellF1', 'macroF1_HA', 'fragmentation', 'spell_count_ratio',
            'spell_precision_05', 'spell_recall_05', 'missed_spells_05', 'spurious_spells_05']
    summary = frame.groupby('model')[keys].mean().reset_index().to_dict(orient='records')
    comparison = {}
    for key in ('partial_reference_spellF1', 'macroF1_HA'):
        pivot = frame.pivot(index='match', columns='model', values=key)
        delta = (pivot.learned_control - pivot.sustained_control).to_numpy()
        rng = np.random.default_rng(0)
        bootstrap = rng.choice(delta, (10000, len(delta))).mean(axis=1)
        comparison[key] = {'mean_difference': float(delta.mean()), 'wins': int((delta > 0).sum()),
                           'paired_match_bootstrap_90pct': np.quantile(bootstrap, [.05, .95]).tolist()}
    if signatures() != lock['sources']:
        raise ValueError('Source changed during final comparison')
    frame.to_csv(out / 'test_per_match.csv', index=False)
    (out / 'test_report.json').write_text(json.dumps({'sources': lock['sources'], 'matches': 8,
        'summary': summary, 'comparison': comparison, 'reused_comparison_set': True,
        'D_reference_available': False, 'post_evaluation_tuning': False}, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
