#!/usr/bin/env bash
# Starts a real (offscreen) Kate after a Kate++ install and reads its live shortcuts over
# D-Bus: our overrides must apply AND every other shortcut must keep Kate's default.
# Also checks that a user's own shortcut customisation survives install + uninstall.
# Needs: kate, dbus-run-session, gdbus.
set -euo pipefail
cd "$(dirname "$0")/.."
H=$(mktemp -d)
trap 'rm -rf "$H"' EXIT
pass() { printf '  \033[32m✓\033[0m %s\n' "$1"; }
die()  { printf '  \033[31m✗\033[0m %s\n' "$1"; exit 1; }
kpp()  { env -i HOME="$H" PATH=/usr/bin:/bin KPP_TEST=1 ./bin/kate-plusplus "$@" >/dev/null; }

# a user customisation that must survive: Ctrl+Alt+N for "New window"
mkdir -p "$H/.local/share/kxmlgui5/kate"
cat >"$H/.local/share/kxmlgui5/kate/kateui.rc" <<'XML'
<!DOCTYPE gui SYSTEM "kpartgui.dtd">
<gui name="kate" version="1">
 <ActionProperties scheme="Default">
  <Action name="view_new_view" shortcut="Ctrl+Alt+N"/>
 </ActionProperties>
</gui>
XML

# shortcut of a main-window action as seen by the running Kate (Qt key code, 0 = none)
read_shortcuts() {
    # shellcheck disable=SC2016  # the inner script is meant to expand inside the D-Bus session
    env -i HOME="$H" PATH=/usr/bin:/bin QT_QPA_PLATFORM=offscreen dbus-run-session -- bash -c '
        kate -n >/dev/null 2>&1 &
        for _ in $(seq 40); do
            svc=$(gdbus call --session --dest org.freedesktop.DBus --object-path /org/freedesktop/DBus \
                  --method org.freedesktop.DBus.ListNames | grep -o "org.kde.kate-[0-9]*" | head -1) || true
            [[ -n $svc ]] && gdbus introspect --session --dest "$svc" --object-path /kate/MainWindow_1/actions/file_quit >/dev/null 2>&1 && break
            sleep 0.5
        done
        for a in "$@"; do
            v=$(gdbus call --session --dest "$svc" --object-path "/kate/MainWindow_1/actions/$a" \
                --method org.freedesktop.DBus.Properties.Get org.qtproject.Qt.QAction shortcut)
            echo "$a $(grep -o "[0-9]\+" <<<"$v" | grep -v "^0$" | paste -sd, - || true)"
        done
        kill %1' _ "$@"
}

kpp install --yes
declare -A s
while read -r a v; do s[$a]=${v:-}; done < <(read_shortcuts file_quit view_quick_open file_close file_save_all view_new_view file_new)
[[ -z ${s[file_quit]} ]]             || die "file_quit override not applied (got ${s[file_quit]})"
[[ -n ${s[view_quick_open]} ]]       || die "Quick Open lost its default shortcut"
[[ -n ${s[file_close]} ]]            || die "Close lost its default shortcut"
[[ -n ${s[file_save_all]} ]]         || die "Save All lost its default shortcut"
[[ -n ${s[view_new_view]} ]]         || die "user's own shortcut was lost"
# D-Bus only exposes an action's *primary* shortcut, so Ctrl+T (secondary) isn't visible here;
# the merge itself is covered by the single-shortcut overrides above.
[[ ${s[file_new]} == 67108942 ]] || die "New should keep Ctrl+N as its primary shortcut (got ${s[file_new]})"
action_shortcut() {  # $1 = kxmlgui file, $2 = action → "=<shortcut>" (attribute present) or "MISSING"
    python3 -c 'import sys, xml.dom.minidom as m
for a in m.parse(sys.argv[1]).getElementsByTagName("Action"):
    if a.parentNode.tagName == "ActionProperties" and a.getAttribute("name") == sys.argv[2]:
        print("=" + a.getAttribute("shortcut") if a.hasAttribute("shortcut") else "MISSING"); break
else: print("MISSING")' "$1" "$2"
}
new_sc=$(action_shortcut "$H/.local/share/kxmlgui5/kate/kateui.rc" file_new) || die "could not read kateui.rc"
[[ $new_sc == "=Ctrl+N; Ctrl+T" ]] || die "New should have Ctrl+N and Ctrl+T in Kate's shortcut file (got $new_sc)"
tr_sc=$(action_shortcut "$H/.local/share/kxmlgui5/katepart/katepart5ui.rc" transpose_char) || die "could not read katepart5ui.rc"
[[ $tr_sc == "=" ]] || die "Transpose Characters needs an explicitly empty shortcut (got $tr_sc)"
pass "overrides applied, Kate's defaults and the user's own shortcut intact"

# Language menu: Kate writes its full menu file on first start, the background job adds the menu
kpp maintain --quiet
UI=$H/.local/share/kxmlgui5/katepart/katepart5ui.rc
grep -q 'kate-plusplus="true"' "$UI" || die "Language menu was not added to the menu bar"
read_shortcuts file_close >/dev/null    # Kate starts again with the menu in place
# the same lister lookup Kate++ uses (incl. kate-syntax-highlighter), with the CLI's PATH
WANT=$(env -i HOME="$H" PATH=/usr/bin:/bin PYTHONPATH=lib python3 -c 'from kpp import languages; print("az" if languages.available() else "grouped")')
python3 - "$UI" "$WANT" <<'PY' || die "Kate dropped the Language menu"
import sys, xml.dom.minidom as m
root = m.parse(sys.argv[1]).documentElement
bar = next(n for n in root.childNodes if n.nodeType == 1 and n.tagName == "MenuBar")
props = next(n for n in root.childNodes if n.nodeType == 1 and n.tagName == "ActionProperties")
label = [a.getAttribute("text") for a in props.getElementsByTagName("Action") if a.getAttribute("name") == "tools_highlighting"]
if sys.argv[2] == "az":
    menu = [n for n in bar.childNodes if n.nodeType == 1 and n.getAttribute("name") == "kpp_language"]
    assert menu, "A–Z Language menu is not on the menu bar"
    acts = [a.getAttribute("name") for a in menu[0].getElementsByTagName("Action")]
    assert "tools_scripts_kppLang_Java" in acts and "tools_highlighting" in acts, acts[:5]
    assert label == ["All Languages"], label
else:
    assert any(n.nodeType == 1 and n.tagName == "Action" and n.getAttribute("name") == "tools_highlighting"
               for n in bar.childNodes), "tools_highlighting is not on the menu bar"
    assert label == ["&Language"], label
PY
pass "Language menu added after Kate's first start and kept by Kate"

kpp uninstall --yes
props() {  # "name=shortcut" for every entry in a file's <ActionProperties>
    python3 -c 'import sys, xml.dom.minidom as m
for ap in m.parse(sys.argv[1]).getElementsByTagName("ActionProperties"):
    for a in ap.getElementsByTagName("Action"): print(a.getAttribute("name") + "=" + a.getAttribute("shortcut"))' "$1"
}
props "$H/.local/share/kxmlgui5/kate/kateui.rc" | grep -q '^view_new_view=Ctrl+Alt+N$' || die "uninstall removed the user's shortcut"
props "$H/.local/share/kxmlgui5/kate/kateui.rc" | grep -q '^file_quit=' && die "uninstall left Kate++ shortcuts behind"
for f in katepart/katepart5ui.rc keyboardmacros/ui.rc formatplugin/ui.rc; do
    [[ ! -f $H/.local/share/kxmlgui5/$f ]] || ! props "$H/.local/share/kxmlgui5/$f" | grep -q . || die "$f still has Kate++ shortcuts"
done
pass "uninstall removes only Kate++ shortcuts"
echo "Shortcut tests passed."
