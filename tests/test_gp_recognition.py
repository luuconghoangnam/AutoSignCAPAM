import unittest

from core.gp_handler import (
    GPHandler, STATE_CREDENTIALS, STATE_PORTAL, STATE_UNKNOWN,
)


class GPRecognitionTests(unittest.TestCase):
    def test_live_portal_geometry(self):
        self.assertEqual(
            GPHandler.classify_fields([(37, 325, 218, 35)], 287, 404),
            STATE_PORTAL,
        )

    def test_direct_credentials_single_password_geometry(self):
        self.assertEqual(
            GPHandler.classify_fields([(37, 339, 218, 35)], 287, 421),
            STATE_CREDENTIALS,
        )

    def test_live_credentials_geometry(self):
        fields = [(37, 240, 218, 30), (37, 294, 218, 30)]
        self.assertEqual(GPHandler.classify_fields(fields, 287, 421), STATE_CREDENTIALS)

    def test_single_visible_field_is_credentials_after_log_announces_form(self):
        fields = [(37, 294, 218, 30)]
        self.assertEqual(
            GPHandler.classify_fields(fields, 287, 421, credentials_expected=True),
            STATE_CREDENTIALS,
        )

    def test_nested_text_false_positive_is_rejected(self):
        fields = [(37, 309, 218, 35), (51, 322, 74, 11)]
        self.assertEqual(GPHandler.classify_fields(fields, 287, 388), STATE_UNKNOWN)

    def test_two_unaligned_fields_are_rejected(self):
        fields = [(20, 200, 218, 30), (120, 260, 150, 30)]
        self.assertEqual(GPHandler.classify_fields(fields, 287, 421), STATE_UNKNOWN)

    def test_gp_label_template_matching(self):
        import os
        import cv2
        from vision.template_matcher import find_gp_fields_by_template

        portal_path = "gp_portal_shown.png"
        window_path = "gp_window_shown.png"

        if not os.path.exists(portal_path) or not os.path.exists(window_path):
            self.skipTest("Local screenshot files not found, skipping template match verification.")

        # Test portal screen template matching
        portal_img = cv2.imread(portal_path)
        fields_portal = find_gp_fields_by_template(portal_img)
        self.assertIsNotNone(fields_portal)
        self.assertEqual(len(fields_portal), 1)

        # Test credentials screen template matching
        window_img = cv2.imread(window_path)
        fields_window = find_gp_fields_by_template(window_img)
        self.assertIsNotNone(fields_window)
        self.assertEqual(len(fields_window), 2)

    def test_gp_label_template_matching_dark_mode(self):
        import os
        import cv2
        from vision.template_matcher import find_gp_fields_by_template

        portal_path = "gp_portal_shown.png"
        window_path = "gp_window_shown.png"

        if not os.path.exists(portal_path) or not os.path.exists(window_path):
            self.skipTest("Local screenshot files not found, skipping template match verification.")

        # Test portal screen template matching in dark mode
        portal_img = cv2.imread(portal_path)
        dark_portal = cv2.bitwise_not(portal_img)
        fields_portal = find_gp_fields_by_template(dark_portal)
        self.assertIsNotNone(fields_portal)
        self.assertEqual(len(fields_portal), 1)

        # Test credentials screen template matching in dark mode
        window_img = cv2.imread(window_path)
        dark_window = cv2.bitwise_not(window_img)
        fields_window = find_gp_fields_by_template(dark_window)
        self.assertIsNotNone(fields_window)
        self.assertEqual(len(fields_window), 2)


if __name__ == "__main__":
    unittest.main()
