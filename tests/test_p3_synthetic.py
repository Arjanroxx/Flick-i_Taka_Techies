from pathlib import Path
import unittest

import numpy as np
import yaml

from src.contracts import validate
from src.p3_synthetic import generate


class P3SyntheticFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = yaml.safe_load(
            (Path(__file__).resolve().parents[1] / "configs/config.yaml").read_text()
        )
        cls.spatial, cls.deadball, cls.truth = generate(seed=0)

    def test_tables_pass_the_shared_contracts(self):
        validate("spatial", self.spatial)
        validate("deadball", self.deadball)

    def test_truth_is_x_only_outside_play(self):
        halves = self.spatial.half.to_numpy()
        labels = self.truth.to_numpy()
        self.assertTrue((labels[halves == 0] == "X").all())
        self.assertTrue(np.isin(labels[halves != 0], list("HAD")).all())
        self.assertTrue(self.truth.index.equals(self.spatial.index))

    def test_imputed_frames_are_short_gaps(self):
        imputed = self.spatial.ball_is_imputed.to_numpy()
        self.assertTrue(imputed.any())
        self.assertTrue(
            self.spatial.gap_length_frames.to_numpy()[imputed].max()
            <= self.config["thresholds"]["short_gap"]
        )
        self.assertFalse(
            self.spatial.loc[imputed, ["ball_x", "ball_y"]].isna().any().any()
        )


if __name__ == "__main__":
    unittest.main()
