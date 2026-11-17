"""Data-gated P1 -> P2 -> P3 integration check on the tactical bundle.

These assertions verify interface compatibility and real-data availability on
BAR-ATH. They are not an accuracy evaluation and must not be used as an
external baseline.
"""
from pathlib import Path
import unittest

import numpy as np
import yaml

from games import require
from src import p1_spatial_features as p1, p2_deadball_detector as p2, p3_sequence_model as p3
from src.contracts import FRAME_COUNT, frame_halves, validate


class P3RealDataIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        cls.config = yaml.safe_load((root / "configs/config.yaml").read_text())
        try:
            require(
                ["atd_meta", "atd_raw", "smart_tagging"],
                data_dir=cls.config["data"]["directory"],
            )
        except IOError as error:
            raise unittest.SkipTest(f"real tactical assets unavailable: {error}") from error

        cls.spatial = validate("spatial", p1.run(cls.config))
        cls.deadball = validate("deadball", p2.run(cls.config, cls.spatial))
        cls.predictions = validate(
            "predictions", p3.run(cls.config, cls.spatial, cls.deadball)
        )
        cls.halves = frame_halves()
        cls.graded = cls.halves != 0

    def test_frame_count_and_half_alignment(self):
        self.assertEqual(FRAME_COUNT, 199_319)
        self.assertEqual(len(self.spatial), 199_319)
        self.assertEqual(len(self.deadball), 199_319)
        self.assertEqual(len(self.predictions), 199_319)
        np.testing.assert_array_equal(self.spatial.half.to_numpy(), self.halves)
        self.assertTrue(self.predictions.index.equals(self.spatial.index))

    def test_spatial_availability_on_graded_frames(self):
        distances = self.spatial.loc[
            self.graded, ["dist_nearest_H", "dist_nearest_A"]
        ].to_numpy()
        finite_both = int(np.isfinite(distances).all(axis=1).sum())
        self.assertGreaterEqual(finite_both, 93_000)
        self.assertLessEqual(finite_both, 95_000)

        self.assertLessEqual(int(self.spatial.ball_is_imputed.sum()), 100)

        gap_fraction = float(
            (self.spatial.loc[self.graded, "gap_length_frames"] > 0).mean()
        )
        self.assertAlmostEqual(gap_fraction, 0.407, delta=0.01)

    def test_dead_ball_probability_is_bounded(self):
        probability = self.deadball.is_dead_ball_prob.to_numpy()
        self.assertTrue(np.isfinite(probability).all())
        self.assertTrue(((probability >= 0) & (probability <= 1)).all())

    def test_p3_probabilities_and_outside_play_labels(self):
        probabilities = self.predictions[["prob_H", "prob_A", "prob_D"]].to_numpy()
        self.assertTrue(np.isfinite(probabilities).all())
        self.assertTrue(((probabilities >= 0) & (probabilities <= 1)).all())
        np.testing.assert_allclose(probabilities.sum(axis=1), 1, atol=1e-5)

        outside = self.halves == 0
        self.assertTrue(outside.any())
        self.assertTrue((self.predictions.loc[outside, "raw_label"] == "X").all())


if __name__ == "__main__":
    unittest.main()
