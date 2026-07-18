import unittest

from recognition.geometry import boxes_stable, points_stable, to_screen_point


class GeometryTests(unittest.TestCase):
    def test_boxes_stable_across_pixel_scale(self):
        self.assertTrue(
            boxes_stable(
                [(100, 200, 400, 80)],
                [(125, 250, 500, 100)],
                2000,
                1000,
                previous_width=1600,
                previous_height=800,
            )
        )

    def test_boxes_reject_large_normalized_shift(self):
        self.assertFalse(
            boxes_stable(
                [(100, 200, 400, 80)],
                [(180, 200, 400, 80)],
                2000,
                1000,
            )
        )

    def test_points_stable_uses_frame_dimensions(self):
        self.assertTrue(points_stable((500, 400), (512, 408), 2000, 1000))
        self.assertFalse(points_stable((500, 400), (550, 408), 2000, 1000))

    def test_image_point_maps_to_screen_rect(self):
        self.assertEqual(
            to_screen_point(
                (1200, 600),
                2400,
                1200,
                {"x": 100, "y": 50, "w": 1600, "h": 800},
            ),
            (900, 450),
        )


if __name__ == "__main__":
    unittest.main()
