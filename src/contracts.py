import numpy as np
import pandas as pd
from games import GAME, GAMES, half_video_blocks

FRAME_COUNT = GAMES[GAME]["n_video_frames"]
FRAMES = pd.Index(np.arange(FRAME_COUNT, dtype="int64"), name="frame")
LABELS = tuple("HADX")
SET_PIECES = "none throw_in corner free_kick goal_kick kick_off penalty foul".split()
SCHEMAS = {
    "spatial": {
        **dict.fromkeys(("ball_x ball_y ball_vx ball_vy ball_speed ball_accel "
                        "dist_nearest_H dist_nearest_A rel_vel_nearest_H rel_vel_nearest_A "
                        "voronoi_control_H").split(), "float32"),
        **dict.fromkeys("half local_density_H_3m local_density_A_3m".split(), "int8"),
        "ball_is_imputed": "bool", "gap_length_frames": "int32",
    },
    "deadball": {"is_dead_ball_prob": "float32", "is_out_of_bounds": "bool",
                 "active_set_piece_type": "string", "restart_frame_flag": "bool"},
    "predictions": {**dict.fromkeys("prob_H prob_A prob_D state_entropy".split(), "float32"),
                    "raw_label": "string"},
    "overrides": {"start_frame": "int64", "end_frame": "int64",
                  "override_label": "string", "confidence": "float32"},
}
BOUNDS = {
    **dict.fromkeys("prob_H prob_A prob_D is_dead_ball_prob confidence voronoi_control_H".split(), (0, 1)),
    **dict.fromkeys("start_frame end_frame".split(), (0, FRAME_COUNT - 1)),
    **dict.fromkeys(("ball_speed ball_accel dist_nearest_H dist_nearest_A rel_vel_nearest_H "
                    "rel_vel_nearest_A local_density_H_3m local_density_A_3m gap_length_frames").split(), (0, np.inf)),
    "half": (0, 2),
}
CATEGORIES = {"active_set_piece_type": SET_PIECES, "raw_label": LABELS, "override_label": LABELS}

def entropy(probs):
    return -(probs * np.log(np.maximum(probs, np.finfo("float32").tiny))).sum(axis=1)

def frame_halves():
    """Zero outside the published play blocks, otherwise one or two."""
    halves = np.zeros(FRAME_COUNT, dtype="int8")
    for half, start, end in half_video_blocks(GAME):
        halves[start:end + 1] = half
    return halves

def validate(kind, table):
    schema = SCHEMAS[kind]
    if set(table.columns) != set(schema) or not table.columns.is_unique:
        raise ValueError(f"{kind}: expected columns {list(schema)}")
    if kind != "overrides":
        index = table.index
        if index.name != "frame" or index.dtype != "int64" or not index.equals(FRAMES):
            raise ValueError(f"{kind}: expected complete ordered int64 frame index")
    for name, dtype in schema.items():
        values = table[name]
        nullable = kind == "spatial" and dtype == "float32"
        if str(values.dtype) != dtype or (not nullable and values.isna().any()):
            raise ValueError(f"{kind}.{name}: invalid dtype or missing value")
        present = values.dropna()
        if dtype == "float32" and not np.isfinite(present).all():
            raise ValueError(f"{kind}.{name}: expected finite values")
        if name in BOUNDS and not present.between(*BOUNDS[name]).all():
            raise ValueError(f"{kind}.{name}: expected range {BOUNDS[name]}")
        if name in CATEGORIES and not values.isin(CATEGORIES[name]).all():
            raise ValueError(f"{kind}.{name}: invalid category")
    if kind == "spatial":
        if not np.array_equal(table.half, frame_halves()):
            raise ValueError("Spatial halves must match the official play blocks (0 outside play)")
        if (table.ball_is_imputed & (table.ball_x.isna() | table.ball_y.isna())).any():
            raise ValueError("Imputed positions must contain both coordinates")
    if kind == "overrides" and (table.start_frame > table.end_frame).any():
        raise ValueError("Override starts after its end")
    if kind == "overrides" and len(table):
        halves = frame_halves()
        starts = halves[table.start_frame.to_numpy()]
        ends = halves[table.end_frame.to_numpy()]
        if ((starts == 0) | (starts != ends)).any():
            raise ValueError("Each override must stay inside one published half")
    if kind == "predictions":
        probs = table[["prob_H", "prob_A", "prob_D"]].to_numpy()
        if not np.allclose(probs.sum(axis=1), 1, atol=1e-5) or not np.allclose(
            entropy(probs), table.state_entropy, atol=1e-5
        ):
            raise ValueError("Expected normalized probabilities and matching entropy in nats")
    return table

def read(kind, path):
    return validate(kind, pd.read_parquet(path))

def write(kind, table, path):
    validate(kind, table)
    path.parent.mkdir(parents=True, exist_ok=True)
    table.to_parquet(path, index=kind != "overrides")

def day1_mocks():
    phase = FRAMES.to_numpy() % 600
    spatial = pd.DataFrame(0, index=FRAMES, columns=list(SCHEMAS["spatial"]))
    spatial = spatial.assign(
        half=frame_halves(),
        ball_x=52.5, ball_y=34, voronoi_control_H=0.5,
        dist_nearest_H=np.where(phase < 300, 1, 5),
        dist_nearest_A=np.where(phase < 300, 5, 1),
        ball_is_imputed=phase < 8, gap_length_frames=np.where(phase < 8, 8, 0),
    ).astype(SCHEMAS["spatial"])
    deadball = pd.DataFrame({
        "is_dead_ball_prob": np.where(phase >= 560, 0.98, 0.02),
        "is_out_of_bounds": False,
        "active_set_piece_type": np.where(phase >= 560, "throw_in", "none"),
        "restart_frame_flag": phase == 0,
    }, index=FRAMES).astype(SCHEMAS["deadball"])
    return spatial, deadball
