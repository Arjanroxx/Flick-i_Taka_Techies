"""Offline weak continuity evidence across short, bracketed tracking outages."""
import numpy as np
from .control_evidence import sustained_control_evidence


def gap_control_evidence(spatial, deadball, temperature, control, settings):
    teams, known = sustained_control_evidence(spatial, deadball, temperature, control)
    fps = settings.get('fps', 25.)
    if not np.isfinite(fps) or fps <= 0:
        raise ValueError('Gap-control FPS must be finite and positive')
    max_gap = int(np.floor(.48 * fps))
    missing = spatial.ball_is_imputed.to_numpy() | ~np.isfinite(
        spatial[['ball_x', 'ball_y']]).all(axis=1).to_numpy()
    edges = np.flatnonzero(np.diff(np.r_[False, missing, False]))
    frames, halves = spatial.index.to_numpy(), spatial.half.to_numpy()
    dead = deadball.is_dead_ball_prob.to_numpy()
    outside = deadball.is_out_of_bounds.to_numpy()
    for start, stop in zip(edges[::2], edges[1::2]):
        if start == 0 or stop == len(spatial) or stop-start > max_gap:
            continue
        span = slice(start-1, stop+1)
        if (not known[start-1] or not known[stop]
                or teams[start-1].argmax() != teams[stop].argmax()
                or halves[start] == 0 or not (halves[span] == halves[start]).all()
                or not (np.diff(frames[span]) == 1).all()
                or (dead[span] > 1/3 + 1e-7).any() or outside[span].any()):
            continue
        owner = teams[start-1].argmax()
        teams[start:stop] = .35
        teams[start:stop, owner] = .65
    # Reconstructed continuity is never upgraded to an observed control frame.
    # P3's original uncertainty shield still applies throughout the outage.
    return teams, known
