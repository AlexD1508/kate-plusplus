"""Popular themes Kate doesn't ship, built from each project's official palette.

Each entry keeps its designer's token choices (which colour keywords, strings, functions … get)
and is only lifted where needed so every colour meets WCAG AA contrast (4.5:1) against its
background. All source palettes are MIT-licensed; credits are in each theme's metadata.
"""
from __future__ import annotations

from .theme import assemble, mix

# (designer, project URL) — every palette below is MIT-licensed
ROSE_PINE = ("the Rosé Pine team", "https://rosepinetheme.com")
KANAGAWA = ("rebelot", "https://github.com/rebelot/kanagawa.nvim")
EVERFOREST = ("sainnhe", "https://github.com/sainnhe/everforest")
NIGHT_OWL = ("Sarah Drasner", "https://github.com/sdras/night-owl-vscode-theme")
SYNTHWAVE = ("Robb Owen", "https://github.com/robb0wen/synthwave-vscode")


def _ui(bg, fg, muted, current_line, selection, line_numbers, raised, raised2, error,
        on_selection=None):
    return {"bg": bg, "fg": fg, "fg_muted": muted, "current_line": current_line,
            "selection": selection, "on_selection": on_selection or fg,
            "line_numbers": line_numbers, "raised": raised, "raised2": raised2,
            "error": error, "error_bg": mix(bg, error, 0.28), "on_error_bg": fg,
            "accent": error, "comment": muted}


def _rose_pine(c):
    ui = _ui(c["base"], c["text"], c["subtle"], c["surface"], c["hl_med"], c["muted"],
             c["overlay"], c["hl_high"], c["love"])
    tokens = {"keyword": c["pine"], "control": c["pine"], "function": c["rose"],
              "builtin": c["love"], "import": c["pine"], "preproc": c["iris"],
              "type": c["foam"], "attribute": c["iris"], "string": c["gold"],
              "special": c["foam"], "number": c["gold"], "constant": c["gold"],
              "comment": c["muted"], "operator": c["subtle"], "others": c["iris"]}
    return ui, tokens


def _kanagawa(c):
    ui = _ui(c["bg"], c["fg"], c["fg_dim"], c["cursorline"], c["selection"], c["linenr"],
             c["raised"], c["raised2"], c["error"])
    tokens = {"keyword": c["keyword"], "control": c["keyword"], "function": c["function"],
              "builtin": c["builtin"], "import": c["preproc"], "preproc": c["preproc"],
              "type": c["type"], "attribute": c["identifier"], "string": c["string"],
              "special": c["special"], "number": c["number"], "constant": c["constant"],
              "comment": c["comment"], "operator": c["operator"], "others": c["identifier"]}
    return ui, tokens


def _everforest(c):
    ui = _ui(c["bg0"], c["fg"], c["grey2"], c["bg1"], c["bg_visual"], c["grey0"],
             c["bg2"], c["bg3"], c["red"])
    tokens = {"keyword": c["red"], "control": c["red"], "function": c["green"],
              "builtin": c["blue"], "import": c["purple"], "preproc": c["purple"],
              "type": c["yellow"], "attribute": c["orange"], "string": c["aqua"],
              "special": c["yellow"], "number": c["purple"], "constant": c["purple"],
              "comment": c["grey1"], "operator": c["orange"], "others": c["blue"]}
    return ui, tokens


ROSE_PINE_MAIN = dict(base="191724", surface="1f1d2e", overlay="26233a", muted="6e6a86",
                      subtle="908caa", text="e0def4", love="eb6f92", gold="f6c177",
                      rose="ebbcba", pine="31748f", foam="9ccfd8", iris="c4a7e7",
                      hl_med="403d52", hl_high="524f67")
ROSE_PINE_MOON = dict(base="232136", surface="2a273f", overlay="393552", muted="6e6a86",
                      subtle="908caa", text="e0def4", love="eb6f92", gold="f6c177",
                      rose="ea9a97", pine="3e8fb0", foam="9ccfd8", iris="c4a7e7",
                      hl_med="44415a", hl_high="56526e")
ROSE_PINE_DAWN = dict(base="faf4ed", surface="fffaf3", overlay="f2e9e1", muted="9893a5",
                      subtle="797593", text="575279", love="b4637a", gold="ea9d34",
                      rose="d7827e", pine="286983", foam="56949f", iris="907aa9",
                      hl_med="dfdad9", hl_high="cecacd")

KANAGAWA_WAVE = dict(bg="1f1f28", fg="dcd7ba", fg_dim="c8c093", cursorline="2a2a37",
                     selection="2d4f67", linenr="54546d", raised="2a2a37", raised2="363646",
                     error="e82424", keyword="957fb8", function="7e9cd8", builtin="7fb4ca",
                     preproc="e46876", type="7aa89f", identifier="e6c384", string="98bb6c",
                     special="7fb4ca", number="d27e99", constant="ffa066", comment="727169",
                     operator="c0a36e")
KANAGAWA_DRAGON = dict(bg="181616", fg="c5c9c5", fg_dim="a6a69c", cursorline="282727",
                       selection="2d4f67", linenr="625e5a", raised="282727", raised2="393836",
                       error="e82424", keyword="8992a7", function="8ba4b0", builtin="949fb5",
                       preproc="c4746e", type="8ea4a2", identifier="c4b28a", string="8a9a7b",
                       special="949fb5", number="a292a3", constant="b6927b", comment="737c73",
                       operator="9e9b93")
KANAGAWA_LOTUS = dict(bg="f2ecbc", fg="545464", fg_dim="43436c", cursorline="e4d794",
                      selection="c9cbd1", linenr="716e61", raised="e7dba0", raised2="dcd5ac",
                      error="e82424", keyword="624c83", function="4d699b", builtin="6693bf",
                      preproc="c84053", type="597b75", identifier="77713f", string="6f894e",
                      special="6693bf", number="b35b79", constant="cc6d00", comment="8a8980",
                      operator="836f4a")

EVERFOREST_DARK = dict(bg0="2d353b", bg1="343f44", bg2="3d484d", bg3="475258", bg_visual="543a48",
                       fg="d3c6aa", red="e67e80", orange="e69875", yellow="dbbc7f",
                       green="a7c080", aqua="83c092", blue="7fbbb3", purple="d699b6",
                       grey0="7a8478", grey1="859289", grey2="9da9a0")
EVERFOREST_LIGHT = dict(bg0="fdf6e3", bg1="f4f0d9", bg2="efebd4", bg3="e6e2cc", bg_visual="f0f2d4",
                        fg="5c6a72", red="f85552", orange="f57d26", yellow="dfa000",
                        green="8da101", aqua="35a77c", blue="3a94c5", purple="df69ba",
                        grey0="a6b0a0", grey1="939f91", grey2="829181")


def _night_owl():
    ui = _ui("011627", "d6deeb", "a7b4c4", "01111d", "1d3b53", "4b6479", "0b2942", "13344f",
             "ef5350")
    tokens = {"keyword": "c792ea", "control": "c792ea", "function": "82aaff",
              "builtin": "addb67", "import": "c792ea", "preproc": "c792ea", "type": "ffcb8b",
              "attribute": "addb67", "string": "ecc48d", "special": "7fdbca",
              "number": "f78c6c", "constant": "ff5874", "comment": "637777",
              "operator": "7fdbca", "others": "addb67", "variable": "d7dbe0"}
    return ui, tokens


def _synthwave():
    ui = _ui("262335", "ffffff", "bbbbbb", "2a2139", "463465", "8a8698", "34294f", "443873",
             "fe4450")
    tokens = {"keyword": "fede5d", "control": "fede5d", "function": "36f9f6",
              "builtin": "72f1b8", "import": "fede5d", "preproc": "fe4450", "type": "fe4450",
              "attribute": "ff7edb", "string": "ff8b39", "special": "72f1b8",
              "number": "f97e72", "constant": "f97e72", "comment": "848bbd",
              "operator": "fede5d", "others": "ff7edb", "variable": "ff7edb"}
    return ui, tokens


# slug → (display name, builder, (designer, url), dark?)
PORTS = {
    "rose-pine": ("Rosé Pine", lambda: _rose_pine(ROSE_PINE_MAIN), ROSE_PINE, True),
    "rose-pine-moon": ("Rosé Pine Moon", lambda: _rose_pine(ROSE_PINE_MOON), ROSE_PINE, True),
    "rose-pine-dawn": ("Rosé Pine Dawn", lambda: _rose_pine(ROSE_PINE_DAWN), ROSE_PINE, False),
    "kanagawa-wave": ("Kanagawa Wave", lambda: _kanagawa(KANAGAWA_WAVE), KANAGAWA, True),
    "kanagawa-dragon": ("Kanagawa Dragon", lambda: _kanagawa(KANAGAWA_DRAGON), KANAGAWA, True),
    "kanagawa-lotus": ("Kanagawa Lotus", lambda: _kanagawa(KANAGAWA_LOTUS), KANAGAWA, False),
    "everforest-dark": ("Everforest Dark", lambda: _everforest(EVERFOREST_DARK), EVERFOREST, True),
    "everforest-light": ("Everforest Light", lambda: _everforest(EVERFOREST_LIGHT), EVERFOREST, False),
    "night-owl": ("Night Owl", _night_owl, NIGHT_OWL, True),
    "synthwave-84": ("Synthwave '84", _synthwave, SYNTHWAVE, True),
}

# family → (dark variant, light variant)
FAMILIES = {
    "rose-pine": ("rose-pine", "rose-pine-dawn"),
    "kanagawa": ("kanagawa-wave", "kanagawa-lotus"),
    "everforest": ("everforest-dark", "everforest-light"),
}


def designer(slug):
    return PORTS[slug][2][0]


def build(slug):
    name, builder, (author, url), _ = PORTS[slug]
    ui, tokens = builder()
    return assemble(name, ui, tokens, token_floor=4.5, comment_floor=4.5,
                    keyword_style={"bold": True},
                    copyright=[f"Palette: {name} by {author}, {url} (MIT)",
                               "Kate port: kate-plusplus contributors"])
