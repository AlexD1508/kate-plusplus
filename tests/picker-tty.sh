#!/usr/bin/env bash
# Drives `kate-plusplus theme --pick` through a pseudo-terminal in a throw-away $HOME:
# browse with keys, apply with Enter, and check the terminal is restored. Needs kate.
set -euo pipefail
cd "$(dirname "$0")/.."
H=$(mktemp -d)
trap 'rm -rf "$H"' EXIT
env -i HOME="$H" PATH=/usr/bin:/bin KPP_TEST=1 ./bin/kate-plusplus install --yes >/dev/null
python3 - "$H" <<'PY'
import os, pty, select, sys, time
home = sys.argv[1]
pid, fd = pty.fork()
if pid == 0:
    os.execve("./bin/kate-plusplus", ["kate-plusplus", "theme", "--pick"],
              {"HOME": home, "PATH": "/usr/bin:/bin", "KPP_TEST": "1", "TERM": "xterm-256color"})
seen = b""
def drain(t):
    global seen
    end = time.time() + t
    while time.time() < end:
        if select.select([fd], [], [], 0.1)[0]:
            try:
                seen += os.read(fd, 65536)
            except OSError:
                return
drain(3)
assert b"Pick a theme" in seen and b"\x1b[48;2;" in seen, "no list / colour preview"
for key in (b"j", b"\x1b[B", b"\x1b[A", b"\r"):   # down, down, up, Enter → 2nd entry
    os.write(fd, key)
    drain(1)
drain(3)
_, status = os.waitpid(pid, 0)
assert os.WIFEXITED(status) and os.WEXITSTATUS(status) == 0, f"picker failed (status {status}):\n{seen[-800:]!r}"
assert b"\x1b[?1049l" in seen and b"\x1b[?25h" in seen, "terminal not restored"
PY
grep -q '^source = ' "$H/.config/kate-plusplus/config.ini"
src=$(sed -n 's/^source = //p' "$H/.config/kate-plusplus/config.ini")
[[ $src != auto ]] || { echo "picker did not change the theme"; exit 1; }
echo "Picker test passed (picked: $src)."
