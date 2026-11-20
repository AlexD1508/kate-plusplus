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
grep -A6 '^\[lspclient\]' "$H/.config/katerc" | grep -q '^InlayHints=true' || die "smart highlighting not enabled"
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

grep -q '^Auto Save' "$H/.config/katerc" && die "auto-save = off must not touch Kate's auto-save keys"
sed -i 's/^auto-save = off/auto-save = 30/' "$H/.config/kate-plusplus/config.ini"
run apply --yes
grep -q '^Auto Save=true' "$H/.config/katerc"              || die "auto-save interval not enabled"
grep -q '^Auto Save Interval=30' "$H/.config/katerc"       || die "auto-save interval not set"
grep -q '^Auto Save On Focus Out=true' "$H/.config/katerc" || die "auto-save on focus out not set"
sed -i 's/^auto-save = 30/auto-save = focus/' "$H/.config/kate-plusplus/config.ini"
run apply --yes
grep -q '^Auto Save=true' "$H/.config/katerc"              || die "focus mode needs the Auto Save master switch (KTextEditor checks both)"
grep -q '^Auto Save On Focus Out=true' "$H/.config/katerc" || die "focus mode must save on focus out"
grep -q '^Auto Save Interval=0$' "$H/.config/katerc"       || die "focus mode must set the idle interval to 0 (kdeglobals may cascade one)"
sed -i 's/^auto-save = focus/auto-save = 2/' "$H/.config/kate-plusplus/config.ini"
run apply --yes
grep -q '^Auto Save' "$H/.config/katerc"                   && die "an out-of-range value must turn Kate++ auto-save off"
sed -i 's/^auto-save = 2/auto-save = focus/' "$H/.config/kate-plusplus/config.ini"
run apply --yes
sed -i 's/^auto-save = focus/auto-save = nonsense/' "$H/.config/kate-plusplus/config.ini"
run apply --yes
grep -q '^Auto Save' "$H/.config/katerc"                   && die "an invalid value must undo Kate++ auto-save"
sed -i 's/^auto-save = nonsense/auto-save = focus/' "$H/.config/kate-plusplus/config.ini"
run apply --yes
grep -q '^Auto Save On Focus Out=true' "$H/.config/katerc" || die "focus not re-enabled before the off check"
sed -i 's/^auto-save = focus/auto-save = off/' "$H/.config/kate-plusplus/config.ini"
run apply --yes
grep -q '^Auto Save' "$H/.config/katerc"                   && die "auto-save = off did not undo Kate++'s keys"
pass "auto-save off / idle delay / focus out / invalid values"

run uninstall --yes
diff -u "$root/katerc.orig" "$H/.config/katerc"    || die "katerc not restored"
diff -u "$root/mime.orig" "$H/.config/mimeapps.list" || die "mimeapps.list not restored"
[[ -f $H/.local/share/kate/sessions/Notepad.katesession ]] || die "user session was deleted"
grep -q '^\[lspclient\]' "$H/.config/katerc" && die "uninstall left LSP settings behind"
pass "uninstall restores everything, keeps notes"

# --- auto-save is removed even when the user declines restoring the full backup ----
H=$root/autosave; mkdir -p "$H/.config"
printf '[General]\nRecent Files Count=10\n' > "$H/.config/katerc"
run install --yes
sed -i 's/^auto-save = off/auto-save = focus/' "$H/.config/kate-plusplus/config.ini"
run apply --yes
# uninstall, answering "yes, remove" but "no" to restoring the full settings backup
env -i HOME="$H" PATH=/usr/bin:/bin KPP_TEST=1 python3 - "$PWD/lib" >/dev/null <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
from types import SimpleNamespace
from kpp import cli
answers = iter([True, False])           # remove Kate++? yes · restore full backup? no
cli.ask = lambda *a, **k: next(answers)
cli.do_uninstall(SimpleNamespace(yes=False))
PY
grep -q '^Auto Save' "$H/.config/katerc" && die "declined restore left Kate++ auto-save enabled"
grep -q '^Recent Files Count=10' "$H/.config/katerc" || die "declined restore lost the user's own setting"
pass "auto-save removed even when restoring the full backup is declined"

# --- the user's own Kate auto-save setting survives off, on → off, and uninstall ---
H=$root/ownautosave; mkdir -p "$H/.config"
printf '[KTextEditor Document]\nAuto Save=true\nAuto Save Interval=60\n' > "$H/.config/katerc"
run install --yes
grep -q '^Auto Save Interval=60' "$H/.config/katerc" || die "auto-save = off changed the user's own setting"
sed -i 's/^auto-save = off/auto-save = focus/' "$H/.config/kate-plusplus/config.ini"
run apply --yes
grep -q '^Auto Save Interval=0$' "$H/.config/katerc" || die "focus mode kept an interval"
sed -i 's/^auto-save = focus/auto-save = off/' "$H/.config/kate-plusplus/config.ini"
run apply --yes
grep -q '^Auto Save Interval=60' "$H/.config/katerc"   || die "switching back to off didn't restore the user's interval"
grep -q '^Auto Save On Focus Out' "$H/.config/katerc"  && die "switching back to off left Kate++'s focus key"
sed -i 's/^auto-save = off/auto-save = 30/' "$H/.config/kate-plusplus/config.ini"
run apply --yes
rm "$H/.local/state/kate-plusplus/katerc.before-kate-plusplus"       # force the per-key restore
run uninstall --yes
grep -q '^Auto Save=true' "$H/.config/katerc"        || die "uninstall didn't restore the user's Auto Save"
grep -q '^Auto Save Interval=60' "$H/.config/katerc" || die "uninstall didn't restore the user's interval"
pass "user's own Kate auto-save setting is restored exactly"

# --- after "off", auto-save is the user's again: a later own setting survives uninstall ---
H=$root/autosaveafteroff; mkdir -p "$H/.config"
run install --yes
sed -i 's/^auto-save = off/auto-save = focus/' "$H/.config/kate-plusplus/config.ini"
run apply --yes
sed -i 's/^auto-save = focus/auto-save = off/' "$H/.config/kate-plusplus/config.ini"
run apply --yes
printf '\n[KTextEditor Document]\nAuto Save=true\nAuto Save Interval=60\n' >> "$H/.config/katerc"   # user's own, later
rm -f "$H/.local/state/kate-plusplus/katerc.before-kate-plusplus"                                   # per-key restore
run uninstall --yes
grep -q '^Auto Save Interval=60' "$H/.config/katerc" || die "uninstall overwrote auto-save the user set after 'off'"
grep -q '^Auto Save=true' "$H/.config/katerc"        || die "uninstall overwrote the user's later Auto Save"
pass "after off, a later own auto-save setting survives uninstall"

# --- turning auto-save on again after 'off' records the user's values from that moment ---
H=$root/autosavereacquire; mkdir -p "$H/.config"
printf '[KTextEditor Document]\nAuto Save Interval=90\n' > "$H/.config/katerc"   # pre-install value
run install --yes
cfg=$H/.config/kate-plusplus/config.ini
sed -i 's/^auto-save = off/auto-save = focus/' "$cfg"; run apply --yes
sed -i 's/^auto-save = focus/auto-save = off/' "$cfg"; run apply --yes
sed -i 's/^Auto Save Interval=90$/Auto Save Interval=45/' "$H/.config/katerc"     # user's own, later
grep -q '^Auto Save Interval=45$' "$H/.config/katerc" || die "test setup: interval not changed"
sed -i 's/^auto-save = off/auto-save = focus/' "$cfg"; run apply --yes
rm -f "$H/.local/state/kate-plusplus/katerc.before-kate-plusplus"                 # per-key restore
run uninstall --yes
grep -q '^Auto Save Interval=45$' "$H/.config/katerc" || die "uninstall restored the pre-install interval, not the user's later one"
pass "re-enabling auto-save records the user's current values"

# --- legacy fallback (records incomplete, no backup) puts recorded auto-save values back ---
H=$root/legacyautosave; mkdir -p "$H/.config"
printf '[KTextEditor Document]\nAuto Save=true\nAuto Save Interval=60\n' > "$H/.config/katerc"
run install --yes
sed -i 's/^auto-save = off/auto-save = focus/' "$H/.config/kate-plusplus/config.ini"
run apply --yes
python3 - "$H/.local/state/kate-plusplus/state.json" <<'PY'
import json, sys
p = sys.argv[1]; s = json.load(open(p)); s["katerc_complete"] = False; json.dump(s, open(p, "w"))
PY
rm "$H/.local/state/kate-plusplus/katerc.before-kate-plusplus"
run uninstall --yes
grep -q '^Auto Save=true' "$H/.config/katerc"        || die "legacy fallback deleted the recorded Auto Save"
grep -q '^Auto Save Interval=60' "$H/.config/katerc" || die "legacy fallback deleted the recorded interval"
grep -q '^Auto Save On Focus Out' "$H/.config/katerc" && die "legacy fallback kept Kate++'s focus key"
pass "legacy uninstall restores recorded auto-save values"

# --- ownership is on disk before the keys change: a later failure in apply can't orphan them ---
H=$root/autosavecrash; mkdir -p "$H/.config"
run install --yes
sed -i 's/^auto-save = off/auto-save = focus/' "$H/.config/kate-plusplus/config.ini"
env -i HOME="$H" PATH=/usr/bin:/bin KPP_TEST=1 python3 - "$PWD/lib" >/dev/null 2>&1 <<'PY' && die "the simulated failure didn't happen"
import sys
sys.path.insert(0, sys.argv[1])
from types import SimpleNamespace
from kpp import cli
def boom(*a, **k):
    raise RuntimeError("simulated failure after auto-save")
cli.set_default_editor = boom          # a later apply step fails
cli.do_apply(SimpleNamespace(yes=True))
PY
grep -q '^Auto Save On Focus Out=true' "$H/.config/katerc" || die "setup: auto-save wasn't enabled before the failure"
grep -q '"auto_save_managed": true' "$H/.local/state/kate-plusplus/state.json" || die "auto-save ownership wasn't saved before the failure"
sed -i 's/^auto-save = focus/auto-save = off/' "$H/.config/kate-plusplus/config.ini"
run apply --yes
grep -q '^Auto Save' "$H/.config/katerc" && die "auto-save stayed on after a failed apply"
pass "auto-save ownership survives a failure later in apply"

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

# --- 3. matching window colours: theme switch, manual choice is kept, uninstall restores ---
H=$root/window; mkdir -p "$H/.config"
printf '[UiSettings]\nColorScheme=BreezeDark\n' > "$H/.config/katerc"
run install --yes
sed -i 's/^source = .*/source = rose-pine/' "$H/.config/kate-plusplus/config.ini"
run apply --yes
grep -q '^ColorScheme=KatePlusPlusRosePine$' "$H/.config/katerc" || die "window colours don't follow the theme"
[[ -f $H/.local/share/color-schemes/KatePlusPlusRosePine.colors ]] || die "no matching colour scheme written"
sed -i 's/^ColorScheme=.*/ColorScheme=Solarized/' "$H/.config/katerc"      # user picks one in Kate
run apply --yes
run apply --yes                                                            # and it must stay picked
grep -q '^ColorScheme=Solarized$' "$H/.config/katerc" || die "a hand-picked window scheme was overwritten"
run uninstall --yes
grep -q '^ColorScheme=BreezeDark$' "$H/.config/katerc" || die "uninstall did not restore the original window scheme"
compgen -G "$H/.local/share/color-schemes/KatePlusPlus*" >/dev/null && die "uninstall left colour schemes behind"
pass "window colours match the theme, respect manual choices, uninstall restores"

# --- 4. user values Kate++ overwrites come back exactly, even without the full backup ---
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
# what 1.0.x left behind: no records, and none of the keys only newer versions write
env -i HOME="$H" PATH=/usr/bin:/bin KPP_TEST=1 PYTHONPATH=lib python3 - "$H/.local/state/kate-plusplus/state.json" <<'PY'
import json, sys
from kpp import cli, core
p = sys.argv[1]; s = json.load(open(p)); records = s.pop("katerc_before")
legacy = {f"{g}\t{k}" for g, k in cli.managed_keys()}
core.merge_rc(core.XDG_CONFIG / "katerc", [(*rec.split("\t", 1), "@delete" if old is None else old)
                            for rec, old in records.items() if rec not in legacy])
json.dump(s, open(p, "w"))
PY
run apply --yes                                                        # 1.0.x → this version
rm "$H/.local/state/kate-plusplus/katerc.before-kate-plusplus"
run uninstall --yes
diff -u "$root/katerc.upgrade" "$H/.config/katerc" || die "upgrade recorded Kate++ values instead of the originals"
pass "upgrade: originals are taken from the pre-install backup"

# --- legacy: no records and no backup → managed settings removed, not falsely 'restored' ---
H=$root/legacy; mkdir -p "$H/.config"
run install --yes
sed -i '/^\[lspclient\]/a MyOwnLspKey=1' "$H/.config/katerc"     # an LSP setting of the user's own
python3 - "$H/.local/state/kate-plusplus/state.json" <<'PY'
import json, sys
p = sys.argv[1]; s = json.load(open(p)); s.pop("katerc_before", None); json.dump(s, open(p, "w"))
PY
rm -f "$H/.local/state/kate-plusplus/katerc.before-kate-plusplus"
out=$(env -i HOME="$H" PATH=/usr/bin:/bin KPP_TEST=1 ./bin/kate-plusplus uninstall --yes 2>&1)
grep -q 'Kate++ settings removed' <<<"$out" || die "legacy uninstall should say settings were removed"
grep -q '^Tabbar Tab Limit=' "$H/.config/katerc" && die "legacy uninstall left Kate++ settings behind"
grep -q '^MyOwnLspKey=1' "$H/.config/katerc" || die "legacy uninstall removed the user's own LSP settings"
pass "legacy uninstall removes Kate++ settings and says so"

# --- legacy upgrade without backup: new [lspclient] keys are still restored exactly ---
H=$root/legacy-lsp; mkdir -p "$H/.config"
run install --yes
python3 - "$H/.local/state/kate-plusplus/state.json" "$H/.config/katerc" <<'PY'
import json, re, sys
p = sys.argv[1]; s = json.load(open(p))
s.pop("katerc_before", None); s.pop("katerc_complete", None); s["version"] = "1.0.1"
json.dump(s, open(p, "w"))
rc = open(sys.argv[2]).read()             # what 1.0.x left: no LSP keys of its own
rc = re.sub(r"\[lspclient\]\n(?:[^\[\n][^\n]*\n|\n)*", "", rc)
open(sys.argv[2], "w").write(rc + "\n[lspclient]\nInlayHints=false\nMyOwnLspKey=1\n")
PY
rm -f "$H/.local/state/kate-plusplus/katerc.before-kate-plusplus"
run apply --yes                                                        # 1.0.x → this version
grep -A8 '^\[lspclient\]' "$H/.config/katerc" | grep -q '^InlayHints=true' || die "upgrade did not enable inlay hints"
out=$(env -i HOME="$H" PATH=/usr/bin:/bin KPP_TEST=1 ./bin/kate-plusplus uninstall --yes 2>&1)
grep -q 'Kate++ settings removed' <<<"$out" || die "legacy upgrade should still use the fallback uninstall"
grep -q '^InlayHints=false' "$H/.config/katerc" || die "legacy uninstall did not restore the user's InlayHints=false"
for k in SemanticHighlighting AutoHover SignatureHelp Diagnostics; do
    grep -q "^$k=" "$H/.config/katerc" && die "legacy uninstall left $k behind"
done
grep -q '^MyOwnLspKey=1' "$H/.config/katerc" || die "legacy uninstall removed the user's own LSP settings"
pass "legacy upgrade without backup: LSP settings restored exactly"

# --- fallback uninstall (records incomplete, no backup): Show Url Nav Bar is removed like
# 1.0.x did (its record may hold Kate++'s own value), the newer symbol key is put back exactly ---
H=$root/legacy-crumbs; mkdir -p "$H/.config"
printf '[General]\nShow Symbol In Navigation Bar=false\n' > "$H/.config/katerc"
run install --yes
grep -q '^Show Symbol In Navigation Bar=true' "$H/.config/katerc" || die "breadcrumb symbol not enabled"
python3 - "$H/.local/state/kate-plusplus/state.json" <<'PY'
import json, sys
p = sys.argv[1]; s = json.load(open(p)); s["katerc_complete"] = False; json.dump(s, open(p, "w"))
PY
rm -f "$H/.local/state/kate-plusplus/katerc.before-kate-plusplus"
run uninstall --yes
grep -q '^Show Symbol In Navigation Bar=false$' "$H/.config/katerc" || die "fallback uninstall lost the user's own breadcrumb symbol setting"
grep -q '^Show Url Nav Bar=' "$H/.config/katerc" && die "fallback uninstall left Show Url Nav Bar (1.0.x wrote it too)"
pass "fallback uninstall restores breadcrumb settings exactly"

# --- a key only newer versions write is recorded from the live katerc, not the old backup ---
H=$root/live-record; mkdir -p "$H/.config"
printf '[General]\nShow Symbol In Navigation Bar=true\n' > "$H/.config/katerc"     # in the pre-install backup
run install --yes
python3 - "$H/.local/state/kate-plusplus/state.json" <<'PY'
import json, sys        # pretend this install predates breadcrumbs: no record for the symbol key yet
p = sys.argv[1]; s = json.load(open(p)); s["katerc_before"].pop("[General]\tShow Symbol In Navigation Bar"); json.dump(s, open(p, "w"))
PY
sed -i 's/^Show Symbol In Navigation Bar=.*/Show Symbol In Navigation Bar=false/' "$H/.config/katerc"   # user's later choice
run apply --yes                          # records the new key (the backup still exists here)
rm "$H/.local/state/kate-plusplus/katerc.before-kate-plusplus"   # as if the user declined the full restore
run uninstall --yes
python3 - "$H/.config/katerc" <<'PY' || die "uninstall restored the old backup's value, not the user's later one"
import sys
assert "Show Symbol In Navigation Bar=false" in open(sys.argv[1]).read()
PY
pass "newer keys are recorded from the live settings"

# --- a symlinked config.ini (dotfiles) stays a symlink when new options are added ---
H=$root/cfg-link; mkdir -p "$H/.config" "$H/dotfiles"
run install --yes
mv "$H/.config/kate-plusplus/config.ini" "$H/dotfiles/kpp.ini"
ln -s "$H/dotfiles/kpp.ini" "$H/.config/kate-plusplus/config.ini"
sed -i '/^breadcrumbs = /d' "$H/dotfiles/kpp.ini"
run apply --yes
[[ -L $H/.config/kate-plusplus/config.ini ]] || die "adding new options replaced the symlinked config.ini"
grep -q '^breadcrumbs = ' "$H/dotfiles/kpp.ini" || die "new option not added to the symlink's target"

# --- an invalid breadcrumbs value warns and uses the default ---
sed -i 's/^breadcrumbs = .*/breadcrumbs = maybe/' "$H/dotfiles/kpp.ini"
out=$(env -i HOME="$H" PATH=/usr/bin:/bin KPP_TEST=1 ./bin/kate-plusplus apply --yes 2>&1)
grep -q "breadcrumbs = maybe isn't true or false" <<<"$out" || die "invalid breadcrumbs value did not warn"
grep -q '^Show Url Nav Bar=true' "$H/.config/katerc" || die "invalid breadcrumbs value did not fall back to true"
pass "symlinked config.ini kept; invalid breadcrumbs value warns"

# --- legacy + 'theme' before 'apply', no backup: partial records must not count as complete ---
H=$root/partial; mkdir -p "$H/.config"
run install --yes
python3 - "$H/.local/state/kate-plusplus/state.json" <<'PY'
import json, sys
p = sys.argv[1]; s = json.load(open(p)); s.pop("katerc_before", None); s.pop("katerc_complete", None); json.dump(s, open(p, "w"))
PY
rm -f "$H/.local/state/kate-plusplus/katerc.before-kate-plusplus"
sed -i 's/^source = .*/source = light/' "$H/.config/kate-plusplus/config.ini"
run theme                                     # records only the renderer keys + window scheme
python3 - "$H/.local/state/kate-plusplus/state.json" <<'PY' || die "theme did not create the partial legacy records"
import json, sys
s = json.load(open(sys.argv[1]))
assert s.get("katerc_complete") is False, s.get("katerc_complete")
keys = set(s.get("katerc_before", {}))
assert keys == {"[KTextEditor Renderer]\tAuto Color Theme Selection", "[KTextEditor Renderer]\tColor Theme",
                "[UiSettings]\tColorScheme"}, keys
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
if env -i HOME="$root/probe" PATH=/usr/bin:/bin KPP_TEST=1 PYTHONPATH=lib python3 -c 'import sys; from kpp import core, formatting
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
env -i HOME="$H" PATH=/usr/bin:/bin KPP_TEST=1 PYTHONPATH=lib python3 - <<'PY' || die "configPath used on a Kate that ignores it"
import pathlib
from kpp import core, formatting
k = core.Kate("native", ["kate"], core.XDG_CONFIG, core.XDG_DATA, "25.08.0")
assert formatting.settings_path(k) == (core.XDG_CONFIG / "kate/formatting/settings.json").resolve()
k.version = "26.08.0"
assert formatting.settings_path(k) != (core.XDG_CONFIG / "kate/formatting/settings.json").resolve()
core.merge_rc(k.katerc, [("[kateformatplugin]", "configPath", "fmt/relative.json")])
assert formatting.settings_path(k) is None, "a relative configPath must not be guessed"
PY
# a typo in format-on-save warns and keeps the default (off) instead of silently meaning false
H=$root/format4; mkdir -p "$H/.config"
run install --yes
sed -i 's/^format-on-save = .*/format-on-save = tru/' "$H/.config/kate-plusplus/config.ini"
out=$(env -i HOME="$H" PATH=/usr/bin:/bin KPP_TEST=1 ./bin/kate-plusplus apply --yes 2>&1)
grep -q "isn't true or false" <<<"$out" || die "invalid format-on-save value did not warn"
pass "prettify: format-on-save off, shortcut merged, settings restored exactly (incl. configPath, 0600)"

# --- fonts, ligatures, snippets, Qt style hint ---
H=$root/polish; mkdir -p "$H/.config/qtengine"
printf '{"theme": {"style": "Darkly"}}' > "$H/.config/qtengine/config.json"
printf '[Snippets]\nenabledRepositories=/home/me/my-snippets.xml\n' > "$H/.config/katerc"
run install --yes --profile generic --no-overlay
[[ -f $H/.local/share/ktexteditor_snippets/data/kate-plusplus.xml ]] || die "snippet pack not installed"
grep -q '^Text Font Features=' "$H/.config/katerc" && die "ligatures are on by default; no font features should be written"
cfg=$H/.config/kate-plusplus/config.ini
sed -i 's/^ligatures = .*/ligatures = false/; s/^font = .*/font = iosevka-not-installed-xyz/' "$cfg"
out=$(env -i HOME="$H" PATH=/usr/bin:/bin KPP_TEST=1 ./bin/kate-plusplus apply --yes 2>&1)
grep -q "isn't installed; using auto" <<<"$out" || die "missing font should warn and fall back"
grep -q '^Text Font Features=liga=0,calt=0,dlig=0$' "$H/.config/katerc" || die "ligatures=false not written"
sed -i 's/^ligatures = .*/ligatures = true/' "$cfg"
run apply --yes
grep -q '^Text Font Features=' "$H/.config/katerc" && die "turning ligatures back on should remove the setting"
out=$(env -i HOME="$H" PATH=/usr/bin:/bin KPP_TEST=1 QT_QPA_PLATFORMTHEME=qtengine ./bin/kate-plusplus doctor 2>&1)
darkly_installed=$(PYTHONPATH=lib python3 -c 'from kpp import cli
print(any("darkly" in f.name.lower() for d in cli.QT_STYLE_DIRS if d.is_dir() for f in d.iterdir()))')
if [[ $darkly_installed == False ]]; then
    grep -q "Qt style 'Darkly' is configured but not installed" <<<"$out" || die "doctor should flag the missing Darkly style"
fi
grep -q '^enabledRepositories=/home/me/my-snippets.xml,.*ktexteditor_snippets/data/kate-plusplus.xml$' "$H/.config/katerc" \
    || die "snippet repository not enabled next to the user's own in Kate's Snippets config"
run uninstall --yes
[[ -f $H/.local/share/ktexteditor_snippets/data/kate-plusplus.xml ]] && die "uninstall left the snippet pack"
grep -q '^enabledRepositories=/home/me/my-snippets.xml$' "$H/.config/katerc" \
    || die "uninstall must keep the user's own snippet repositories"

# a snippet pack edited in Kate's Snippets panel survives apply, and uninstall keeps it in backups
H=$root/snipedit; mkdir -p "$H"
run install --yes
pack=$H/.local/share/ktexteditor_snippets/data/kate-plusplus.xml
sed -i 's#</snippets>#<!-- my edit --></snippets>#' "$pack"
grep -q 'my edit' "$pack" || die "test setup: could not edit the snippet pack"
run apply --yes
grep -q 'my edit' "$pack" || die "apply overwrote the user's edited snippet pack"
run uninstall --yes
[[ -f $pack ]] && die "uninstall left the edited pack in Kate's snippet folder"
grep -lq 'my edit' "$H"/.local/share/kate-plusplus/backups/snippets-edited-*.xml 2>/dev/null \
    || die "uninstall lost the user's edited snippet pack"

# a file with the same name that existed before Kate++ comes back on uninstall
H=$root/snipforeign; mkdir -p "$H/.local/share/ktexteditor_snippets/data"
pack=$H/.local/share/ktexteditor_snippets/data/kate-plusplus.xml
printf '<snippets name="mine"/>\n' > "$pack"
run install --yes
grep -q 'name="mine"' "$pack" && die "install should replace the old file with the pack (after backing it up)"
run uninstall --yes
[[ $(cat "$pack") == '<snippets name="mine"/>' ]] || die "uninstall did not put back the user's earlier snippet file"

# same, but the fallback uninstall (no backup, records incomplete): the pack's repository
# entry must still go, and a symlinked original comes back as the same symlink
H=$root/snipfallback; sd=$H/.local/share/ktexteditor_snippets/data; mkdir -p "$sd" "$H/dotfiles"
printf '<snippets name="mine"/>\n' > "$H/dotfiles/snips.xml"
ln -s "$H/dotfiles/snips.xml" "$sd/kate-plusplus.xml"
run install --yes
[[ -L $sd/kate-plusplus.xml ]] && die "install wrote through the user's symlink"
grep -q 'name="mine"' "$H/dotfiles/snips.xml" || die "install changed the symlink's target"
python3 - "$H/.local/state/kate-plusplus/state.json" <<'PY'
import json, sys
p = sys.argv[1]; s = json.load(open(p)); s["katerc_complete"] = False; json.dump(s, open(p, "w"))
PY
rm -f "$H/.local/state/kate-plusplus/katerc.before-kate-plusplus"
run uninstall --yes
[[ $(readlink "$sd/kate-plusplus.xml") == "$H/dotfiles/snips.xml" ]] || die "uninstall did not restore the user's symlink"
grep -q 'kate-plusplus.xml' "$H/.config/katerc" && die "fallback uninstall left the pack in enabledRepositories"

# a pre-existing file identical to the pack (plain, and as a symlink) comes back on uninstall
for kind in file link; do
    H=$root/snipsame-$kind; sd=$H/.local/share/ktexteditor_snippets/data; mkdir -p "$sd" "$H/dotfiles"
    if [[ $kind == file ]]; then cp snippets/kate-plusplus.xml "$sd/kate-plusplus.xml"
    else cp snippets/kate-plusplus.xml "$H/dotfiles/snips.xml"; ln -s "$H/dotfiles/snips.xml" "$sd/kate-plusplus.xml"; fi
    run install --yes
    run uninstall --yes
    if [[ $kind == file ]]; then
        cmp -s snippets/kate-plusplus.xml "$sd/kate-plusplus.xml" || die "uninstall deleted the user's own copy of the pack"
    else
        [[ $(readlink "$sd/kate-plusplus.xml") == "$H/dotfiles/snips.xml" ]] || die "uninstall did not restore the symlink to the user's copy"
    fi
done

# a same-named file Kate++ has no record of owning is left alone by uninstall
H=$root/snipnotours; sd=$H/.local/share/ktexteditor_snippets/data
run install --yes
printf '<snippets name="mine"/>\n' > "$sd/kate-plusplus.xml"
python3 - "$H/.local/state/kate-plusplus/state.json" <<'PY'
import json, sys
p = sys.argv[1]; s = json.load(open(p)); s.pop("snippets_sha", None); json.dump(s, open(p, "w"))
PY
run uninstall --yes
grep -q 'name="mine"' "$sd/kate-plusplus.xml" || die "uninstall deleted a snippet file Kate++ didn't own"

# a fresh install leaves no empty snippet folders behind
H=$root/snipdirs; mkdir -p "$H"
run install --yes
run uninstall --yes
[[ -e $H/.local/share/ktexteditor_snippets ]] && die "uninstall left the empty snippet folders Kate++ created"

# snippet repositories enabled after install survive uninstall (full backup restore too)
H=$root/snipadded; mkdir -p "$H/.config"
printf '[Snippets]\nenabledRepositories=/home/me/a.xml\n' > "$H/.config/katerc"
run install --yes
sed -i 's#^enabledRepositories=\(.*\)$#enabledRepositories=\1,/home/me/b.xml#' "$H/.config/katerc"
run uninstall --yes
grep -q '^enabledRepositories=/home/me/a.xml,/home/me/b.xml$' "$H/.config/katerc" \
    || die "uninstall lost a snippet repository enabled after install: $(grep enabledRepositories "$H/.config/katerc")"

# fallback uninstall puts back the user's own snippets-plugin setting instead of deleting it
H=$root/snipplugin; mkdir -p "$H/.config"
printf '[Kate Plugins]\nkatesnippetsplugin=false\n' > "$H/.config/katerc"
run install --yes
grep -q '^katesnippetsplugin=true' "$H/.config/katerc" || die "snippets plugin not enabled"
python3 - "$H/.local/state/kate-plusplus/state.json" <<'PY'
import json, sys
p = sys.argv[1]; s = json.load(open(p)); s["katerc_complete"] = False; json.dump(s, open(p, "w"))
PY
rm -f "$H/.local/state/kate-plusplus/katerc.before-kate-plusplus"
run uninstall --yes
grep -q '^katesnippetsplugin=false$' "$H/.config/katerc" || die "fallback uninstall lost the user's snippets-plugin setting"

# fresh Kate (no katerc) → install → apply → uninstall: no reference to the removed snippet pack
H=$root/snipfresh; mkdir -p "$H"
run install --yes
run apply --yes
run uninstall --yes
[[ ! -f $H/.config/katerc ]] || ! grep -q 'kate-plusplus.xml' "$H/.config/katerc" \
    || die "uninstall left Kate's Snippets config pointing at the removed pack"

# legacy fallback (no complete records, no backup) puts back the user's own font features
H=$root/featlegacy; mkdir -p "$H/.config"
printf '[KTextEditor Renderer]\nText Font Features=ss01=1\n' > "$H/.config/katerc"
run install --yes
sed -i 's/^ligatures = .*/ligatures = false/' "$H/.config/kate-plusplus/config.ini"
run apply --yes
grep -q '^Text Font Features=liga=0,calt=0,dlig=0$' "$H/.config/katerc" || die "ligatures=false not applied"
python3 - "$H/.local/state/kate-plusplus/state.json" <<'PY'
import json, sys
p = sys.argv[1]; s = json.load(open(p)); s["katerc_complete"] = False; json.dump(s, open(p, "w"))
PY
rm -f "$H/.local/state/kate-plusplus/katerc.before-kate-plusplus"
run uninstall --yes
grep -q '^Text Font Features=ss01=1$' "$H/.config/katerc" || die "legacy uninstall lost the user's recorded font features"

# fallback uninstall (no backup) keeps font features the user set themselves
H=$root/features; mkdir -p "$H/.config"
run install --yes
printf '\n[KTextEditor Renderer]\nText Font Features=ss01=1\n' >> "$H/.config/katerc"
rm -f "$H/.local/state/kate-plusplus/katerc.before-kate-plusplus"
run uninstall --yes
grep -q '^Text Font Features=ss01=1$' "$H/.config/katerc" || die "uninstall deleted the user's own font features"
pass "font shortcuts, ligatures switch, snippets and Qt style hint"

# --- legacy upgrade restores the original window scheme even without the full backup ---
H=$root/legacy-scheme; mkdir -p "$H/.config"
printf '[UiSettings]\nColorScheme=BreezeDark\n' > "$H/.config/katerc"
run install --yes
python3 - "$H/.local/state/kate-plusplus/state.json" <<'PY'
import json, sys
p = sys.argv[1]; s = json.load(open(p)); s.pop("katerc_before", None); s.pop("katerc_complete", None); json.dump(s, open(p, "w"))
PY
sed -i 's/^source = .*/source = rose-pine/' "$H/.config/kate-plusplus/config.ini"
run apply --yes
rm "$H/.local/state/kate-plusplus/katerc.before-kate-plusplus"
run uninstall --yes
grep -q '^ColorScheme=BreezeDark$' "$H/.config/katerc" || die "legacy upgrade lost the original window scheme"
pass "legacy upgrade: the original window scheme comes back"

# --- upgrade without backup: a scheme the user picked is kept and survives uninstall ---
H=$root/legacy-pick; mkdir -p "$H/.config"
run install --yes
python3 - "$H/.local/state/kate-plusplus/state.json" <<'PY'
import json, sys   # an install from a version without window colours or records
p = sys.argv[1]; s = json.load(open(p))
for k in ("katerc_before", "katerc_complete", "window_scheme"): s.pop(k, None)
json.dump(s, open(p, "w"))
PY
rm -f "$H/.local/state/kate-plusplus/katerc.before-kate-plusplus"
PYTHONPATH=lib python3 -c 'import sys, pathlib; from kpp import core
core.merge_rc(pathlib.Path(sys.argv[1]), [("[UiSettings]", "ColorScheme", "Solarized")])' "$H/.config/katerc"   # picked in Kate
sed -i 's/^source = .*/source = rose-pine/' "$H/.config/kate-plusplus/config.ini"
run apply --yes
grep -q '^ColorScheme=Solarized$' "$H/.config/katerc" || die "upgrade replaced a scheme the user picked"
run uninstall --yes
grep -q '^ColorScheme=Solarized$' "$H/.config/katerc" || die "uninstall lost the user's scheme"
pass "upgrade without backup keeps the user's window scheme through uninstall"

echo "All sandbox tests passed."
