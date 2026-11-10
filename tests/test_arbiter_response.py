import json
import unittest

from games import GAME, half_video_blocks
from src.p4_arbiter_and_eval import parse_arbiter_response


class ArbiterResponseTests(unittest.TestCase):
    def test_response_contract(self):
        (_, start, end), (_, next_start, _) = half_video_blocks(GAME)
        record = dict(start_frame=start, end_frame=start + 1, override_label="A", confidence=0.9)
        window = (start, start + 2)
        result = parse_arbiter_response(json.dumps(record), window)
        self.assertEqual(result.override_label.iloc[0], "A")
        for changes in (
            {"override_label": "HOME"}, {"confidence": 1.00000001},
            {"confidence": -0.01}, {"confidence": "0.9"},
            {"confidence": float("nan")}, {"confidence": float("inf")}, {"confidence": True},
            {"start_frame": float(start)}, {"end_frame": start - 1},
            {"start_frame": -1}, {"start_frame": start - 1},
            {"end_frame": start + 3}, {"extra": 1},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                parse_arbiter_response(json.dumps(record | changes), window)
        with self.assertRaises(ValueError):
            parse_arbiter_response(json.dumps(record | {"start_frame": end, "end_frame": next_start}),
                                   (end, next_start))
        with self.assertRaises(ValueError):
            parse_arbiter_response('{"start_frame":', window)
        with self.assertRaises(ValueError):
            parse_arbiter_response(json.dumps({k: v for k, v in record.items() if k != "confidence"}),
                                   window)
        with self.assertRaisesRegex(ValueError, "Duplicate fields"):
            parse_arbiter_response(json.dumps(record)[:-1] + ', "confidence": 0.95}', window)

        for label in ("H", "A", "D", "X"):
            for confidence in (0, 1):
                with self.subTest(label=label, confidence=confidence):
                    response = json.dumps(record | {"override_label": label, "confidence": confidence})
                    result = parse_arbiter_response(response, window)
                    self.assertEqual(result.override_label.iloc[0], label)
                    self.assertEqual(result.confidence.iloc[0], confidence)


if __name__ == "__main__":
    unittest.main()
