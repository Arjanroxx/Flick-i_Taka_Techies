"""Two-phase H/A duration model with a geometric tail and original D evidence.

The phases are hidden possession age, not extra submission labels. Both young
and mature possessions can end; no fixed minimum or maximum duration is imposed.
"""
import numpy as np

LABEL_STATE = np.array([0, 0, 1, 1, 2])


def phase_transition(base, scale_seconds, fps):
    if (np.shape(base) != (3, 3) or not np.isfinite([scale_seconds, fps]).all()
            or scale_seconds <= 0 or fps <= 0):
        raise ValueError('Duration model requires a constant 3-state transition and positive scale/FPS')
    matrix = np.zeros((5, 5))
    rate = -np.expm1(-2 / (scale_seconds * fps))
    for team in (0, 1):
        young, mature, other = 2*team, 2*team+1, 2*(1-team)
        dead = base[team, 2]
        early_exit = .1 * base[team, 1-team]
        advance = min(rate, 1-dead-early_exit)
        late_exit = min(rate, 1-dead)
        matrix[young, [young, mature, other, 4]] = [1-dead-early_exit-advance, advance, early_exit, dead]
        matrix[mature, [mature, other, 4]] = [1-dead-late_exit, late_exit, dead]
    matrix[4, [0, 2, 4]] = base[2]
    if not np.isfinite(matrix).all() or (matrix < 0).any() or not np.allclose(matrix.sum(axis=1), 1):
        raise ValueError('Invalid duration transition probabilities')
    return matrix


def infer_block(emissions, transition):
    """Exact forward-backward and MAP hidden-phase path for one playing block."""
    n, states = emissions.shape
    prior = np.array([1/6, 1/6, 1/6, 1/6, 1/3])
    alpha = np.empty_like(emissions)
    back = np.empty((n, states), dtype=np.int8)
    with np.errstate(divide='ignore'):
        log_t = np.log(transition)
    score = np.log(prior) + np.log(emissions[0])
    for i in range(n):
        posterior = prior * emissions[i]
        alpha[i] = posterior / posterior.sum()
        prior = alpha[i] @ transition
        if i:
            candidate = score[:, None] + log_t
            back[i] = candidate.argmax(axis=0)
            score = candidate.max(axis=0) + np.log(emissions[i])
    path = np.empty(n, dtype=np.int8)
    path[-1] = score.argmax()
    for i in range(n-1, 0, -1):
        path[i-1] = back[i, path[i]]
    beta = np.ones(states)
    for i in range(n-1, -1, -1):
        posterior = alpha[i] * beta
        alpha[i] = posterior / posterior.sum()
        beta = transition @ (emissions[i] * beta)
        beta /= beta.sum()
    return alpha, path


def decode_duration(emissions, halves, base, settings):
    transition = phase_transition(base, settings['scale_seconds'], settings['fps'])
    probs = np.zeros_like(emissions)
    labels = np.full(len(emissions), 'X', dtype='<U1')
    edges = np.r_[0, np.flatnonzero(halves[1:] != halves[:-1])+1, len(halves)]
    for start, stop in zip(edges[:-1], edges[1:]):
        if halves[start] == 0:
            probs[start:stop, 2] = 1
            continue
        alpha, path = infer_block(emissions[start:stop, LABEL_STATE], transition)
        probs[start:stop] = np.column_stack([alpha[:, :2].sum(axis=1),
                                            alpha[:, 2:4].sum(axis=1), alpha[:, 4]])
        labels[start:stop] = np.array(list('HAD'))[LABEL_STATE[path]]
    return probs, labels
