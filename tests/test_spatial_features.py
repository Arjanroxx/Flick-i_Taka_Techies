import unittest

import numpy as np

from games import GAME, half_video_blocks
from src.contracts import FRAME_COUNT, frame_halves, validate
from src.p1_spatial_features import build_features, project
from starter.load_homography import project as project_to_pixels

SHORT_GAP = 12
SLOTS_PER_TEAM = 2


def make_inputs():
    """Full-length synthetic tracking: ball present in both play blocks, four player slots."""
    halves = frame_halves()
    blocks = half_video_blocks(GAME)
    ball = np.full((FRAME_COUNT, 2), np.nan, dtype="float32")
    players = np.full((FRAME_COUNT, 2 * SLOTS_PER_TEAM, 3), np.nan, dtype="float32")
    for _, start, end in blocks:
        ball[start:end + 1] = (51.0, 31.0)
        players[start:end + 1, 0, :2] = (50.0, 30.0)  # within 3 m of the ball
        players[start:end + 1, 1, :2] = (50.0, 32.0)
        players[start:end + 1, 2, :2] = (52.0, 30.0)
        players[start:end + 1, 3, :2] = (52.0, 32.0)
    teams = np.array([0] * SLOTS_PER_TEAM + [1] * SLOTS_PER_TEAM, dtype=np.int8)
    return ball, players, teams, halves, blocks


class SpatialFeaturesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ball0, cls.players, cls.teams, cls.halves, cls.blocks = make_inputs()
        (_, cls.first, cls.last), (_, cls.second, cls.second_last) = cls.blocks
        cls.start1, cls.stop1 = cls.first, cls.last + 1
        cls.start2, cls.stop2 = cls.second, cls.second_last + 1

    def build(self, ball):
        return validate("spatial", build_features(ball, self.players, self.teams, SHORT_GAP))

    def test_contract_and_metre_coordinates(self):
        table = self.build(self.ball0.copy())
        self.assertTrue(np.array_equal(table.half, self.halves))
        self.assertFalse(table.ball_is_imputed.any())
        self.assertTrue((table.gap_length_frames == 0).all())
        intact = self.start1 + 50
        self.assertAlmostEqual(float(table.ball_x[intact]), 51.0, places=4)
        self.assertAlmostEqual(float(table.ball_y[intact]), 31.0, places=4)

    def test_short_gap_linear_fill_and_flags(self):
        ball = self.ball0.copy()
        left = self.start1 + 200
        ball[left - 1] = (10.0, 10.0)
        ball[left + 5] = (20.0, 20.0)
        ball[left:left + 5] = np.nan
        table = self.build(ball)
        for offset in range(5):
            frame = left + offset
            expected = 10.0 + 10.0 * (offset + 1) / 6.0
            self.assertAlmostEqual(float(table.ball_x[frame]), expected, places=3)
            self.assertAlmostEqual(float(table.ball_y[frame]), expected, places=3)
            self.assertTrue(bool(table.ball_is_imputed[frame]))
            self.assertEqual(int(table.gap_length_frames[frame]), 5)

    def test_long_gap_stays_missing(self):
        ball = self.ball0.copy()
        left = self.start1 + 400
        ball[left:left + 50] = np.nan
        table = self.build(ball)
        self.assertTrue(table.ball_x[left:left + 50].isna().all())
        self.assertTrue((~table.ball_is_imputed[left:left + 50]).all())
        self.assertTrue((table.gap_length_frames[left:left + 50] == 50).all())
        self.assertTrue(np.isfinite(table.ball_x[left + 50]))

    def test_edge_and_half_boundary_gaps_never_interpolated(self):
        ball = self.ball0.copy()
        ball[self.start1:self.start1 + 4] = np.nan
        ball[self.stop1 - 4:self.stop1] = np.nan
        ball[self.start2:self.start2 + 4] = np.nan
        ball[self.stop2 - 4:self.stop2] = np.nan
        table = self.build(ball)
        for frames in (slice(self.start1, self.start1 + 4),
                       slice(self.stop1 - 4, self.stop1),
                       slice(self.start2, self.start2 + 4),
                       slice(self.stop2 - 4, self.stop2)):
            self.assertTrue(table.ball_x[frames].isna().all())
            self.assertTrue((~table.ball_is_imputed[frames]).all())
        self.assertTrue(table.ball_x[self.halves == 0].isna().all())

    def test_observed_velocity_acceleration_and_half_reset(self):
        ball = self.ball0.copy()
        frames = np.arange(self.start1, self.stop1)
        ball[self.start1:self.stop1, 0] = 51.0 + 0.08 * (frames - self.start1)  # 2 m/s in x
        table = self.build(ball)
        self.assertTrue(np.isnan(table.ball_vx[self.start1]))
        self.assertTrue(np.isnan(table.ball_speed[self.start1]))
        mid = self.start1 + 1000
        self.assertAlmostEqual(float(table.ball_vx[mid]), 2.0, places=4)
        self.assertAlmostEqual(float(table.ball_vy[mid]), 0.0, places=4)
        self.assertAlmostEqual(float(table.ball_speed[mid]), 2.0, places=4)
        self.assertAlmostEqual(float(table.ball_accel[mid]), 0.0, places=4)
        # Second half keeps its own stationary ball: no derivative crosses the halftime gap.
        self.assertAlmostEqual(float(table.ball_vx[self.start2 + 10]), 0.0, places=4)
        self.assertTrue(np.isnan(table.ball_vx[self.start2]))
        self.assertFalse(bool(np.isnan(table.ball_vx[self.stop1 - 1])))

    def test_missing_ball_gives_nan_distances_and_zero_density(self):
        ball = self.ball0.copy()
        left = self.start1 + 700
        ball[left:left + 20] = np.nan  # longer than short_gap: stays unobserved
        table = self.build(ball)
        frame = left + 10
        self.assertTrue(np.isnan(table.ball_x[frame]))
        self.assertTrue(np.isnan(table.dist_nearest_H[frame]))
        self.assertTrue(np.isnan(table.dist_nearest_A[frame]))
        self.assertTrue(np.isnan(table.rel_vel_nearest_H[frame]))
        self.assertEqual(int(table.local_density_H_3m[frame]), 0)
        self.assertEqual(int(table.local_density_A_3m[frame]), 0)
        self.assertTrue(np.isnan(table.voronoi_control_H[frame]))
        observed = frame + 30
        self.assertTrue(np.isfinite(table.dist_nearest_H[observed]))
        self.assertGreater(int(table.local_density_H_3m[observed]), 0)

    def test_out_of_bounds_coordinates_retained(self):
        ball = self.ball0.copy()
        frame = self.start1 + 600
        ball[frame] = (-3.0, 71.0)
        table = self.build(ball)
        self.assertAlmostEqual(float(table.ball_x[frame]), -3.0, places=4)
        self.assertAlmostEqual(float(table.ball_y[frame]), 71.0, places=4)
        self.assertFalse(bool(table.ball_is_imputed[frame]))

    def test_validate_rejects_imputed_position_without_coordinates(self):
        ball = self.ball0.copy()
        left = self.start1 + 900
        ball[left:left + 5] = np.nan
        table = self.build(ball)  # the short gap is imputed, so the flag is set
        self.assertTrue(bool(table.ball_is_imputed[left]))
        table.loc[left, "ball_x"] = np.nan
        with self.assertRaises(ValueError):
            validate("spatial", table)

    def test_inverse_homography_helper_roundtrip(self):
        matrix = np.array([[900.0, 0.0, 80.0],
                           [0.0, 880.0, 60.0],
                           [0.0005, 0.0004, 1.0]])
        pitch = np.array([105.3, 68.0])
        metres = np.array([[51.0, 31.0], [0.0, 0.0], [105.3, 68.0], [10.0, 60.0]])
        pixel_x, pixel_y = project_to_pixels(matrix, metres[:, 0] / pitch[0],
                                             metres[:, 1] / pitch[1])
        back = project(np.column_stack((pixel_x, pixel_y)), matrix)
        np.testing.assert_allclose(back, metres, rtol=1e-9, atol=1e-9)

    def test_project_scales_normalised_pixels_by_pitch(self):
        identity = np.eye(3)
        got = project(np.array([[0.5, 0.5]]), identity)
        np.testing.assert_allclose(got, [[0.5 * 105.3, 0.5 * 68.0]], rtol=1e-12)


if __name__ == "__main__":
    unittest.main()
