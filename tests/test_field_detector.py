import unittest
import tempfile
from pathlib import Path

import cv2
import numpy as np

from vision.field_detector import _deduplicate_fields, detect_input_fields


class FieldDetectorTests(unittest.TestCase):
    def test_nested_text_contour_is_not_a_second_field(self):
        fields = [(37, 309, 218, 35), (51, 322, 74, 11)]
        self.assertEqual(_deduplicate_fields(fields), [(37, 309, 218, 35)])

    def test_separate_credential_fields_are_kept(self):
        fields = [(37, 230, 218, 35), (37, 280, 218, 35)]
        self.assertEqual(len(_deduplicate_fields(fields)), 2)

    def test_canny_and_pixel_candidates_merge_into_two_fields(self):
        canny = [(37, 240, 218, 30)]
        pixel = [(36, 239, 220, 32), (37, 294, 218, 30)]

        merged = _deduplicate_fields(canny + pixel)

        self.assertEqual(len(merged), 2)
        self.assertTrue(any(field[1] < 260 for field in merged))
        self.assertTrue(any(field[1] > 280 for field in merged))

    def test_rounded_gp_fields_are_found_from_combined_sources(self):
        image = np.full((421, 287, 3), 185, dtype=np.uint8)
        cv2.rectangle(image, (37, 240), (254, 269), (245, 245, 245), -1)
        cv2.rectangle(image, (37, 294), (254, 323), (245, 245, 245), -1)
        cv2.rectangle(image, (37, 240), (254, 269), (80, 80, 80), 1)

        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "gp-rounded.png"
            cv2.imwrite(str(path), image)
            fields = detect_input_fields(str(path), profile="gp")

        self.assertEqual(len(fields), 2)


if __name__ == "__main__":
    unittest.main()
