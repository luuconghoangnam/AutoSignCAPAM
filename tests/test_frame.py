import unittest

import numpy as np

from capture.frame import FrameSnapshot


class FrameSnapshotTests(unittest.TestCase):
    def test_identical_frames_share_fingerprint_and_zero_delta(self):
        image = np.full((20, 20, 3), 120, dtype=np.uint8)
        first = FrameSnapshot.from_image(image, {"id": 1, "w": 20, "h": 20})
        second = FrameSnapshot.from_image(image.copy(), {"id": 1, "w": 20, "h": 20})
        self.assertEqual(first.fingerprint, second.fingerprint)
        self.assertEqual(second.mean_delta(first), 0.0)

    def test_blank_frame_is_detected(self):
        image = np.zeros((20, 20, 3), dtype=np.uint8)
        self.assertTrue(FrameSnapshot.from_image(image, {}).is_blank)

    def test_changed_frame_has_positive_delta(self):
        first = FrameSnapshot.from_image(
            np.zeros((20, 20, 3), dtype=np.uint8), {}
        )
        second = FrameSnapshot.from_image(
            np.full((20, 20, 3), 255, dtype=np.uint8), {}
        )
        self.assertGreater(second.mean_delta(first), 0.0)


if __name__ == "__main__":
    unittest.main()
