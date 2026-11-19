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
            echo "$a $(grep -o "[0-9]\+" <<<"$v" | head -1)"
        done
        kill %1' _ "$@"
}

kpp install --yes
declare -A s
while read -r a v; do s[$a]=$v; done < <(read_shortcuts file_quit view_quick_open file_close file_save_all view_new_view)
[[ ${s[file_quit]} == 0 ]]           || die "file_quit override not applied (got ${s[file_quit]})"
[[ ${s[view_quick_open]} != 0 ]]     || die "Quick Open lost its default shortcut"
[[ ${s[file_close]} != 0 ]]          || die "Close lost its default shortcut"
[[ ${s[file_save_all]} != 0 ]]       || die "Save All lost its default shortcut"
[[ ${s[view_new_view]} != 0 ]]       || die "user's own shortcut was lost"
pass "overrides applied, Kate's defaults and the user's own shortcut intact"

# Language menu: Kate writes its full menu file on first start, the background job adds the menu
kpp maintain --quiet
grep -q '<Action name="tools_highlighting" kate-plusplus="true"/>' "$H/.local/share/kxmlgui5/katepart/katepart5ui.rc" \
    || die "Language menu was not added to the menu bar"
read_shortcuts file_close >/dev/null    # Kate starts again with the menu in place
grep -q 'text="&amp;Language"' "$H/.local/share/kxmlgui5/katepart/katepart5ui.rc" || die "Kate dropped the Language menu"
pass "Language menu added after Kate's first start and kept by Kate"

kpp uninstall --yes
props() {  # "name=shortcut" for every entry in a file's <ActionProperties>
    python3 -c 'import sys, xml.dom.minidom as m
for ap in m.parse(sys.argv[1]).getElementsByTagName("ActionProperties"):
    for a in ap.getElementsByTagName("Action"): print(a.getAttribute("name") + "=" + a.getAttribute("shortcut"))' "$1"
}
props "$H/.local/share/kxmlgui5/kate/kateui.rc" | grep -q '^view_new_view=Ctrl+Alt+N$' || die "uninstall removed the user's shortcut"
props "$H/.local/share/kxmlgui5/kate/kateui.rc" | grep -q '^file_quit=' && die "uninstall left Kate++ shortcuts behind"
for f in katepart/katepart5ui.rc keyboardmacros/ui.rc; do
    [[ ! -f $H/.local/share/kxmlgui5/$f ]] || ! props "$H/.local/share/kxmlgui5/$f" | grep -q . || die "$f still has Kate++ shortcuts"
done
pass "uninstall removes only Kate++ shortcuts"
echo "Shortcut tests passed."
