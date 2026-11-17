"""Freeze P3's C handoff and the team CSV from validated A and B artifacts.

The script reuses the merged modules rather than reimplementing the pipeline:
P1's A and P2's B are read through their contracts, P3 decodes C, P4 applies
the configured overrides, and the official validator checks the export.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import p3_sequence_model as p3, p4_arbiter_and_eval as p4
from src.contracts import frame_halves, read, write


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest().upper()


def git(*args):
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/config.yaml")
    parser.add_argument("--out", type=Path, default=ROOT / "artifacts/p3/freeze")
    parser.add_argument("--submission", type=Path,
                        help="Also write the validated CSV to this path")
    args = parser.parse_args()
    args.config = args.config.resolve()
    args.out = args.out.resolve()
    if args.submission:
        args.submission = args.submission.resolve()
    args.out.mkdir(parents=True, exist_ok=True)
    raw_config = args.config.read_text(encoding="utf-8-sig")
    config = yaml.safe_load(raw_config)
    paths = {name: (ROOT / value).resolve() for name, value in config["paths"].items()}

    spatial = read("spatial", paths["spatial"])
    deadball = read("deadball", paths["deadball"])
    predictions = p3.run(config, spatial, deadball)
    candidate_c = args.out / "base_predictions.parquet"
    write("predictions", predictions, candidate_c)

    # Use the same provenance checks as the full pipeline, bound to the C just
    # generated here rather than any older C at the normal handoff path.
    override_config = {**config, "paths": {**paths, "predictions": candidate_c}}
    overrides = p4.run(override_config, predictions)
    labels = p4.apply_overrides(predictions, overrides,
                                config["thresholds"]["override_confidence"])
    labels.iloc[frame_halves() == 0] = "X"
    submission = args.out / "Flick-i_Taka_Techies.csv"
    labels.to_csv(submission, header=True)

    validator = subprocess.run(
        [sys.executable, str(paths["validator"]), str(submission)],
        cwd=ROOT, capture_output=True, text=True,
    )
    (args.out / "validator.log").write_text(
        validator.stdout + validator.stderr, encoding="utf-8"
    )
    if validator.returncode != 0:
        raise SystemExit(validator.stdout + validator.stderr)

    if args.submission:
        args.submission.parent.mkdir(parents=True, exist_ok=True)
        labels.to_csv(args.submission, header=True)

    labels_array = labels.to_numpy()
    manifest = {
        "git_head": git("rev-parse", "HEAD"),
        "git_status": git("status", "--porcelain"),
        "config_path": str(args.config.relative_to(ROOT)) if args.config.is_relative_to(ROOT)
        else str(args.config),
        "config_sha256": hashlib.sha256(raw_config.encode("utf-8")).hexdigest().upper(),
        "settings": {"hmm": config["hmm"], "thresholds": config["thresholds"]},
        "inputs": {
            "a_path": str(paths["spatial"].relative_to(ROOT)),
            "a_sha256": digest(paths["spatial"]),
            "b_path": str(paths["deadball"].relative_to(ROOT)),
            "b_sha256": digest(paths["deadball"]),
        },
        "overrides": {
            "path": (str(paths["overrides"].relative_to(ROOT))
                     if paths["overrides"].is_file() else None),
            "rows": int(len(overrides)),
        },
        "outputs": {
            "c_path": str(candidate_c.relative_to(ROOT)),
            "c_sha256": digest(candidate_c),
            "csv_path": str(submission.relative_to(ROOT)),
            "csv_sha256": digest(submission),
            "csv_rows": int(len(labels)),
            "label_counts": {label: int((labels_array == label).sum())
                             for label in "HADX"},
            "label_segments": int((labels_array[1:] != labels_array[:-1]).sum() + 1),
        },
        "validator": {
            "command": f"{Path(sys.executable).name} evaluation/validate_submission.py "
                       f"{submission.name}",
            "returncode": validator.returncode,
            "output": (validator.stdout + validator.stderr).strip(),
        },
    }
    if args.submission:
        manifest["outputs"]["release_csv_path"] = str(args.submission)
        manifest["outputs"]["release_csv_sha256"] = digest(args.submission)
    (args.out / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
