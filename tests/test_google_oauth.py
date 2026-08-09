import unittest
from unittest.mock import MagicMock, patch

from app.services import google_oauth


class GoogleOAuthTests(unittest.TestCase):
    def test_exchange_code_sends_saved_pkce_verifier(self):
        """The token exchange must use the verifier that created the challenge."""
        flow = MagicMock()
        credentials = MagicMock()
        flow.credentials = credentials

        with patch.object(google_oauth, "create_google_flow", return_value=flow):
            result = google_oauth.exchange_code_for_credentials(
                "authorization-code", "saved-pkce-verifier"
            )

        self.assertIs(result, credentials)
        flow.fetch_token.assert_called_once_with(
            code="authorization-code",
            code_verifier="saved-pkce-verifier",
        )
