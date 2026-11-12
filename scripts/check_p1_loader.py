"""P1 loader checks: tactical ATD alignment, real missingness, synthetic gap handling.

Run from the repository root with the tactical bundle in ./data (or MTAH_DATA_DIR):

    .venv/Scripts/python.exe scripts/check_p1_loader.py [--write-a]

Prints a JSON report and exits non-zero if any check fails. --write-a additionally
regenerates artifacts/spatial_features.parquet (handoff A) from the current code.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games import GAME, GAMES, half_video_blocks  # noqa: E402
from src import p1_spatial_features as p1  # noqa: E402
from src.contracts import FRAME_COUNT, SCHEMAS, frame_halves, validate, write  # noqa: E402
from starter.load_atd import check_alignment_raw  # noqa: E402


def real_tracking_report():
    """Alignment plus missing-value statistics on the delivered tactical tracking."""
    alignment = check_alignment_raw()
    ball, players, teams = p1.load_tracking()
    halves = frame_halves()
    playing = halves != 0

    ball_missing = ~np.isfinite(ball).all(axis=1)
    player_missing = ~np.isfinite(players[:, :, :2]).all(axis=2)

    report = {
        "alignment": {
            "n_records": alignment["n_records"],
            "frame_id_range": list(alignment["frame_id_range"]),
            "contiguous": alignment["contiguous"],
            "first_video_frame": alignment["first_video_frame"],
            "agrees_frame_id_minus_1": alignment["agrees"],
        },
        "teams": {
            "H_slots": int((teams == 0).sum()),
            "A_slots": int((teams == 1).sum()),
            "total_slots": int(len(teams)),
        },
        "ball_missing": {
            "all_frames_pct": round(100.0 * ball_missing.mean(), 2),
            "play_blocks_pct": round(100.0 * ball_missing[playing].mean(), 2),
            "half_1_pct": round(100.0 * ball_missing[halves == 1].mean(), 2),
            "half_2_pct": round(100.0 * ball_missing[halves == 2].mean(), 2),
            "outside_play_frames": int((ball_missing & ~playing).sum()),
        },
        "player_missing": {
            "all_frames_pct": round(100.0 * player_missing.mean(), 2),
            "play_blocks_pct": round(100.0 * player_missing[playing].mean(), 2),
        },
        "coordinate_ranges_m": {
            "ball_x": [round(float(np.nanmin(ball[:, 0])), 2), round(float(np.nanmax(ball[:, 0])), 2)],
            "ball_y": [round(float(np.nanmin(ball[:, 1])), 2), round(float(np.nanmax(ball[:, 1])), 2)],
            "players_x": [round(float(np.nanmin(players[:, :, 0])), 2),
                          round(float(np.nanmax(players[:, :, 0])), 2)],
            "players_y": [round(float(np.nanmin(players[:, :, 1])), 2),
                          round(float(np.nanmax(players[:, :, 1])), 2)],
        },
        "coordinate_medians_m": {
            "ball_x": round(float(np.nanmedian(ball[:, 0])), 2),
            "ball_y": round(float(np.nanmedian(ball[:, 1])), 2),
            "players_x": round(float(np.nanmedian(players[:, :, 0])), 2),
            "players_y": round(float(np.nanmedian(players[:, :, 1])), 2),
        },
        "out_of_bounds_frames": {
            "ball_beyond_pitch_pct": round(100.0 * (
                ((ball[:, 0] < 0) | (ball[:, 0] > GAMES[GAME]["pitch"][0])
                 | (ball[:, 1] < 0) | (ball[:, 1] > GAMES[GAME]["pitch"][1]))
                & playing & np.isfinite(ball).all(axis=1)).sum() / max(playing.sum(), 1), 3),
        },
        "pitch_m": list(GAMES[GAME]["pitch"]),
    }

    failures = []
    if not alignment["agrees"]:
        failures.append("ATD alignment is not contiguous frame_id 1..n with video_frame = frame_id - 1")
    if int((teams == 0).sum()) == 0 or int((teams == 1).sum()) == 0:
        failures.append("tracking metadata produced an empty team")
    # Coordinates are normalised 0-1 upstream, so metres must land in a sane neighbourhood
    # of the pitch. Tracker drift pushes a few percent of frames out of bounds (preserved on
    # purpose for P2), so the bound is deliberately loose; the median check is what catches a
    # forgotten scale or swapped axes, which a min/max bound alone would miss.
    pitch_x, pitch_y = GAMES[GAME]["pitch"]
    for name, (lo, hi) in report["coordinate_ranges_m"].items():
        axis = pitch_x if name.endswith("_x") else pitch_y
        if lo < -0.5 * axis or hi > 1.5 * axis:
            failures.append(f"{name} range [{lo}, {hi}] is outside pitch +/-50%")
    for name, value in report["coordinate_medians_m"].items():
        axis = pitch_x if name.endswith("_x") else pitch_y
        if not 0.1 * axis < value < 0.9 * axis:
            failures.append(f"{name} median {value} m is not a plausible on-pitch value")
    return report, failures, (ball, players, teams, halves)


def synthetic_report(short_gap):
    """Missing-observation fixtures through build_features + the spatial contract."""
    halves = frame_halves()
    play1 = np.flatnonzero(halves == 1)
    play2 = np.flatnonzero(halves == 2)
    start1, stop1 = play1[0], play1[-1] + 1
    start2, stop2 = play2[0], play2[-1] + 1

    teams = np.array([0, 0, 1, 1], dtype=np.int8)  # two slots per team
    players = np.full((FRAME_COUNT, 4, 3), np.nan, dtype="float32")
    # Two stationary players per team, 2 m apart, somewhere inside each half.
    for half_start, half_stop in ((start1, stop1), (start2, stop2)):
        players[half_start:half_stop, 0, :2] = (50.0, 30.0)
        players[half_start:half_stop, 1, :2] = (50.0, 32.0)
        players[half_start:half_stop, 2, :2] = (55.0, 30.0)
        players[half_start:half_stop, 3, :2] = (55.0, 32.0)

    ball = np.full((FRAME_COUNT, 2), np.nan, dtype="float32")
    ball[start1:stop1] = (51.0, 31.0)
    ball[start2:stop2] = (51.0, 31.0)

    cases = {}

    # 1. Short mid-half gap (5 frames <= short_gap): interpolated, flagged, length recorded.
    short_left = start1 + 200
    ball[short_left:short_left + 5] = np.nan
    cases["short_gap"] = {"left": short_left, "length": 5}

    # 2. Long mid-half gap (50 frames > short_gap): stays missing, length recorded.
    long_left = start1 + 400
    ball[long_left:long_left + 50] = np.nan
    cases["long_gap"] = {"left": long_left, "length": 50}

    # 3. Edge gap at the very start of the half: never interpolated (no left neighbour).
    ball[start1:start1 + 4] = np.nan
    cases["edge_gap"] = {"left": start1, "length": 4}

    # 4. Gap touching the last frame of half 1: never interpolated (no right neighbour),
    #    so nothing can bridge into halftime.
    ball[stop1 - 4:stop1] = np.nan
    cases["half_end_gap"] = {"left": stop1 - 4, "length": 4}

    table = p1.build_features(ball, players, teams, short_gap)
    validate("spatial", table)

    checks = []

    def check(name, ok, detail):
        checks.append({"check": name, "ok": bool(ok), "detail": detail})

    left, length = cases["short_gap"]["left"], cases["short_gap"]["length"]
    filled = table.iloc[left:left + length]
    check("short_gap_imputed",
          bool(filled.ball_is_imputed.all() and filled.ball_x.notna().all()),
          f"frames {left}..{left + length - 1}")
    check("short_gap_length_recorded",
          int(table.gap_length_frames.iloc[left]) == length,
          f"gap_length_frames={int(table.gap_length_frames.iloc[left])}")

    left, length = cases["long_gap"]["left"], cases["long_gap"]["length"]
    filled = table.iloc[left:left + length]
    check("long_gap_preserved_missing",
          bool(filled.ball_x.isna().all() and (~filled.ball_is_imputed).all()),
          f"frames {left}..{left + length - 1}")
    check("long_gap_length_recorded",
          int(table.gap_length_frames.iloc[left]) == length,
          f"gap_length_frames={int(table.gap_length_frames.iloc[left])}")

    left, length = cases["edge_gap"]["left"], cases["edge_gap"]["length"]
    check("edge_gap_not_interpolated",
          bool(table.ball_x.iloc[left:left + length].isna().all()),
          f"half start frames {left}..{left + length - 1}")

    left, length = cases["half_end_gap"]["left"], cases["half_end_gap"]["length"]
    check("half_end_gap_not_interpolated",
          bool(table.ball_x.iloc[left:left + length].isna().all()),
          f"frames {left}..{left + length - 1} stay missing across halftime")

    # No interpolated position anywhere outside the published play blocks.
    check("outside_play_stays_nan",
          bool(table.ball_x[halves == 0].isna().all()),
          "half=0 frames have no ball coordinates")

    # Imputed flag can only appear where both coordinates exist (contract rule) and only
    # on frames inside a half.
    bad_imputed = table.ball_is_imputed & (table.ball_x.isna() | table.ball_y.isna())
    check("imputed_implies_coordinates", bool(~bad_imputed.any()),
          f"{int(bad_imputed.sum())} violations")

    # Half column must match the official blocks, and velocity must not bridge halves:
    # the first frame of each half has no within-half predecessor, so its speed is NaN.
    check("half_column_matches_blocks", bool(np.array_equal(table.half, halves)),
          "half=0 outside 11185..90651 and 110808..190197")
    check("half_start_speed_nan",
          bool(np.isnan(table.ball_speed.iloc[start1]) and np.isnan(table.ball_speed.iloc[start2])),
          f"ball_speed NaN at frames {start1} and {start2}")

    # Distances/densities: with the ball missing and no imputation, the ball-relative
    # observations are unavailable, so density counts are zero and distances NaN.
    missing_frame = int(np.flatnonzero(table.ball_x.isna().to_numpy() & (halves != 0))[0])
    check("missing_ball_distances_nan",
          bool(np.isnan(table.dist_nearest_H.iloc[missing_frame])
               and np.isnan(table.dist_nearest_A.iloc[missing_frame])),
          f"frame {missing_frame}")
    check("missing_ball_density_zero",
          int(table.local_density_H_3m.iloc[missing_frame]) == 0
          and int(table.local_density_A_3m.iloc[missing_frame]) == 0,
          f"frame {missing_frame}")

    # Metre conversion: the synthetic ball sits at (51, 31) m, untouched by gaps elsewhere.
    intact = int(start1 + 50)
    check("metre_coordinates_preserved",
          abs(float(table.ball_x.iloc[intact]) - 51.0) < 1e-3
          and abs(float(table.ball_y.iloc[intact]) - 31.0) < 1e-3,
          f"frame {intact} -> ({table.ball_x.iloc[intact]}, {table.ball_y.iloc[intact]})")

    # Out-of-bounds coordinates are preserved for P2 (unclipped).
    oob = ball.copy()
    oob[start1 + 600] = (-3.0, 71.0)
    oob_table = p1.build_features(oob, players, teams, short_gap)
    validate("spatial", oob_table)
    check("out_of_bounds_preserved",
          float(oob_table.ball_x.iloc[start1 + 600]) == -3.0
          and float(oob_table.ball_y.iloc[start1 + 600]) == 71.0,
          "unclipped ball position kept for P2 boundary evidence")

    failures = [c["check"] for c in checks if not c["ok"]]
    return {"short_gap_threshold": short_gap, "checks": checks}, failures


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--write-a", action="store_true",
                        help="regenerate artifacts/spatial_features.parquet from this code")
    parser.add_argument("--short-gap", type=int, default=12,
                        help="short-gap threshold used for the synthetic fixtures")
    args = parser.parse_args()

    alignment_report, alignment_failures, arrays = real_tracking_report()
    synthetic, synthetic_failures = synthetic_report(args.short_gap)

    report = {
        "real_tracking": alignment_report,
        "synthetic_missing_observation": synthetic,
        "failures": alignment_failures + synthetic_failures,
    }
    print(json.dumps(report, indent=2))

    if args.write_a:
        ball, players, teams, _ = arrays
        import yaml
        config = yaml.safe_load((ROOT / "configs" / "config.yaml").read_text(encoding="utf-8-sig"))
        table = validate("spatial", p1.build_features(
            ball, players, teams, config["thresholds"]["short_gap"]))
        path = ROOT / "artifacts" / "spatial_features.parquet"
        write("spatial", table, path)
        print(f"wrote {path} ({len(table)} rows)", file=sys.stderr)

    if report["failures"]:
        print("FAIL: " + ", ".join(report["failures"]), file=sys.stderr)
        return 1
    print("All loader checks passed.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
