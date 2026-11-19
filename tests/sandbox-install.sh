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
grep -A6 '^\[lspclient\]' "$H/.config/katerc" | grep -q '^InlayHints=true' || die "smart highlighting not enabled"
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
grep -q '^\[lspclient\]' "$H/.config/katerc" && die "uninstall left LSP settings behind"
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
