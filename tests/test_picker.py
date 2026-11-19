"""Unit tests for the theme picker's non-interactive parts.  Run: python3 -m unittest tests/test_picker.py"""
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

# Sandbox *before* importing kpp: core captures HOME/XDG paths and KPP_TEST at import time.
_SANDBOX = tempfile.mkdtemp(prefix="kpp-picker-test-")
_ENV_KEYS = ("HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME", "KPP_TEST")
_SAVED_ENV = {k: os.environ.get(k) for k in _ENV_KEYS}
os.environ.update({
    "HOME": _SANDBOX, "KPP_TEST": "1",
    "XDG_CONFIG_HOME": os.path.join(_SANDBOX, ".config"),
    "XDG_DATA_HOME": os.path.join(_SANDBOX, ".local/share"),
    "XDG_STATE_HOME": os.path.join(_SANDBOX, ".local/state"),
    "XDG_CACHE_HOME": os.path.join(_SANDBOX, ".cache"),
})

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

from kpp import cli, core, picker, ports  # noqa: E402


def tearDownModule():
    shutil.rmtree(_SANDBOX, ignore_errors=True)
    for k, v in _SAVED_ENV.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


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

    def test_sandbox_is_in_place(self):
        self.assertTrue(str(core.XDG_STATE).startswith(_SANDBOX))
        self.assertFalse(core.CAELESTIA_SCHEME.exists())

    def test_escape_sequence_split_across_reads(self):
        r, w = os.pipe()
        def feed():
            for part in (b"\x1b", b"[", b"B"):
                os.write(w, part)
                time.sleep(0.02)
        threading.Thread(target=feed).start()
        self.assertEqual(picker._read_key(r), "down")
        os.write(w, b"\x1b")
        self.assertEqual(picker._read_key(r), "esc")          # a lone Escape still cancels
        os.write(w, b"\x1b[6~")
        self.assertEqual(picker._read_key(r), "pgdn")
        os.close(r)
        os.close(w)

    def test_kate_list_excludes_themes_kate_plusplus_installed(self):
        listing = "Dracula\nRosé Pine\nKanagawa Wave\nKate++ Dark\nNord\n"
        with mock.patch.object(cli, "have", return_value=True), \
                mock.patch.object(cli, "run", return_value=mock.Mock(stdout=listing)):
            self.assertEqual(cli.kate_builtin_themes(), ["Dracula", "Nord"])

    def test_theme_written_when_auto_selection_is_still_on(self):
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            kate = core.Kate("native", ["kate"], Path(tmp), Path(tmp))
            kate.katerc.write_text("[KTextEditor Renderer]\nAuto Color Theme Selection=true\nColor Theme=Dracula\n")
            cfg = core.Config()
            cfg.parser.read_dict({"theme": {"source": "Dracula"}})
            with mock.patch.object(cli, "need_kate", return_value=kate), \
                    mock.patch.object(core, "load_config", return_value=cfg), \
                    mock.patch.object(cli, "build_themes", return_value="Dracula"), \
                    mock.patch.object(cli, "step"), mock.patch.object(cli, "info"):
                cli.do_theme(mock.Mock(pick=False))
            self.assertIn("Auto Color Theme Selection=false", kate.katerc.read_text())

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
