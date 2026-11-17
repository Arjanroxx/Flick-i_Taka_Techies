"""Observed, sustained ball proximity as an experimental control proxy.

This is not a learned control classifier. Missing/distant/contested evidence is
neutral and the sequence model supplies temporal context. No player IDs needed.
"""
import numpy as np
from scipy.special import softmax


def sustained_control_evidence(spatial, deadball, temperature, settings):
    confirmation = settings.get('confirmation_frames', 3)
    distance = settings.get('max_distance_m', 2.0)
    margin = settings.get('min_margin_m', 2.0)
    dead_limit = settings.get('max_dead_probability', 0.2)
    if (type(confirmation) is not int or confirmation < 2
            or not np.isfinite([distance, margin, dead_limit, temperature]).all()
            or distance <= 0 or margin <= 0 or not 0 <= dead_limit < 1
            or temperature <= 0):
        raise ValueError('Invalid sustained-control settings')
    if not spatial.index.equals(deadball.index):
        raise ValueError('Control evidence requires aligned spatial and dead-ball frames')
    distances = spatial[['dist_nearest_H', 'dist_nearest_A']].to_numpy()
    near, far = np.min(distances, axis=1), np.max(distances, axis=1)
    eligible = (
        np.isfinite(distances).all(axis=1)
        & np.isfinite(spatial[['ball_x', 'ball_y']]).all(axis=1).to_numpy()
        & ~spatial.ball_is_imputed.to_numpy()
        & (spatial.gap_length_frames.to_numpy() == 0)
        & (spatial.half.to_numpy() > 0)
        & ~deadball.is_out_of_bounds.to_numpy()
        & (deadball.is_dead_ball_prob.to_numpy() <= dead_limit)
        & (near <= distance) & (far - near >= margin)
    )
    preference = np.where(eligible, distances.argmin(axis=1), -1)
    frames = spatial.index.to_numpy()
    halves = spatial.half.to_numpy()
    if not len(frames):
        return np.empty((0, 2)), np.empty(0, dtype=bool)
    boundaries = np.r_[True, (preference[1:] != preference[:-1])
                        | (halves[1:] != halves[:-1]) | (np.diff(frames) != 1), True]
    edges = np.flatnonzero(boundaries)
    confirmed = np.zeros(len(spatial), dtype=bool)
    for start, stop in zip(edges[:-1], edges[1:]):
        if preference[start] >= 0 and stop - start >= confirmation:
            # Offline confirmation backdates support to the first observed
            # contact, avoiding a fixed confirmation-delay shift in boundaries.
            confirmed[start:stop] = True
    teams = np.full((len(spatial), 2), 0.5)
    teams[confirmed] = softmax(-distances[confirmed] / temperature, axis=1)
    return teams, confirmed


def accumulated_control_evidence(spatial, deadball, temperature, settings):
    """Confirm nearby control using time-weighted evidence, not a hard margin.

    Weak consistent advantages take longer than strong contacts. Confirmed
    likelihoods are bounded so one extreme tracker reading cannot overwhelm the
    HMM. This remains an uncalibrated control proxy, not player-level ground truth.
    """
    fps = settings.get('fps', 25.)
    duration = settings.get('confirmation_seconds', .24)
    distance = settings.get('max_distance_m', 2.)
    margin = settings.get('strong_margin_m', 2.)
    dead_limit = settings.get('max_dead_probability', .2)
    lower = settings.get('min_evidence_probability', 2 / 3)
    upper = settings.get('max_evidence_probability', .9)
    decay = settings.get('neutral_decay', 1.)
    if (not np.isfinite([fps, duration, distance, margin, dead_limit, lower, upper,
                         decay, temperature]).all() or min(fps, duration, distance, margin,
                                                          decay, temperature) <= 0
            or not 0 <= dead_limit < 1 or not .5 < lower <= upper < 1):
        raise ValueError('Invalid accumulated-control settings')
    if not spatial.index.equals(deadball.index):
        raise ValueError('Control evidence requires aligned spatial and dead-ball frames')
    distances = spatial[['dist_nearest_H', 'dist_nearest_A']].to_numpy()
    observed = (np.isfinite(distances).all(axis=1)
                & np.isfinite(spatial[['ball_x', 'ball_y']]).all(axis=1).to_numpy()
                & ~spatial.ball_is_imputed.to_numpy()
                & (spatial.gap_length_frames.to_numpy() == 0)
                & (spatial.half.to_numpy() > 0)
                & ~deadball.is_out_of_bounds.to_numpy()
                & (deadball.is_dead_ball_prob.to_numpy() <= dead_limit))
    near, far = distances.min(axis=1), distances.max(axis=1)
    preference = distances.argmin(axis=1)
    eligible = observed & (near <= distance) & (far > near)
    strength = np.clip((far - near) / margin, 0, 1)
    confirmed = np.zeros(len(spatial), dtype=bool)
    frames, halves = spatial.index.to_numpy(), spatial.half.to_numpy()
    team, score, accepted, pending = -1, 0., False, []
    for i in range(len(spatial)):
        if (not observed[i] or (i and (halves[i] != halves[i-1] or frames[i] != frames[i-1] + 1))):
            team, score, accepted, pending = -1, 0., False, []
        if not observed[i]:
            continue
        if not eligible[i]:
            score = max(0., score - decay / fps)
            if score == 0:
                team, accepted, pending = -1, False, []
            continue
        if preference[i] != team:
            team, score, accepted, pending = int(preference[i]), 0., False, []
        score = min(duration, score + strength[i] / fps)
        if accepted:
            confirmed[i] = True
        else:
            pending.append(i)
            if score + 1e-12 >= duration:
                confirmed[pending] = True
                pending = []
                accepted = True
    teams = np.full((len(spatial), 2), .5)
    if confirmed.any():
        base = softmax(-distances[confirmed] / temperature, axis=1)
        confidence = np.clip(base.max(axis=1), lower, upper)
        rows = np.flatnonzero(confirmed)
        teams[rows, preference[confirmed]] = confidence
        teams[rows, 1 - preference[confirmed]] = 1 - confidence
    return teams, confirmed
