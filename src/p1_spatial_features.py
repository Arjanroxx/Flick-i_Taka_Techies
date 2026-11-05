"""Tactical ATD baseline in metres, with conservative short-gap interpolation."""
import numpy as np
import pandas as pd

from games import GAME, GAMES, require
from starter.baseline import team_of_each_track
from starter.load_atd import video_frame_of
from starter.load_homography import unproject
from .contracts import FRAME_COUNT, FRAMES, SCHEMAS, frame_halves


def project(points, homography):
    """Image pixels to metres, using the inverse of the supplied pitch-to-image matrix."""
    points = np.asarray(points, dtype=float)
    x, y = unproject(homography, points[:, 0], points[:, 1])
    return np.column_stack((x, y)) * GAMES[GAME]["pitch"]


def load_tracking(data_dir=None):
    """Stream the official raw format without assigning identities to team slots."""
    meta, raw = require(["atd_meta", "atd_raw"], data_dir=data_dir)
    teams = team_of_each_track(meta)
    players = np.full((FRAME_COUNT, len(teams), 3), np.nan, dtype="float32")
    ball = np.full((FRAME_COUNT, 2), np.nan, dtype="float32")
    count = 0
    with open(raw, encoding="utf-8-sig") as handle:
        for count, line in enumerate(handle, start=1):
            frame_id, slots_text, ball_text = line.strip().split(":")
            frame = video_frame_of(frame_id)
            if frame != count - 1 or frame >= FRAME_COUNT:
                raise ValueError(f"ATD must have contiguous frame IDs 1..{FRAME_COUNT}")
            slots = np.fromstring(slots_text.replace(";", ","), sep=",")
            observation = np.fromstring(ball_text, sep=",")
            if len(slots) != len(teams) * 3 or len(observation) < 2:
                raise ValueError(f"Unexpected ATD field count at frame {frame}")
            players[frame] = slots.reshape(-1, 3)
            ball[frame] = observation[:2]
    if count != FRAME_COUNT:
        raise ValueError(f"ATD has {count} rows, expected {FRAME_COUNT}")
    scale = np.asarray(GAMES[GAME]["pitch"])
    players[:, :, :2] *= scale
    ball *= scale
    return ball, players, teams


def build_features(ball, players, teams, short_gap):
    halves = frame_halves()
    table = pd.DataFrame(np.nan, index=FRAMES, columns=list(SCHEMAS["spatial"]))
    table["half"] = halves
    table["ball_is_imputed"] = False
    table["gap_length_frames"] = 0
    table["local_density_H_3m"] = 0
    table["local_density_A_3m"] = 0
    filled = ball.copy()
    missing = ~np.isfinite(ball).all(axis=1)
    filled[missing] = np.nan
    for half in (1, 2):
        indices = np.flatnonzero(halves == half)
        start, stop = indices[0], indices[-1] + 1
        flags = np.r_[False, missing[start:stop], False]
        starts = np.flatnonzero(~flags[:-1] & flags[1:]) + start
        ends = np.flatnonzero(flags[:-1] & ~flags[1:]) + start
        for left, right in zip(starts, ends):
            table.loc[left:right - 1, "gap_length_frames"] = right - left
            if right - left <= short_gap and left > start and right < stop:
                for axis in (0, 1):
                    filled[left:right, axis] = np.interp(
                        np.arange(left, right), [left - 1, right], filled[[left - 1, right], axis]
                    )
                table.loc[left:right - 1, "ball_is_imputed"] = True
        # Derivatives never cross a half boundary or an unresolved gap.
        velocity = np.full((stop - start, 2), np.nan, dtype="float32")
        velocity[1:] = np.diff(filled[start:stop], axis=0) * GAMES[GAME]["fps"]
        speed = np.linalg.norm(velocity, axis=1)
        acceleration = np.full(len(speed), np.nan, dtype="float32")
        acceleration[1:] = np.linalg.norm(np.diff(velocity, axis=0), axis=1) * GAMES[GAME]["fps"]
        table.loc[start:stop - 1, ["ball_vx", "ball_vy"]] = velocity
        table.loc[start:stop - 1, "ball_speed"] = speed
        table.loc[start:stop - 1, "ball_accel"] = acceleration
    filled[halves == 0] = np.nan
    table[["ball_x", "ball_y"]] = filled
    for team, label in enumerate(("H", "A")):
        slots = players[:, teams == team]
        if slots.shape[1] == 0:
            raise ValueError(f"No tracking slots for team {label}")
        distances = np.linalg.norm(slots[:, :, :2] - filled[:, None, :], axis=2)
        ranked = np.where(np.isfinite(distances), distances, np.inf)
        nearest = ranked.argmin(axis=1)
        distance = ranked[np.arange(FRAME_COUNT), nearest]
        available = np.isfinite(distance)
        table[f"dist_nearest_{label}"] = np.where(available, distance, np.nan)
        player_velocity = np.full_like(slots[:, :, :2], np.nan)
        player_velocity[1:] = np.diff(slots[:, :, :2], axis=0) * GAMES[GAME]["fps"]
        player_velocity[np.r_[True, halves[1:] != halves[:-1]]] = np.nan
        nearest_velocity = player_velocity[np.arange(FRAME_COUNT), nearest]
        ball_velocity = table[["ball_vx", "ball_vy"]].to_numpy()
        table[f"rel_vel_nearest_{label}"] = np.where(
            available, np.linalg.norm(ball_velocity - nearest_velocity, axis=1), np.nan
        )
        table[f"local_density_{label}_3m"] = (distances <= 3).sum(axis=1)
    # Distance-based proxy until P1 implements geometric local Voronoi control.
    home, away = table.dist_nearest_H, table.dist_nearest_A
    table["voronoi_control_H"] = (away + 0.01) / (home + away + 0.02)
    return table.astype(SCHEMAS["spatial"])


def run(config):
    if config["data"]["source"] != "tactical":
        raise ValueError("Submission features require tactical tracking; broadcast needs synchronization")
    ball, players, teams = load_tracking(config["data"]["directory"])
    return build_features(ball, players, teams, config["thresholds"]["short_gap"])
