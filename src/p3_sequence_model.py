"""Smoothed possession sequence over P1 spatial features and P2 stoppage evidence."""
import numpy as np
import pandas as pd
from scipy.special import softmax

from .contracts import SCHEMAS, entropy

DECODERS = ("posterior", "viterbi", "duration")
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
    dead = deadball.is_dead_ball_prob.to_numpy(dtype=float)
    # Contract B stores float32. Restore the exact neutral weight so rounding
    # cannot break an otherwise symmetric missing-evidence Viterbi tie.
    dead = np.where(np.isclose(dead, 1 / 3, rtol=0, atol=1e-7), 1 / 3, dead)
    temperature = config.get("hmm", {}).get("emission_temperature", 1.0)
    mode = config.get("hmm", {}).get("team_evidence", "distance")
    if mode == "distance":
        teams, known = team_evidence(spatial, temperature)
    elif mode == "sustained_control":
        from .control_evidence import sustained_control_evidence
        teams, known = sustained_control_evidence(
            spatial, deadball, temperature, config.get("control", {}))
    elif mode == 'gap_control':
        from .gap_control import gap_control_evidence
        teams, known = gap_control_evidence(spatial, deadball, temperature,
            config.get('control', {}), config.get('gap_control', {}))
    elif mode == 'stable_contact':
        from .stable_contact import stable_contact_evidence
        teams, known = stable_contact_evidence(spatial, deadball, temperature,
            config.get('control', {}), config.get('stable_contact', {}))
    elif mode == 'learned_control':
        from .learned_control import learned_control_evidence
        teams, known = learned_control_evidence(
            spatial, deadball, temperature, config.get('control', {}), config['learned_control'])
    else:
        raise ValueError("Unknown team evidence mode: " + str(mode))
    emissions = np.column_stack((teams * (1 - dead[:, None]), dead))
    emissions = np.maximum(emissions, 1e-12)
    emissions /= emissions.sum(axis=1, keepdims=True)
    power = config.get('hmm', {}).get('emission_power', 1.0)
    if not np.isfinite(power) or power <= 0:
        raise ValueError('Emission power must be finite and positive')
    if power != 1:
        # External lower-rate observations represent more elapsed time. This
        # option is never enabled for the 25 Hz competition configuration.
        emissions = softmax(np.log(emissions) * power, axis=1)
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
            step = transition[frame + 1] if transition.ndim == 3 and frame + 1 < stop else transition
            if frame + 1 < stop:
                prior = probs[frame] @ step
        backward = np.ones(3)
        for frame in range(stop - 1, start - 1, -1):
            posterior = probs[frame] * backward
            probs[frame] = posterior / posterior.sum()
            step = transition[frame] if transition.ndim == 3 else transition
            backward = step @ (emissions[frame] * backward)
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
            step = log_transition[frame] if transition.ndim == 3 else log_transition
            candidate = score[:, None] + step
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
    if 'contact_switch_probability' in config.get('hmm', {}):
        from .contact_transitions import transition_schedule
        transition = transition_schedule(spatial, deadball, transition, config)
    halves = spatial.half.to_numpy()
    if decoder == 'duration':
        from .duration_model import decode_duration
        probs, labels = decode_duration(emissions, halves, transition, config['duration'])
    else:
        probs = forward_backward(emissions, halves, transition)
        labels = STATES[probs.argmax(axis=1)].copy()
    uncertainty = entropy(probs)
    if decoder == "viterbi":
        labels = viterbi(emissions, halves, transition)
    if config.get('boundary_refinement', {}).get('enabled', False):
        from .boundary_refinement import refine_boundaries
        labels = refine_boundaries(labels, spatial, deadball,
            config.get('hmm', {}).get('emission_temperature', 1.),
            config.get('control', {}), config['boundary_refinement'])
    thresholds = config["thresholds"]
    if not np.isfinite(thresholds["entropy"]) or not 0 <= thresholds["entropy"] <= np.log(3):
        raise ValueError("Entropy threshold must be between zero and log(3) nats")
    short_gap = spatial.gap_length_frames.between(1, thresholds["short_gap"]).to_numpy()
    team_limit = thresholds.get("team_uncertainty", 0.9)
    if not np.isfinite(team_limit) or not 0 <= team_limit <= 1:
        raise ValueError("Team uncertainty threshold must be between zero and one")
    conditional = probs[:, :2] / np.maximum(probs[:, :2].sum(axis=1, keepdims=True), 1e-12)
    team_uncertainty = entropy(conditional) / np.log(2)
    ambiguous = (uncertainty >= thresholds["entropy"]) | (team_uncertainty >= team_limit)
    shield = (short_gap | ~known) & ambiguous & (labels != "D")
    labels[shield] = "X"
    labels[halves == 0] = "X"
    result = pd.DataFrame(probs, index=spatial.index, columns=["prob_H", "prob_A", "prob_D"])
    return result.assign(state_entropy=uncertainty, raw_label=labels).astype(SCHEMAS["predictions"])


def run(config, spatial, deadball):
    return decode(config, spatial, deadball)
