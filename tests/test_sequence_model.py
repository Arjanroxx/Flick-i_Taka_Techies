from pathlib import Path
import unittest

import numpy as np
import pandas as pd
import yaml

from src.contracts import SCHEMAS, day1_mocks, entropy
from src.p3_sequence_model import run


class SequenceModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = yaml.safe_load(
            (Path(__file__).resolve().parents[1] / "configs/config.yaml").read_text()
        )
        cls.spatial, cls.deadball = day1_mocks()
        cls.predictions = run(cls.config, cls.spatial, cls.deadball)
        cls.halves = cls.spatial.half.to_numpy()
        cls.playing_frame = cls.spatial.index[cls.halves == 1][0]

    def single_frame_predictions(self, home_distance, away_distance, imputed):
        # One frame has identical temporal context in every case, so the posterior
        # equals the spatial emission and cannot be sharpened by neighbouring frames.
        spatial = self.spatial.loc[[self.playing_frame]].copy()
        deadball = self.deadball.loc[[self.playing_frame]].copy()
        spatial.loc[self.playing_frame, ["dist_nearest_H", "dist_nearest_A"]] = [
            home_distance, away_distance
        ]
        spatial.loc[self.playing_frame, "ball_is_imputed"] = imputed
        spatial.loc[self.playing_frame, "gap_length_frames"] = 0
        deadball.loc[self.playing_frame, "is_dead_ball_prob"] = 0.02
        return run(self.config, spatial, deadball)

    def test_imputed_positions_receive_neutral_spatial_evidence(self):
        imputed = self.single_frame_predictions(1, 5, True)
        unavailable = self.single_frame_predictions(np.nan, np.nan, False)
        pd.testing.assert_frame_equal(imputed, unavailable)

    def test_observed_positions_retain_spatial_evidence(self):
        for home, away, closer, farther in (
            (1, 5, "prob_H", "prob_A"),
            (5, 1, "prob_A", "prob_H"),
        ):
            with self.subTest(home=home, away=away):
                observed = self.single_frame_predictions(home, away, False)
                self.assertGreater(observed.at[self.playing_frame, closer], 0.9)
                self.assertGreater(
                    observed.at[self.playing_frame, closer],
                    observed.at[self.playing_frame, farther],
                )

    def test_output_structure(self):
        self.assertEqual(list(self.predictions.columns), list(SCHEMAS["predictions"]))
        for name, dtype in SCHEMAS["predictions"].items():
            with self.subTest(column=name):
                self.assertEqual(str(self.predictions[name].dtype), dtype)
        self.assertEqual(self.predictions.index.name, "frame")
        self.assertEqual(self.predictions.index.dtype, np.dtype("int64"))
        self.assertTrue(self.predictions.index.equals(self.spatial.index))
        self.assertEqual(len(self.predictions), len(self.spatial))

    def test_probabilities_are_finite_and_normalized(self):
        probs = self.predictions[["prob_H", "prob_A", "prob_D"]].to_numpy()
        self.assertTrue(np.isfinite(probs).all())
        self.assertTrue(((probs >= 0) & (probs <= 1)).all())
        np.testing.assert_allclose(probs.sum(axis=1), 1, atol=1e-5)

    def test_entropy_matches_probability_entropy(self):
        probs = self.predictions[["prob_H", "prob_A", "prob_D"]].to_numpy()
        np.testing.assert_allclose(
            self.predictions.state_entropy.to_numpy(), entropy(probs), atol=1e-5
        )

    def test_outside_play_frames_are_labelled_x(self):
        outside = self.halves == 0
        self.assertTrue(outside.any())
        self.assertTrue((self.predictions.raw_label.to_numpy()[outside] == "X").all())

    def test_half_predictions_ignore_other_half_observations(self):
        for target, other in ((1, 2), (2, 1)):
            with self.subTest(target_half=target):
                target_mask = self.halves == target
                other_mask = self.halves == other
                self.assertTrue(target_mask.any())
                self.assertTrue(other_mask.any())

                spatial = self.spatial.copy()
                deadball = self.deadball.copy()
                spatial.loc[other_mask, ["dist_nearest_H", "dist_nearest_A"]] = np.nan
                spatial.loc[other_mask, "gap_length_frames"] = 1
                deadball.loc[other_mask, "is_dead_ball_prob"] = 1.0

                perturbed = run(self.config, spatial, deadball)
                self.assertFalse(
                    perturbed.loc[other_mask].equals(self.predictions.loc[other_mask])
                )
                pd.testing.assert_frame_equal(
                    perturbed.loc[target_mask], self.predictions.loc[target_mask]
                )


if __name__ == "__main__":
    unittest.main()
