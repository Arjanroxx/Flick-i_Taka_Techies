"""Conservative moving-contact proxy; nearest-team stability is not player identity."""
import numpy as np
from scipy.special import softmax
from .control_evidence import sustained_control_evidence


def stable_contact_evidence(spatial, deadball, temperature, control, settings):
    teams, known = sustained_control_evidence(spatial, deadball, temperature, control)
    fps = settings.get('fps', 25.)
    if not np.isfinite(fps) or fps <= 0:
        raise ValueError('Invalid stable-contact frame rate')
    d = spatial[['dist_nearest_H', 'dist_nearest_A']].to_numpy(dtype=float)
    near = d.min(axis=1)
    preference = d.argmin(axis=1)
    frames, halves = spatial.index.to_numpy(), spatial.half.to_numpy()
    valid = (np.isfinite(d).all(axis=1) & np.isfinite(spatial[['ball_x', 'ball_y']]).all(axis=1)
        & ~spatial.ball_is_imputed.to_numpy() & (spatial.gap_length_frames.to_numpy() == 0)
        & (halves > 0) & ~deadball.is_out_of_bounds.to_numpy()
        & (deadball.is_dead_ball_prob.to_numpy() <= .2)
        & (near <= 2.) & (np.abs(d[:, 1]-d[:, 0]) >= .5)
        & spatial.ball_speed.between(1., 12.).to_numpy())
    valid = np.asarray(valid)
    continuation = np.zeros(len(d), dtype=bool)
    continuation[1:] = ((np.diff(frames) == 1) & (halves[1:] == halves[:-1])
        & valid[1:] & valid[:-1] & (preference[1:] == preference[:-1])
        & (np.abs(np.diff(near))*fps <= 2.))
    # Every observation must be valid. Never accumulate contacts across a gap.
    edges = np.r_[0, np.flatnonzero(~continuation[1:])+1, len(d)]
    extra = np.zeros(len(d), dtype=bool)
    for start, stop in zip(edges[:-1], edges[1:]):
        if stop > start and valid[start] and stop-start >= max(2, int(np.ceil(.4*fps))):
            extra[start:stop] = True
    extra &= ~known
    teams[extra] = softmax(-d[extra]/temperature, axis=1)
    return teams, known | extra
