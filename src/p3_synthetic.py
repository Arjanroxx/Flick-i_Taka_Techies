"""Fixed-seed synthetic possession spells for P3 development and regression checks.

The generator writes the same A and B tables the real pipeline produces, but it
knows the state behind every frame. It is a fixture, not a substitute for an
external match with frame-level possession labels: metrics computed here measure
behaviour on the generator's assumptions, not real-football accuracy.
"""
import numpy as np
import pandas as pd

from .contracts import FRAME_COUNT, FRAMES, SCHEMAS, frame_halves

SET_PIECES = ("throw_in", "corner", "free_kick", "goal_kick", "kick_off")


def _spell_labels(rng, spell_lengths=None):
    """H/A/D spells inside the published halves; X outside play."""
    halves = frame_halves()
    labels = np.full(FRAME_COUNT, "X", dtype="<U1")
    for half in (1, 2):
        frames = np.flatnonzero(halves == half)
        position = 0
        current = "H" if rng.random() < 0.5 else "A"
        while position < len(frames):
            if position and rng.random() < 0.10:
                stop = min(len(frames), position + int(rng.integers(60, 420)))
                labels[frames[position:stop]] = "D"
                position = stop
                if position >= len(frames):
                    break
            length = (int(rng.choice(spell_lengths)) if spell_lengths is not None
                      else int(np.clip(rng.geometric(1 / 355), 60, 1400)))
            stop = min(len(frames), position + length)
            labels[frames[position:stop]] = current
            position = stop
            current = "A" if current == "H" else "H"
    return labels


def _runs(mask):
    edges = np.flatnonzero(np.diff(np.r_[False, mask, False]))
    return list(zip(edges[::2], edges[1::2]))


def _gap_mask(rng, halves, rate=0.0015, low=1, high=40):
    """Occlusion runs that never cross a half boundary."""
    mask = np.zeros(FRAME_COUNT, dtype=bool)
    for half in (1, 2):
        frames = np.flatnonzero(halves == half)
        start, stop = frames[0], frames[-1] + 1
        count = max(1, int(rate * (stop - start)))
        for _ in range(count):
            left = int(rng.integers(start, max(start + 1, stop - high)))
            right = min(stop, left + int(rng.integers(low, high + 1)))
            mask[left:right] = True
    return mask


def generate(seed=0, *, spell_lengths=None):
    """Return (spatial, deadball, truth) with contracts valid and truth a label Series."""
    rng = np.random.default_rng(seed)
    halves = frame_halves()
    if spell_lengths is not None and (
            not len(spell_lengths) or any(type(n) is not int or n < 1 for n in spell_lengths)):
        raise ValueError("Synthetic spell lengths must be positive integer frame counts")
    labels = _spell_labels(rng, spell_lengths)
    n = FRAME_COUNT

    near = rng.lognormal(mean=np.log(1.8), sigma=0.5, size=n)
    margin = rng.gamma(shape=2.0, scale=1.4, size=n)
    home = near.copy()
    away = near + margin
    is_away = labels == "A"
    home[is_away], away[is_away] = (near + margin)[is_away], near[is_away]
    is_dead = labels == "D"
    home[is_dead] += rng.gamma(shape=3.0, scale=2.2, size=int(is_dead.sum()))
    away[is_dead] += rng.gamma(shape=3.0, scale=2.2, size=int(is_dead.sum())) + 1.0

    # Short observed-to-observed identity confusion bursts. These are the honest
    # kinematic jumps P1 documented, not missing observations.
    teleport = np.zeros(n, dtype=bool)
    for _ in range(int(0.0008 * n)):
        left = int(rng.integers(0, n - 30))
        teleport[left:left + int(np.clip(rng.geometric(1 / 6), 1, 30))] = True
    teleport &= ~is_dead
    home[teleport], away[teleport] = away[teleport].copy(), home[teleport].copy()

    missing = _gap_mask(rng, halves)
    short = missing.copy()
    for left, right in _runs(missing):
        if right - left > 12:
            short[left:right] = False

    gap_length = np.zeros(n, dtype=np.int32)
    for left, right in _runs(missing):
        gap_length[left:right] = right - left

    ball = np.column_stack((rng.uniform(5, 100, n), rng.uniform(5, 63, n)))
    ball[is_dead] = np.column_stack((
        rng.uniform(-2, 107, int(is_dead.sum())),
        rng.uniform(-2, 70, int(is_dead.sum())),
    ))
    ball[missing & ~short] = np.nan
    home[missing & ~short] = np.nan
    away[missing & ~short] = np.nan

    probabilities = np.full(n, 0.05, dtype=np.float64)
    outside = np.zeros(n, dtype=bool)
    set_piece = np.full(n, "none", dtype=object)
    restart = np.zeros(n, dtype=bool)
    for left, right in _runs(is_dead):
        piece = SET_PIECES[int(rng.integers(0, len(SET_PIECES)))]
        set_piece[left:right] = piece
        if rng.random() < 0.55:
            probabilities[left:right] = 0.98
            outside[left:right] = True
        else:
            probabilities[left:right] = 0.60
        if right < n and halves[right] == halves[left]:
            restart[right] = True

    # False boundary exits: short projected out-of-bounds bursts during live play.
    live = (labels != "D") & (halves != 0)
    for _ in range(int(0.0012 * live.sum())):
        candidates = np.flatnonzero(live)
        left = int(rng.choice(candidates))
        right = min(n, left + int(rng.integers(3, 9)))
        probabilities[left:right] = 0.98
        outside[left:right] = True

    spatial = pd.DataFrame(index=FRAMES)
    spatial["ball_x"] = ball[:, 0]
    spatial["ball_y"] = ball[:, 1]
    speed = np.where(is_dead, rng.uniform(0, 3, n), rng.uniform(0, 15, n))
    spatial["ball_speed"] = np.where(missing & ~short, np.nan, speed)
    spatial["ball_vx"] = np.where(missing & ~short, np.nan, rng.normal(0, 3, n))
    spatial["ball_vy"] = np.where(missing & ~short, np.nan, rng.normal(0, 3, n))
    spatial["ball_accel"] = np.where(missing & ~short, np.nan, rng.uniform(0, 8, n))
    spatial["dist_nearest_H"] = home
    spatial["dist_nearest_A"] = away
    spatial["rel_vel_nearest_H"] = rng.uniform(0, 20, n)
    spatial["rel_vel_nearest_A"] = rng.uniform(0, 20, n)
    spatial["voronoi_control_H"] = np.clip(away / (home + away), 0, 1)
    spatial["local_density_H_3m"] = rng.integers(0, 4, n)
    spatial["local_density_A_3m"] = rng.integers(0, 4, n)
    spatial["half"] = halves
    spatial["ball_is_imputed"] = short
    spatial["gap_length_frames"] = gap_length
    spatial = spatial.astype(SCHEMAS["spatial"])

    deadball = pd.DataFrame({
        "is_dead_ball_prob": probabilities,
        "is_out_of_bounds": outside,
        "active_set_piece_type": set_piece,
        "restart_frame_flag": restart,
    }, index=FRAMES).astype(SCHEMAS["deadball"])

    truth = pd.Series(labels, index=FRAMES, name="label")
    return spatial, deadball, truth


def generate_with_detector(config, seed=0):
    """Additional stress fixture: derive B through P2, not from truth weights.

    Synthetic tags deliberately omit every third stoppage. Long tracking gaps
    affect both live and stopped spells. This is a diagnostic, not a calibrated
    model of real tracking or a replacement for independent labelled matches.
    """
    from .p2_deadball_detector import build_mask

    # Boundary stress cases span one frame to one minute; their lengths are
    # independent of the public match's reported possession-duration statistic.
    spatial, _, truth = generate(seed, spell_lengths=(1, 25, 100, 250, 750, 1500))
    rng = np.random.default_rng(seed + 10000)
    halves = spatial.half.to_numpy()
    missing = _gap_mask(rng, halves, rate=0.001, low=100, high=1000)
    spatial.loc[missing, ['ball_x', 'ball_y', 'ball_speed', 'ball_vx', 'ball_vy',
                          'ball_accel', 'dist_nearest_H', 'dist_nearest_A']] = np.nan
    spatial.loc[missing, 'ball_is_imputed'] = False
    for left, right in _runs(missing):
        spatial.loc[left:right - 1, 'gap_length_frames'] = right - left
    events = []
    for index, (left, right) in enumerate(_runs(truth.to_numpy() == 'D')):
        if index % 3:
            events.append({'code': 'SET PIECES', 'tags': {'Type': 'Free Kick'},
                           'start_frame': left, 'end_frame': right})
    return spatial, build_mask(config, spatial, events), truth
