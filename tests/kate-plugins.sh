#!/usr/bin/env bash
# Starts a real (offscreen) Kate after a Kate++ install and checks that the plugins Kate++
# switches on really load: Kate saves each loaded plugin's side panel in the session file.
# Needs: kate, dbus-run-session, gdbus.
set -euo pipefail
cd "$(dirname "$0")/.."
H=$(mktemp -d)
trap 'rm -rf "$H"' EXIT
pass() { printf '  \033[32m✓\033[0m %s\n' "$1"; }
die()  { printf '  \033[31m✗\033[0m %s\n' "$1"; exit 1; }

env -i HOME="$H" PATH=/usr/bin:/bin KPP_TEST=1 ./bin/kate-plusplus install --yes >/dev/null
# shellcheck disable=SC2016  # the inner script is meant to expand inside the D-Bus session
env -i HOME="$H" PATH=/usr/bin:/bin QT_QPA_PLATFORM=offscreen dbus-run-session -- bash -c '
    set -euo pipefail
    kate -n >/dev/null 2>&1 &
    pid=$!
    stop() { kill "$pid" 2>/dev/null || true; exit 1; }
    svc=
    for _ in $(seq 60); do
        svc=$(gdbus call --session --dest org.freedesktop.DBus --object-path /org/freedesktop/DBus \
              --method org.freedesktop.DBus.ListNames | grep -o "org.kde.kate-[0-9]*" | head -1) || true
        [[ -n $svc ]] && gdbus introspect --session --dest "$svc" --object-path /kate/MainWindow_1/actions/file_quit >/dev/null 2>&1 && break
        svc=
        sleep 0.5
    done
    [[ -n $svc ]] || { echo "Kate did not start" >&2; stop; }
    sleep 2
    gdbus call --session --dest "$svc" --object-path /kate/MainWindow_1/actions/file_quit \
        --method org.qtproject.Qt.QAction.trigger >/dev/null || stop
    for _ in $(seq 60); do kill -0 "$pid" 2>/dev/null || break; sleep 0.5; done   # saves its session
    kill -0 "$pid" 2>/dev/null && { echo "Kate did not quit" >&2; stop; }
    wait "$pid" || true'
f=$H/.local/share/kate/sessions/Notepad.katesession
[[ -f $f ]] || die "Kate didn't save the Notepad session"
panels=$(grep '^Kate-MDI-Sidebar-.*TvList=' "$f" | cut -d= -f2 | tr ',' '\n')
for want in symbolviewer fileselector snippets preview; do
    grep -qi "$want" <<<"$panels" || die "the $want panel didn't load (plugins not on in the session?)"
done
pass "Kate++'s plugins load in a real Kate (function list, folder, snippets, preview panels)"
