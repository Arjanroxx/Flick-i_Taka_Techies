import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd
import yaml

from games import GAME, half_video_blocks
from scripts.run_local_arbiter import select_windows
from src.contracts import FRAMES, SCHEMAS, day1_mocks, entropy, read, write
from src.p4_arbiter_and_eval import apply_overrides, local_arbiter

ROOT = Path(__file__).resolve().parents[1]


class LocalArbiterTests(unittest.TestCase):
    def setUp(self):
        self.start = half_video_blocks(GAME)[0][1]
        self.window = (self.start, self.start + 7)
        index = pd.Index(range(self.start, self.start + 8), name="frame")
        self.spatial = pd.DataFrame({
            "ball_x": 52.0, "ball_y": 34.0, "half": 1,
            "ball_is_imputed": False, "gap_length_frames": 0,
            "dist_nearest_H": 1.0, "dist_nearest_A": 9.0,
        }, index=index)
        self.deadball = pd.DataFrame({"is_dead_ball_prob": 0.05,
                                      "is_out_of_bounds": False}, index=index)
        self.predictions = pd.DataFrame({"raw_label": "A"}, index=index)

    def propose(self):
        return local_arbiter(self.spatial, self.deadball, self.predictions, self.window)

    def test_sustained_observation_proposes_inclusive_interval(self):
        result = self.propose()
        self.assertEqual(len(result), 1)
        row = result.iloc[0]
        self.assertEqual((row.start_frame, row.end_frame), self.window)
        self.assertEqual(row.override_label, "H")
        self.assertAlmostEqual(row.confidence, 0.9, places=6)

    def test_retains_base_for_missing_imputed_contested_and_stopped_inputs(self):
        for column, value in (("ball_x", np.nan), ("ball_is_imputed", True),
                              ("gap_length_frames", 4), ("dist_nearest_H", np.nan),
                              ("dist_nearest_A", 1.5)):
            with self.subTest(column=column):
                original = self.spatial[column].copy()
                self.spatial[column] = value
                self.assertTrue(self.propose().empty)
                self.spatial[column] = original
        self.deadball["is_dead_ball_prob"] = 0.7
        self.assertTrue(self.propose().empty)
        self.deadball["is_dead_ball_prob"] = 0.05
        self.deadball["is_out_of_bounds"] = True
        self.assertTrue(self.propose().empty)

    def test_turnover_proposals_keep_opposing_runs_separate(self):
        self.spatial.loc[self.start + 4:, ["dist_nearest_H", "dist_nearest_A"]] = [9, 1]
        self.predictions["raw_label"] = "X"
        result = self.propose()
        self.assertEqual(result.override_label.tolist(), ["H", "A"])
        self.assertEqual(result.end_frame.iloc[0], self.start + 3)
        self.assertEqual(result.start_frame.iloc[1], self.start + 4)

    def test_short_evidence_and_agreement_produce_no_override(self):
        self.spatial.loc[self.start + 2:, "ball_is_imputed"] = True
        self.assertTrue(self.propose().empty)
        self.spatial["ball_is_imputed"] = False
        self.predictions["raw_label"] = "H"
        self.assertTrue(self.propose().empty)

    def test_confidence_threshold_filters_a_valid_proposal(self):
        proposals = self.propose()
        predictions = pd.DataFrame({"raw_label": "A"}, index=FRAMES)
        self.assertTrue(apply_overrides(predictions, proposals, 0.95).eq("A").all())
        labels = apply_overrides(predictions, proposals, 0.8)
        self.assertTrue(labels.loc[self.window[0]:self.window[1]].eq("H").all())
        self.assertEqual(labels.loc[self.window[1] + 1], "A")

    def test_window_selection_is_bounded_and_half_local(self):
        predictions = pd.DataFrame({"state_entropy": 0.0}, index=FRAMES)
        blocks = half_video_blocks(GAME)
        for _, start, end in blocks:
            predictions.loc[start:start + 20, "state_entropy"] = 1.0
            predictions.loc[end - 20:end, "state_entropy"] = 1.0
        selected = select_windows(predictions, 0.9, 3, 5)
        self.assertEqual(len(selected), 3)
        for start, end in selected:
            self.assertLessEqual(end - start + 1, 5)
            self.assertTrue(any(left <= start <= end <= right for _, left, right in blocks))


class LocalArbiterCommandTests(unittest.TestCase):
    def test_cli_cache_and_csv_are_reproducible(self):
        (ROOT / "artifacts").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / "artifacts") as directory:
            folder = Path(directory)
            config = yaml.safe_load((ROOT / "configs/config.yaml").read_text(encoding="utf-8-sig"))
            spatial, deadball = day1_mocks()
            start = half_video_blocks(GAME)[0][1]
            end = start + 7
            spatial.loc[start:end, ["ball_is_imputed"]] = False
            spatial.loc[start:end, "gap_length_frames"] = 0
            spatial.loc[start:end, ["dist_nearest_H", "dist_nearest_A"]] = [1, 9]
            deadball.loc[start:end, "is_dead_ball_prob"] = 0.05
            probabilities = np.tile([0.99, 0.005, 0.005], (len(FRAMES), 1))
            probabilities[start:end + 1] = 1 / 3
            predictions = pd.DataFrame(probabilities, index=FRAMES,
                                       columns=["prob_H", "prob_A", "prob_D"])
            predictions["state_entropy"] = entropy(probabilities)
            predictions["raw_label"] = "A"
            predictions = predictions.astype(SCHEMAS["predictions"])
            for kind, table in (("spatial", spatial), ("deadball", deadball),
                                ("predictions", predictions)):
                path = folder / f"{kind}.parquet"
                write(kind, table, path)
                config["paths"][kind] = str(path)
            config_path = folder / "config.yaml"
            config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
            for name in ("first", "second"):
                subprocess.run([sys.executable, str(ROOT / "scripts/run_local_arbiter.py"),
                                "--config", str(config_path), "--out", str(folder / name)],
                               cwd=ROOT, check=True, capture_output=True, text=True)
            summary = json.loads((folder / "first/summary.json").read_text())
            self.assertEqual(summary["changed_frames"], 8)
            self.assertEqual(summary["overrides_accepted"], 1)
            self.assertEqual((folder / "first/summary.json").read_bytes(),
                             (folder / "second/summary.json").read_bytes())
            overrides = read("overrides", folder / "first/llm_overrides.parquet")
            self.assertEqual(overrides.override_label.iloc[0], "H")
            cache = json.loads((folder / "first/response_cache.json").read_text())
            self.assertEqual(len(cache["requests"]), 1)
            self.assertEqual(cache["requests"][0]["decision"], "override")


if __name__ == "__main__":
    unittest.main()
