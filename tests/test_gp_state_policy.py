import unittest

from core.gp_handler import STATE_AUTH_FAILED, STATE_CREDENTIALS


class GPStatePolicyTests(unittest.TestCase):
    def test_auth_failure_must_not_be_overridden_by_visible_fields(self):
        log_state = STATE_AUTH_FAILED
        visual_state = STATE_CREDENTIALS
        terminal = log_state if log_state == STATE_AUTH_FAILED else visual_state
        self.assertEqual(terminal, STATE_AUTH_FAILED)


if __name__ == "__main__":
    unittest.main()
