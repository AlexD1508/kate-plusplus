#!/usr/bin/env bash
# Full install → apply → theme → backup → uninstall round trip in a throw-away $HOME.
# Never touches your real session: KPP_TEST=1 disables systemctl/hyprctl calls.
set -euo pipefail
cd "$(dirname "$0")/.."
root=$(mktemp -d)
trap 'rm -rf "$root"' EXIT
pass() { printf '  \033[32m✓\033[0m %s\n' "$1"; }
die()  { printf '  \033[31m✗\033[0m %s\n' "$1"; exit 1; }

run() { env -i HOME="$H" PATH=/usr/bin:/bin KPP_TEST=1 XDG_CURRENT_DESKTOP="${DESK:-GNOME}" ./bin/kate-plusplus "$@" >/dev/null; }

# --- 1. generic, existing Kate config + explicit mime default -------------
H=$root/generic; mkdir -p "$H/.config"
printf '[General]\nRecent Files Count=10\n\n[Other]\nX=1\n' > "$H/.config/katerc"
printf '[Default Applications]\ntext/plain=org.gnome.TextEditor.desktop\nimage/png=viewer.desktop\n' > "$H/.config/mimeapps.list"
cp "$H/.config/katerc" "$root/katerc.orig"; cp "$H/.config/mimeapps.list" "$root/mime.orig"

run install --yes
grep -q '^Current Scheme=' "$H/.config/katerc"                && die "a shortcut scheme is set (it would wipe normal keys)"
grep -q '^Stash unsaved file changes=true' "$H/.config/katerc"  || die "stash not enabled"
grep -q '^Color Theme=Kate++ ' "$H/.config/katerc"              || die "theme not set"
grep -q '^Recent Files Count=10' "$H/.config/katerc"            || die "existing setting lost"
grep -q '^text/plain=org.kde.kate.desktop' "$H/.config/mimeapps.list" || die "default editor not set"
for f in kxmlgui5/kate/kateui.rc kxmlgui5/katepart/katepart5ui.rc kxmlgui5/keyboardmacros/ui.rc \
         katepart5/script/commands/kate-plusplus.js \
         org.kde.syntax-highlighting/themes/kate-plusplus-dark.theme kate/sessions/Notepad.katesession; do
    [[ -f $H/.local/share/$f ]] || die "missing $f"
done
pass "generic install"

sed -i 's/^accent =$/accent = #e06c75/; s/^syntax-colors = balanced/syntax-colors = vivid/' "$H/.config/kate-plusplus/config.ini"
run apply --yes
run theme
python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$H/.local/share/org.kde.syntax-highlighting/themes/kate-plusplus-dark.theme"
pass "apply + theme with overrides"

run backup
ls "$H/.local/share/kate-plusplus/backups/"*.tar.gz >/dev/null || die "no snapshot"
pass "backup"

run uninstall --yes
diff -u "$root/katerc.orig" "$H/.config/katerc"    || die "katerc not restored"
diff -u "$root/mime.orig" "$H/.config/mimeapps.list" || die "mimeapps.list not restored"
[[ -f $H/.local/share/kate/sessions/Notepad.katesession ]] || die "user session was deleted"
pass "uninstall restores everything, keeps notes"

# --- 2. fresh Kate on KDE Plasma ---------------------------------------
H=$root/plasma; mkdir -p "$H/.config"
printf '[General]\nAccentColor=61,174,233\n\n[Colors:View]\nBackgroundNormal=20,22,24\nForegroundNormal=252,252,252\nForegroundNegative=218,68,83\n' > "$H/.config/kdeglobals"
DESK=KDE run install --yes
grep -q '^Color Theme=Kate++ Plasma' "$H/.config/katerc" || die "plasma theme not chosen"
grep -q 'kdeglobals' "$H/.config/systemd/user/kate-plusplus-theme.path" || die "plasma watcher missing"
DESK=KDE run uninstall --yes
[[ ! -s $H/.config/katerc ]] || ! grep -q 'Notepad++\|Kate++' "$H/.config/katerc" || die "fresh uninstall left Kate++ keys"
pass "plasma install + clean uninstall"

# --- Language menu touches only what Kate++ owns ---
H=$root/menu; mkdir -p "$H/.local/share/kxmlgui5/katepart"
cat > "$H/.local/share/kxmlgui5/katepart/katepart5ui.rc" <<'XML'
<!DOCTYPE gui SYSTEM 'kpartgui.dtd'>
<gui name="KatePartView" version="999">
 <MenuBar>
  <Menu name="tools"><text>Tools</text><Action name="tools_highlighting"/></Menu>
  <Menu name="settings"><text>Settings</text></Menu>
 </MenuBar>
 <ActionProperties>
  <Action name="tools_highlighting" shortcut="Ctrl+Alt+L" text="My Highlighting"/>
 </ActionProperties>
</gui>
XML
run install --yes
grep -q 'text="&amp;Language"' "$H/.local/share/kxmlgui5/katepart/katepart5ui.rc" || die "Language menu not added"
sed -i 's/^language-menu = true/language-menu = false/' "$H/.config/kate-plusplus/config.ini"
run apply --yes
run uninstall --yes
python3 - "$H/.local/share/kxmlgui5/katepart/katepart5ui.rc" <<'PY' || die "the user's own entry was not restored exactly"
import sys, xml.dom.minidom as m
root = m.parse(sys.argv[1]).documentElement
bar = next(n for n in root.childNodes if n.nodeType == 1 and n.tagName == "MenuBar")
assert not any(n.nodeType == 1 and n.tagName == "Action" for n in bar.childNodes), "Kate++ entry left on the bar"
a = [a for a in root.getElementsByTagName("Action") if a.parentNode.tagName == "ActionProperties"
     and a.getAttribute("name") == "tools_highlighting"]
assert len(a) == 1, a
assert a[0].getAttribute("text") == "My Highlighting" and a[0].getAttribute("shortcut") == "Ctrl+Alt+L"
assert not [k for k in a[0].attributes.keys() if k.startswith("kate-plusplus")], a[0].attributes.keys()
PY
pass "Language menu: only Kate++'s own entries are removed, the user's label comes back"

# --- a shortcut file Kate++ created keeps shortcuts the user added later ---
H=$root/created; mkdir -p "$H"
run install --yes
F="$H/.local/share/kxmlgui5/kate/kateui.rc"
[[ -f $F ]] || die "Kate++ should have created kateui.rc"
python3 - "$F" <<'PY'
import sys, xml.dom.minidom as m
doc = m.parse(sys.argv[1])
props = doc.getElementsByTagName("ActionProperties")[0]
a = doc.createElement("Action"); a.setAttribute("name", "view_new_view"); a.setAttribute("shortcut", "Ctrl+Alt+N")
props.appendChild(a); open(sys.argv[1], "w").write(doc.toxml())
PY
run uninstall --yes
[[ -f $F ]] || die "uninstall deleted a file that holds the user's own shortcut"
grep -q 'view_new_view' "$F" || die "the user's own shortcut was removed"
grep -q 'kate-plusplus=' "$F" && die "Kate++ entries left behind"
H=$root/created2; mkdir -p "$H"
run install --yes
run uninstall --yes
[[ ! -e $H/.local/share/kxmlgui5/kate/kateui.rc ]] || die "a Kate++-only file should be removed on uninstall"
pass "files Kate++ created: removed when untouched, kept with the user's own shortcuts"

# --- 3. user values Kate++ overwrites come back exactly, even without the full backup ---
H=$root/restore; mkdir -p "$H/.config"
printf '[General]\nTabbar Tab Limit=5\nShow Status Bar=false\nMy Own Key=1\n\n[KTextEditor Renderer]\nColor Theme=Dracula\n' > "$H/.config/katerc"
cp "$H/.config/katerc" "$root/katerc.user"
run install --yes
grep -q '^Tabbar Tab Limit=0' "$H/.config/katerc" || die "install did not apply Kate++ settings"
rm "$H/.local/state/kate-plusplus/katerc.before-kate-plusplus"   # force the key-by-key path
run uninstall --yes
diff -u "$root/katerc.user" "$H/.config/katerc" || die "overwritten user values were not restored exactly"
pass "uninstall restores each overwritten value exactly"

# --- upgrade from 1.0.x (no per-key records yet): originals come from the pre-install backup ---
H=$root/upgrade; mkdir -p "$H/.config"
printf '[General]\nTabbar Tab Limit=5\n\n[KTextEditor Renderer]\nColor Theme=Dracula\n' > "$H/.config/katerc"
cp "$H/.config/katerc" "$root/katerc.upgrade"
run install --yes
python3 - "$H/.local/state/kate-plusplus/state.json" <<'PY'
import json, sys
p = sys.argv[1]; s = json.load(open(p)); s.pop("katerc_before", None); json.dump(s, open(p, "w"))
PY
run apply --yes                                                        # 1.0.x → this version
rm "$H/.local/state/kate-plusplus/katerc.before-kate-plusplus"
run uninstall --yes
diff -u "$root/katerc.upgrade" "$H/.config/katerc" || die "upgrade recorded Kate++ values instead of the originals"
pass "upgrade: originals are taken from the pre-install backup"

# --- legacy: no records and no backup → managed settings removed, not falsely 'restored' ---
H=$root/legacy; mkdir -p "$H/.config"
run install --yes
python3 - "$H/.local/state/kate-plusplus/state.json" <<'PY'
import json, sys
p = sys.argv[1]; s = json.load(open(p)); s.pop("katerc_before", None); json.dump(s, open(p, "w"))
PY
rm -f "$H/.local/state/kate-plusplus/katerc.before-kate-plusplus"
out=$(env -i HOME="$H" PATH=/usr/bin:/bin KPP_TEST=1 ./bin/kate-plusplus uninstall --yes 2>&1)
grep -q 'Kate++ settings removed' <<<"$out" || die "legacy uninstall should say settings were removed"
grep -q '^Tabbar Tab Limit=' "$H/.config/katerc" && die "legacy uninstall left Kate++ settings behind"
pass "legacy uninstall removes Kate++ settings and says so"

# --- legacy + 'theme' before 'apply', no backup: partial records must not count as complete ---
H=$root/partial; mkdir -p "$H/.config"
run install --yes
python3 - "$H/.local/state/kate-plusplus/state.json" <<'PY'
import json, sys
p = sys.argv[1]; s = json.load(open(p)); s.pop("katerc_before", None); s.pop("katerc_complete", None); json.dump(s, open(p, "w"))
PY
rm -f "$H/.local/state/kate-plusplus/katerc.before-kate-plusplus"
sed -i 's/^source = .*/source = light/' "$H/.config/kate-plusplus/config.ini"
run theme                                     # records only the two renderer keys
python3 - "$H/.local/state/kate-plusplus/state.json" <<'PY' || die "theme did not create the partial legacy records"
import json, sys
s = json.load(open(sys.argv[1]))
assert s.get("katerc_complete") is False, s.get("katerc_complete")
keys = set(s.get("katerc_before", {}))
assert keys == {"[KTextEditor Renderer]\tAuto Color Theme Selection", "[KTextEditor Renderer]\tColor Theme"}, keys
PY
out=$(env -i HOME="$H" PATH=/usr/bin:/bin KPP_TEST=1 ./bin/kate-plusplus uninstall --yes 2>&1)
grep -q 'Kate++ settings removed' <<<"$out" || die "partial legacy records were treated as a full restore"
grep -q '^Tabbar Tab Limit=' "$H/.config/katerc" && die "partial legacy uninstall left Kate++ settings behind"
pass "partial legacy records fall back to removing Kate++ settings"
# --- prettify: format-on-save off by default, your own settings.json restored on uninstall ---
H=$root/format; mkdir -p "$H/.config/kate/formatting"
printf '{\n    "formatterForPython": "black",\n    "formatOnSave": true\n}\n' > "$H/.config/kate/formatting/settings.json"
cp "$H/.config/kate/formatting/settings.json" "$root/format.orig"
run install --yes
python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); assert d["formatOnSave"] is False and d["formatterForPython"] == "black", d' \
    "$H/.config/kate/formatting/settings.json" || die "format-on-save not turned off (or user keys lost)"
grep -q 'name="format_document" shortcut="Ctrl+Alt+Shift+B"' "$H/.local/share/kxmlgui5/formatplugin/ui.rc" || die "format shortcut missing"
run uninstall --yes
python3 -c 'import json,sys; a,b=(json.load(open(f)) for f in sys.argv[1:]); assert a == b, (a, b)' \
    "$root/format.orig" "$H/.config/kate/formatting/settings.json" || die "formatting settings not restored"
H=$root/format2; mkdir -p "$H/.config"
run install --yes; run uninstall --yes
[[ -e $H/.config/kate/formatting/settings.json ]] && die "uninstall left a formatting settings file Kate++ created"
# custom [kateformatplugin] configPath (Kate 26.08+ reads it): that file is changed and restored
if PYTHONPATH=lib python3 -c 'import sys; from kpp import core, formatting
k = core.detect_kate(); sys.exit(0 if formatting._kate_at_least(k, formatting.CONFIG_PATH_MIN_KATE) else 1)'; then
    H=$root/format3; mkdir -p "$H/.config" "$H/fmt"
    printf '[kateformatplugin]\nconfigPath=%s\n' "$H/fmt/my.json" > "$H/.config/katerc"
    printf '{\n    "formatOnSave": true\n}\n' > "$H/fmt/my.json"; chmod 600 "$H/fmt/my.json"
    run install --yes
    python3 -c 'import json,sys; assert json.load(open(sys.argv[1]))["formatOnSave"] is False' "$H/fmt/my.json" \
        || die "custom configPath not honoured"
    [[ $(stat -c %a "$H/fmt/my.json") == 600 ]] || die "settings file permissions changed"
    [[ -e $H/.config/kate/formatting/settings.json ]] && die "wrote the default file although configPath is set"
    # the same file through a '..' alias must reuse its baseline, not record Kate++'s value
    sed -i "s|^configPath=.*|configPath=$H/fmt/../fmt/my.json|" "$H/.config/katerc"
    run apply --yes
    sed -i "s|^configPath=.*|configPath=$H/fmt/my.json|" "$H/.config/katerc"
    # switch configPath to a second file and apply again: both files must be restored
    printf '{\n    "formatOnSave": true\n}\n' > "$H/fmt/other.json"
    sed -i "s|^configPath=.*|configPath=$H/fmt/other.json|" "$H/.config/katerc"
    run apply --yes
    python3 -c 'import json,sys; assert json.load(open(sys.argv[1]))["formatOnSave"] is False' "$H/fmt/other.json" \
        || die "new configPath not honoured"
    run uninstall --yes
    for f in my other; do
        python3 -c 'import json,sys; assert json.load(open(sys.argv[1]))["formatOnSave"] is True' "$H/fmt/$f.json" \
            || die "settings file $f.json not restored"
    done
else   # older Kate ignores configPath, so the default file is the one Kate++ must change
    H=$root/format3; mkdir -p "$H/.config"
    printf '[kateformatplugin]\nconfigPath=%s\n' "$H/ignored.json" > "$H/.config/katerc"
    run install --yes
    python3 -c 'import json,sys; assert json.load(open(sys.argv[1]))["formatOnSave"] is False' \
        "$H/.config/kate/formatting/settings.json" || die "default settings file not used on older Kate"
    [[ -e $H/ignored.json ]] && die "wrote configPath although this Kate ignores it"
    run uninstall --yes
fi
# Kate before 26.08 ignores configPath: Kate++ must then change the default file
env -i HOME="$H" PATH=/usr/bin:/bin PYTHONPATH=lib python3 - <<'PY' || die "configPath used on a Kate that ignores it"
import pathlib
from kpp import core, formatting
k = core.Kate("native", ["kate"], core.XDG_CONFIG, core.XDG_DATA, "25.08.0")
assert formatting.settings_path(k) == (core.XDG_CONFIG / "kate/formatting/settings.json").resolve()
k.version = "26.08.0"
assert formatting.settings_path(k) != (core.XDG_CONFIG / "kate/formatting/settings.json").resolve()
PY
# a typo in format-on-save warns and keeps the default (off) instead of silently meaning false
H=$root/format4; mkdir -p "$H/.config"
run install --yes
sed -i 's/^format-on-save = .*/format-on-save = tru/' "$H/.config/kate-plusplus/config.ini"
out=$(env -i HOME="$H" PATH=/usr/bin:/bin KPP_TEST=1 ./bin/kate-plusplus apply --yes 2>&1)
grep -q "isn't true or false" <<<"$out" || die "invalid format-on-save value did not warn"
pass "prettify: format-on-save off, shortcut merged, settings restored exactly (incl. configPath, 0600)"

echo "All sandbox tests passed."
