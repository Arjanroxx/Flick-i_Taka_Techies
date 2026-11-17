"""Match-level cross-validation of a geometry-only conditional ownership model."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.download_skillcorner import digest
from scripts.validate_skillcorner import verify_source
from scripts.validate_accumulated_control import load_cached
from src.skillcorner_validation import native_config, evaluate_reference
from src.learned_control import control_features, fit_model, calibrate_model
from src.p3_sequence_model import run


def training_data(matches, data):
    x, y, weights = [], [], []
    for match in matches:
        item = data[match]
        mask = item['eligible'] & item['reference'].isin(['H', 'A']).to_numpy()
        if not mask.any():
            raise ValueError('No eligible labelled training observations in ' + match)
        x.append(item['x'][mask])
        y.append(np.where(item['reference'].to_numpy()[mask] == 'H', 1., -1.))
        weights.append(np.full(int(mask.sum()), 1 / mask.sum()))
    return np.concatenate(x), np.concatenate(y), np.concatenate(weights)


def main():
    out = ROOT / 'artifacts/learned_control'
    out.mkdir(exist_ok=True)
    protocol = json.loads((ROOT / 'configs/skillcorner_protocol.json').read_text())
    plan = json.loads((ROOT / 'configs/learned_control_protocol.json').read_text())
    blobs = json.loads((ROOT / 'configs/skillcorner_source_blobs.json').read_text())
    source_names = ['src/learned_control.py', 'src/control_evidence.py', 'src/p3_sequence_model.py',
                    'src/skillcorner_validation.py', 'scripts/train_learned_control.py',
                    'configs/learned_control_protocol.json', 'configs/skillcorner_protocol.json']
    sources = {name: digest(ROOT / name) for name in source_names}
    (out / 'locked_protocol.json').write_text(json.dumps({'plan': plan, 'sources': sources}, indent=2))
    development = protocol['development_matches']
    if len(development) != 12 or set(development) & set(protocol['test_matches']):
        raise ValueError('Invalid development/test split')
    data = {}
    for match in development:
        folder = ROOT / 'artifacts/external/skillcorner' / match
        tracking = verify_source(folder, match, protocol, blobs)
        a, b, reference = load_cached(folder, protocol,
            ROOT / 'artifacts/accumulated_validation/feature_cache' / match, tracking)
        x, eligible = control_features(a, b, protocol['source_fps'])
        data[match] = {'a': a, 'b': b, 'reference': reference, 'x': x, 'eligible': eligible}
        print(match + ': label-free features prepared', flush=True)
    variants = [(ridge, confidence) for ridge in plan['ridge_candidates']
                 for confidence in plan['confidence_candidates']]
    baseline = {}
    rows, splits = [], []
    for fold in range(plan['folds']):
        validation = [match for index, match in enumerate(development) if index % 3 == fold]
        remaining = [match for match in development if match not in validation]
        fit_matches, calibration = remaining[:-2], remaining[-2:]
        if set(validation) & set(fit_matches + calibration):
            raise ValueError('Outer-fold leakage')
        splits.append({'fold': fold, 'fit': fit_matches, 'calibration': calibration, 'validation': validation})
        train = training_data(fit_matches, data)
        calibration_data = training_data(calibration, data)
        for ridge in plan['ridge_candidates']:
            model = calibrate_model(fit_model(*train, ridge), *calibration_data)
            model.update(fit_matches=fit_matches, calibration_matches=calibration,
                         excluded_validation_matches=validation)
            (out / f'fold{fold}_ridge{ridge}.json').write_text(json.dumps(model, indent=2))
            for match in validation:
                item = data[match]
                if match not in baseline:
                    config = native_config(protocol, 'sustained_control')
                    c = run(config, item['a'], item['b'])
                    baseline[match] = evaluate_reference(item['reference'], c.raw_label,
                                                         item['a'].half, protocol['source_fps'])
                for confidence in plan['confidence_candidates']:
                    config = native_config(protocol, 'sustained_control')
                    config['hmm']['team_evidence'] = 'learned_control'
                    config['learned_control'] = {'model': model, 'confidence': confidence,
                                                 'fps': protocol['source_fps']}
                    c = run(config, item['a'], item['b'])
                    metrics = evaluate_reference(item['reference'], c.raw_label,
                                                  item['a'].half, protocol['source_fps'])
                    half = metrics['per_iou'][.5]
                    rows.append({'match': match, 'fold': fold, 'ridge': ridge, 'confidence': confidence,
                                 **{key:metrics[key] for key in ('partial_reference_spellF1', 'macroF1_HA',
                                                                'fragmentation', 'spell_count_ratio')},
                                 'spell_precision_05': half['precision'], 'spell_recall_05': half['recall'],
                                 'baseline_spellF1': baseline[match]['partial_reference_spellF1'],
                                 'baseline_macroF1_HA': baseline[match]['macroF1_HA']})
                    pd.DataFrame(rows).to_csv(out / 'cross_validation_per_match.csv', index=False)
            print(f'fold {fold}, ridge {ridge}: four held-out matches evaluated', flush=True)
    frame = pd.DataFrame(rows)
    summary = frame.groupby(['ridge', 'confidence'])[['partial_reference_spellF1', 'macroF1_HA',
                         'fragmentation', 'spell_count_ratio', 'spell_precision_05', 'spell_recall_05']].mean()
    summary = summary.sort_values(['partial_reference_spellF1', 'macroF1_HA'], ascending=False)
    ridge, confidence = summary.index[0]
    selected = frame[(frame.ridge == ridge) & (frame.confidence == confidence)]
    delta = (selected.partial_reference_spellF1 - selected.baseline_spellF1).to_numpy()
    rng = np.random.default_rng(0)
    interval = np.quantile(rng.choice(delta, (10000, len(delta))).mean(axis=1), [.05, .95])
    gate = plan['promotion_gate']
    passes = (delta.mean() >= gate['minimum_mean_spell_gain']
              and int((delta > 0).sum()) >= gate['minimum_match_wins']
              and interval[0] > gate['paired_bootstrap_lower_bound'])
    result = {'sources': sources, 'splits': splits, 'development_only': True,
              'ridge': float(ridge), 'confidence': float(confidence),
              'summary': summary.reset_index().to_dict(orient='records'),
              'baseline_mean_spellF1': float(selected.baseline_spellF1.mean()),
              'baseline_mean_macroF1_HA': float(selected.baseline_macroF1_HA.mean()),
              'mean_spell_gain': float(delta.mean()), 'match_wins': int((delta > 0).sum()),
              'paired_match_bootstrap_90pct': interval.tolist(), 'promotion_gate_passed': bool(passes),
              'eight_matches_or_public_evaluated': False}
    if passes:
        fit_matches, calibration = development[:-2], development[-2:]
        model = calibrate_model(fit_model(*training_data(fit_matches, data), float(ridge)),
                                 *training_data(calibration, data))
        model.update(fit_matches=fit_matches, calibration_matches=calibration,
                     external_reference='SkillCorner provider H/A labels, detected nearby geometry only')
        (out / 'candidate_model.json').write_text(json.dumps(model, indent=2))
        result['candidate_model_sha256'] = digest(out / 'candidate_model.json')
    if sources != {name: digest(ROOT / name) for name in source_names}:
        raise RuntimeError('Experiment source changed during evaluation')
    (out / 'development_report.json').write_text(json.dumps(result, indent=2))
    summary.to_csv(out / 'cross_validation_summary.csv')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
