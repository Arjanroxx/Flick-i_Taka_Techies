"""Evaluate two predeclared frozen models on independent public match references."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.download_skillcorner import digest
from src.skillcorner_validation import load_match, native_config, evaluate_reference, match_split
from src.p3_sequence_model import run


def verify_source(folder, match, protocol, blobs):
    stem = f'data/matches/{match}/{match}'
    for local, suffix in [('match.json', '_match.json'), ('phases.csv', '_phases_of_play.csv'),
                          ('tracking.lfs', '_tracking_extrapolated.jsonl')]:
        content = (folder / local).read_bytes()
        git_digest = hashlib.sha1(b'blob ' + str(len(content)).encode() + b'\0' + content).hexdigest()
        if git_digest != blobs[stem + suffix]:
            raise ValueError('Pinned Git blob mismatch: ' + local)
    pointer = dict(line.split(' ', 1) for line in (folder / 'tracking.lfs').read_text().splitlines())
    actual = digest(folder / 'tracking.jsonl')
    if (actual != pointer['oid'].removeprefix('sha256:')
            or (folder / 'tracking.jsonl').stat().st_size != int(pointer['size'])):
        raise ValueError('Tracking LFS content mismatch')
    return actual


def phase_consistency(folder, reference):
    phases = pd.read_csv(folder / 'phases.csv')
    interior = np.zeros(len(reference), dtype=bool)
    closed = np.zeros(len(reference), dtype=bool)
    for row in phases.itertuples():
        start, end = int(row.frame_start), int(row.frame_end)
        if start < 0 or end < start or end > len(reference):
            raise ValueError('Phase interval lies outside tracking')
        # Endpoint convention is not asserted: compare conservative strict
        # interiors with closed coverage, and do not derive D from either.
        interior[start + 1:end] = True
        closed[start:end + 1] = True
    known = reference.isin(['H', 'A']).to_numpy()
    return {'phase_interiors': int(interior.sum()),
            'unknown_reference_inside_phase': int((interior & ~known).sum()),
            'known_reference_outside_closed_phase': int((known & ~closed).sum())}


def aggregate(records, protocol):
    flat = []
    for record in records:
        for mode, result in record['models'].items():
            row = {'match_id': record['match_id'], 'split': record['split'], 'model': mode,
                   'home': record['home'], 'away': record['away'], **record['input_coverage'],
                   **record['phase_consistency']}
            row.update({key: value for key, value in result.items()
                        if not isinstance(value, dict)})
            flat.append(row)
    frame = pd.DataFrame(flat)
    keys = ['partial_reference_spellF1', 'macroF1_HA', 'reference_coverage',
            'fragmentation', 'spell_count_ratio', 'predicted_spell_duration_seconds']
    summaries = []
    for (split, mode), group in frame.groupby(['split', 'model']):
        summaries.append({'split': split, 'model': mode, 'matches': len(group),
                          **{key: float(group[key].mean()) for key in keys}})
    comparisons = []
    for split in ('development', 'test'):
        group = frame[frame.split == split]
        for metric in ('partial_reference_spellF1', 'macroF1_HA'):
            pivot = group.pivot(index='match_id', columns='model', values=metric)
            differences = (pivot.sustained_control - pivot.distance).to_numpy()
            rng = np.random.default_rng(0)
            bootstrap = rng.choice(differences, size=(10000, len(differences)), replace=True).mean(axis=1)
            comparisons.append({'split': split, 'metric': metric, 'matches': len(differences),
                                'mean_control_minus_distance': float(differences.mean()),
                                'paired_match_bootstrap_90pct': np.quantile(bootstrap, [.05, .95]).tolist(),
                                'control_wins': int((differences > 0).sum())})
    return frame, {'summary': summaries, 'paired_comparisons': comparisons,
                   'reference_scope': 'Known provider H/A labels only; unknown excluded, no D reference',
                   'challenge_score': False, 'tuning_performed': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=ROOT / 'artifacts/external/skillcorner')
    parser.add_argument('--out', type=Path, default=ROOT / 'artifacts/skillcorner_validation')
    args = parser.parse_args()
    protocol_path = ROOT / 'configs/skillcorner_protocol.json'
    protocol = json.loads(protocol_path.read_text())
    blobs = json.loads((ROOT / 'configs/skillcorner_source_blobs.json').read_text())
    args.out.mkdir(parents=True, exist_ok=True)
    names = ['src/skillcorner_validation.py', 'src/control_evidence.py', 'src/p2_deadball_detector.py',
             'src/p3_sequence_model.py', 'src/contracts.py', 'scripts/validate_skillcorner.py',
             'evaluation/possession_metrics.py', 'configs/skillcorner_protocol.json',
             'configs/skillcorner_source_blobs.json']
    sources = {name: digest(ROOT / name) for name in names}
    # Fail if the recorded split changes or has overlap; no match-level tuning.
    if (set(protocol['development_matches']) & set(protocol['test_matches'])
            or set(protocol['development_matches'] + protocol['test_matches']) != set(protocol['match_ids'])):
        raise ValueError('Invalid predeclared match split')
    (args.out / 'locked_protocol.json').write_text(json.dumps(protocol, indent=2))
    records = []
    for match in protocol['match_ids']:
        folder = args.data_dir / match
        tracking_sha = verify_source(folder, match, protocol, blobs)
        signature = {'sources': sources, 'tracking_sha256': tracking_sha}
        checkpoint = args.out / (match + '.json')
        if checkpoint.exists():
            saved = json.loads(checkpoint.read_text())
            if saved.get('signature') == signature:
                records.append(saved)
                print(match + ': verified cached evaluation', flush=True)
                continue
        spatial, deadball, reference, metadata = load_match(folder, protocol)
        playing = spatial.half > 0
        record = {'match_id': match, 'split': match_split(protocol, match),
                  'home': metadata['home_team']['name'], 'away': metadata['away_team']['name'],
                  'signature': signature, 'input_coverage': {
                      'ball_observation_fraction': float(spatial.loc[playing, 'ball_x'].notna().mean()),
                      'both_team_distance_fraction': float(spatial.loc[playing,
                          ['dist_nearest_H', 'dist_nearest_A']].notna().all(axis=1).mean())},
                  'phase_consistency': phase_consistency(folder, reference), 'models': {}}
        for mode in protocol['frozen_models']:
            config = native_config(protocol, mode)
            predictions = run(config, spatial, deadball)
            if (not predictions.index.equals(reference.index)
                    or not np.isfinite(predictions[['prob_H', 'prob_A', 'prob_D']]).all().all()):
                raise ValueError('Invalid external predictions')
            record['models'][mode] = evaluate_reference(
                reference, predictions.raw_label, spatial.half, protocol['source_fps'])
        checkpoint.write_text(json.dumps(record, indent=2))
        records.append(record)
        print(f'{match}: both frozen models evaluated ({record["split"]})', flush=True)
    if sources != {name: digest(ROOT / name) for name in names}:
        raise RuntimeError('Model or protocol changed during the benchmark')
    frame, report = aggregate(records, protocol)
    frame.to_csv(args.out / 'per_match.csv', index=False)
    pd.DataFrame(report['summary']).to_csv(args.out / 'summary.csv', index=False)
    report.update(protocol_sha256=digest(protocol_path), sources=sources, match_count=len(records))
    (args.out / 'report.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report['summary'], indent=2))


if __name__ == '__main__':
    main()
