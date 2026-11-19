"""Unit tests for the theme picker's non-interactive parts.  Run: python3 -m unittest tests/test_picker.py"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

from kpp import picker, ports  # noqa: E402


def ansi_fg(h):
    h = h.lstrip("#")
    return f"\033[38;2;{int(h[0:2], 16)};{int(h[2:4], 16)};{int(h[4:6], 16)}m"


class PickerTest(unittest.TestCase):
    def test_entries_cover_every_group(self):
        items = picker.entries(["Dracula", "Nord"])
        sources = [e.source for e in items]
        self.assertIn("auto", sources)
        self.assertIn("dark", sources)
        self.assertIn("light", sources)
        self.assertEqual(sum(e.group == "Popular" for e in items), len(ports.PORTS))
        self.assertIn("rose-pine-main", sources, "Rosé Pine must select Main exactly, not the adaptive family")
        self.assertEqual([e.source for e in items if e.group == "Kate"], ["Dracula", "Nord"])

    def test_render_uses_the_themes_real_colours(self):
        t = ports.build("night-owl")
        out = "\n".join(picker.render(t))
        self.assertIn(ansi_fg(t["text-styles"]["Keyword"]["text-color"]), out)
        self.assertIn(ansi_fg(t["text-styles"]["String"]["text-color"]), out)
        bg = t["editor-colors"]["BackgroundColor"].lstrip("#")
        self.assertIn(f"\033[48;2;{int(bg[0:2], 16)};{int(bg[2:4], 16)};{int(bg[4:6], 16)}m", out)
        self.assertEqual(len(picker.render(t)), len(picker.SAMPLE))

    def test_every_kate_plusplus_and_popular_entry_previews_without_tools(self):
        with mock.patch.object(picker.core, "have", return_value=False):
            for e in picker.entries([]):
                lines = picker.preview(e)
                self.assertTrue(lines and "\033[38;2;" in lines[0], e.label)

    def test_list_fallback_picks_by_number(self):
        items = picker.entries(["Dracula"])
        with mock.patch.object(picker.core, "prompt", return_value=str(len(items))), \
                mock.patch("builtins.print"):
            self.assertEqual(picker.pick_list(items, "auto").source, "Dracula")
        with mock.patch.object(picker.core, "prompt", return_value=""), mock.patch("builtins.print"):
            self.assertIsNone(picker.pick_list(items, "auto"))


if __name__ == "__main__":
    unittest.main()
