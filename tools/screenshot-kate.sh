#!/usr/bin/env bash
# Take "before" (stock Kate) and "after" (Kate++) screenshots on an invisible
# Hyprland headless monitor, using throw-away config sandboxes so the real Kate
# session is never touched. Hyprland only.
#
#   tools/screenshot-kate.sh <out-dir> [files to open…]
set -euo pipefail
out=$(realpath "$1"); shift
files=("$@")
work=$(mktemp -d)
mkdir -p "$out"

existing=$(hyprctl monitors -j | python3 -c 'import json,sys;print(" ".join(m["name"] for m in json.load(sys.stdin)))')
hyprctl output create headless >/dev/null
sleep 1
mon=$(hyprctl monitors -j | python3 -c '
import json,sys
old=set(sys.argv[1].split())
for m in json.load(sys.stdin):
    if m["name"] not in old: print(m["name"], m["activeWorkspace"]["id"])' "$existing")
read -r name ws <<<"$mon"
cleanup() {
    for p in $(pgrep -x kate); do
        tr '\0' '\n' </proc/"$p"/environ 2>/dev/null | grep -q "XDG_CONFIG_HOME=$work" && kill "$p" 2>/dev/null
    done
    sleep 1
    hyprctl output remove "$name" >/dev/null 2>&1 || true
    rm -rf "$work"
}
trap cleanup EXIT

sandbox() {  # $1 = before|after
    local d=$work/$1
    mkdir -p "$d"/{config,data,state,cache}
    [[ -d ~/.config/qtengine ]] && cp -r ~/.config/qtengine "$d/config/"
    [[ -f ~/.config/kdeglobals ]] && cp ~/.config/kdeglobals "$d/config/"
    if [[ $1 == after ]]; then
        cp ~/.config/katerc "$d/config/katerc"
        for x in org.kde.syntax-highlighting katepart5 katepart keyboardmacros; do
            [[ -d ~/.local/share/$x ]] && cp -r ~/.local/share/$x "$d/data/"
        done
        mkdir -p "$d/data/kate/sessions"
        cp -r ~/.local/share/kate/shortcuts "$d/data/kate/" 2>/dev/null || true
        printf '[Open Documents]\nCount=0\n' >"$d/data/kate/sessions/Notepad.katesession"
    fi
}

shoot() {  # $1 = before|after
    local d=$work/$1 session_args=""
    [[ $1 == after ]] && session_args="-s Notepad"
    hyprctl dispatch "hl.dsp.exec_cmd(\"env XDG_CONFIG_HOME=$d/config XDG_DATA_HOME=$d/data XDG_STATE_HOME=$d/state XDG_CACHE_HOME=$d/cache kate -n $session_args ${files[*]}\", { workspace = \"$ws silent\" })" >/dev/null
    sleep 9
    grim -o "$name" "$out/$1.png"
    for p in $(pgrep -x kate); do
        tr '\0' '\n' </proc/"$p"/environ 2>/dev/null | grep -q "XDG_CONFIG_HOME=$d/config" && kill "$p" 2>/dev/null
    done
    sleep 1
}

sandbox before; sandbox after
shoot before
shoot after
echo "screenshots in $out"
