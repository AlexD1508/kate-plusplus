"""Unit tests for the theme picker's non-interactive parts.  Run: python3 -m unittest tests/test_picker.py"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

from kpp import cli, core, picker, ports  # noqa: E402


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

    def test_adaptive_preview_matches_what_apply_builds(self):
        cfg = core.Config()
        cfg.parser.read_dict({"theme": {"background": "#1a1b26", "accent": "#e06c75", "syntax-colors": "vivid"}})
        dark = next(e for e in picker.entries([]) if e.source == "dark")
        got = picker.theme_dict(dark, cfg)
        want = cli.adaptive_theme("dark", "#e06c75", "#1a1b26", "vivid")
        self.assertEqual(got, want)
        self.assertEqual(got["editor-colors"]["BackgroundColor"], "#1a1b26")

    def test_auto_preview_uses_the_apply_resolver(self):
        auto = next(e for e in picker.entries([]) if e.source == "auto")
        with mock.patch.object(cli, "resolve_theme_source", return_value="light") as resolver:
            got = picker.theme_dict(auto, core.Config())
        resolver.assert_called_once()
        self.assertEqual(got, cli.adaptive_theme("light", "", "", "balanced"))

    def test_theme_is_written_even_while_kate_runs(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            kate = core.Kate("native", ["kate"], Path(tmp), Path(tmp))
            kate.katerc.write_text("[KTextEditor Renderer]\nColor Theme=Breeze Dark\n")
            cfg = core.Config()
            cfg.parser.read_dict({"theme": {"source": "Dracula"}})
            args = mock.Mock(pick=False)
            with mock.patch.object(cli, "need_kate", return_value=kate), \
                    mock.patch.object(core, "load_state", return_value={}), \
                    mock.patch.object(core, "save_state"), \
                    mock.patch.object(cli, "PRE_INSTALL", Path(tmp) / "no-backup"), \
                    mock.patch.object(core, "load_config", return_value=cfg), \
                    mock.patch.object(core, "kate_running", return_value=True), \
                    mock.patch.object(cli, "build_themes", return_value="Dracula"), \
                    mock.patch.object(cli, "step"), mock.patch.object(cli, "info") as info:
                cli.do_theme(args)
            self.assertIn("Color Theme=Dracula", kate.katerc.read_text())
            info.assert_called_once()

    def test_layout_fits_small_terminals(self):
        for height in (24, 30, 18, 12):
            rows, preview_lines = picker._layout(height)
            self.assertLessEqual(3 + rows + 3 + preview_lines, max(height, 3 + 3 + 3 + 3), height)
            self.assertGreaterEqual(rows, 3)

    def test_every_kate_plusplus_and_popular_entry_previews_without_tools(self):
        with mock.patch.object(picker.core, "have", return_value=False), \
                mock.patch.object(picker.core, "load_config", return_value=core.Config()), \
                mock.patch.object(cli, "resolve_theme_source", side_effect=lambda c, p: (
                    "dark" if c.get("theme", "source") == "auto" else c.get("theme", "source"))):
            for e in picker.entries([]):
                lines = picker.preview(e)
                self.assertTrue(lines and "\033[38;2;" in lines[0], e.label)

    def test_list_fallback_reads_the_number_from_stdin(self):
        import io
        items = picker.entries(["Dracula"])
        with mock.patch("sys.stdin", io.StringIO(f"{len(items)}\n")), mock.patch("builtins.print"):
            self.assertEqual(picker.pick_list(items, "auto").source, "Dracula")
        with mock.patch("sys.stdin", io.StringIO("")), mock.patch("builtins.print"):
            self.assertIsNone(picker.pick_list(items, "auto"))


if __name__ == "__main__":
    unittest.main()
