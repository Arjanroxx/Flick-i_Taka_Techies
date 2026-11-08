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
            {"confidence": float("nan")}, {"confidence": True},
            {"start_frame": float(start)}, {"end_frame": start - 1},
            {"end_frame": start + 3}, {"extra": 1},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                parse_arbiter_response(json.dumps(record | changes), window)
        with self.assertRaises(ValueError):
            parse_arbiter_response(json.dumps(record | {"start_frame": end, "end_frame": next_start}),
                                   (end, next_start))
        with self.assertRaises(ValueError):
            parse_arbiter_response('{"start_frame":', window)


if __name__ == "__main__":
    unittest.main()
