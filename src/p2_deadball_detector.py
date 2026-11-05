"""Weak stoppage evidence from automatic tags and ball kinematics."""
import numpy as np
import pandas as pd

from games import GAME, GAMES
from starter.load_smart_tagging import load
from .contracts import FRAME_COUNT, FRAMES, SCHEMAS

SET_PIECE_TYPES = {
    "throw-in": "throw_in", "corner kick": "corner", "free kick": "free_kick",
    "goal kick": "goal_kick", "kick off (start)": "kick_off",
    "kick off (after goal)": "kick_off", "penalty": "penalty", "foul": "foul",
}


def out_of_bounds(x, y, pitch):
    """Check unclipped coordinates so boundary crossings remain observable."""
    return (x < 0) | (x > pitch["length"]) | (y < 0) | (y > pitch["width"])


def build_mask(config, spatial, events):
    thresholds = config["thresholds"]
    length, width = GAMES[GAME]["pitch"]
    outside = out_of_bounds(spatial.ball_x, spatial.ball_y, {"length": length, "width": width})
    probability = np.full(FRAME_COUNT, 0.05, dtype="float32")
    probability[outside] = 0.98
    types = np.full(FRAME_COUNT, "none", dtype=object)
    restarts = np.zeros(FRAME_COUNT, dtype=bool)
    spikes = ((spatial.ball_speed >= thresholds["restart_speed"])
              & (spatial.ball_accel >= thresholds["restart_accel"])
              & ~spatial.ball_is_imputed & ~outside)
    for event in events:
        if (event["code"] or "").strip().casefold() != "set pieces":
            continue
        tags = {key.casefold(): value for key, value in event["tags"].items() if key}
        piece = SET_PIECE_TYPES.get((tags.get("type") or "").strip().casefold())
        if piece is None:
            continue
        start = max(0, event["start_frame"])
        stop = min(FRAME_COUNT, event["end_frame"])
        if start >= stop:
            continue
        types[start:stop] = piece
        candidates = np.flatnonzero(spikes.iloc[start:stop].to_numpy()
                                    & (spatial.half.iloc[start:stop].to_numpy() != 0))
        if len(candidates):
            restart = start + candidates[0]
            restarts[restart] = True
            probability[start:restart] = np.maximum(probability[start:restart], 0.7)
        else:
            # A phase window is not an exact restart or proof of dead ball.
            stationary = spatial.ball_speed.iloc[start:stop].to_numpy() < thresholds["stationary_speed"]
            probability[start:stop] = np.maximum(probability[start:stop], np.where(stationary, 0.6, 0.2))
    probability[spatial.half.to_numpy() == 0] = 1
    return pd.DataFrame({
        "is_dead_ball_prob": probability, "is_out_of_bounds": outside,
        "active_set_piece_type": types, "restart_frame_flag": restarts,
    }, index=FRAMES).astype(SCHEMAS["deadball"])


def run(config, spatial):
    return build_mask(config, spatial, load(data_dir=config["data"]["directory"]))
