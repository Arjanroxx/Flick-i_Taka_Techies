"""Estimate frame-level stoppages from Smart Tagging and tactical ball tracking."""

import numpy as np
import pandas as pd

from games import GAME, GAMES
from starter.load_smart_tagging import load
from .contracts import FRAMES, SCHEMAS

SET_PIECE_TYPES = {
    "throw-in": "throw_in", "corner kick": "corner", "free kick": "free_kick",
    "goal kick": "goal_kick", "kick off (start)": "kick_off",
    "kick off (after goal)": "kick_off", "penalty": "penalty", "foul": "foul",
}


def out_of_bounds(x, y, pitch, margin=0):
    """Test unclipped positions in metres against the pitch rectangle."""
    return ((x < -margin) | (x > pitch["length"] + margin)
            | (y < -margin) | (y > pitch["width"] + margin))


def _runs(mask):
    edges = np.flatnonzero(np.diff(np.r_[False, mask, False]))
    return zip(edges[::2], edges[1::2])


def _tag_windows(events, blocks):
    """Intersect each recognised half-open tag interval with the play blocks."""
    windows = set()
    for event in events:
        if (event["code"] or "").strip().casefold() != "set pieces":
            continue
        tags = {key.strip().casefold(): value for key, value in event["tags"].items() if key}
        piece = SET_PIECE_TYPES.get((tags.get("type") or "").strip().casefold())
        if piece is None:
            continue
        for block_start, block_stop in blocks:
            start = max(block_start, event["start_frame"])
            stop = min(block_stop, event["end_frame"])
            if start < stop:
                windows.add((start, stop, piece))
    # Narrower windows take precedence for the displayed category.
    return sorted(windows, key=lambda window: (window[0] - window[1], *window))


def build_mask(config, spatial, events):
    thresholds = config["thresholds"]
    game = GAMES[GAME]
    length, width = game["pitch"]
    pitch = {"length": length, "width": width}
    # Defaults also support local configs copied before these settings were added.
    confirmation = thresholds.get("stoppage_confirm_frames", 3)
    margin = thresholds.get("boundary_margin_m", 0.35)
    lookback = round(thresholds.get("stoppage_lookback_seconds", 3.0) * game["fps"])
    if confirmation < 2 or margin < 0 or lookback < confirmation:
        raise ValueError("P2 needs at least two confirmation frames, a nonnegative margin and sufficient lookback")

    halves = spatial.half.to_numpy()
    x, y = spatial.ball_x.to_numpy(), spatial.ball_y.to_numpy()
    speed, accel = spatial.ball_speed.to_numpy(), spatial.ball_accel.to_numpy()
    observed = (np.isfinite(x) & np.isfinite(y) & ~spatial.ball_is_imputed.to_numpy()
                & (halves != 0))
    outside = observed & out_of_bounds(x, y, pitch)
    clearly_outside = outside & out_of_bounds(x, y, pitch, margin)
    boundary = np.zeros(len(spatial), dtype=bool)
    stationary = np.zeros(len(spatial), dtype=bool)
    moving = np.zeros(len(spatial), dtype=bool)
    candidates = np.zeros(len(spatial), dtype=bool)
    edges = np.r_[0, np.flatnonzero(halves[1:] != halves[:-1]) + 1, len(halves)]
    blocks = [(start, stop) for start, stop in zip(edges[:-1], edges[1:]) if halves[start]]

    for start, stop in blocks:
        block = slice(start, stop)
        for left, right in _runs(outside[block]):
            span = slice(start + left, start + right)
            if right - left >= confirmation and clearly_outside[span].any():
                boundary[span] = True

        # P1 speed uses two positions. Acceleration uses three. Reject derivatives
        # that depend on missing/imputed positions, even if the current position is real.
        tracked = observed[block]
        speed_ok = tracked & np.r_[False, tracked[:-1]]
        accel_ok = speed_ok & np.r_[False, speed_ok[:-1]]
        quiet = speed_ok & ~outside[block] & (speed[block] <= thresholds["stationary_speed"])
        for left, right in _runs(quiet):
            if right - left >= confirmation:
                stationary[start + left:start + right] = True

        fast = speed_ok & ~outside[block] & (speed[block] >= thresholds["restart_speed"])
        moving[block] = fast
        for left, right in _runs(fast):
            if right - left < confirmation or left == 0:
                continue
            frame = start + left
            # A sustained on-pitch return or a quiet-to-fast kick can confirm a restart.
            returned = boundary[frame - 1]
            recent_quiet = stationary[max(start, frame - confirmation - 1):frame].any()
            kicked = (recent_quiet and accel_ok[left]
                      and accel[frame] >= thresholds["restart_accel"])
            candidates[frame] = returned or kicked

    tag_probability = np.full(len(spatial), 0.05, dtype="float32")
    types = np.full(len(spatial), "none", dtype=object)
    restart_types = {}
    for start, stop, piece in _tag_windows(events, blocks):
        window = slice(start, stop)
        types[window] = piece
        possible = np.flatnonzero(candidates[window])
        if not possible.size:
            quiet_frames = stationary[window]
            weak_evidence = tag_probability[window]
            weak_evidence[quiet_frames] = np.maximum(weak_evidence[quiet_frames], 0.6)
            continue

        restart = start + possible[0]
        restart_types[restart] = piece
        lead_start = max(start, restart - lookback)
        earlier_motion = np.flatnonzero(moving[lead_start:restart])
        if earlier_motion.size:
            lead_start += earlier_motion[-1] + 1
        lead = slice(lead_start, restart)
        support = np.flatnonzero(boundary[lead] | stationary[lead])
        if support.size:
            lead = slice(lead_start + support[0], restart)
            tag_probability[lead] = 0.7

    # The restart frame itself is live evidence, including in overlapping tag windows.
    restarts = np.zeros(len(spatial), dtype=bool)
    for frame, piece in restart_types.items():
        restarts[frame] = True
        types[frame] = piece
    probability = tag_probability
    probability[restarts] = 0.05
    probability[boundary] = 0.98
    probability[halves == 0] = 1
    return pd.DataFrame({
        "is_dead_ball_prob": probability, "is_out_of_bounds": outside,
        "active_set_piece_type": types, "restart_frame_flag": restarts,
    }, index=FRAMES).astype(SCHEMAS["deadball"])


def run(config, spatial):
    return build_mask(config, spatial, load(data_dir=config["data"]["directory"]))
