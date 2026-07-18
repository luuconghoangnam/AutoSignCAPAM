import unittest

from vision.field_detector import _deduplicate_fields


class FieldDetectorTests(unittest.TestCase):
    def test_nested_text_contour_is_not_a_second_field(self):
        fields = [(37, 309, 218, 35), (51, 322, 74, 11)]
        self.assertEqual(_deduplicate_fields(fields), [(37, 309, 218, 35)])

    def test_separate_credential_fields_are_kept(self):
        fields = [(37, 230, 218, 35), (37, 280, 218, 35)]
        self.assertEqual(len(_deduplicate_fields(fields)), 2)


if __name__ == "__main__":
    unittest.main()
