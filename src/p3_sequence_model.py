import numpy as np
import pandas as pd
from scipy.special import softmax

from .contracts import SCHEMAS, entropy

def run(config, spatial, deadball):
    dead = deadball.is_dead_ball_prob.to_numpy()
    distances = spatial[["dist_nearest_H", "dist_nearest_A"]].to_numpy()
    # An absent team observation provides no preference, rather than a fake distance.
    known = np.isfinite(distances).all(axis=1)
    teams = np.full((len(spatial), 2), 0.5)
    teams[known] = softmax(-distances[known], axis=1)
    emissions = np.column_stack((teams * (1 - dead[:, None]), dead))
    emissions = np.maximum(emissions, 1e-12)
    emissions /= emissions.sum(axis=1, keepdims=True)
    transition = np.asarray(config["hmm"]["transition"], dtype=float)
    if (transition.shape != (3, 3) or not np.isfinite(transition).all()
            or (transition < 0).any() or not np.allclose(transition.sum(axis=1), 1)):
        raise ValueError("HMM transition must be a finite 3x3 row-stochastic matrix")
    probs = np.empty_like(emissions)
    halves = spatial.half.to_numpy()
    boundaries = np.r_[0, np.flatnonzero(halves[1:] != halves[:-1]) + 1, len(halves)]
    for start, stop in zip(boundaries[:-1], boundaries[1:]):
        if halves[start] == 0:
            probs[start:stop] = (0, 0, 1)
            continue
        # Normalize at every step to avoid underflow across a full half.
        prior = np.full(3, 1 / 3)
        for frame in range(start, stop):
            posterior = prior * emissions[frame]
            probs[frame] = posterior / posterior.sum()
            prior = probs[frame] @ transition
        backward = np.ones(3)
        for frame in range(stop - 1, start - 1, -1):
            posterior = probs[frame] * backward
            probs[frame] = posterior / posterior.sum()
            backward = transition @ (emissions[frame] * backward)
            backward /= backward.sum()
    uncertainty = entropy(probs)
    labels = np.array(list("HAD"))[probs.argmax(axis=1)]
    thresholds = config["thresholds"]
    short_gap = spatial.gap_length_frames.between(1, thresholds["short_gap"])
    shield = (short_gap | ~known) & (uncertainty >= thresholds["entropy"]) & (labels != "D")
    labels[shield] = "X"
    labels[halves == 0] = "X"
    result = pd.DataFrame(probs, index=spatial.index, columns=["prob_H", "prob_A", "prob_D"])
    return result.assign(state_entropy=uncertainty, raw_label=labels).astype(SCHEMAS["predictions"])
