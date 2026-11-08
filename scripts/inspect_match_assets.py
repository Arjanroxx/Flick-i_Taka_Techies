"""Verify delivered tracking, geometry and videos locally without uploading extracts."""
import argparse
import json
from pathlib import Path
import sys

import cv2
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games import GAME, GAMES, asset_paths, source_frames
from starter.load_atd import check_alignment_raw
from starter.load_homography import check_alignment, load as load_homography
from starter.load_smart_tagging import load as load_tags, check_time_base
from src.contracts import read
from src.p4_arbiter_and_eval import extract_frame, find_windows


def check_video(path, source, output):
    capture = cv2.VideoCapture(str(path))
    try:
        if not capture.isOpened():
            raise ValueError(f"Cannot open {source} video")
        count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = capture.get(cv2.CAP_PROP_FPS)
        expected_count = source_frames(source)
        metadata_agrees = count == expected_count and np.isclose(fps, GAMES[GAME]["fps"])
        if source == "tactical" and not metadata_agrees:
            raise ValueError(f"{source} video frame count or FPS disagrees with the official timeline")
        if count <= 0 or not np.isfinite(fps) or fps <= 0:
            raise ValueError(f"{source} video metadata is unavailable")
    finally:
        capture.release()
    # Decode and save one local extraction, then verify a read near the end as well.
    frame = 11185 if source == "tactical" else 0
    image = extract_frame(path, frame)
    if not cv2.imwrite(str(output / f"{source}_read_check.png"), image):
        raise ValueError("Failed to save local extraction")
    extract_frame(path, count - 1)
    return {"path": str(path.resolve()), "frames": count, "fps": fps, "decode_check": True,
            "official_metadata_agrees": bool(metadata_agrees), "expected_frames": expected_count}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--tactical-video", type=Path)
    parser.add_argument("--broadcast-video", type=Path)
    parser.add_argument("--out", type=Path, default=ROOT / "artifacts/p4/nov06")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    report = {"tracking": {}, "homography": {}, "videos": {}}
    for source in ("tactical", "broadcast"):
        alignment = check_alignment_raw(data_dir=str(args.data_dir), source=source)
        if not alignment["agrees"]:
            raise ValueError(f"{source} tracking frame alignment failed")
        report["tracking"][source] = alignment
        geometry = Path(asset_paths(data_dir=str(args.data_dir), source=source)["homography"])
        if geometry.exists():
            alignment = check_alignment(data_dir=str(args.data_dir), source=source)
            if not alignment["agrees"]:
                raise ValueError(f"{source} homography frame alignment failed")
            matrices, errors, valid = load_homography(data_dir=str(args.data_dir), source=source)
            if not np.isfinite(matrices[valid]).all() or not np.isfinite(errors[valid]).all():
                raise ValueError(f"{source} homography contains invalid usable values")
            report["homography"][source] = {"alignment": alignment, "usable_rows": int(valid.sum())}
        else:
            report["homography"][source] = {"available": False}
        video = getattr(args, f"{source}_video")
        if video:
            report["videos"][source] = check_video(video, source, args.out)
    tags = load_tags(data_dir=str(args.data_dir))
    time_base = check_time_base(tags)
    if not time_base["agrees"]:
        raise ValueError("Smart Tagging time-base check failed")
    report["tag_time_base"] = time_base
    predictions = ROOT / "artifacts/base_predictions.parquet"
    if predictions.exists():
        windows = find_windows(read("predictions", predictions), 0.9)
        pd.DataFrame(windows, columns=["start_frame", "end_frame"]).to_csv(
            args.out / "contested_windows.csv", index=False
        )
        report["contested_windows"] = len(windows)
    (args.out / "asset_checks.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("Asset alignment and requested video checks passed. Detailed evidence and extracts saved locally.")


if __name__ == "__main__":
    main()
