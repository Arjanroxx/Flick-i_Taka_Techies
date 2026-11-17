"""Development-only spell failures; diagnostic categories are descriptive, not targets."""
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from evaluation import possession_metrics as pm
from scripts.validate_skillcorner import verify_source
from src.learned_control_cache import load_cached
from src.skillcorner_validation import native_config, labelled_runs, evaluate_reference
from src.control_evidence import sustained_control_evidence
from src.p3_sequence_model import run


def describe(reference, labels, spatial, deadball, config, fps):
    gt, pred = pm.label_codes(reference), pm.label_codes(labels)
    runs = labelled_runs(gt, spatial.half.to_numpy())
    filled = pm.fill_abstentions(pred, runs)
    truth = pm.possession_spells(gt, runs)
    predicted = pm.possession_spells(filled, runs)
    overlaps = pm.spell_overlaps(truth, predicted)
    matched = pm.matched_gt_flags(overlaps, len(truth), .5)
    teams, known = sustained_control_evidence(spatial, deadball,
        config['hmm']['emission_temperature'], config['control'])
    support = np.where(known, teams.argmax(axis=1), -1)
    rows = []
    for index, (start, stop, team) in enumerate(truth):
        candidates = [(iou, j) for iou, i, j in overlaps if i == index]
        best, best_index = max(candidates, default=(0., -1))
        if matched[index]:
            category = 'matched'
        elif not candidates:
            category = 'no_same_team_overlap'
        elif sum(j == best_index for _, _, j in overlaps) > 1 and (
                predicted[best_index][1] - predicted[best_index][0] > stop - start):
            category = 'shared_long_prediction'
        elif len(candidates) > 1:
            category = 'multiple_prediction_fragments'
        else:
            category = 'boundary_or_duration_mismatch'
        rows.append({'category': category, 'seconds': (stop-start)/fps,
                     'best_iou': best, 'same_team_supported_frames': int((support[start:stop] == team).sum()),
                     'observed_ball_fraction': float(spatial.ball_x.iloc[start:stop].notna().mean()),
                     'predicted_D_fraction': float((pred[start:stop] == pm.D).mean())})
    return pd.DataFrame(rows)


def main():
    out = ROOT / 'artifacts/contact_boundaries'
    out.mkdir(exist_ok=True)
    protocol = json.loads((ROOT / 'configs/skillcorner_protocol.json').read_text())
    blobs = json.loads((ROOT / 'configs/skillcorner_source_blobs.json').read_text())
    rows = []
    for match in protocol['development_matches']:
        folder = ROOT / 'artifacts/external/skillcorner' / match
        tracking = verify_source(folder, match, protocol, blobs)
        a, b, reference = load_cached(folder, protocol,
            ROOT / 'artifacts/learned_control/feature_cache' / match, tracking)
        config = native_config(protocol, 'sustained_control')
        c = run(config, a, b)
        c.to_parquet(out / (match + '_baseline.parquet'))
        table = describe(reference, c.raw_label, a, b, config, protocol['source_fps'])
        table['match'] = match
        rows.append(table)
        print(match + ': development baseline diagnosed', flush=True)
    frame = pd.concat(rows, ignore_index=True)
    frame.to_csv(out / 'development_spells.csv', index=False)
    summary = frame.groupby('category').agg(spells=('category', 'size'),
        median_seconds=('seconds', 'median'), mean_best_iou=('best_iou', 'mean'),
        fraction_with_team_support=('same_team_supported_frames', lambda x: float((x > 0).mean())),
        mean_predicted_D_fraction=('predicted_D_fraction', 'mean'))
    summary.to_csv(out / 'diagnosis_summary.csv')
    print(summary.to_string(), flush=True)


if __name__ == '__main__':
    main()
