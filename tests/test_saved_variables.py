"""Импортированные данные не должны повторно отправляться в базу."""

import unittest

from saved_variables import own_data, player_key


class SavedVariablesTests(unittest.TestCase):
    def test_own_data_without_imports(self):
        text = '''INEEDGEARDB = {
            ["imported"] = { ["Друг"] = "сложная строка { } \\\" characters" },
            ["characters"] = { ["Игрок-Реалм"] = { ["equipped"] = { "предмет { }" } } },
        }'''
        result = own_data(text)
        self.assertNotIn("Друг", result)
        self.assertIn("предмет { }", result)
        self.assertEqual(player_key(text), "Игрок-Реалм")

    def test_truncated_table_is_rejected(self):
        with self.assertRaises(ValueError):
            own_data('INEEDGEARDB = { ["characters"] = { ["Игрок"] = {')

    def test_marker_in_string_does_not_strip_data(self):
        text = 'INEEDGEARDB = { ["characters"] = { ["Игрок"] = { "characters", "\\\\", "\\\"" } } }'
        self.assertEqual(player_key(text), "Игрок")
        self.assertIn('"\\\\"', own_data(text))


if __name__ == "__main__":
    unittest.main()
