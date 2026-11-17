"""Smoothed possession sequence over P1 spatial features and P2 stoppage evidence."""
import numpy as np
import pandas as pd
from scipy.special import softmax

from .contracts import SCHEMAS, entropy

DECODERS = ("posterior", "viterbi")
STATES = np.array(list("HAD"))


def _half_blocks(halves):
    """[(start, stop)] for each contiguous run, with the half value at its first frame."""
    edges = np.r_[0, np.flatnonzero(halves[1:] != halves[:-1]) + 1, len(halves)]
    return [(start, stop, halves[start]) for start, stop in zip(edges[:-1], edges[1:])]


def check_transition(transition):
    matrix = np.asarray(transition, dtype=float)
    if (matrix.shape != (3, 3) or not np.isfinite(matrix).all()
            or (matrix < 0).any() or not np.allclose(matrix.sum(axis=1), 1)):
        raise ValueError("HMM transition must be a finite 3x3 row-stochastic matrix")
    return matrix


def team_evidence(spatial, temperature=1.0):
    """Distance-based team preference and the frames where it is observable.

    An absent team observation provides no preference, rather than a fake distance.
    ``temperature`` divides the metre distances before the softmax; it is the
    calibration knob tested by the P3 fixture experiments (1.0 retains the baseline).
    """
    if not np.isfinite(temperature) or temperature <= 0:
        raise ValueError("Emission temperature must be a positive finite number")
    distances = spatial[["dist_nearest_H", "dist_nearest_A"]].to_numpy()
    known = np.isfinite(distances).all(axis=1) & ~spatial.ball_is_imputed.to_numpy()
    teams = np.full((len(spatial), 2), 0.5)
    if known.any():
        teams[known] = softmax(-distances[known] / temperature, axis=1)
    return teams, known


def build_emissions(spatial, deadball, config):
    """Normalized (frames, 3) H/A/D emissions and the observed-team mask."""
    dead = deadball.is_dead_ball_prob.to_numpy()
    temperature = config.get("hmm", {}).get("emission_temperature", 1.0)
    teams, known = team_evidence(spatial, temperature)
    emissions = np.column_stack((teams * (1 - dead[:, None]), dead))
    emissions = np.maximum(emissions, 1e-12)
    emissions /= emissions.sum(axis=1, keepdims=True)
    return emissions, known


def forward_backward(emissions, halves, transition):
    """Forward-backward posteriors, reset independently at every half boundary."""
    probs = np.empty_like(emissions)
    for start, stop, half in _half_blocks(halves):
        if half == 0:
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
    return probs


def viterbi(emissions, halves, transition):
    """Single most-likely state path, decoded independently inside each half."""
    labels = np.full(len(emissions), "X", dtype="<U1")
    log_emissions = np.log(emissions)
    log_transition = np.log(transition)
    for start, stop, half in _half_blocks(halves):
        if half == 0:
            continue
        score = np.log(np.full(3, 1 / 3)) + log_emissions[start]
        back = np.empty((stop - start, 3), dtype=np.int8)
        back[0] = -1
        for offset, frame in enumerate(range(start + 1, stop)):
            candidate = score[:, None] + log_transition
            back[offset + 1] = candidate.argmax(axis=0)
            score = candidate.max(axis=0) + log_emissions[frame]
        state = int(score.argmax())
        path = np.empty(stop - start, dtype=np.int8)
        path[-1] = state
        for offset in range(stop - start - 1, 0, -1):
            state = int(back[offset][state])
            path[offset - 1] = state
        labels[start:stop] = STATES[path]
    return labels


def decode(config, spatial, deadball):
    """Posteriors, entropy and the configured decoded label path."""
    transition = check_transition(config["hmm"]["transition"])
    decoder = config.get("hmm", {}).get("decoder", "posterior")
    if decoder not in DECODERS:
        raise ValueError(f"HMM decoder must be one of {DECODERS}")
    emissions, known = build_emissions(spatial, deadball, config)
    halves = spatial.half.to_numpy()
    probs = forward_backward(emissions, halves, transition)
    uncertainty = entropy(probs)
    labels = STATES[probs.argmax(axis=1)].copy()
    if decoder == "viterbi":
        labels = viterbi(emissions, halves, transition)
    thresholds = config["thresholds"]
    short_gap = spatial.gap_length_frames.between(1, thresholds["short_gap"]).to_numpy()
    shield = (short_gap | ~known) & (uncertainty >= thresholds["entropy"]) & (labels != "D")
    labels[shield] = "X"
    labels[halves == 0] = "X"
    result = pd.DataFrame(probs, index=spatial.index, columns=["prob_H", "prob_A", "prob_D"])
    return result.assign(state_entropy=uncertainty, raw_label=labels).astype(SCHEMAS["predictions"])


def run(config, spatial, deadball):
    return decode(config, spatial, deadball)
