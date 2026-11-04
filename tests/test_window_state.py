"""Сохранённая позиция не должна оставлять окно на отключённом мониторе."""

import unittest
from window_state import fit_position


class PositionTests(unittest.TestCase):
    def test_position_on_left_monitor_is_preserved(self):
        self.assertEqual(fit_position({"x": -1800, "y": 100}, (900, 680),
                                     [(-1920, 0, 0, 1080), (0, 0, 1920, 1040)]), (-1800, 100))

    def test_disconnected_monitor_and_taskbar(self):
        x, y = fit_position({"x": 2500, "y": 900}, (900, 680), [(0, 0, 1920, 1040)])
        self.assertGreaterEqual(x, 0)
        self.assertGreaterEqual(y, 0)
        self.assertLessEqual(x + 900, 1920)
        self.assertLessEqual(y + 680, 1040)

    def test_invalid_saved_position(self):
        for value in (None, {}, {"x": "100", "y": 10}, {"x": True, "y": 1}):
            self.assertIsNone(fit_position(value, (900, 680), [(0, 0, 1920, 1080)]))


if __name__ == "__main__":
    unittest.main()
