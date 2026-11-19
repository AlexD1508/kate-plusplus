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
grep -q '^Show Url Nav Bar=true' "$H/.config/katerc"            || die "breadcrumbs not enabled"
grep -q '^Show Symbol In Navigation Bar=true' "$H/.config/katerc" || die "breadcrumb symbol not enabled"
grep -q '^text/plain=org.kde.kate.desktop' "$H/.config/mimeapps.list" || die "default editor not set"
for f in kxmlgui5/kate/kateui.rc kxmlgui5/katepart/katepart5ui.rc kxmlgui5/keyboardmacros/ui.rc \
         katepart5/script/commands/kate-plusplus.js \
         org.kde.syntax-highlighting/themes/kate-plusplus-dark.theme kate/sessions/Notepad.katesession; do
    [[ -f $H/.local/share/$f ]] || die "missing $f"
done
pass "generic install"

sed -i 's/^accent =$/accent = #e06c75/; s/^syntax-colors = balanced/syntax-colors = vivid/' "$H/.config/kate-plusplus/config.ini"
sed -i 's/^breadcrumbs = true/breadcrumbs = false/' "$H/.config/kate-plusplus/config.ini"
run apply --yes
grep -q '^Show Url Nav Bar=false' "$H/.config/katerc" || die "breadcrumbs = false not applied"

# config.ini from an older Kate++ (no breadcrumbs line) gains the option on apply,
# with its comment, while the user's own values stay as they are
sed -i '/^breadcrumbs = /d' "$H/.config/kate-plusplus/config.ini"
run apply --yes
grep -q '^breadcrumbs = true' "$H/.config/kate-plusplus/config.ini" || die "new option not added to an existing config.ini"
grep -q '^accent = #e06c75' "$H/.config/kate-plusplus/config.ini"   || die "upgrade changed the user's own values"
[[ $(grep -c '^breadcrumbs = ' "$H/.config/kate-plusplus/config.ini") == 1 ]] || die "option added twice"
run apply --yes
[[ $(grep -c '^breadcrumbs = ' "$H/.config/kate-plusplus/config.ini") == 1 ]] || die "option duplicated on re-apply"
# Every fixture below drops one template option (font-size) first, so apply has to insert it:
# the insertion, the parse check and the rejection paths all run.
C="$H/.config/kate-plusplus/config.ini"
upgrade() {  # run only the migration, capture its warnings; fails the test on an exception
    env -i HOME="$H" PATH=/usr/bin:/bin KPP_TEST=1 python3 - "$PWD/lib" 2>&1 >/dev/null <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
from kpp import core
print(",".join(core.upgrade_user_config()))
PY
}
loads() { python3 -c 'import configparser,sys; c=configparser.ConfigParser(interpolation=None); c.read(sys.argv[1])' "$C"; }

# the other ways ConfigParser accepts a file: a header with a trailing comment, another
# capitalisation, and ':' as the delimiter. Existing options are recognised, never duplicated.
sed -i 's/^\[editor\]$/[editor]  # my editor settings/; s/^minimap = true .*/MiniMap = true/; s/^breadcrumbs = true .*/breadcrumbs: true/; /^font-size = /d' "$C"
run apply --yes
loads || die "upgrade broke a config written in alternative syntax"
[[ $(grep -c '^\[editor\]' "$C") == 1 ]]   || die "section with a trailing comment was duplicated"
[[ $(grep -ci '^minimap' "$C") == 1 ]]      || die "MiniMap was duplicated"
[[ $(grep -c '^breadcrumbs' "$C") == 1 ]]   || die "'breadcrumbs:' was duplicated"
[[ $(grep -c '^font-size = ' "$C") == 1 ]]  || die "missing font-size was not inserted exactly once"
grep -q '^MiniMap = true$' "$C"             || die "the user's original text was changed"

# an indented "[example]" inside a multi-line value is not a section (ConfigParser rules)
python3 - "$C" <<'PY'
import sys
p = sys.argv[1]
s = open(p).read().replace("[editor]  # my editor settings\n",
                           "[editor]  # my editor settings\nnotes = example configuration\n    [example]\n", 1)
open(p, "w").write(s)
PY
sed -i '/^font-size = /d' "$C"
run apply --yes
loads || die "upgrade broke a config with a multi-line value"
[[ $(grep -ci '^minimap' "$C") == 1 ]]     || die "option after a multi-line value was duplicated"
[[ $(grep -c '^font-size = ' "$C") == 1 ]] || die "font-size not inserted next to a multi-line value"
grep -q '^    \[example\]$' "$C"           || die "the multi-line value was changed"

# "[ editor ]" is a different section for ConfigParser: the option must land in a real [editor]
cp "$C" "$root/config.before"
printf '[ editor ]\nnote = spaced\n' > "$C"
added=$(upgrade | tail -1)
loads || die "upgrade broke a config with a spaced section name"
python3 -c 'import configparser,sys; c=configparser.ConfigParser(interpolation=None); c.read(sys.argv[1]); sys.exit(0 if c.has_option("editor","breadcrumbs") and c.has_section(" editor ") else 1)' "$C" \
    || die "options were added to '[ editor ]' instead of [editor] (got: $added)"
cp "$root/config.before" "$C"

# a config.ini that's already unreadable is never rewritten, and the user is told
sed -i '/^font-size = /d' "$C"
printf '\n[editor]\nfont = auto\n' >> "$C"            # duplicate section → ConfigParser error
cp "$C" "$root/config.broken"
out=$(upgrade)
cmp -s "$root/config.broken" "$C"            || die "an unreadable config.ini was rewritten"
grep -q "left unchanged" <<<"$out"           || die "no warning for an unreadable config.ini"
cp "$root/config.before" "$C"

# read / write errors warn and never stop apply (missing options just use their defaults)
sed -i '/^font-size = /d' "$C"
chmod 000 "$C"
out=$(upgrade); chmod 644 "$C"
grep -q "Couldn't read" <<<"$out"            || die "no warning when config.ini can't be read"
chmod 555 "$(dirname "$C")"
out=$(upgrade); chmod 755 "$(dirname "$C")"
grep -q "Couldn't write" <<<"$out"           || die "no warning when config.ini can't be written"
cp "$root/config.before" "$C"
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

echo "All sandbox tests passed."
