"""Generate local diagnostics and reproducibility evidence for handoff B."""
from collections import Counter
from hashlib import file_digest
from pathlib import Path
from shutil import which
import subprocess
from tempfile import TemporaryDirectory

from src import p2_deadball_detector as p2
from src.contracts import read, write
from starter.load_smart_tagging import check_time_base, load, pattern_path


def sha256(path):
    with path.open("rb") as handle:
        return file_digest(handle, "sha256").hexdigest()


def tag_summary(events, mask):
    windows = p2.tag_windows(events)
    overlap = Counter()
    matched = Counter()
    examples = {}
    latest_end = -1
    for start, stop, piece in sorted(windows):
        if start < latest_end:
            overlap[piece] += 1
        latest_end = max(latest_end, stop)
        tagged = mask.iloc[start:stop]
        selected = tagged.restart_frame_flag & (tagged.active_set_piece_type == piece)
        frames = [int(frame) for frame in tagged.index[selected]]
        if frames:
            matched[piece] += 1
        examples.setdefault(piece, {
            "start_frame": int(start), "end_frame_exclusive": int(stop),
            "restart_frames": frames,
        })
    time_base = check_time_base(events)
    # The upstream diagnostic treats the end as inclusive. P2 uses half-open intervals.
    for row in time_base["halves"]:
        frame = row["true_kickoff_frame"]
        row["contains_kickoff"] = any(start <= frame < end for start, end in row["tagged"])
    time_base["agrees"] = all(row["contains_kickoff"] for row in time_base["halves"])
    return {
        "kickoff_time_base": time_base,
        "set_piece_tags_by_type": dict(Counter(
            p2.set_piece_type(event) or "unmapped"
            for event in events if (event["code"] or "").strip().casefold() == "set pieces"
        )),
        "play_block_windows_by_type": dict(Counter(piece for _, _, piece in windows)),
        "windows_overlapping_earlier_window_by_type": dict(overlap),
        "windows_with_matching_restart_by_type": dict(matched),
        "first_window_examples_by_type": examples,
    }


def generate(config, paths, config_path, root, verify=False):
    spatial_path = Path(paths["spatial"])
    output = Path(paths["deadball"])
    xml = Path(pattern_path(data_dir=config["data"]["directory"]))
    input_paths = {"spatial": spatial_path, "smart_tagging": xml, "config": config_path}
    if output.resolve() in {path.resolve() for path in input_paths.values()}:
        raise ValueError("Handoff B output must have a different path from its inputs")
    fingerprints = {name: sha256(path) for name, path in input_paths.items()}

    spatial = read("spatial", spatial_path)
    events = load(data_dir=config["data"]["directory"])
    deadball = p2.build_mask(config, spatial, events)
    playing = deadball.loc[spatial.half != 0]
    git = which("git")
    commit = subprocess.run(
        [git, "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True,
    ).stdout.strip() if git else None
    report = {
        "code_commit": commit or None,
        "inputs_sha256": fingerprints,
        "path": str(output),
        "frames": len(deadball),
        "missing_position_frames": int(spatial.loc[spatial.half != 0, ["ball_x", "ball_y"]]
                                       .isna().any(axis=1).sum()),
        "imputed_position_frames": int((spatial.ball_is_imputed & (spatial.half != 0)).sum()),
        "out_of_bounds_frames": int(playing.is_out_of_bounds.sum()),
        "strong_boundary_frames": int((playing.is_dead_ball_prob >= 0.98).sum()),
        "restart_candidates_by_type": playing.loc[
            playing.restart_frame_flag, "active_set_piece_type"
        ].value_counts().to_dict(),
        "tagged_frames_by_type": playing.loc[
            playing.active_set_piece_type != "none", "active_set_piece_type"
        ].value_counts().to_dict(),
        **tag_summary(events, deadball),
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output.parent) as directory:
        staged = Path(directory) / "candidate.parquet"
        write("deadball", deadball, staged)
        report["deadball_sha256"] = sha256(staged)
        if verify:
            repeated = Path(directory) / "repeat.parquet"
            write("deadball", p2.run(config, read("spatial", spatial_path)), repeated)
            if sha256(repeated) != report["deadball_sha256"]:
                raise RuntimeError("Repeated P2 generation produced a different Parquet file")
            report["reproduced_byte_for_byte"] = True
        if any(sha256(path) != fingerprints[name] for name, path in input_paths.items()):
            raise RuntimeError("A P2 input changed during generation. Retry with stable inputs.")
        staged.replace(output)
    return report
