"""Leave-one-match-out duration-scale estimation; development references only."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from evaluation import possession_metrics as pm
from scripts.download_skillcorner import digest
from scripts.validate_skillcorner import verify_source
from src.learned_control_cache import load_cached
from src.skillcorner_validation import native_config, evaluate_reference, labelled_runs
from src.p3_sequence_model import run


def uncensored_durations(reference, halves, fps):
    codes = pm.label_codes(reference)
    durations = []
    for start, stop in labelled_runs(codes, np.asarray(halves)):
        for left, right, _ in pm.possession_spells(codes, [(start, stop)]):
            if left > start and right < stop:
                durations.append((right-left)/fps)
    if not durations:
        raise ValueError('No fully observed interior reference spells')
    return np.asarray(durations)


def main():
    out = ROOT / 'artifacts/duration_model'
    out.mkdir(exist_ok=True)
    protocol = json.loads((ROOT / 'configs/skillcorner_protocol.json').read_text())
    blobs = json.loads((ROOT / 'configs/skillcorner_source_blobs.json').read_text())
    names = ['src/duration_model.py', 'src/p3_sequence_model.py', 'src/control_evidence.py',
        'src/p2_deadball_detector.py', 'src/skillcorner_validation.py', 'src/learned_control_cache.py',
        'scripts/evaluate_duration_model.py', 'evaluation/possession_metrics.py',
        'configs/skillcorner_protocol.json']
    sources = {name: digest(ROOT / name) for name in names}
    plan = {'sources': sources, 'folds': 'leave one development match out',
        'scale_estimator': 'equal-match average of uncensored interior H/A spell mean durations; teams pooled',
        'architecture': 'two phases per team, original D state; young exit 0.1 times original H/A exit',
        'stage_rate': '1-exp(-2/(scale_seconds*fps)); fixed structure, no hyperparameter sweep',
        'gate': {'mean_spell_gain': .01, 'match_wins': 8, 'bootstrap_lower': 0},
        'public_or_comparison_used_for_fitting': False}
    (out / 'protocol.json').write_text(json.dumps(plan, indent=2))
    data, duration_stats = {}, {}
    for match in protocol['development_matches']:
        folder = ROOT / 'artifacts/external/skillcorner' / match
        tracking = verify_source(folder, match, protocol, blobs)
        a,b,reference = load_cached(folder, protocol,
            ROOT / 'artifacts/learned_control/feature_cache' / match, tracking)
        data[match] = a,b,reference
        durations = uncensored_durations(reference, a.half, protocol['source_fps'])
        duration_stats[match] = {'mean_seconds': float(durations.mean()), 'spells': len(durations)}
    rows, folds = [], []
    for match, (a,b,reference) in data.items():
        fit = [other for other in data if other != match]
        scale = float(np.mean([duration_stats[other]['mean_seconds'] for other in fit]))
        folds.append({'validation': match, 'fit_matches': fit, 'scale_seconds': scale})
        for mode in ('original', 'duration'):
            cfg = native_config(protocol, 'sustained_control')
            if mode == 'duration':
                cfg['hmm']['decoder'] = 'duration'
                cfg['duration'] = {'scale_seconds': scale, 'fps': protocol['source_fps']}
            c = run(cfg, a, b)
            m = evaluate_reference(reference, c.raw_label, a.half, protocol['source_fps'])
            rows.append({'match': match, 'mode': mode, 'spellF1': m['partial_reference_spellF1'],
                'macroF1_HA': m['macroF1_HA'], 'precision_05': m['per_iou'][.5]['precision'],
                'recall_05': m['per_iou'][.5]['recall'], 'spell_count_ratio': m['spell_count_ratio']})
        pd.DataFrame(rows).to_csv(out / 'development.csv', index=False)
        print(match + ': excluded from its duration-scale estimation', flush=True)
    frame = pd.DataFrame(rows)
    pivot = frame.pivot(index='match', columns='mode', values='spellF1')
    delta = (pivot.duration-pivot.original).to_numpy()
    interval = np.quantile(np.random.default_rng(0).choice(delta,(10000,len(delta))).mean(axis=1),[.05,.95])
    passes = bool(delta.mean() >= .01 and (delta>0).sum() >= 8 and interval[0] > 0)
    final_scale = float(np.mean([row['mean_seconds'] for row in duration_stats.values()]))
    cfg = yaml.safe_load((ROOT / 'configs/control_candidate.yaml').read_text())
    cfg['hmm']['decoder'] = 'duration'
    cfg['duration'] = {'scale_seconds': final_scale, 'fps': 25}
    for key in ('spatial','deadball','predictions','overrides','submission','evaluation_results','evaluation_reports'):
        cfg['paths'][key] = 'artifacts/duration_candidate/' + Path(cfg['paths'][key]).name
    (ROOT / 'configs/duration_candidate.yaml').write_text(yaml.safe_dump(cfg, sort_keys=False))
    if sources != {name: digest(ROOT / name) for name in names}:
        raise RuntimeError('Sources changed during experiment')
    report = {'sources': sources, 'summary': frame.groupby('mode').mean(numeric_only=True).to_dict(),
        'folds': folds, 'duration_stats': duration_stats, 'final_scale_seconds': final_scale,
        'mean_spell_gain': float(delta.mean()), 'wins': int((delta>0).sum()),
        'paired_match_bootstrap_90pct': interval.tolist(), 'development_gate_passed': passes,
        'public_or_eight_evaluated': False, 'promoted': False}
    (out / 'report.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
