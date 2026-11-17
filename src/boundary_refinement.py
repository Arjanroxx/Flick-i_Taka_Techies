"""Offline midpoint localization of existing H/A boundaries; no new possessions."""
import numpy as np
from .control_evidence import sustained_control_evidence


def refine_boundaries(labels, spatial, deadball, temperature, control, settings):
    fps = settings.get('fps', 25.)
    if not np.isfinite(fps) or fps <= 0:
        raise ValueError('Boundary refinement requires a positive finite FPS')
    radius = max(1, int(round(fps)))  # Fixed +/- one-second search, not fitted.
    labels = np.asarray(labels)
    if len(labels) != len(spatial):
        raise ValueError('Boundary labels and tracking must align')
    output = labels.copy()
    teams, known = sustained_control_evidence(spatial, deadball, temperature, control)
    preference = teams.argmax(axis=1)
    halves, frames = spatial.half.to_numpy(), spatial.index.to_numpy()
    edges = np.r_[0, np.flatnonzero(labels[1:] != labels[:-1])+1, len(labels)]
    for index in range(1, len(edges)-1):
        left, boundary, right = edges[index-1:index+2]
        old, new = labels[boundary-1], labels[boundary]
        if old not in ('H', 'A') or new not in ('H', 'A') or old == new:
            continue
        # Disjoint half-segment movement budgets prevent neighboring proposals
        # from crossing or deleting a short possession when applied together.
        low = boundary-min(radius, (boundary-left-1)//2)
        high = boundary+min(radius, (right-boundary-1)//2)
        span = slice(low-1, high+1)
        if (halves[boundary] == 0 or not (halves[span] == halves[boundary]).all()
                or not (np.diff(frames[span]) == 1).all()
                or deadball.is_out_of_bounds.iloc[span].any()
                or (deadball.is_dead_ball_prob.iloc[span] > 1/3+1e-7).any()):
            continue
        observed = np.flatnonzero(known[span])+low-1
        if len(observed) < 2:
            continue
        codes = preference[observed]
        changes = np.flatnonzero(codes[1:] != codes[:-1])+1
        if (len(changes) != 1 or codes[0] != (old == 'A') or codes[-1] != (new == 'A')):
            continue
        split = changes[0]
        last_old, first_new = observed[split-1], observed[split]
        proposal = int(np.floor((last_old+1+first_new)/2))
        if not low <= proposal <= high:
            continue
        if proposal < boundary:
            output[proposal:boundary] = new
        elif proposal > boundary:
            output[boundary:proposal] = old
    return output
