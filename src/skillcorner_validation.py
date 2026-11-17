"""Native-rate external geometry adapter and partial-reference possession metrics.

Provider possession labels are read separately and never become input features.
Unknown possession is X, never inferred D. These metrics are not challenge scores.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.linalg import fractional_matrix_power

from evaluation import possession_metrics as pm
from . import p2_deadball_detector as p2


def match_split(protocol, match_id):
    if match_id in protocol['development_matches']:
        return 'development'
    if match_id in protocol['test_matches']:
        return 'test'
    raise ValueError('Match not predeclared in protocol')


def native_config(protocol, mode):
    config = deepcopy(protocol['frozen_settings'])
    if mode not in protocol['frozen_models']:
        raise ValueError('Unknown frozen model')
    ratio = protocol['reference_fps'] / protocol['source_fps']
    matrix = fractional_matrix_power(np.asarray(config['hmm']['transition']), ratio)
    if np.iscomplexobj(matrix) or matrix.min() < -1e-12:
        raise ValueError('Transition matrix cannot be adapted as a real Markov matrix')
    matrix = np.maximum(matrix, 0)
    matrix /= matrix.sum(axis=1, keepdims=True)
    config['hmm'].update(transition=matrix.tolist(), team_evidence=mode, emission_power=ratio)
    config['control']['confirmation_frames'] = protocol['time_adaptation']['confirmation_frames']
    config['thresholds']['stoppage_confirm_frames'] = protocol['time_adaptation']['confirmation_frames']
    config['thresholds']['short_gap'] = protocol['time_adaptation']['short_gap_frames']
    return config


def finite_pair(x, y):
    return x is not None and y is not None and np.isfinite([x, y]).all()


def observation_features(row, metadata, roster):
    """Only geometry/detection/period fields; deliberately does not read possession."""
    length, width = metadata['pitch_length'], metadata['pitch_width']
    period = row.get('period') or 0
    if type(period) is not int or period not in (0, 1, 2):
        raise ValueError('Unexpected tracking period')
    ball = row.get('ball_data') or {}
    observed = (period > 0 and ball.get('is_detected') is True
                and finite_pair(ball.get('x'), ball.get('y')))
    x, y = ((float(ball['x']) + length / 2, float(ball['y']) + width / 2)
            if observed else (np.nan, np.nan))
    nearest = [np.nan, np.nan]
    if observed:
        for player in row.get('player_data', []):
            team = roster.get(player.get('player_id'))
            if (team is None or player.get('is_detected') is not True
                    or not finite_pair(player.get('x'), player.get('y'))):
                continue
            distance = float(np.hypot(float(player['x']) - ball['x'],
                                      float(player['y']) - ball['y']))
            if not np.isfinite(nearest[team]) or distance < nearest[team]:
                nearest[team] = distance
    return period, x, y, *nearest


def reference_label(row):
    group = (row.get('possession') or {}).get('group')
    if group not in (None, 'home team', 'away team'):
        raise ValueError('Unmapped possession group: ' + str(group))
    if not row.get('period'):
        return 'X'
    return {'home team': 'H', 'away team': 'A', None: 'X'}[group]


def load_match(folder, protocol):
    folder = Path(folder)
    metadata = json.loads((folder / 'match.json').read_text(encoding='utf-8'))
    if not np.isfinite([metadata['pitch_length'], metadata['pitch_width']]).all():
        raise ValueError('Nonfinite pitch dimensions')
    if min(metadata['pitch_length'], metadata['pitch_width']) <= 0:
        raise ValueError('Pitch dimensions must be positive')
    teams = {metadata['home_team']['id']: 0, metadata['away_team']['id']: 1}
    roster = {player['id']: teams[player['team_id']] for player in metadata['players']
              if player['team_id'] in teams}
    rows, reference, previous_time, previous_period = [], [], None, 0
    with (folder / 'tracking.jsonl').open(encoding='utf-8') as handle:
        for expected, line in enumerate(handle):
            row = json.loads(line)
            if type(row['frame']) is not int or row['frame'] != expected:
                raise ValueError('Tracking must provide each native frame in order from zero')
            feature = observation_features(row, metadata, roster)
            period = feature[0]
            if period and row.get('timestamp') is not None:
                parts = [float(p) for p in row['timestamp'].split(':')]
                if len(parts) != 3:
                    raise ValueError('Unexpected timestamp format')
                seconds = parts[0] * 3600 + parts[1] * 60 + parts[2]
                if (period == previous_period and previous_time is not None
                        and not np.isclose(seconds - previous_time,
                                           1 / protocol['source_fps'], atol=1e-5)):
                    raise ValueError('Tracking timestamp does not agree with native frame rate')
                previous_time, previous_period = seconds, period
            else:
                previous_time, previous_period = None, period
            rows.append(feature)
            reference.append(reference_label(row))
    if not rows:
        raise ValueError('Empty tracking file')
    spatial = pd.DataFrame(rows, columns=['half', 'ball_x', 'ball_y',
                                         'dist_nearest_H', 'dist_nearest_A'])
    spatial.index = pd.Index(np.arange(len(spatial), dtype='int64'), name='frame')
    spatial['half'] = spatial.half.astype('int8')
    spatial['ball_is_imputed'] = False
    missing = spatial.ball_x.isna()
    groups = (missing.ne(missing.shift()) | spatial.half.ne(spatial.half.shift())).cumsum()
    spatial['gap_length_frames'] = missing.groupby(groups).transform('size').where(
        missing & spatial.half.ne(0), 0).astype('int32')
    fps = protocol['source_fps']
    coordinates = spatial[['ball_x', 'ball_y']].to_numpy()
    pair = np.r_[False, (spatial.half.to_numpy()[1:] == spatial.half.to_numpy()[:-1])]
    velocity = np.full_like(coordinates, np.nan)
    velocity[1:] = np.diff(coordinates, axis=0) * fps
    velocity[~pair] = np.nan
    spatial['ball_speed'] = np.linalg.norm(velocity, axis=1)
    acceleration = np.full(len(spatial), np.nan)
    acceleration[1:] = np.linalg.norm(np.diff(velocity, axis=0), axis=1) * fps
    acceleration[~pair] = np.nan
    spatial['ball_accel'] = acceleration
    config = native_config(protocol, 'distance')
    pitch = {'length': metadata['pitch_length'], 'width': metadata['pitch_width']}
    # No SkillCorner possession/phase labels enter B. Actual P2 uses geometry
    # only here; this benchmark cannot validate tactical Smart Tagging quality.
    deadball = p2.build_mask(config, spatial, [], fps=fps, pitch=pitch)
    return spatial, deadball, pd.Series(reference, index=spatial.index, name='reference'), metadata


def labelled_runs(reference, periods):
    known = reference != pm.X
    edges = np.r_[0, np.flatnonzero((known[1:] != known[:-1])
                                    | (periods[1:] != periods[:-1])) + 1, len(known)]
    return [(int(a), int(b)) for a, b in zip(edges[:-1], edges[1:]) if known[a]]


def evaluate_reference(reference, labels, periods, fps):
    gt, pred = pm.label_codes(reference), pm.label_codes(labels)
    periods = np.asarray(periods)
    if len(gt) != len(pred) or len(gt) != len(periods):
        raise ValueError('External reference and predictions must align')
    runs = labelled_runs(gt, periods)
    filled = pm.fill_abstentions(pred, runs)
    cm = pm.scored_confusion(pm.confusion(gt, pred))
    spell = pm.spell_scores(gt, filled, runs)
    gt_spells, pred_spells = pm.possession_spells(gt, runs), pm.possession_spells(filled, runs)
    known = gt != pm.X
    playing = periods > 0
    if not known.any():
        raise ValueError('Match has no available possession reference')
    frame_scores = {name: pm.per_class_prf(cm, code)[2] for code, name in enumerate(('H', 'A'))}
    transition_metrics = {}
    for seconds in (.48, 1.0):
        tol = round(seconds * fps)
        tp = fp = fn = 0
        latency = []
        for start, stop in runs:
            gt_trans = pm.transitions(gt, [(start, stop)])
            pred_trans = pm.transitions(filled, [(start, stop)])
            pairs, missed, extra = pm.match_transitions(gt_trans, pred_trans, tol)
            tp += len(pairs); fp += len(extra); fn += len(missed)
            latency.extend(abs(p[0] - g[0]) / fps for g, p in pairs)
        transition_metrics[str(seconds)] = {
            'f1': 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.,
            'matched': tp, 'spurious': fp, 'missed': fn,
            'mean_absolute_latency_seconds': float(np.mean(latency)) if latency else None}
    return {'partial_reference_spellF1': spell['mean_f1'],
            'macroF1_HA': float(np.mean(list(frame_scores.values()))),
            'per_class_f1': frame_scores, 'in_period_frames': int(playing.sum()),
            'labelled_frames': int(known.sum()), 'reference_coverage': float(known.sum() / playing.sum()),
            'labelled_runs': len(runs), 'reference_spells': len(gt_spells),
            'predicted_spells': len(pred_spells),
            'spell_count_ratio': len(pred_spells) / len(gt_spells) if gt_spells else None,
            'fragmentation': (len(pm.segments(filled, runs)) / len(pm.segments(gt, runs))),
            'predicted_spell_duration_seconds': float(np.mean([b-a for a,b,_ in pred_spells]) / fps)
                if pred_spells else 0.,
            'predicted_X_on_labelled': int((pred[known] == pm.X).sum()),
            'predicted_D_on_labelled': int((pred[known] == pm.D).sum()),
            'transitions': transition_metrics, 'per_iou': spell['per_iou'],
            'D_reference_available': False}
