import unittest

from adapters.windows import WindowsAdapter


class BrowserCallbackTests(unittest.TestCase):
    def test_correlated_gp_tab_is_accepted(self):
        self.assertTrue(
            WindowsAdapter.is_gp_browser_callback("brave.exe", "GlobalProtect - Brave")
        )

    def test_unrelated_user_tab_is_rejected(self):
        self.assertFalse(
            WindowsAdapter.is_gp_browser_callback("brave.exe", "WebSphere - Brave")
        )

    def test_non_browser_same_title_is_rejected(self):
        self.assertFalse(
            WindowsAdapter.is_gp_browser_callback("other.exe", "GlobalProtect")
        )

    def test_callback_url_title_is_accepted(self):
        self.assertTrue(
            WindowsAdapter.is_gp_browser_callback(
                "brave.exe",
                "file:///C:/Users/congl/AppData/Local/Palo Alto Networks/GlobalProtect/gpwelcome.html",
            )
        )


if __name__ == "__main__":
    unittest.main()
