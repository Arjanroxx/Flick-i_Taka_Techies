"""Run the tactical-feed baseline or replay the team's validated handoffs."""
import argparse
from copy import deepcopy
from pathlib import Path
import shutil
import subprocess
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from games import GAME, GAMES
from src import p1_spatial_features as p1, p2_deadball_detector as p2
from src import p3_sequence_model as p3, p4_arbiter_and_eval as p4
from src.contracts import day1_mocks, frame_halves, read, validate, write


def main():
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--mock", action="store_true", help="Use synthetic A and B under artifacts/mock")
    modes.add_argument("--from-artifacts", action="store_true", help="Replay real A and B handoffs")
    parser.add_argument("--data-dir", type=Path, help="Override ./data and MTAH_DATA_DIR")
    parser.add_argument("--config", type=Path, default=ROOT / "configs/config.yaml")
    parser.add_argument("--skip-evaluation", action="store_true", help="Skip public scoring, retain validation")
    args = parser.parse_args()
    config = yaml.safe_load(args.config.read_text(encoding="utf-8-sig"))
    config = deepcopy(config)
    paths = {name: (ROOT / path).resolve() for name, path in config["paths"].items()}
    if args.data_dir:
        config["data"]["directory"] = str(args.data_dir.resolve())
    elif config["data"]["directory"]:
        config["data"]["directory"] = str((ROOT / config["data"]["directory"]).resolve())
    if (config["pitch"]["length"], config["pitch"]["width"]) != GAMES[GAME]["pitch"]:
        parser.error("Pitch dimensions must agree with official games.py")
    if args.mock:
        for name in ("spatial", "deadball", "predictions", "overrides", "submission"):
            paths[name] = ROOT / "artifacts/mock" / paths[name].name
        print("Synthetic smoke run. Output is for integration checks.", flush=True)
    config["paths"] = {name: str(path) for name, path in paths.items()}
    if not paths["validator"].is_file():
        parser.error(f"Missing official validator at {paths['validator']}")
    if args.mock:
        spatial, deadball = day1_mocks()
    elif args.from_artifacts:
        spatial = read("spatial", paths["spatial"])
        deadball = read("deadball", paths["deadball"])
    else:
        # Fail before expensive loading if required match files are absent.
        from games import require

        require(["atd_meta", "atd_raw", "smart_tagging"], data_dir=config["data"]["directory"])
        spatial = validate("spatial", p1.run(config))
        deadball = validate("deadball", p2.run(config, spatial))
    if not args.from_artifacts:
        write("spatial", spatial, paths["spatial"])
        write("deadball", deadball, paths["deadball"])
    predictions = p3.run(config, spatial, deadball)
    write("predictions", predictions, paths["predictions"])
    overrides = p4.run(config, predictions)
    write("overrides", overrides, paths["overrides"])
    labels = p4.apply_overrides(predictions, overrides, config["thresholds"]["override_confidence"])
    labels.iloc[frame_halves() == 0] = "X"
    submission = paths["submission"]
    submission.parent.mkdir(parents=True, exist_ok=True)
    labels.to_csv(submission, header=True)
    subprocess.run([sys.executable, str(paths["validator"]), str(submission)], cwd=ROOT, check=True)
    print(submission, flush=True)
    if not (args.mock or args.skip_evaluation):
        results = paths["evaluation_results"]
        results.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(submission, results / submission.name)
        subprocess.run([
            sys.executable, str(paths["evaluator"]), "--gt", "public",
            "--results", str(results), "--out", str(paths["evaluation_reports"]), "--no-detail",
        ], cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
