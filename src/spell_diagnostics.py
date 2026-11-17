"""Read-only, reference-based error attribution using the official spell semantics.

Categories describe interval geometry, not proven physical causes. Unknown GT and
period boundaries censor comparisons; predicted X is filled only inside those runs.
"""
import numpy as np
import pandas as pd

from evaluation import possession_metrics as pm


def _aligned(reference, prediction, periods, extras):
    tables = [reference, prediction, periods] + [x for x in extras if x is not None]
    if not all(isinstance(x, pd.Series) for x in tables):
        raise ValueError('Diagnostics require indexed Series, not positional arrays')
    index = reference.index
    if (not pd.api.types.is_integer_dtype(index.dtype) or not index.is_unique
            or (len(index) > 1 and not np.all(np.diff(index.to_numpy()) == 1))
            or any(not x.index.equals(index) for x in tables)):
        raise ValueError('All inputs must share an ordered consecutive integer frame index')
    if periods.isna().any() or not periods.isin([0, 1, 2]).all():
        raise ValueError('Periods must contain only 0, 1, 2')


def _pairs(overlaps, n_gt, n_pred, threshold=.5):
    """Official descending-IoU greedy matching, retaining both interval identities."""
    pairs, used_gt, used_pred = {}, set(), set()
    for iou, i, j in overlaps:
        if iou < threshold:
            break
        if i not in used_gt and j not in used_pred:
            pairs[i] = j
            used_gt.add(i)
            used_pred.add(j)
    expected = pm.match_spells(overlaps, n_gt, n_pred, threshold)[0]
    if len(pairs) != expected:
        raise AssertionError('Diagnostic matching differs from official matching')
    return pairs


def diagnose(reference, prediction, periods, fps, *, dead_reference_available=True,
             control_support=None, ball_observed=None):
    _aligned(reference, prediction, periods, [control_support, ball_observed])
    if not np.isfinite(fps) or fps <= 0:
        raise ValueError('FPS must be positive and finite')
    gt, raw = pm.label_codes(reference), pm.label_codes(prediction)
    if ((gt != pm.X) & (periods.to_numpy() == 0)).any():
        raise ValueError('Scored reference cannot occur outside a period')
    if not dead_reference_available and (gt == pm.D).any():
        raise ValueError('D labels contradict a declared H/A-only reference')
    support = pm.label_codes(control_support) if control_support is not None else None
    if ball_observed is not None and (ball_observed.isna().any()
                                      or not pd.api.types.is_bool_dtype(ball_observed.dtype)):
        raise ValueError('Observed-ball mask must be nonmissing boolean')
    n = len(gt)
    known = gt != pm.X
    edges = np.r_[0, np.flatnonzero((known[1:] != known[:-1]) |
        (periods.to_numpy()[1:] != periods.to_numpy()[:-1])) + 1, n]
    runs = [(int(a), int(b)) for a, b in zip(edges[:-1], edges[1:]) if a < b and known[a]]
    filled = pm.fill_abstentions(raw, runs)
    truth, predicted = pm.possession_spells(gt, runs), pm.possession_spells(filled, runs)
    overlaps = pm.spell_overlaps(truth, predicted)
    pairs = _pairs(overlaps, len(truth), len(predicted))
    frames = reference.index.to_numpy()

    def interval(start, stop):
        return {'start_frame': int(frames[start]), 'stop_frame_exclusive': int(frames[stop-1])+1,
                'duration_seconds': (stop-start)/fps,
                'touches_reference_window_edge': any(start == a or stop == b for a, b in runs)}

    # Separators count concrete bridges by one predicted same-team spell. They
    # are not an additive decomposition of missed spells (one bridge can harm several).
    bridges, bridge_gt = [], set()
    for j, (ps, pe, team) in enumerate(predicted):
        touched = sorted(i for _, i, p in overlaps if p == j)
        for left, right in zip(touched[:-1], touched[1:]):
            start, stop = truth[left][1], truth[right][0]
            if start >= stop or not any(a <= start < stop <= b for a, b in runs):
                continue
            values = set(gt[start:stop])
            if values == {pm.D}:
                category = 'merged_across_stoppage'
            elif values == {1-team}:
                category = 'merged_across_opponent_possession'
            else:
                category = 'merged_across_mixed_separator'
            bridges.append({'predicted_spell': j, 'left_reference_spell': left,
                'right_reference_spell': right, 'team': pm.LABELS[team], 'category': category,
                **interval(start, stop)})
            bridge_gt.update((left, right))

    spell_rows = []
    for i, (start, stop, team) in enumerate(truth):
        candidates = [(iou, j) for iou, g, j in overlaps if g == i]
        best, best_j = min(candidates, key=lambda x: (-x[0], x[1])) if candidates else (0., None)
        if i in pairs:
            category = 'matched'
        elif not candidates:
            if (filled[start:stop] == 1-team).any():
                category = 'missed_team_possession'
            elif (filled[start:stop] == pm.D).any():
                category = 'predicted_dead_instead_of_possession'
            else:
                category = 'unanswered_reference_run'
        elif best >= .5:
            category = 'one_to_one_match_conflict'
        elif i in bridge_gt:
            category = 'merged_prediction_overlap'
        elif len(candidates) > 1:
            category = 'fragmented_or_boundary_mismatch'
        else:
            category = 'boundary_or_duration_mismatch'
        chosen = pairs.get(i, best_j)
        ps, pe, _ = predicted[chosen] if chosen is not None else (None, None, None)
        row = {'reference_spell': i, 'team': pm.LABELS[team], **interval(start, stop),
            'category': category, 'matched_iou_05': i in pairs, 'best_same_team_iou': best,
            'candidate_predicted_spell': chosen,
            'candidate_start_error_seconds': (ps-start)/fps if ps is not None else None,
            'candidate_end_error_seconds': (pe-stop)/fps if pe is not None else None,
            'raw_X_fraction': float((raw[start:stop] == pm.X).mean()),
            'filled_opponent_fraction': float((filled[start:stop] == 1-team).mean()),
            'filled_D_fraction': float((filled[start:stop] == pm.D).mean())}
        if support is not None:
            row['same_team_supported_frames'] = int((support[start:stop] == team).sum())
        if ball_observed is not None:
            row['observed_ball_fraction'] = float(ball_observed.iloc[start:stop].mean())
        spell_rows.append(row)

    stops = []
    if dead_reference_available:
        for start, stop, team in pm.segments(gt, runs):
            if team != pm.D:
                continue
            coverage = float((filled[start:stop] == pm.D).mean())
            stops.append({**interval(start, stop), 'predicted_D_coverage': coverage,
                'category': 'missed' if coverage == 0 else ('fully_covered' if coverage == 1 else 'partly_covered')})
    pred_rows = [{'predicted_spell': j, 'team': pm.LABELS[team], **interval(start, stop),
        'matched_iou_05': j in set(pairs.values()),
        'overlapping_same_team_reference_spells': sum(p == j for _, _, p in overlaps)}
        for j, (start, stop, team) in enumerate(predicted)]
    metrics = pm.spell_scores(gt, filled, runs)
    endpoint_errors = []
    for i, j in pairs.items():
        gs, ge, _ = truth[i]
        ps, pe, _ = predicted[j]
        if not any(gs == a for a, _ in runs):
            endpoint_errors.append(abs(ps-gs)/fps)
        if not any(ge == b for _, b in runs):
            endpoint_errors.append(abs(pe-ge)/fps)
    counts = lambda rows: dict(pd.Series([row['category'] for row in rows], dtype='string').value_counts().items())
    summary = {'scored_frames': int(known.sum()), 'scored_runs': len(runs),
        'reference_spells': len(truth), 'predicted_spells': len(predicted),
        'spellF1': metrics['mean_f1'], 'per_iou': metrics['per_iou'],
        'reference_spell_categories': counts(spell_rows), 'merge_bridge_categories': counts(bridges),
        'dead_reference_available': dead_reference_available,
        'stoppage_categories': counts(stops) if dead_reference_available else None,
        'reference_stoppage_frames': int((gt == pm.D).sum()) if dead_reference_available else None,
        'raw_X_on_scored_frames': int((raw[known] == pm.X).sum()),
        'matched_spell_internal_endpoint_errors': {'endpoint_observations': len(endpoint_errors),
            'mean_absolute_seconds': float(np.mean(endpoint_errors)) if endpoint_errors else None,
            'median_absolute_seconds': float(np.median(endpoint_errors)) if endpoint_errors else None,
            'max_absolute_seconds': float(max(endpoint_errors)) if endpoint_errors else None,
            'shared_transition_can_contribute_two_spell_endpoints': True},
        'diagnostic_only': True, 'prediction_modified': False}
    interval_columns = ['start_frame', 'stop_frame_exclusive', 'duration_seconds', 'touches_reference_window_edge']
    reference_columns = ['reference_spell', 'team', *interval_columns, 'category', 'matched_iou_05',
        'best_same_team_iou', 'candidate_predicted_spell', 'candidate_start_error_seconds',
        'candidate_end_error_seconds', 'raw_X_fraction', 'filled_opponent_fraction', 'filled_D_fraction']
    if support is not None:
        reference_columns.append('same_team_supported_frames')
        summary['unmatched_spells_with_control_support'] = sum(
            not row['matched_iou_05'] and row['same_team_supported_frames'] > 0 for row in spell_rows)
    if ball_observed is not None:
        reference_columns.append('observed_ball_fraction')
    return summary, {
        'reference_spells': pd.DataFrame(spell_rows, columns=reference_columns),
        'merge_bridges': pd.DataFrame(bridges, columns=['predicted_spell', 'left_reference_spell',
            'right_reference_spell', 'team', 'category', *interval_columns]),
        'stoppages': pd.DataFrame(stops, columns=[*interval_columns, 'predicted_D_coverage', 'category']),
        'predicted_spells': pd.DataFrame(pred_rows, columns=['predicted_spell', 'team', *interval_columns,
            'matched_iou_05', 'overlapping_same_team_reference_spells'])}
