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


if __name__ == "__main__":
    unittest.main()
