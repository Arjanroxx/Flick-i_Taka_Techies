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
