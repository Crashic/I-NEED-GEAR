"""Публикация использует токен только для операций разработчика."""

import io
import json
import unittest
from unittest.mock import patch

import developer


class DeveloperTests(unittest.TestCase):
    def test_dispatch_uses_local_token_and_default_branch(self):
        responses = [io.BytesIO(b'{"default_branch":"main"}'), io.BytesIO(b'')]
        with patch("developer.local_token", return_value="локальный-тестовый-токен"), \
                patch("developer.urllib.request.urlopen", side_effect=responses) as network, \
                patch("developer.webbrowser.open"):
            messages = []
            developer.publish_release("1.2.3", messages.append)
            self.assertEqual(network.call_count, 2)
            dispatch = network.call_args_list[1].args[0]
            self.assertEqual(dispatch.method, "POST")
            self.assertEqual(json.loads(dispatch.data), {"ref": "main", "inputs": {"version": "1.2.3"}})
            self.assertEqual(dispatch.headers["Authorization"], "Bearer локальный-тестовый-токен")
            self.assertNotIn("локальный-тестовый-токен", " ".join(messages))

    def test_invalid_version_does_not_contact_github(self):
        with patch("developer.urllib.request.urlopen") as network:
            with self.assertRaises(ValueError):
                developer.publish_release("1.0.0; команда", lambda message: None)
            network.assert_not_called()


if __name__ == "__main__":
    unittest.main()
